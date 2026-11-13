"""Tracing mit Langfuse: Einhängen, Maskierung, Ticket-Referenz. Alles ohne Netzwerk:
LLM-Antworten kommen aus einem gemockten HTTP-Transport bzw. FakeListChatModel, Spans
landen in einem InMemorySpanExporter statt bei Langfuse.

Das SDK hält einen Client pro Public Key im Prozess. Jeder Test mit echtem Client bekommt
deshalb einen eigenen Public Key und schließt den Client am Ende mit shutdown()."""
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import observability
from app.config import Settings
from app.graph import llm_utils, orchestrator
from app.graph.nodes import classifier, extractor, risk_guard
from app.models.ticket import TicketInput

GUARD = "Herr Wächterhaus-7Q"
# Langfuse kodiert input/output als JSON mit ä statt ä. Eine Suche nur nach GUARD fände
# ein Leck dort nie; der ASCII-Teil kommt in beiden Schreibweisen vor.
GUARD_ASCII = "chterhaus-7Q"
TICKET = TicketInput(
    ticket_id="EVAL-001",
    source="email",
    raw_text=f"Ich bin {GUARD}. Die Rechnung ist falsch, ich gehe zum Anwalt.",
)
# Antwort für alle drei Nodes: urgency high, damit der Risk Guard sein LLM aufruft.
LLM_JSON = json.dumps({
    "category": "billing_dispute", "urgency": "high",
    "summary": f"Beschwerde von {GUARD}", "extracted_data": {"customer_name": GUARD},
    "risk_flag": True, "risk_reason": f"{GUARD} droht mit Anwalt",
})


def _settings(**overrides) -> Settings:
    """Settings mit allen Tracing-Feldern explizit gesetzt: Init-Argumente schlagen .env
    und Umgebung, eine lokale .env mit echten Schlüsseln kann die Tests nicht erreichen."""
    values = {
        "langfuse_public_key": "", "langfuse_secret_key": "",
        "langfuse_base_url": "http://localhost:1",
        "langfuse_capture_content": False,
        "langfuse_tracing_environment": "local",
        "ticket_id_hmac_key": "", "git_sha": "abc1234",
        "llm_provider": "azure", "azure_openai_endpoint": "https://example.openai.azure.com/",
        "azure_max_retries": 0,
    }
    values.update(overrides)
    return Settings(**values)


def _tracing_settings(**overrides) -> Settings:
    """Tracing an, mit eigenem Public Key pro Aufruf (siehe Moduldoku)."""
    base = {"langfuse_public_key": f"pk-test-{uuid.uuid4().hex[:8]}", "langfuse_secret_key": "sk-test",
            "ticket_id_hmac_key": "test-hmac-schluessel"}
    base.update(overrides)
    return _settings(**base)


@pytest.fixture
def use_settings(monkeypatch):
    """Setzt Settings für alle Module, die sie lesen, und leert den Client-Cache."""
    # Referenz vorher sichern: _traced_run ersetzt get_langfuse durch eine Lambda.
    get_langfuse = observability.get_langfuse

    def _use(settings: Settings) -> Settings:
        for module in (observability, orchestrator, llm_utils):
            monkeypatch.setattr(module, "get_settings", lambda: settings)
        get_langfuse.cache_clear()
        return settings
    yield _use
    get_langfuse.cache_clear()


class _AzureMock:
    """Gemockter HTTP-Transport für Azure OpenAI: merkt sich jeden Request."""
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={
            "id": "chatcmpl-1", "object": "chat.completion", "created": 0,
            "model": "gpt-4.1-mini-2025-04-14",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": LLM_JSON}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        })


def _azure_llm(monkeypatch, mock: _AzureMock):
    """Der echte Azure-Client aus build_json_llm(), nur der HTTP-Transport ist gemockt."""
    monkeypatch.setattr(llm_utils, "get_azure_token_provider", lambda: (lambda: "fake-token"))
    llm = llm_utils.build_json_llm("ticket-llm", temperature=0)
    llm.root_async_client._client = httpx.AsyncClient(transport=httpx.MockTransport(mock))
    return llm


def _use_llm_for_all_nodes(monkeypatch, llm) -> None:
    for node in (classifier, extractor, risk_guard):
        monkeypatch.setattr(node, "_llm", llm)


async def _traced_run(monkeypatch, settings: Settings) -> list:
    """Ein echter Graph-Lauf mit Langfuse-Client; gibt die exportierten Spans zurück."""
    exporter = InMemorySpanExporter()
    client = observability._build_client(span_exporter=exporter)
    assert client is not None
    monkeypatch.setattr(observability, "get_langfuse", lambda: client)
    _use_llm_for_all_nodes(monkeypatch, _azure_llm(monkeypatch, _AzureMock()))
    try:
        await orchestrator.run_graph(TICKET)
        client.flush()
        return list(exporter.get_finished_spans())
    finally:
        client.shutdown()


def _all_attribute_text(spans) -> str:
    return "\n".join(f"{k}={v}" for sp in spans for k, v in (sp.attributes or {}).items())


# --- Tracing aus ---------------------------------------------------------------

@pytest.mark.parametrize("public, secret", [("", ""), ("pk-x", ""), ("", "sk-x")])
def test_tracing_aus_ohne_vollstaendiges_schluesselpaar(use_settings, public, secret):
    settings = use_settings(_settings(langfuse_public_key=public, langfuse_secret_key=secret))
    assert settings.tracing_enabled is False
    assert observability.get_langfuse() is None
    assert observability.get_callbacks() == []
    observability.shutdown_tracing()  # harmlos, auch ohne Client


def test_shutdown_ohne_vorherigen_client_baut_keinen(use_settings, monkeypatch):
    use_settings(_tracing_settings())
    monkeypatch.setattr(observability, "_build_client", lambda **_: pytest.fail("Client gebaut"))
    observability.shutdown_tracing()


def test_ohne_schluessel_wird_langfuse_nicht_importiert():
    # Eigener Prozess: In diesem Prozess haben andere Tests langfuse längst importiert.
    code = ("import sys; from app import observability as o; "
            "assert o.get_callbacks() == []; print('langfuse' in sys.modules)")
    env = {**os.environ, "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": ""}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                         cwd=Path(__file__).resolve().parents[1], check=True)
    assert out.stdout.strip() == "False"


