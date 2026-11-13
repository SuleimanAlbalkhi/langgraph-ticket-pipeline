"""Tracing mit Langfuse Cloud (EU).

Ein Trace pro Ticket-Analyse, ein Span pro Node, eine Generation pro LLM-Aufruf. Eingehängt
wird zentral in run_graph() über einen LangChain-Callback; Nodes und invoke_json() wissen
nichts davon.

Standard ist maskiert: Ticketinhalte verlassen Azure nicht (dieselbe DSGVO-Regel wie bei
den Logs). Das SDK wird nur importiert, wenn beide Schlüssel gesetzt sind, damit ein
Betrieb ohne Tracing keinen Langfuse-Code lädt.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from app.config import get_settings

if TYPE_CHECKING:
    from langfuse import Langfuse
    from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult

logger = logging.getLogger(__name__)

# Name des Metadaten-Schlüssels für die gehashte Ticket-ID (Trace- und Span-Metadaten).
TICKET_REF_KEY = "ticket_ref"
# 16 Hex-Zeichen = 64 Bit: reicht zum Wiederfinden eines Tickets, Kollisionen sind bei
# den erwarteten Mengen praktisch ausgeschlossen.
TICKET_REF_LENGTH = 16

REDACTED = "[redacted]"

# ticket.source ist ein freier String vom Absender (n8n reicht body.source durch). Als Tag
# gehen nur diese festen Werte raus, alles andere wird "other": Tags sind nicht maskiert,
# über einen freien Wert könnte ein Absender beliebigen Text nach Langfuse schreiben.
KNOWN_SOURCES = frozenset({"email", "web_form", "api", "eval"})

# Attribute, die Inhalte tragen. Sie werden ersetzt statt gelöscht, damit in Langfuse
# sichtbar bleibt, dass hier etwas war und bewusst maskiert wurde.
_REDACT_ATTRIBUTES = frozenset({
    "langfuse.observation.input",
    "langfuse.observation.output",
    "langfuse.trace.input",
    "langfuse.trace.output",
})

# Allowlist: nur diese Attribute gehen unverändert raus, alles andere wird gelöscht.
# Fail-closed: Bringt ein SDK-Update oder LangGraph ein neues Attribut mit Inhalt mit,
# geht es nicht unbemerkt nach außen. Ermittelt aus einem aufgezeichneten Graph-Lauf
# (langfuse 4.18.0, InMemorySpanExporter). Metadaten kommen in v4 flach an, ein Attribut
# pro Schlüssel ("langfuse.observation.metadata.<key>"), Strings ohne JSON-Kodierung.
_ALLOWED_ATTRIBUTES = frozenset({
    "langfuse.environment",
    "langfuse.release",
    "langfuse.version",
    "langfuse.observation.type",
    "langfuse.observation.level",
    "langfuse.observation.model.name",
    "langfuse.observation.model.parameters",
    "langfuse.observation.usage_details",
    "langfuse.observation.cost_details",
    "langfuse.observation.completion_start_time",
    "langfuse.trace.name",
    "langfuse.trace.tags",
    f"langfuse.trace.metadata.{TICKET_REF_KEY}",
    f"langfuse.observation.metadata.{TICKET_REF_KEY}",
    "langfuse.observation.metadata.langgraph_node",
    "langfuse.observation.metadata.langgraph_step",
    "langfuse.observation.metadata.ls_model_name",
    "langfuse.observation.metadata.ls_model_type",
    "langfuse.observation.metadata.ls_provider",
    "langfuse.observation.metadata.ls_temperature",
})
# Interne Steuerattribute des SDK (z.B. is_app_root), ohne Inhalt.
_ALLOWED_PREFIXES = ("langfuse.internal.",)


def _is_allowed(key: str) -> bool:
    return key in _ALLOWED_ATTRIBUTES or key.startswith(_ALLOWED_PREFIXES)


def _span_patch_values(attributes: Any) -> tuple[list[str], dict[str, str]]:
    """(zu löschende Schlüssel, zu ersetzende Schlüssel) für die Attribute eines Spans.
    Unerwartete Typen gelten als "keine Attribute", statt einen Fehler zu werfen."""
    try:
        keys = [k for k in attributes if isinstance(k, str)] if attributes else []
    except Exception:  # noqa: BLE001 — Masking darf nie werfen, sonst fällt der ganze Batch weg
        keys = []
    delete = [k for k in keys if k not in _REDACT_ATTRIBUTES and not _is_allowed(k)]
    redact = {k: REDACTED for k in keys if k in _REDACT_ATTRIBUTES}
    return delete, redact


def mask_otel_spans(*, params: MaskOtelSpansParams) -> MaskOtelSpansResult:
    """Export-Hook für Langfuse: entfernt alles außer der Allowlist.

    Läuft im Export-Thread des SDK. Wirft er oder liefert er ein ungültiges Ergebnis,
    verwirft Langfuse den ganzen Batch. Deshalb nur einfache, deterministische
    Dict-Operationen, kein Netzwerk, kein Request-Kontext, und Fehler pro Span abfangen."""
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    patches: dict[Any, OtelSpanPatch] = {}
    spans = getattr(params, "spans", None) or {}
    try:
        items = list(spans.items())
    except Exception:  # noqa: BLE001
        items = []
    for identifier, span in items:
        delete, redact = _span_patch_values(getattr(span, "attributes", None))
        if delete or redact:
            patches[identifier] = OtelSpanPatch(delete_attributes=tuple(delete), set_attributes=redact)
    return MaskOtelSpansResult(span_patches=patches)


def _build_client(span_exporter: Any = None) -> Langfuse | None:
    """Baut den Langfuse-Client. `span_exporter` nur für Tests (InMemorySpanExporter).
    Jeder Fehler schaltet Tracing ab, statt die Analyse zu gefährden."""
    s = get_settings()
    if not s.tracing_enabled:
        return None
    try:
        from langfuse import Langfuse

        kwargs: dict[str, Any] = {
            "public_key": s.langfuse_public_key,
            "secret_key": s.langfuse_secret_key,
            "base_url": s.langfuse_base_url,
            "release": s.git_sha,
            "environment": s.langfuse_tracing_environment,
        }
        if not s.langfuse_capture_content:
            kwargs["mask_otel_spans"] = mask_otel_spans
        if span_exporter is not None:
            kwargs["span_exporter"] = span_exporter
        return Langfuse(**kwargs)
    except Exception as exc:  # noqa: BLE001 — Tracing darf nie zu einem HTTP-Fehler führen
        # Nur der Fehlertyp: Die Meldung könnte Konfigurationswerte enthalten.
        logger.error("Tracing aus: Langfuse-Client konnte nicht erstellt werden (%s)", type(exc).__name__)
        return None


@lru_cache
def get_langfuse() -> Langfuse | None:
    """Ein Client pro Prozess; None, wenn Tracing aus ist oder der Aufbau scheiterte."""
    return _build_client()


def get_callbacks() -> list:
    """Callbacks für einen Graph-Lauf. Pro Aufruf ein NEUER Handler: Langfuse warnt vor
    wiederverwendeten Handlern bei nebenläufigen Requests (der Handler hält Run-Zustand)."""
    if get_langfuse() is None:
        return []
    try:
        from langfuse.langchain import CallbackHandler

        return [CallbackHandler(public_key=get_settings().langfuse_public_key)]
    except Exception as exc:  # noqa: BLE001
        logger.error("Tracing für diesen Request aus: Handler-Fehler (%s)", type(exc).__name__)
        return []


def hash_ticket_id(ticket_id: str) -> str | None:
    """Gekürzter HMAC-SHA256 der Ticket-ID für die Trace-Metadaten.

    HMAC statt einfachem Hash: Ticket-IDs sind vorhersagbar (EVAL-001 …), ein einfacher
    Hash ließe sich durch Durchprobieren umkehren. Ohne Schlüssel None, und die Ticket-ID
    wird gar nicht gesendet; bewusst keine Rückfallebene auf Hash oder Klartext."""
    key = get_settings().ticket_id_hmac_key
    if not key:
        return None
    digest = hmac.new(key.encode(), ticket_id.encode(), hashlib.sha256).hexdigest()
    return digest[:TICKET_REF_LENGTH]


def source_tag(source: str) -> str:
    """Quelle des Tickets als Tag, beschränkt auf KNOWN_SOURCES."""
    return source if source in KNOWN_SOURCES else "other"


def log_tracing_status() -> None:
    """Startzeile für den Lifespan. Loggt nie Schlüsselwerte, nur ob sie gesetzt sind."""
    s = get_settings()
    if not s.tracing_enabled:
        logger.info("Tracing: aus (LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY nicht beide gesetzt)")
        return
    logger.info(
        "Tracing: an (%s, Environment %s, Inhalte %s, HMAC-Schlüssel %s)",
        s.langfuse_base_url,
        s.langfuse_tracing_environment,
        "GESENDET" if s.langfuse_capture_content else "maskiert",
        "vorhanden" if s.ticket_id_hmac_key else "fehlt",
    )
    if not s.ticket_id_hmac_key:
        logger.warning("Tracing ohne TICKET_ID_HMAC_KEY: Traces enthalten keine Ticket-Referenz.")


def shutdown_tracing() -> None:
    """Gepufferte Spans beim Beenden senden. Container Apps skaliert auf 0 Replikate,
    ohne Shutdown gingen die letzten Spans verloren. Baut keinen Client, nur um ihn
    gleich wieder zu schließen."""
    if get_langfuse.cache_info().currsize == 0:
        return
    client = get_langfuse()
    if client is None:
        return
    try:
        client.shutdown()
    except Exception as exc:  # noqa: BLE001
        logger.error("Tracing: Shutdown fehlgeschlagen (%s)", type(exc).__name__)
