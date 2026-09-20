"""
Rolling LLM telemetry: token usage, prompt-cache effectiveness, latency and cost.

Every call through app.llm.client lands here. The aggregate is what the UI shows
as its live "prompt cache" panel, so the numbers must be real measurements, never
estimates — the only derived figure is cost, computed from published per-MTok rates.
"""
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

# USD per 1M tokens. Cache reads bill at 0.1x input, cache writes at 1.25x.
PRICING: Dict[str, Dict[str, float]] = {
    "claude-opus-5":     {"input": 5.00, "output": 25.00},
    "claude-sonnet-5":   {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5":  {"input": 1.00, "output": 5.00},
    # Claude Code CLI model aliases resolve to the same underlying models.
    "sonnet":            {"input": 2.00, "output": 10.00},
    "opus":              {"input": 5.00, "output": 25.00},
    "haiku":             {"input": 1.00, "output": 5.00},
}
DEFAULT_PRICING = {"input": 0.0, "output": 0.0}  # free OpenRouter / NIM models

CACHE_READ_MULTIPLIER = 0.10
CACHE_WRITE_MULTIPLIER = 1.25


def price_for(model: str) -> Dict[str, float]:
    if model in PRICING:
        return PRICING[model]
    for known, rates in PRICING.items():
        if known in model:
            return rates
    return DEFAULT_PRICING


class CallRecord:
    """One LLM round-trip."""

    __slots__ = (
        "provider", "model", "stage", "input_tokens", "output_tokens",
        "cache_read_tokens", "cache_write_tokens", "latency_s", "ok", "timestamp",
        "seq",
    )

    def __init__(
        self,
        provider: str,
        model: str,
        stage: str = "planner",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        latency_s: float = 0.0,
        ok: bool = True,
    ):
        self.provider = provider
        self.model = model
        self.stage = stage
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_tokens = cache_read_tokens
        self.cache_write_tokens = cache_write_tokens
        self.latency_s = latency_s
        self.ok = ok
        self.timestamp = time.time()
        self.seq = 0  # assigned by LLMStats.record

    @property
    def was_cache_hit(self) -> bool:
        return self.cache_read_tokens > 0

    @property
    def billable_cost(self) -> float:
        """What this call actually cost, with the cache discount applied."""
        rates = price_for(self.model)
        per_token_in = rates["input"] / 1_000_000
        per_token_out = rates["output"] / 1_000_000
        return (
            self.input_tokens * per_token_in
            + self.cache_read_tokens * per_token_in * CACHE_READ_MULTIPLIER
            + self.cache_write_tokens * per_token_in * CACHE_WRITE_MULTIPLIER
            + self.output_tokens * per_token_out
        )

    @property
    def uncached_cost(self) -> float:
        """What the same call would have cost with no cache at all."""
        rates = price_for(self.model)
        per_token_in = rates["input"] / 1_000_000
        per_token_out = rates["output"] / 1_000_000
        full_input = self.input_tokens + self.cache_read_tokens + self.cache_write_tokens
        return full_input * per_token_in + self.output_tokens * per_token_out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "stage": self.stage,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cache_hit": self.was_cache_hit,
            "latency_s": round(self.latency_s, 2),
            "cost_usd": round(self.billable_cost, 6),
            "uncached_cost_usd": round(self.uncached_cost, 6),
            "saved_usd": round(max(0.0, self.uncached_cost - self.billable_cost), 6),
            "ok": self.ok,
        }


