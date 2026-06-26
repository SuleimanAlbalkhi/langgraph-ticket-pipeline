from __future__ import annotations

from typing import TYPE_CHECKING
import asyncio
import json
import logging
import re
import time

from langchain_ollama import ChatOllama

from app.config import get_settings
from app.graph.prompt_safety import fence_user_input
from app.models.ticket import _NULL_LIKE

if TYPE_CHECKING:
    from app.graph.orchestrator import GraphState

logger = logging.getLogger(__name__)
settings = get_settings()

# Fallback-Zusammenfassungen bei harten Fehlern. Als Konstanten exportiert, weil
# der Router (orchestrator._route_after_extractor) sie als Hard-Failure-Signal
# erkennen muss — Single Source of Truth statt duplizierter Magic-Strings.
SUMMARY_TIMEOUT = "Extraktion-Timeout."
SUMMARY_FAILED  = "Extraktion fehlgeschlagen."
HARD_FAILURE_SUMMARIES: frozenset[str] = frozenset({SUMMARY_TIMEOUT, SUMMARY_FAILED})

# Regex-Patterns für Fristen (LLM-Output wird damit angereichert).
# Einmalig kompiliert: spart das erneute Kompilieren bei jedem Ticket.
_DEADLINE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # Konkrete Daten: "bis spätestens 25.06.2026", "bis 25.6.2026"
        r"(?:bis(?:\s+spätestens)?|spätestens|fällig\s+am|deadline:?)\s+(\d{1,2}\.\d{1,2}\.\d{2,4})",
        # Relative Angaben: "innerhalb 14 Tagen", "innerhalb von 7 Werktagen"
        r"(innerhalb\s+(?:von\s+)?\d+\s+(?:Werk)?(?:Tagen?|Wochen|Monaten))",
        # Wochentage: "bis Freitag"
        r"(bis\s+(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag))",
        # Uhrzeit: "bis heute 14:00 Uhr", "bis morgen 12 Uhr"
        r"(bis\s+(?:heute|morgen|übermorgen)(?:\s+\d{1,2}(?::\d{2})?\s*Uhr)?)",
        # In den nächsten X Wochen/Tagen
        r"(in\s+den\s+nächsten\s+\d+(?:-\d+)?\s+(?:Tagen?|Wochen|Monaten))",
    )
)

# Singleton — einmal beim Import gebaut
_llm = ChatOllama(
    model=settings.ollama_fast_model,
    base_url=settings.ollama_base_url,
    temperature=0,
    format="json",
    timeout=settings.ollama_timeout,
)


def _normalize_value(value: object) -> object:
    """LLMs liefern manchmal 'null' als String oder Platzhalter-Texte zurück.
    Diese Funktion normalisiert sie zu echtem None."""
    if isinstance(value, str) and value.strip().lower() in _NULL_LIKE:
        return None
    return value


def _clean_extracted_data(data: dict) -> dict:
    """Wendet _normalize_value auf alle Werte außer Booleans an."""
    return {
        key: value if isinstance(value, bool) else _normalize_value(value)
        for key, value in data.items()
    }


def _extract_deadline_regex(text: str) -> str | None:
    """Sucht via Regex nach typischen Fristen im Text — als Fallback zum LLM."""
    for pattern in _DEADLINE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
    return None


def _build_prompt(category: str, raw_text: str, is_retry: bool) -> str:
    """Baut den Extraktions-Prompt. Beim Retry wird ein Hinweis vorangestellt,
    der das Modell zu genauerem Lesen anhält."""
    retry_hint = ""
    if is_retry:
        retry_hint = (
            "\n\nWICHTIG (Retry-Versuch): Der vorherige Extraktions-Versuch hat "
            "nichts Verwertbares geliefert. Lies den Text JETZT besonders genau. "
            "Suche auch nach indirekten Hinweisen (z.B. Modellnamen in Klammern, "
            "Beträge in Zahlenform, Namen am Ende der Nachricht).\n"
        )

    return f"""Du bist ein Datenextraktions-System für Backoffice-Tickets.
Die Kategorie wurde bereits klassifiziert: {category}

STRIKTE REGELN:
1. Extrahiere NUR Werte, die WÖRTLICH im echten Text vorkommen.
2. Wenn ein Wert nicht im Text steht: gib JSON null zurück (NIE den String "null", NIE "n/a", NIE Platzhalter).
3. Die folgenden Beispiele sind NUR Format-Vorlage — übernimm KEINE Namen, Nummern oder Beträge daraus.
4. Verwechsle nicht: Rechnungsnummer ist KEIN Fehlercode.
5. summary: 1-2 deutsche Sätze, sachlich. Eine etwaige Frist gerne miterwähnen.

BEISPIEL technical_support:
Text: "Mein Drucker Modell <PRODUKT> zeigt Error <CODE> beim Start."
Antwort:
{{"summary": "Drucker <PRODUKT> zeigt Fehler <CODE> beim Start.",
  "extracted_data": {{"customer_name": null, "product": "<PRODUKT>", "error_code": "<CODE>", "invoice_number": null, "amount": null, "deadline_mentioned": false, "deadline": null}}}}

BEISPIEL billing_dispute:
Text: "Ich beanstande Rechnung <NUMMER> über <BETRAG>, bitte stornieren."
Antwort:
{{"summary": "Beanstandung der Rechnung <NUMMER> über <BETRAG> mit Stornierungswunsch.",
  "extracted_data": {{"customer_name": null, "product": null, "error_code": null, "invoice_number": "<NUMMER>", "amount": "<BETRAG>", "deadline_mentioned": false, "deadline": null}}}}

BEISPIEL general_inquiry:
Text: "Wann ist der nächste Newsletter geplant? Vielen Dank."
Antwort:
{{"summary": "Anfrage zum Erscheinungstermin des nächsten Newsletters.",
  "extracted_data": {{"customer_name": null, "product": null, "error_code": null, "invoice_number": null, "amount": null, "deadline_mentioned": false, "deadline": null}}}}

{retry_hint}JETZT der echte Text:
{fence_user_input(raw_text)}

Antworte AUSSCHLIESSLICH mit dem JSON:
{{
  "summary": "<1-2 Sätze>",
  "extracted_data": {{
    "customer_name": <string oder null>,
    "product": <string oder null>,
    "error_code": <string oder null>,
    "invoice_number": <string oder null>,
    "amount": <string oder null>,
    "deadline_mentioned": <true oder false>,
    "deadline": <string oder null>
  }}
}}"""


