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


def _llm_base_url() -> str:
    """OpenAI-compatible API base URL (e.g. e-infra Chat AI). HESPI_LLM_BASE_URL wins over OPENAI_BASE_URL."""
    primary = os.getenv("HESPI_LLM_BASE_URL", "").strip()
    if primary:
        return primary
    return os.getenv("OPENAI_BASE_URL", "").strip()


@dataclass(frozen=True)
class Settings:
    api_tokens: frozenset[str]
    max_upload_mb: int
    process_timeout_seconds: int
    retention_days: int
    temp_root: Path
    hespi_use_gpu: bool
    hespi_llm_model: str
    hespi_trocr_size: str
    hespi_batch_size: int
    hespi_sheet_component_res: int
    hespi_label_field_res: int
    hespi_llm_base_url: str
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
        hespi_trocr_size=os.getenv("HESPI_TROCR_SIZE", "small"),
        hespi_batch_size=_env_int("HESPI_BATCH_SIZE", 16),
        hespi_sheet_component_res=_env_int("HESPI_SHEET_COMPONENT_RES", 640),
        hespi_label_field_res=_env_int("HESPI_LABEL_FIELD_RES", 640),
        hespi_llm_base_url=_llm_base_url(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    )
