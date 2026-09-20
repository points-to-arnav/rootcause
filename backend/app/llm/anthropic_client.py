"""
Direct Anthropic API adapter, with prompt caching.

The planner sends the same two things on every turn of a session — the planning
instructions and the dataset's schema — followed by a question that changes each
time. That is exactly the shape prompt caching rewards: mark the stable prefix,
leave the volatile tail unmarked, and the prefix bills at 0.1x on every turn after
the first.

Caching is a prefix match, so ordering matters: instructions, then schema, then
(uncached) the question. Anything volatile above the breakpoint — a timestamp, a
turn counter — would invalidate the entry on every call and silently cost more
than not caching at all.
"""
import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# Below this many tokens the API silently declines to create a cache entry.
# Claude Sonnet 5 / Opus 4.8: 1024. Claude Opus 5: 512. See the caching docs.
MODEL_CACHE_MINIMUMS = {
    "claude-opus-5": 512,
    "claude-sonnet-5": 1024,
    "claude-haiku-4-5": 4096,
}
DEFAULT_CACHE_MINIMUM = 1024


class AnthropicUnavailable(RuntimeError):
    """No API key, SDK missing, or the request failed."""


def is_available() -> bool:
    if not settings.ANTHROPIC_API_KEY.strip():
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def cache_minimum_for(model: str) -> int:
    for known, minimum in MODEL_CACHE_MINIMUMS.items():
        if known in model:
            return minimum
    return DEFAULT_CACHE_MINIMUM


def estimate_tokens(text: str) -> int:
    """Rough chars/4 estimate — only used to decide whether a breakpoint is worth
    setting. Being wrong costs a wasted marker, never a failed request."""
    return len(text) // 4


def _client():
    try:
        import anthropic
    except ImportError as exc:
        raise AnthropicUnavailable(
            "The 'anthropic' package is not installed. Run: pip install anthropic"
        ) from exc

    key = settings.ANTHROPIC_API_KEY.strip()
    if not key:
        raise AnthropicUnavailable("ANTHROPIC_API_KEY is not set in backend/.env")
    return anthropic.Anthropic(api_key=key, timeout=settings.ANTHROPIC_TIMEOUT_S)


def build_system_blocks(
    stable_parts: Sequence[str],
    model: str,
    enable_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Assembles the system array and puts a single cache breakpoint at the end of the
    stable prefix — but only when the prefix is long enough for the API to honour it.
    """
    parts = [p for p in stable_parts if p and p.strip()]
    if not parts:
        return []

    blocks: List[Dict[str, Any]] = [{"type": "text", "text": p} for p in parts]

    if enable_cache:
        combined = "\n\n".join(parts)
        if estimate_tokens(combined) >= cache_minimum_for(model):
            blocks[-1]["cache_control"] = {"type": "ephemeral"}
        else:
            logger.debug(
                "Prefix of ~%d tokens is below the %d-token cache minimum for %s; "
                "skipping the breakpoint.",
                estimate_tokens(combined), cache_minimum_for(model), model,
            )
    return blocks


def complete(
    stable_parts: Sequence[str],
    user_prompt: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Returns (text, usage). Raises AnthropicUnavailable on failure."""
    client = _client()
    chosen_model = model or settings.ANTHROPIC_MODEL
    cap = max_tokens or settings.ANTHROPIC_MAX_TOKENS

    system_blocks = build_system_blocks(
        stable_parts, chosen_model, enable_cache=settings.ENABLE_PROMPT_CACHING
    )

    # Claude Sonnet 5 and the 4.7+ family reject temperature/top_p/top_k with a 400,
    # so sampling is never forwarded. Determinism comes from the prompt and from
    # thinking being off, not from temperature.
    request: Dict[str, Any] = {
        "model": chosen_model,
        "max_tokens": cap,
        "system": system_blocks,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    if settings.ANTHROPIC_THINKING:
        request["thinking"] = {"type": "adaptive"}
    else:
        # A schema-constrained planner is a mechanical transformation; thinking adds
        # seconds to an interactive path for no accuracy gain.
        request["thinking"] = {"type": "disabled"}

    if settings.ANTHROPIC_EFFORT:
        request["output_config"] = {"effort": settings.ANTHROPIC_EFFORT}

    start = time.time()
    try:
        response = client.messages.create(**request)
    except Exception as exc:
        raise AnthropicUnavailable(f"Anthropic API call failed: {exc}") from exc
    elapsed = time.time() - start

    if getattr(response, "stop_reason", None) == "refusal":
        raise AnthropicUnavailable("The model declined this request.")

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    if not text.strip():
        raise AnthropicUnavailable("Anthropic returned an empty response.")

    raw = response.usage
    usage = {
        "input_tokens": int(getattr(raw, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(raw, "output_tokens", 0) or 0),
        "cache_read_tokens": int(getattr(raw, "cache_read_input_tokens", 0) or 0),
        "cache_write_tokens": int(getattr(raw, "cache_creation_input_tokens", 0) or 0),
        "latency_s": elapsed,
        "model": chosen_model,
    }
    logger.info(
        "Anthropic ok in %.2fs (in=%d, cache_read=%d, cache_write=%d, out=%d)",
        elapsed, usage["input_tokens"], usage["cache_read_tokens"],
        usage["cache_write_tokens"], usage["output_tokens"],
    )
    return text, usage
