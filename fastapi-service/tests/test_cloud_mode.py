"""Tests für den Cloud-Betrieb: Provider-Factory, API-Key-Schutz, /ready und das
LLM_FAILURE-Log. Kein Netzwerk: Token-Provider und Graph sind gemockt."""
import logging
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI

from app import main
from app.config import Settings
from app.graph import llm_utils, orchestrator
from app.graph.llm_utils import LLMFailure, build_json_llm, invoke_json
from app.models.ticket import TicketAnalysis

client = TestClient(main.app)
TICKET = {"ticket_id": "T-1", "raw_text": "Drucker druckt nur leere Etiketten."}


# --- Provider-Factory -------------------------------------------------------------

def test_factory_builds_ollama_by_default(monkeypatch):
    monkeypatch.setattr(llm_utils, "get_settings", lambda: Settings())
    llm = build_json_llm("qwen2.5:3b", temperature=0)
    assert isinstance(llm, ChatOllama)
    assert llm.format == "json"


def test_factory_builds_azure_with_json_mode_and_sdk_retries(monkeypatch):
    settings = Settings(llm_provider="azure", azure_openai_endpoint="https://example.openai.azure.com/")
    monkeypatch.setattr(llm_utils, "get_settings", lambda: settings)
    monkeypatch.setattr(llm_utils, "get_azure_token_provider", lambda: (lambda: "fake-token"))

    llm = build_json_llm("ticket-llm", temperature=0)

    assert isinstance(llm, AzureChatOpenAI)
    assert llm.deployment_name == "ticket-llm"
    assert llm.temperature == 0
    assert llm.max_retries == 3
    assert llm.model_kwargs["response_format"] == {"type": "json_object"}
    # Keyless: kein API-Key, stattdessen Token-Provider
    assert llm.openai_api_key is None
    assert llm.azure_ad_token_provider is not None


def test_model_tiers_follow_provider():
    assert Settings().fast_model == "qwen2.5:3b"
    azure = Settings(llm_provider="azure", azure_smart_deployment="ticket-llm-smart")
    assert azure.fast_model == "ticket-llm"
    assert azure.smart_model == "ticket-llm-smart"


def test_old_ollama_timeout_variable_still_works(monkeypatch):
    monkeypatch.setenv("OLLAMA_TIMEOUT", "42")
    assert Settings().llm_timeout == 42


# --- API-Key-Schutz ---------------------------------------------------------------

@pytest.fixture
def fake_graph(monkeypatch):
    fake = AsyncMock(return_value=TicketAnalysis(
        ticket_id="T-1", category="technical_support", urgency="high",
        summary="Drucker druckt leere Etiketten.", confidence_score=1.0,
    ))
    monkeypatch.setattr(orchestrator, "run_graph", fake)
    return fake


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "geheim")
    return "geheim"


def test_missing_api_key_is_rejected(api_key, fake_graph):
    resp = client.post("/analyze", json=TICKET)
    assert resp.status_code == 401
    fake_graph.assert_not_awaited()


def test_wrong_api_key_is_rejected(api_key, fake_graph):
    resp = client.post("/analyze", json=TICKET, headers={"X-API-Key": "falsch"})
    assert resp.status_code == 401
    fake_graph.assert_not_awaited()


def test_correct_api_key_is_accepted(api_key, fake_graph):
    resp = client.post("/analyze", json=TICKET, headers={"X-API-Key": api_key})
    assert resp.status_code == 200


def test_probes_need_no_api_key(api_key):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


# --- /ready -----------------------------------------------------------------------

def test_ready_with_ollama_reports_commit(monkeypatch):
    monkeypatch.setattr(main.settings, "git_sha", "abc1234")
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "provider": "ollama", "git_sha": "abc1234"}


def test_ready_with_azure_reports_missing_config(monkeypatch):
    monkeypatch.setattr(main.settings, "llm_provider", "azure")
    resp = client.get("/ready")
    assert resp.status_code == 503
    problems = " ".join(resp.json()["problems"])
    assert "AZURE_OPENAI_ENDPOINT" in problems
    assert "API_KEY" in problems


@pytest.fixture
def azure_configured(monkeypatch):
    monkeypatch.setattr(main.settings, "llm_provider", "azure")
    monkeypatch.setattr(main.settings, "azure_openai_endpoint", "https://example.openai.azure.com/")
    monkeypatch.setattr(main.settings, "api_key", "geheim")


def test_ready_with_azure_fetches_token_but_calls_no_model(monkeypatch, azure_configured):
    calls = []
    monkeypatch.setattr(llm_utils, "get_azure_token_provider", lambda: (lambda: calls.append(1) or "token"))
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert calls == [1]


def test_ready_with_azure_fails_when_token_fails(monkeypatch, azure_configured):
    def broken():
        raise RuntimeError("keine Identität")
    monkeypatch.setattr(llm_utils, "get_azure_token_provider", lambda: broken)
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert "Token" in resp.json()["problems"][0]


# --- LLM_FAILURE-Log --------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_failure_is_logged_without_ticket_text(make_llm, caplog):
    with caplog.at_level(logging.WARNING, logger="app.graph.llm_utils"):
        result = await invoke_json(make_llm(side_effect=ConnectionError("down")), "Ticket von Max Muster", "Classifier")
    assert result is LLMFailure.ERROR
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("LLM_FAILURE")]
    assert lines == ["LLM_FAILURE node='Classifier' reason=error"]
    assert "Max Muster" not in caplog.text
