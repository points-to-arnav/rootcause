from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
ENV_FILES = [str(BACKEND_DIR / ".env"), str(ROOT_DIR / ".env")]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Active LLM provider
    LLM_PROVIDER: Literal["openrouter", "nvidia_nim"] = "openrouter"

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "nex-agi/nex-n2.5-mini:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # NVIDIA NIM (fallback)
    NVIDIA_NIM_API_KEY: str = ""
    NVIDIA_NIM_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Storage & Limits
    DATA_DIR: str = str(BACKEND_DIR / "data")
    SEND_SAMPLES: bool = True
    MAX_RESULT_ROWS: int = 1000
    NARRATOR_MAX_ROWS: int = 50
    QUERY_TIMEOUT_S: int = 20

    # Why / Analysis Thresholds
    WHY_MAX_CARDINALITY: int = 50
    WHY_MIN_SHARE: float = 0.30
    WHY_MIN_LIFT: float = 1.5
    WHY_MIN_CHANGE_PCT: float = 1.0
    WHY_OFFSET_RATIO: float = 1.5

    # Alert Thresholds
    ALERT_DROP_PCT: float = 10.0
    ALERT_Z: float = 3.0
    ALERT_MIN_POINTS: int = 8
    ALERT_CONCENTRATION: float = 0.5

settings = Settings()