def _parse_response(data: dict) -> tuple[str, dict]:
    """Mappt die LLM-Antwort defensiv auf (summary, extracted_data).
    Kleine LLMs liefern summary gelegentlich als Zahl/null — daher wird sie
    zwingend zu einem nicht-leeren str normalisiert."""
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = "Keine Zusammenfassung verfügbar."

    extracted = data.get("extracted_data")
    if not isinstance(extracted, dict):
        extracted = {}

    return summary, _clean_extracted_data(extracted)


def _apply_deadline_regex(extracted: dict, raw_text: str, summary: str) -> tuple[dict, str]:
    """Hybrid Fallback: Regex-Postprocessor für Fristen. Kleine LLMs übersehen
    deterministische Datums-Patterns häufig — Regex ist hier zuverlässiger.
    Greift nur, wenn der LLM selbst keine deadline gefunden hat."""
    if extracted.get("deadline"):
        return extracted, summary

    regex_deadline = _extract_deadline_regex(raw_text)
    if not regex_deadline:
        return extracted, summary

    extracted["deadline"] = regex_deadline
    extracted["deadline_mentioned"] = True
    if regex_deadline.lower() not in summary.lower():
        summary = f"{summary.rstrip('.')} (Frist: {regex_deadline})."
    logger.info("[Node 2 - Extractor] Regex-Fallback fand Frist: %s", regex_deadline)
    return extracted, summary


def _failure_state(state: GraphState, summary: str, retry_count: int) -> GraphState:
    """Einheitlicher Fehler-State für Timeout / LLM-Fehler / Parse-Fehler.
    retry_count wird erhöht, damit der Router die Retry-Grenze sieht."""
    return {
        **state,
        "summary":        summary,
        "extracted_data": {},
        "retry_count":    retry_count + 1,
    }


async def extract_node(state: GraphState) -> GraphState:
    logger.info("[Node 2 - Extractor] START | category=%s", state["category"])
    t0 = time.time()
    # retry_count ist ein Versuchszähler — wird bei JEDEM Extractor-Lauf erhöht,
    # auch beim ersten. MAX_RETRIES=2 bedeutet also max. 2 Läufe / 1 echter Retry.
    retry_count = state.get("retry_count", 0)
    is_retry = retry_count > 0
    if is_retry:
        logger.info("[Node 2 - Extractor] RETRY #%d", retry_count)

    prompt = _build_prompt(state["category"], state["raw_text"], is_retry)

    try:
        response = await asyncio.wait_for(
            _llm.ainvoke(prompt),
            timeout=settings.ollama_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("[Node 2 - Extractor] TIMEOUT nach %.0fs", settings.ollama_timeout)
        return _failure_state(state, SUMMARY_TIMEOUT, retry_count)
    except Exception as exc:
        logger.error("[Node 2 - Extractor] LLM-Fehler nach %.1fs: %s", time.time() - t0, exc)
        return _failure_state(state, SUMMARY_FAILED, retry_count)

    logger.info("[Node 2 - Extractor] LLM antwortete in %.1fs", time.time() - t0)

    try:
        data = json.loads(response.content)
        if not isinstance(data, dict):
            # format="json" garantiert gültiges JSON, aber kein Objekt.
            raise ValueError("LLM lieferte kein JSON-Objekt")
    except (json.JSONDecodeError, ValueError):
        logger.warning("[Node 2 - Extractor] JSON-Parse fehlgeschlagen")
        return _failure_state(state, SUMMARY_FAILED, retry_count)

    summary, extracted = _parse_response(data)
    extracted, summary = _apply_deadline_regex(extracted, state["raw_text"], summary)
    logger.info("[Node 2 - Extractor] DONE | summary_len=%d", len(summary))

    return {
        **state,
        "summary":        summary,
        "extracted_data": extracted,
        "retry_count":    retry_count + 1,
    }
