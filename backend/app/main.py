import logging
from typing import Literal, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.api.routes_datasets import router as datasets_router
from app.api.routes_sessions import router as sessions_router
from app.api.routes_dashboard import router as dashboard_router
from app.llm.client import provider_status
from app.llm.stats import STATS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("askdata")

app = FastAPI(
    title="AskData / RootCause API",
    description="AI-powered Data Analyst: Deterministic calculations via DuckDB, planning & narration via LLM.",
    version="1.1.0"
)

app.include_router(datasets_router)
app.include_router(sessions_router)
app.include_router(dashboard_router)

# Enable CORS for the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ProviderName = Literal["openrouter", "nvidia_nim", "claude_code", "anthropic"]


def _settings_payload() -> dict:
    return {
        "active_provider": settings.LLM_PROVIDER,
        "openrouter_model": settings.OPENROUTER_MODEL,
        "nvidia_nim_model": settings.NVIDIA_NIM_MODEL,
        "claude_code_model": settings.CLAUDE_CODE_MODEL,
        "anthropic_model": settings.ANTHROPIC_MODEL,
        "prompt_caching_enabled": settings.ENABLE_PROMPT_CACHING,
        "max_result_rows": settings.MAX_RESULT_ROWS,
        "query_timeout_s": settings.QUERY_TIMEOUT_S,
        "providers": provider_status(),
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "prompt_caching_enabled": settings.ENABLE_PROMPT_CACHING,
        "providers": provider_status(),
    }


class UpdateSettingsRequest(BaseModel):
    active_provider: Optional[ProviderName] = None
    openrouter_model: Optional[str] = None
    nvidia_nim_model: Optional[str] = None
    claude_code_model: Optional[str] = None
    anthropic_model: Optional[str] = None
    prompt_caching_enabled: Optional[bool] = None


@app.get("/api/settings")
def get_settings():
    return _settings_payload()


@app.post("/api/settings")
def update_settings(
    req: Optional[UpdateSettingsRequest] = None,
    provider: Optional[str] = None,
):
    valid = {"openrouter", "nvidia_nim", "claude_code", "anthropic"}

    chosen_provider = None
    if req and req.active_provider:
        chosen_provider = req.active_provider
    elif provider:
        chosen_provider = provider

    if chosen_provider:
        if chosen_provider not in valid:
            return {
                "status": "error",
                "message": f"Invalid provider. Choose one of: {', '.join(sorted(valid))}",
                **_settings_payload(),
            }
        settings.LLM_PROVIDER = chosen_provider
        logger.info("Switched LLM provider to: %s", chosen_provider)

    if req:
        if req.openrouter_model:
            settings.OPENROUTER_MODEL = req.openrouter_model.strip()
        if req.nvidia_nim_model:
            settings.NVIDIA_NIM_MODEL = req.nvidia_nim_model.strip()
        if req.claude_code_model:
            settings.CLAUDE_CODE_MODEL = req.claude_code_model.strip()
        if req.anthropic_model:
            settings.ANTHROPIC_MODEL = req.anthropic_model.strip()
        if req.prompt_caching_enabled is not None:
            settings.ENABLE_PROMPT_CACHING = req.prompt_caching_enabled
            logger.info("Prompt caching set to: %s", settings.ENABLE_PROMPT_CACHING)

    return _settings_payload()


@app.get("/api/stats")
def get_stats():
    """Live LLM telemetry: token usage, prompt-cache effectiveness, latency, cost."""
    return {
        "status": "ok",
        "provider": settings.LLM_PROVIDER,
        "prompt_caching_enabled": settings.ENABLE_PROMPT_CACHING,
        "summary": STATS.summary(),
    }


@app.post("/api/stats/reset")
def reset_stats():
    STATS.reset()
    return {"status": "ok", "summary": STATS.summary()}


@app.on_event("startup")
def warmup_on_startup():
    import os
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    sample_db = os.path.join(settings.DATA_DIR, "ds_retail_sample", "data.duckdb")
    if os.path.exists(sample_db):
        logger.info("Warmup: Demo dataset 'ds_retail_sample' pre-loaded and ready.")

    available = [p["id"] for p in provider_status() if p["available"]]
    if available:
        logger.info("LLM providers available: %s (active: %s)",
                    ", ".join(available), settings.LLM_PROVIDER)
    else:
        logger.warning(
            "No LLM provider is configured. Set a key in backend/.env or install "
            "the Claude Code CLI; the pipeline will fall back to heuristic planning."
        )
