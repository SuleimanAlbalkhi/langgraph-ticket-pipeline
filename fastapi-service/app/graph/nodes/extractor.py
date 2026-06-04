from langchain_ollama import ChatOllama
from app.config import get_settings
import json
import logging
import time
import asyncio

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
1. Extrahiere NUR Werte, die WÖRTLICH im Text vorkommen.
2. Wenn ein Wert nicht im Text steht: gib JSON null zurück (NICHT den String "null", NICHT "n/a", NICHT Platzhalter wie "Name oder null").
3. Erfinde KEINE Werte. Halluzinationen sind verboten.
4. Verwechsle nicht: Rechnungsnummer ist KEIN Fehlercode.
5. summary: 1-2 deutsche Sätze, sachlich.

BEISPIEL technical_support:
Text: "Mein Drucker Modell HP-X100 zeigt Error E22 beim Start."
Antwort:
{{"summary": "Drucker HP-X100 zeigt Fehler E22 beim Start.",
  "extracted_data": {{"customer_name": null, "product": "HP-X100", "error_code": "E22", "invoice_number": null, "amount": null, "deadline_mentioned": false}}}}

BEISPIEL billing_dispute:
Text: "Frau Müller hier, ich beanstande Rechnung 2026-99 über 500 EUR, bitte stornieren innerhalb 7 Tagen."
Antwort:
{{"summary": "Frau Müller beanstandet Rechnung 2026-99 über 500 EUR und fordert Stornierung innerhalb 7 Tagen.",
  "extracted_data": {{"customer_name": "Müller", "product": null, "error_code": null, "invoice_number": "2026-99", "amount": "500 EUR", "deadline_mentioned": true}}}}

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
    "deadline_mentioned": <true oder false>
  }}
}}"""

    try:
        response = await asyncio.wait_for(
            _llm.ainvoke(prompt),
            timeout=settings.ollama_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("[Node 2 - Extractor] TIMEOUT nach %.0fs", settings.ollama_timeout)
        return {**state, "summary": "Extraktion-Timeout.", "extracted_data": {}, "retry_count":    retry_count + 1,}
    except Exception as e:
        logger.error("[Node 2 - Extractor] LLM-Fehler nach %.1fs: %s", time.time() - t0, e)
        return {**state, "summary": "Extraktion fehlgeschlagen.", "extracted_data": {}, "retry_count":    retry_count + 1,}

    logger.info("[Node 2 - Extractor] LLM antwortete in %.1fs", time.time() - t0)

    try:
        data = json.loads(response.content)
        logger.info("[Node 2 - Extractor] DONE | summary_len=%d", len(data.get("summary", "")))
        extracted = data.get("extracted_data", {})
        if not isinstance(extracted, dict):
            extracted = {}
        extracted = _clean_extracted_data(extracted)
        return {
            **state,
            "summary":        data.get("summary", "Keine Zusammenfassung verfügbar."),
            "extracted_data": extracted,
            "retry_count":    retry_count + 1,
        }
    except (json.JSONDecodeError, ValueError):
        logger.warning("[Node 2 - Extractor] JSON-Parse fehlgeschlagen")
        return {**state, "summary": "Extraktion fehlgeschlagen.", "extracted_data": {}, "retry_count":    retry_count + 1,}
