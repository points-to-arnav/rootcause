import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional, Type, TypeVar
from openai import OpenAI
from pydantic import BaseModel
from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

def _get_client(provider: str) -> tuple[OpenAI, str]:
    """Returns the OpenAI client and model name for the given provider."""
    if provider == "nvidia_nim":
        client = OpenAI(
            base_url=settings.NVIDIA_NIM_BASE_URL,
            api_key=settings.NVIDIA_NIM_API_KEY,
        )
        return client, settings.NVIDIA_NIM_MODEL
    else:  # default openrouter
        client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=settings.OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": "https://github.com/points-to-arnav/rootcause",
                "X-Title": "AskData Analyst",
            }
        )
        return client, settings.OPENROUTER_MODEL

def log_llm_call(provider: str, model: str, prompt_summary: str, response_text: str, latency_s: float, error: Optional[str] = None):
    """Logs LLM calls to backend/data/logs/llm.jsonl."""
    try:
        log_dir = os.path.join(settings.DATA_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "llm.jsonl")
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "model": model,
            "prompt_summary": prompt_summary[:200],
            "response_text": response_text[:500] if response_text else "",
            "latency_s": round(latency_s, 2),
            "error": error
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log LLM call: {e}")

def repair_truncated_json(raw: str) -> Optional[dict]:
    """Attempts to recover valid JSON if truncated at trailing keys."""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()

    # 1. Direct parse attempt
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2. Trim unclosed trailing string / key like ',"assumptions'
    trimmed = re.sub(r',\s*"[a-zA-Z0-9_]*"?\s*:?\s*$', '', text)
    # Balance unclosed curly braces
    open_braces = trimmed.count("{") - trimmed.count("}")
    if open_braces > 0:
        candidate = trimmed + ("}" * open_braces)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None

def complete_chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 1024,
    timeout: float = 25.0,
    forced_provider: Optional[str] = None
) -> str:
    """
    Executes a chat completion with automatic fallback between OpenRouter and NVIDIA NIM.
    """
    providers = [forced_provider] if forced_provider else (
        ["openrouter", "nvidia_nim"] if settings.LLM_PROVIDER == "openrouter" else ["nvidia_nim", "openrouter"]
    )

    last_error = None
    for provider in providers:
        client, model = _get_client(provider)
        start_t = time.time()
        try:
            logger.info(f"Calling LLM via {provider} ({model})...")
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            elapsed = time.time() - start_t
            content = completion.choices[0].message.content or ""
            log_llm_call(provider, model, user_prompt, content, elapsed)
            return content
        except Exception as e:
            elapsed = time.time() - start_t
            last_error = e
            logger.warning(f"LLM call to {provider} ({model}) failed after {elapsed:.2f}s: {e}")
            log_llm_call(provider, model, user_prompt, "", elapsed, error=str(e))

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

def complete_json(
    system_prompt: str,
    user_prompt: str,
    schema_cls: Type[T],
    temperature: float = 0.1,
    max_tokens: int = 1024,
    timeout: float = 25.0
) -> T:
    """
    Calls the LLM expecting structured JSON that validates into schema_cls.
    Falls back to secondary provider if first provider returns invalid JSON.
    """
    providers = ["openrouter", "nvidia_nim"] if settings.LLM_PROVIDER == "openrouter" else ["nvidia_nim", "openrouter"]

    last_error = None
    for provider in providers:
        try:
            raw = complete_chat(
                system_prompt=system_prompt + "\nIMPORTANT: You must output strictly valid JSON conforming to the requested schema. No conversational filler or markdown.",
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                forced_provider=provider
            )

            data = repair_truncated_json(raw)
            if data is not None:
                return schema_cls.model_validate(data)
            else:
                raise ValueError(f"Unrecoverable JSON syntax in response: {raw[:200]}")
        except Exception as e:
            last_error = e
            logger.warning(f"JSON validation failed on {provider}: {e}. Trying fallback provider...")

    raise ValueError(f"Failed to obtain valid JSON from any LLM provider. Last error: {last_error}")
