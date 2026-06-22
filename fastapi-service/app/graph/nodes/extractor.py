from langchain_ollama import ChatOllama
from app.config import get_settings
import json
import logging
import time
import asyncio
import re

logger = logging.getLogger(__name__)
settings = get_settings()

# String-Werte die in echtes None überführt werden sollen
_NULL_LIKE = {"null", "none", "n/a", "na", "-", "", "kein", "keiner", "unbekannt"}


def _normalize_value(value):
    """LLMs liefern manchmal 'null' als String oder Platzhalter-Texte zurück.
    Diese Funktion normalisiert sie zu echtem None."""
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip().lower() in _NULL_LIKE:
            return None
        # Platzhalter wie "Name oder null" filtern
        if " oder null" in value.lower():
            return None
    return value


# Regex-Patterns für Fristen (LLM-Output wird damit angereichert)
_DEADLINE_PATTERNS = [
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
]


def _extract_deadline_regex(text: str) -> str | None:
    """Sucht via Regex nach typischen Fristen im Text — als Fallback zum LLM."""
    for pattern in _DEADLINE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def _clean_extracted_data(data: dict) -> dict:
    """Wendet _normalize_value auf alle Werte außer Booleans an."""
    cleaned = {}
    for key, value in data.items():
        if isinstance(value, bool):
            cleaned[key] = value
        else:
            cleaned[key] = _normalize_value(value)
    return cleaned

# Singleton — einmal beim Import gebaut
_llm = ChatOllama(
    model=settings.ollama_fast_model,
    base_url=settings.ollama_base_url,
    temperature=0,
    format="json",
    timeout=settings.ollama_timeout,
)


async def extract_node(state: dict) -> dict:
    logger.info("[Node 2 - Extractor] START | category=%s", state["category"])
    t0 = time.time()
    retry_count = state.get("retry_count", 0)
    is_retry = retry_count > 0

    retry_hint = ""
    if is_retry:
        retry_hint = (
            "\n\nWICHTIG (Retry-Versuch): Der vorherige Extraktions-Versuch hat "
            "nichts Verwertbares geliefert. Lies den Text JETZT besonders genau. "
            "Suche auch nach indirekten Hinweisen (z.B. Modellnamen in Klammern, "
            "Beträge in Zahlenform, Namen am Ende der Nachricht).\n"
        )
        logger.info("[Node 2 - Extractor] RETRY #%d", retry_count)

    prompt = f"""Du bist ein Datenextraktions-System für Backoffice-Tickets.
Die Kategorie wurde bereits klassifiziert: {state['category']}

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
\"\"\"{state['raw_text']}\"\"\"

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

    try:
        response = await asyncio.wait_for(
            _llm.ainvoke(prompt),
            timeout=settings.ollama_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("[Node 2 - Extractor] TIMEOUT nach %.0fs", settings.ollama_timeout)
        return {**state, "summary": "Extraktion-Timeout.", "extracted_data": {}, "retry_count": retry_count + 1,}
    except Exception as e:
        logger.error("[Node 2 - Extractor] LLM-Fehler nach %.1fs: %s", time.time() - t0, e)
        return {**state, "summary": "Extraktion fehlgeschlagen.", "extracted_data": {}, "retry_count": retry_count + 1,}

    logger.info("[Node 2 - Extractor] LLM antwortete in %.1fs", time.time() - t0)

    try:
        data = json.loads(response.content)
        logger.info("[Node 2 - Extractor] DONE | summary_len=%d", len(data.get("summary", "")))
        extracted = data.get("extracted_data", {})
        if not isinstance(extracted, dict):
            extracted = {}
        extracted = _clean_extracted_data(extracted)

        # Hybrid Fallback: Regex-Postprocessor für Fristen.
        # Kleine LLMs übersehen deterministische Datums-Patterns häufig —
        # Regex ist hier zuverlässiger als das Modell.
        summary = data.get("summary", "Keine Zusammenfassung verfügbar.")
        if not extracted.get("deadline"):
            regex_deadline = _extract_deadline_regex(state["raw_text"])
            if regex_deadline:
                extracted["deadline"] = regex_deadline
                extracted["deadline_mentioned"] = True
                if regex_deadline.lower() not in summary.lower():
                    summary = f"{summary.rstrip('.')} (Frist: {regex_deadline})."
                logger.info("[Node 2 - Extractor] Regex-Fallback fand Frist: %s", regex_deadline)

        return {
            **state,
            "summary":        summary,
            "extracted_data": extracted,
            "retry_count": retry_count + 1,
        }
    except (json.JSONDecodeError, ValueError):
        logger.warning("[Node 2 - Extractor] JSON-Parse fehlgeschlagen")
        return {**state, "summary": "Extraktion fehlgeschlagen.", "extracted_data": {}, "retry_count": retry_count + 1,}
