from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ALLOWED_MIME_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/jp2",
    "image/jpeg2000",
})


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    api_tokens: frozenset[str]
    max_upload_mb: int
    process_timeout_seconds: int
    retention_days: int
    temp_root: Path
    hespi_use_gpu: bool
    hespi_llm_model: str
    openai_api_key: str

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def load_settings() -> Settings:
    tokens_raw = os.getenv("MYHESPI_API_TOKENS", "").strip()
    tokens = frozenset(t.strip() for t in tokens_raw.split(",") if t.strip())

    return Settings(
        api_tokens=tokens,
        max_upload_mb=_env_int("MYHESPI_MAX_UPLOAD_MB", 5),
        process_timeout_seconds=_env_int("MYHESPI_PROCESS_TIMEOUT_SECONDS", 300),
        retention_days=_env_int("MYHESPI_RETENTION_DAYS", 30),
        temp_root=Path(os.getenv("MYHESPI_TEMP_ROOT", "myhespi-temp")).resolve(),
        hespi_use_gpu=os.getenv("HESPI_USE_GPU", "1").lower() in {"1", "true", "yes"},
        hespi_llm_model=os.getenv("HESPI_LLM_MODEL", "none"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    )