def test_client_fehler_schaltet_tracing_ab(use_settings, monkeypatch):
    use_settings(_tracing_settings())
    import langfuse

    def broken(**_):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(langfuse, "Langfuse", broken)
    assert observability.get_langfuse() is None
    assert observability.get_callbacks() == []


# --- Callback erreicht jeden LLM-Aufruf -----------------------------------------

class _RecordingHandler(AsyncCallbackHandler):
    def __init__(self) -> None:
        self.llm_starts = 0
        self.chain_names: list[str] = []

    async def on_chat_model_start(self, serialized, messages, **kwargs) -> None:
        self.llm_starts += 1

    async def on_chain_start(self, serialized, inputs, **kwargs) -> None:
        self.chain_names.append(kwargs.get("name"))


@pytest.mark.asyncio
async def test_callback_erreicht_jeden_llm_aufruf(use_settings, monkeypatch):
    use_settings(_settings())
    handler = _RecordingHandler()
    monkeypatch.setattr(orchestrator, "get_callbacks", lambda: [handler])
    monkeypatch.setattr(classifier, "N_VOTES", 3)
    for node, n in ((classifier, 3), (extractor, 1), (risk_guard, 1)):
        monkeypatch.setattr(node, "_llm", FakeListChatModel(responses=[LLM_JSON] * n))

    result = await orchestrator.run_graph(TICKET)

    assert result.urgency.value == "high"
    # 3 Classifier-Votes (asyncio.gather) + Extractor + Risk Guard
    assert handler.llm_starts == 5
    assert "ticket-analysis" in handler.chain_names


# --- Export: maskiert vs. Inhalte ------------------------------------------------

@pytest.mark.asyncio
async def test_kein_ticketinhalt_im_export(use_settings, monkeypatch):
    settings = use_settings(_tracing_settings())
    spans = await _traced_run(monkeypatch, settings)

    assert len(spans) == 7  # Root + 3 Nodes + 3 Generations
    text = _all_attribute_text(spans)
    assert GUARD not in text
    assert GUARD_ASCII not in text

    generations = [sp.attributes for sp in spans
                   if sp.attributes.get("langfuse.observation.type") == "generation"]
    assert len(generations) == 3
    for attrs in generations:
        assert attrs["langfuse.observation.model.name"] == "gpt-4.1-mini-2025-04-14"
        assert json.loads(attrs["langfuse.observation.usage_details"])["total"] == 120
        assert attrs["langfuse.observation.input"] == observability.REDACTED
        assert attrs["langfuse.observation.output"] == observability.REDACTED

    root = next(sp.attributes for sp in spans if sp.name == "ticket-analysis")
    expected_ref = observability.hash_ticket_id(TICKET.ticket_id)
    assert root[f"langfuse.trace.metadata.{observability.TICKET_REF_KEY}"] == expected_ref
    assert set(root["langfuse.trace.tags"]) == {"azure", "email"}
    # Environment und Release wie entschieden: Stufe (Default local) und Commit-SHA
    for sp in spans:
        assert sp.attributes["langfuse.environment"] == "local"
        assert sp.attributes["langfuse.release"] == "abc1234"


