"""
Claude Code CLI adapter.

Runs the locally-installed `claude` binary in headless mode (`-p`) and returns the
model's text plus its real token usage. This uses whatever credentials the CLI is
already logged in with, so it needs no API key in .env.

Two things keep the call cheap and predictable:
  * --system-prompt-file replaces Claude Code's own ~40k-token harness prompt with ours.
  * every built-in tool is disabled — this is a text-in/text-out call, and a planner
    that could read the filesystem is both slower and a liability.

The CLI caches the system prompt between calls, so repeated questions against the
same dataset report cache_read_input_tokens instead of cache_creation_input_tokens.
"""
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# Every built-in tool, denied. Keep in sync with `claude --help`; unknown names are
# ignored by the CLI, so listing a tool that no longer exists is harmless.
_DENIED_TOOLS = [
    "Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch",
    "Task", "Agent", "TodoWrite", "NotebookEdit", "Skill", "SlashCommand",
    "BashOutput", "KillShell", "ExitPlanMode", "ListMcpResources", "ReadMcpResource",
]


class ClaudeCodeUnavailable(RuntimeError):
    """The CLI is missing, not logged in, or returned nothing usable."""


def is_available() -> bool:
    return resolve_binary() is not None


def resolve_binary() -> Optional[str]:
    configured = (settings.CLAUDE_CODE_BIN or "").strip()
    if configured:
        return configured if shutil.which(configured) or _looks_like_path(configured) else None
    return shutil.which("claude")


def _looks_like_path(value: str) -> bool:
    return os.path.sep in value and os.path.exists(value)


def complete(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns (text, usage). Raises ClaudeCodeUnavailable on any failure so the
    caller's provider-fallback chain can move on.
    """
    binary = resolve_binary()
    if not binary:
        raise ClaudeCodeUnavailable(
            "The 'claude' CLI was not found on PATH. Install Claude Code or set CLAUDE_CODE_BIN."
        )

    chosen_model = model or settings.CLAUDE_CODE_MODEL
    limit = timeout or settings.CLAUDE_CODE_TIMEOUT_S

    # Neither prompt may travel on the command line. On Windows the `claude` shim
    # is a .cmd file run through cmd.exe, which rejects anything over ~8,000
    # characters with "The command line is too long" - and the planner prompt plus
    # dataset context is several times that. The user prompt goes in on stdin and
    # the system prompt through a file. The CLI still caches it by content.
    prompt_file = tempfile.NamedTemporaryFile(
        "w", suffix=".md", prefix="rootcause_system_", delete=False, encoding="utf-8"
    )
    try:
        with prompt_file:
            prompt_file.write(system_prompt)

        cmd = [
            binary,
            "--print",
            "--output-format", "json",
            "--model", chosen_model,
            "--system-prompt-file", prompt_file.name,
            "--disallowed-tools", *_DENIED_TOOLS,
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--setting-sources", "",
        ]

        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                input=user_prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=limit,
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeCodeUnavailable(f"Claude Code CLI timed out after {limit}s.") from exc
        except OSError as exc:
            raise ClaudeCodeUnavailable(f"Could not run the Claude Code CLI: {exc}") from exc
    finally:
        try:
            os.unlink(prompt_file.name)
        except OSError:
            logger.debug("Could not remove temp prompt file %s", prompt_file.name)

    elapsed = time.time() - start

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:300]
        raise ClaudeCodeUnavailable(
            f"Claude Code CLI exited with code {proc.returncode}: {detail}"
        )

    raw = (proc.stdout or "").strip()
    if not raw:
        raise ClaudeCodeUnavailable("Claude Code CLI returned no output.")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClaudeCodeUnavailable(
            f"Claude Code CLI returned output that was not JSON: {raw[:200]}"
        ) from exc

    if payload.get("is_error"):
        raise ClaudeCodeUnavailable(
            f"Claude Code CLI reported an error: {payload.get('result') or payload.get('subtype')}"
        )

    text = payload.get("result") or ""
    if not text.strip():
        raise ClaudeCodeUnavailable("Claude Code CLI returned an empty result.")

    raw_usage = payload.get("usage") or {}
    usage = {
        "input_tokens": int(raw_usage.get("input_tokens") or 0),
        "output_tokens": int(raw_usage.get("output_tokens") or 0),
        "cache_read_tokens": int(raw_usage.get("cache_read_input_tokens") or 0),
        "cache_write_tokens": int(raw_usage.get("cache_creation_input_tokens") or 0),
        "latency_s": elapsed,
        # The CLI reports its own cost; keep it for reconciliation but let stats.py
        # compute the figure it displays so every provider is priced the same way.
        "reported_cost_usd": payload.get("total_cost_usd"),
        "model": _canonical_model(payload, chosen_model),
    }
    logger.info(
        "Claude Code CLI ok in %.2fs (cache_read=%d, cache_write=%d)",
        elapsed, usage["cache_read_tokens"], usage["cache_write_tokens"],
    )
    return text, usage


def _canonical_model(payload: Dict[str, Any], fallback: str) -> str:
    """The CLI reports the model it actually used under modelUsage."""
    model_usage = payload.get("modelUsage") or {}
    for name, detail in model_usage.items():
        if isinstance(detail, dict) and detail.get("canonicalModel"):
            # Skip the tiny helper model the CLI uses for its own bookkeeping.
            if "haiku" in name and len(model_usage) > 1:
                continue
            return detail["canonicalModel"]
    return fallback
