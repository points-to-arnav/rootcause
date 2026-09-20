"""
Provider-agnostic LLM entry point.

Four providers sit behind one call:
  openrouter   - OpenAI-compatible HTTP, free models (default)
  nvidia_nim   - OpenAI-compatible HTTP, fallback
  claude_code  - the local `claude` CLI, using your existing login (no API key)
  anthropic    - the Anthropic SDK directly, with prompt caching

Whichever is active, the caller passes the same thing: a list of *stable* prompt
parts (instructions, dataset schema) and one *volatile* user prompt (the question).
Keeping those separate is what lets the Anthropic path put a cache breakpoint in the
right place, and it costs the other providers nothing - they just get the stable
parts concatenated into a system prompt.
"""
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, TypeVar

from pydantic import BaseModel

from app.config import settings
from app.llm.stats import STATS, CallRecord

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Which providers to try, in order, for each active selection. A provider that is
# not configured is skipped rather than failed, so a chain degrades quietly.
PROVIDER_CHAINS: Dict[str, List[str]] = {
    "openrouter":  ["openrouter", "nvidia_nim"],
    "nvidia_nim":  ["nvidia_nim", "openrouter"],
    "claude_code": ["claude_code", "anthropic", "openrouter"],
    "anthropic":   ["anthropic", "claude_code", "openrouter"],
}


class LLMResult:
    """Text plus the usage that produced it."""

    def __init__(self, text: str, usage: Dict[str, Any], provider: str, model: str):
        self.text = text
        self.usage = usage
        self.provider = provider
        self.model = model

    def __str__(self) -> str:  # lets callers keep treating this as text
        return self.text

    def strip(self) -> str:
        return self.text.strip()


def provider_chain(active: Optional[str] = None) -> List[str]:
    chosen = active or settings.LLM_PROVIDER
    return PROVIDER_CHAINS.get(chosen, ["openrouter", "nvidia_nim"])


def provider_available(provider: str) -> bool:
    if provider == "openrouter":
        return bool(settings.OPENROUTER_API_KEY.strip())
    if provider == "nvidia_nim":
        return bool(settings.NVIDIA_NIM_API_KEY.strip())
    if provider == "claude_code":
        from app.llm import claude_code
        return claude_code.is_available()
    if provider == "anthropic":
        from app.llm import anthropic_client
        return anthropic_client.is_available()
    return False


def provider_status() -> List[Dict[str, Any]]:
    """What the settings UI shows: which providers can actually be selected."""
    from app.llm import anthropic_client, claude_code

    return [
        {
            "id": "openrouter",
            "label": "OpenRouter",
            "model": settings.OPENROUTER_MODEL,
            "available": bool(settings.OPENROUTER_API_KEY.strip()),
            "supports_caching": False,
            "requires": "OPENROUTER_API_KEY in backend/.env",
        },
        {
            "id": "nvidia_nim",
            "label": "NVIDIA NIM",
            "model": settings.NVIDIA_NIM_MODEL,
            "available": bool(settings.NVIDIA_NIM_API_KEY.strip()),
            "supports_caching": False,
            "requires": "NVIDIA_NIM_API_KEY in backend/.env",
        },
        {
            "id": "claude_code",
            "label": "Claude Code (local)",
            "model": settings.CLAUDE_CODE_MODEL,
            "available": claude_code.is_available(),
            "supports_caching": True,
            "requires": "the `claude` CLI on PATH, already logged in",
        },
        {
            "id": "anthropic",
            "label": "Anthropic API",
            "model": settings.ANTHROPIC_MODEL,
            "available": anthropic_client.is_available(),
            "supports_caching": True,
            "requires": "ANTHROPIC_API_KEY in backend/.env",
        },
    ]


def _openai_client(provider: str):
    from openai import OpenAI

    if provider == "nvidia_nim":
        return OpenAI(
            base_url=settings.NVIDIA_NIM_BASE_URL,
            api_key=settings.NVIDIA_NIM_API_KEY,
        ), settings.NVIDIA_NIM_MODEL

    return OpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": "https://github.com/points-to-arnav/rootcause",
            "X-Title": "AskData Analyst",
        },
    ), settings.OPENROUTER_MODEL


def log_llm_call(
    provider: str,
    model: str,
    prompt_summary: str,
    response_text: str,
    latency_s: float,
    error: Optional[str] = None,
) -> None:
    """Appends to backend/data/logs/llm.jsonl. Never raises."""
    try:
        log_dir = os.path.join(settings.DATA_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "llm.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "provider": provider,
                "model": model,
                "prompt_summary": prompt_summary[:200],
                "response_text": (response_text or "")[:500],
                "latency_s": round(latency_s, 2),
                "error": error,
            }) + "\n")
    except Exception as exc:
        logger.warning("Failed to log LLM call: %s", exc)


def repair_truncated_json(raw: str) -> Optional[dict]:
    """Recovers JSON from fenced blocks, prose padding, or a truncated tail."""
    text = (raw or "").strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # Some models wrap the object in a sentence; take the outermost braces.
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except Exception:
            text = text[first:]

    trimmed = re.sub(r',\s*"[a-zA-Z0-9_]*"?\s*:?\s*$', "", text)
    open_braces = trimmed.count("{") - trimmed.count("}")
    open_brackets = trimmed.count("[") - trimmed.count("]")
    if open_braces > 0 or open_brackets > 0:
        candidate = trimmed + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None