@pytest.mark.asyncio
async def test_gegenprobe_capture_content_sendet_inhalte(use_settings, monkeypatch):
    settings = use_settings(_tracing_settings(langfuse_capture_content=True,
                                              langfuse_tracing_environment="production"))
    spans = await _traced_run(monkeypatch, settings)

    assert GUARD_ASCII in _all_attribute_text(spans)
    assert all(sp.attributes["langfuse.environment"] == "production" for sp in spans)


@pytest.mark.asyncio
async def test_ohne_hmac_schluessel_keine_ticket_referenz(use_settings, monkeypatch):
    settings = use_settings(_tracing_settings(ticket_id_hmac_key=""))
    spans = await _traced_run(monkeypatch, settings)

    text = _all_attribute_text(spans)
    assert observability.TICKET_REF_KEY not in text
    assert TICKET.ticket_id not in text


def test_environment_kommt_aus_umgebungsvariable(monkeypatch):
    monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "production")
    assert Settings().langfuse_tracing_environment == "production"


# --- Tags -------------------------------------------------------------------------

@pytest.mark.parametrize("source, tag", [
    ("email", "email"), ("web_form", "web_form"), ("api", "api"), ("eval", "eval"),
    ("Max Mustermann <max@example.com>", "other"), ("", "other"),
])
def test_source_tag_nur_feste_werte(source, tag):
    assert observability.source_tag(source) == tag


# --- hash_ticket_id ---------------------------------------------------------------

def test_hash_ticket_id(use_settings):
    use_settings(_settings(ticket_id_hmac_key="schluessel-a"))
    a1 = observability.hash_ticket_id("EVAL-001")
    a2 = observability.hash_ticket_id("EVAL-001")
    other_id = observability.hash_ticket_id("EVAL-002")

    use_settings(_settings(ticket_id_hmac_key="schluessel-b"))
    b = observability.hash_ticket_id("EVAL-001")

    assert a1 == a2  # deterministisch
    assert a1 != b  # abhängig vom Schlüssel
    assert a1 != other_id
    assert len(a1) == observability.TICKET_REF_LENGTH
    assert "EVAL" not in a1


def test_hash_ticket_id_ohne_schluessel_none(use_settings):
    use_settings(_settings(ticket_id_hmac_key=""))
    assert observability.hash_ticket_id("EVAL-001") is None


# --- Masking-Funktion -------------------------------------------------------------

def _span(attributes):
    return SimpleNamespace(attributes=attributes)


@pytest.mark.parametrize("params", [
    SimpleNamespace(spans={}),
    SimpleNamespace(spans=None),
    SimpleNamespace(),
    SimpleNamespace(spans={"a": _span(None)}),
    SimpleNamespace(spans={"a": _span({})}),
    SimpleNamespace(spans={"a": _span("kein dict")}),
    SimpleNamespace(spans={"a": _span({1: "x", None: "y"})}),
    SimpleNamespace(spans={"a": SimpleNamespace()}),
    SimpleNamespace(spans="kein mapping"),
])
def test_masking_wirft_nicht(params):
    from langfuse.types import MaskOtelSpansResult

    result = observability.mask_otel_spans(params=params)
    assert isinstance(result, MaskOtelSpansResult)


def test_masking_allowlist():
    from langfuse.types import OtelSpanPatch

    attrs = {
        "langfuse.observation.input": "Text",
        "langfuse.observation.output": "Text",
        "langfuse.observation.status_message": "Fehler mit Text",
        "langfuse.observation.metadata.unbekannt": "Text",
        "langfuse.observation.metadata.langgraph_path": "[...]",
        "langfuse.observation.model.name": "gpt-4.1-mini",
        f"langfuse.trace.metadata.{observability.TICKET_REF_KEY}": "0123456789abcdef",
        "langfuse.internal.is_app_root": True,
    }
    result = observability.mask_otel_spans(params=SimpleNamespace(spans={"a": _span(attrs)}))
    patch: OtelSpanPatch = result.span_patches["a"]

    assert set(patch.delete_attributes) == {
        "langfuse.observation.status_message",
        "langfuse.observation.metadata.unbekannt",
        "langfuse.observation.metadata.langgraph_path",
    }
    assert dict(patch.set_attributes) == {
        "langfuse.observation.input": observability.REDACTED,
        "langfuse.observation.output": observability.REDACTED,
    }


# --- Request an Azure bleibt unverändert (kein model=) ----------------------------

@pytest.mark.asyncio
async def test_azure_request_unveraendert(use_settings, monkeypatch):
    use_settings(_settings())
    mock = _AzureMock()
    llm = _azure_llm(monkeypatch, mock)

    await llm.ainvoke("Antworte als JSON.")

    request = mock.requests[0]
    body = json.loads(request.content)
    assert request.url.path == "/openai/deployments/ticket-llm/chat/completions"
    assert body["response_format"] == {"type": "json_object"}
    assert body["temperature"] == 0
    # Kein model= am Client (Entscheidung): Azure wählt das Modell über das Deployment.
    assert body.get("model") is None
