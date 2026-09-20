import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes_datasets import router as datasets_router
from app.api.routes_sessions import router as sessions_router
from app.api.routes_dashboard import router as dashboard_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("askdata")

app = FastAPI(
    title="AskData / RootCause API",
    description="AI-powered Data Analyst: Deterministic calculations via DuckDB, planning & narration via LLM.",
    version="1.0.0"
)

app.include_router(datasets_router)
app.include_router(sessions_router)
app.include_router(dashboard_router)

# Enable CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "openrouter_model": settings.OPENROUTER_MODEL,
        "nvidia_nim_model": settings.NVIDIA_NIM_MODEL
    }

from typing import Optional, Literal
from pydantic import BaseModel

class UpdateSettingsRequest(BaseModel):
    active_provider: Optional[Literal["openrouter", "nvidia_nim"]] = None
    openrouter_model: Optional[str] = None
    nvidia_nim_model: Optional[str] = None

@app.get("/api/settings")
def get_settings():
    return {
        "active_provider": settings.LLM_PROVIDER,
        "openrouter_model": settings.OPENROUTER_MODEL,
        "nvidia_nim_model": settings.NVIDIA_NIM_MODEL,
        "max_result_rows": settings.MAX_RESULT_ROWS,
        "query_timeout_s": settings.QUERY_TIMEOUT_S
    }

@app.post("/api/settings")
def update_settings(req: Optional[UpdateSettingsRequest] = None, provider: Optional[str] = None):
    chosen_provider = None
    if req and req.active_provider:
        chosen_provider = req.active_provider
    elif provider:
        chosen_provider = provider

    if chosen_provider:
        if chosen_provider not in ["openrouter", "nvidia_nim"]:
            return {"status": "error", "message": "Invalid provider. Choose 'openrouter' or 'nvidia_nim'"}
        settings.LLM_PROVIDER = chosen_provider
        logger.info(f"Switched LLM provider to: {chosen_provider}")

    if req and req.openrouter_model:
        settings.OPENROUTER_MODEL = req.openrouter_model.strip()
        logger.info(f"Updated OpenRouter model to: {settings.OPENROUTER_MODEL}")

    if req and req.nvidia_nim_model:
        settings.NVIDIA_NIM_MODEL = req.nvidia_nim_model.strip()
        logger.info(f"Updated NVIDIA NIM model to: {settings.NVIDIA_NIM_MODEL}")

    return {
        "active_provider": settings.LLM_PROVIDER,
        "openrouter_model": settings.OPENROUTER_MODEL,
        "nvidia_nim_model": settings.NVIDIA_NIM_MODEL,
        "max_result_rows": settings.MAX_RESULT_ROWS,
        "query_timeout_s": settings.QUERY_TIMEOUT_S
    }

@app.on_event("startup")
def warmup_on_startup():
    import os
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    sample_db = os.path.join(settings.DATA_DIR, "ds_retail_sample", "data.duckdb")
    if os.path.exists(sample_db):
        logger.info("Warmup: Demo dataset 'ds_retail_sample' pre-loaded and ready.")

