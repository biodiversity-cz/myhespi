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