def _call_provider(
    provider: str,
    stable_parts: Sequence[str],
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: float,
) -> Tuple[str, Dict[str, Any], str]:
    """Returns (text, usage, model). Raises on failure."""
    if provider == "claude_code":
        from app.llm import claude_code
        system_prompt = "\n\n".join(p for p in stable_parts if p and p.strip())
        text, usage = claude_code.complete(
            system_prompt=system_prompt, user_prompt=user_prompt, timeout=timeout
        )
        return text, usage, usage.get("model", settings.CLAUDE_CODE_MODEL)

    if provider == "anthropic":
        from app.llm import anthropic_client
        text, usage = anthropic_client.complete(
            stable_parts=stable_parts, user_prompt=user_prompt, max_tokens=max_tokens
        )
        return text, usage, usage.get("model", settings.ANTHROPIC_MODEL)

    # OpenAI-compatible providers
    client, model = _openai_client(provider)
    system_prompt = "\n\n".join(p for p in stable_parts if p and p.strip())
    start = time.time()
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    elapsed = time.time() - start

    message = completion.choices[0].message
    content = message.content or ""
    if not content.strip():
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning and reasoning.strip():
            content = reasoning
        else:
            raise ValueError(f"Provider {provider} ({model}) returned empty content.")

    raw_usage = getattr(completion, "usage", None)
    usage = {
        "input_tokens": int(getattr(raw_usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(raw_usage, "completion_tokens", 0) or 0),
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "latency_s": elapsed,
        "model": model,
    }
    return content, usage, model


def complete_chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 1024,
    timeout: float = 25.0,
    forced_provider: Optional[str] = None,
    stable_parts: Optional[Sequence[str]] = None,
    stage: str = "planner",
) -> LLMResult:
    """
    Runs the active provider chain until one succeeds.

    `stable_parts` is the cacheable prefix. When omitted, `system_prompt` is the
    whole prefix - which is the right default for short, non-cacheable prompts.
    """
    prefix = list(stable_parts) if stable_parts else [system_prompt]
    chain = [forced_provider] if forced_provider else provider_chain()

    last_error: Optional[Exception] = None
    for provider in chain:
        if not provider_available(provider):
            logger.debug("Skipping %s: not configured.", provider)
            continue

        start = time.time()
        try:
            logger.info("Calling LLM via %s...", provider)
            text, usage, model = _call_provider(
                provider, prefix, user_prompt, max_tokens, temperature, timeout
            )
            STATS.record(CallRecord(
                provider=provider,
                model=model,
                stage=stage,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_tokens=usage.get("cache_read_tokens", 0),
                cache_write_tokens=usage.get("cache_write_tokens", 0),
                latency_s=usage.get("latency_s", time.time() - start),
                ok=True,
            ))
            log_llm_call(provider, model, user_prompt, text, usage.get("latency_s", 0.0))
            return LLMResult(text, usage, provider, model)

        except Exception as exc:
            elapsed = time.time() - start
            last_error = exc
            logger.warning("LLM call to %s failed after %.2fs: %s", provider, elapsed, exc)
            STATS.record(CallRecord(provider=provider, model="?", stage=stage,
                                    latency_s=elapsed, ok=False))
            log_llm_call(provider, "?", user_prompt, "", elapsed, error=str(exc))

    configured = [p for p in chain if provider_available(p)]
    if not configured:
        raise RuntimeError(
            f"No LLM provider is configured. Tried: {', '.join(chain)}. "
            "Set an API key in backend/.env, or install the Claude Code CLI."
        )
    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


def complete_json(
    system_prompt: str,
    user_prompt: str,
    schema_cls: Type[T],
    temperature: float = 0.1,
    max_tokens: int = 1500,
    timeout: float = 25.0,
    stable_parts: Optional[Sequence[str]] = None,
    stage: str = "planner",
) -> T:
    """As complete_chat, but the response must validate against schema_cls."""
    json_rule = (
        "\nIMPORTANT: Output strictly valid JSON conforming to the requested schema. "
        "No conversational filler, no markdown fences, and no internal or system XML tags."
    )
    prefix = list(stable_parts) if stable_parts else [system_prompt]
    prefix = [prefix[0] + json_rule] + list(prefix[1:])

    chain = provider_chain()
    last_error: Optional[Exception] = None

    for provider in chain:
        if not provider_available(provider):
            continue
        try:
            result = complete_chat(
                system_prompt=prefix[0],
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                forced_provider=provider,
                stable_parts=prefix,
                stage=stage,
            )
            data = repair_truncated_json(result.text)
            if data is None:
                raise ValueError(f"Unrecoverable JSON in response: {result.text[:200]}")
            return schema_cls.model_validate(data)
        except Exception as exc:
            last_error = exc
            logger.warning("JSON validation failed on %s: %s. Trying next provider...",
                           provider, exc)

    raise ValueError(f"Failed to obtain valid JSON from any provider. Last error: {last_error}")
