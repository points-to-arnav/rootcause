from pathlib import Path
from typing import Literal, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
ENV_FILES = [str(BACKEND_DIR / ".env"), str(ROOT_DIR / ".env")]

Provider = Literal["openrouter", "nvidia_nim", "claude_code", "anthropic"]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Active LLM provider
    LLM_PROVIDER: Provider = "openrouter"

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "nex-agi/nex-n2.5-mini:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # NVIDIA NIM (fallback)
    NVIDIA_NIM_API_KEY: str = ""
    NVIDIA_NIM_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Claude Code CLI (uses the local `claude` login — no API key needed)
    CLAUDE_CODE_BIN: str = ""              # blank => look for `claude` on PATH
    CLAUDE_CODE_MODEL: str = "sonnet"
    CLAUDE_CODE_TIMEOUT_S: int = 90

    # Anthropic API (direct SDK, supports prompt caching)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-5"
    ANTHROPIC_MAX_TOKENS: int = 4000
    ANTHROPIC_TIMEOUT_S: float = 60.0
    ANTHROPIC_THINKING: bool = False       # off keeps the interactive path fast
    ANTHROPIC_EFFORT: Optional[str] = "low"

    # Prompt caching
    ENABLE_PROMPT_CACHING: bool = True

    # Storage & Limits.
    # DATA_DIR is always resolved to an absolute path anchored at backend/, so the
    # app reads and writes the same place whether it was started from the repo root
    # (setup.sh) or from backend/ (README). A relative value here used to mean the
    # ingester and the dashboard could disagree about where a dataset lives.
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

    @field_validator("DATA_DIR")
    @classmethod
    def _anchor_data_dir(cls, value: str) -> str:
        path = Path(value)
        return str(path if path.is_absolute() else (BACKEND_DIR / path).resolve())

settings = Settings()
