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
def update_provider(provider: str):
    if provider not in ["openrouter", "nvidia_nim"]:
        return {"status": "error", "message": "Invalid provider. Choose 'openrouter' or 'nvidia_nim'"}
    settings.LLM_PROVIDER = provider
    logger.info(f"Switched LLM provider to: {provider}")
    return {"status": "ok", "active_provider": settings.LLM_PROVIDER}
