"""Tests for environment-driven settings."""

from myhespi.config import load_settings


def test_llm_base_url_prefers_hespi_over_openai(monkeypatch):
    monkeypatch.setenv("HESPI_LLM_BASE_URL", "https://a.example/v1")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://b.example/v1")
    s = load_settings()
    assert s.hespi_llm_base_url == "https://a.example/v1"


def test_llm_base_url_falls_back_to_openai_url(monkeypatch):
    monkeypatch.delenv("HESPI_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai-compat.example/v1")
    s = load_settings()
    assert s.hespi_llm_base_url == "https://openai-compat.example/v1"


def test_llm_base_url_empty_when_unset(monkeypatch):
    monkeypatch.delenv("HESPI_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    s = load_settings()
    assert s.hespi_llm_base_url == ""


def test_hespi_runtime_env_values(monkeypatch):
    monkeypatch.setenv("HESPI_TROCR_SIZE", "small")
    monkeypatch.setenv("HESPI_BATCH_SIZE", "16")
    monkeypatch.setenv("HESPI_SHEET_COMPONENT_RES", "640")
    monkeypatch.setenv("HESPI_LABEL_FIELD_RES", "640")

    s = load_settings()

    assert s.hespi_trocr_size == "small"
    assert s.hespi_batch_size == 16
    assert s.hespi_sheet_component_res == 640
    assert s.hespi_label_field_res == 640


def test_max_image_long_side_default(monkeypatch):
    monkeypatch.delenv("MYHESPI_MAX_IMAGE_LONG_SIDE", raising=False)
    s = load_settings()
    assert s.max_image_long_side == 2560


def test_max_image_long_side_zero_disables(monkeypatch):
    monkeypatch.setenv("MYHESPI_MAX_IMAGE_LONG_SIDE", "0")
    s = load_settings()
    assert s.max_image_long_side == 0