class LLMStats:
    """Process-wide tracker. Thread-safe; FastAPI serves requests on a worker pool."""

    def __init__(self, max_records: int = 200):
        self._lock = threading.Lock()
        self._records: Deque[CallRecord] = deque(maxlen=max_records)
        self._seq = 0

    def record(self, rec: CallRecord) -> None:
        with self._lock:
            self._seq += 1
            rec.seq = self._seq
            self._records.append(rec)

    def current_seq(self) -> int:
        """A marker a caller can hold across a request to find its own calls again."""
        with self._lock:
            return self._seq

    def since(self, seq: int) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records if r.seq > seq]

    def turn_summary(self, seq: int) -> Dict[str, Any]:
        """Aggregate for just the calls made after `seq` - i.e. one question."""
        with self._lock:
            records = [r for r in self._records if r.seq > seq and r.ok]

        if not records:
            return {
                "calls": 0, "cache_read_tokens": 0, "cache_write_tokens": 0,
                "input_tokens": 0, "output_tokens": 0, "cache_hit": False,
                "latency_s": 0.0, "cost_usd": 0.0, "uncached_cost_usd": 0.0,
                "saved_usd": 0.0, "provider": None, "model": None,
            }

        billed = sum(r.billable_cost for r in records)
        unbilled = sum(r.uncached_cost for r in records)
        return {
            "calls": len(records),
            "cache_read_tokens": sum(r.cache_read_tokens for r in records),
            "cache_write_tokens": sum(r.cache_write_tokens for r in records),
            "input_tokens": sum(r.input_tokens for r in records),
            "output_tokens": sum(r.output_tokens for r in records),
            "cache_hit": any(r.was_cache_hit for r in records),
            "latency_s": round(sum(r.latency_s for r in records), 2),
            "cost_usd": round(billed, 6),
            "uncached_cost_usd": round(unbilled, 6),
            "saved_usd": round(max(0.0, unbilled - billed), 6),
            "provider": records[-1].provider,
            "model": records[-1].model,
        }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._seq = 0

    def last_n(self, n: int) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in list(self._records)[-n:]]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._records)

        ok_records = [r for r in records if r.ok]
        if not ok_records:
            return {
                "calls": 0, "cache_hits": 0, "cache_hit_rate": 0.0,
                "cached_tokens": 0, "written_tokens": 0, "fresh_tokens": 0,
                "output_tokens": 0, "total_prompt_tokens": 0,
                "cost_usd": 0.0, "uncached_cost_usd": 0.0, "saved_usd": 0.0,
                "saved_pct": 0.0, "avg_latency_s": 0.0,
                "avg_latency_cached_s": 0.0, "avg_latency_uncached_s": 0.0,
                "providers": [], "recent": [],
            }

        hits = [r for r in ok_records if r.was_cache_hit]
        misses = [r for r in ok_records if not r.was_cache_hit]

        cached_tokens = sum(r.cache_read_tokens for r in ok_records)
        written_tokens = sum(r.cache_write_tokens for r in ok_records)
        fresh_tokens = sum(r.input_tokens for r in ok_records)
        output_tokens = sum(r.output_tokens for r in ok_records)
        total_prompt = cached_tokens + written_tokens + fresh_tokens

        billed = sum(r.billable_cost for r in ok_records)
        unbilled = sum(r.uncached_cost for r in ok_records)
        saved = max(0.0, unbilled - billed)

        def mean(values: List[float]) -> float:
            return round(sum(values) / len(values), 2) if values else 0.0

        return {
            "calls": len(ok_records),
            "cache_hits": len(hits),
            "cache_hit_rate": round(len(hits) / len(ok_records) * 100, 1),
            "cached_tokens": cached_tokens,
            "written_tokens": written_tokens,
            "fresh_tokens": fresh_tokens,
            "output_tokens": output_tokens,
            "total_prompt_tokens": total_prompt,
            "cached_share_pct": round(cached_tokens / total_prompt * 100, 1) if total_prompt else 0.0,
            "cost_usd": round(billed, 6),
            "uncached_cost_usd": round(unbilled, 6),
            "saved_usd": round(saved, 6),
            "saved_pct": round(saved / unbilled * 100, 1) if unbilled > 0 else 0.0,
            "avg_latency_s": mean([r.latency_s for r in ok_records]),
            "avg_latency_cached_s": mean([r.latency_s for r in hits]),
            "avg_latency_uncached_s": mean([r.latency_s for r in misses]),
            "providers": sorted({r.provider for r in ok_records}),
            "recent": [r.to_dict() for r in ok_records[-12:]],
        }


STATS = LLMStats()
