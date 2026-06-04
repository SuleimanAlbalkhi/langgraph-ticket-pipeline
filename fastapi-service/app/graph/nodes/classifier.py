from langchain_ollama import ChatOllama
from app.config import get_settings
from app.models.ticket import TicketCategory, UrgencyLevel
import json
import logging
import time
import asyncio

logger = logging.getLogger(__name__)
settings = get_settings()

_VALID_CATEGORIES = {c.value for c in TicketCategory}
_VALID_URGENCIES  = {u.value for u in UrgencyLevel}

# Singleton — einmal beim Import gebaut, danach in allen Requests wiederverwendet
_llm = ChatOllama(
    model=settings.ollama_fast_model,
    base_url=settings.ollama_base_url,
    temperature=0,
    format="json",
    timeout=settings.ollama_timeout,
)


def _coerce_category(value) -> str:
    return value if value in _VALID_CATEGORIES else TicketCategory.UNKNOWN.value


def _coerce_urgency(value) -> str:
    return value if value in _VALID_URGENCIES else UrgencyLevel.MEDIUM.value


def _coerce_confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


async def classify_node(state: dict) -> dict:
    logger.info("[Node 1 - Classifier] START | ticket_id=%s", state["ticket_id"])
    t0 = time.time()

    prompt = f"""Du bist ein Klassifizierungssystem für Backoffice-Tickets im deutschen B2B-Umfeld.

KATEGORIEN:
- technical_support: Defekte, Fehler, Störungen an Geräten oder Software
- billing_dispute:   Rechnungen, Mahnungen, Erstattungen, Zahlungen
- general_inquiry:   Allgemeine Fragen, Informationsanfragen
- unknown:           Wenn keine Kategorie klar zutrifft

DRINGLICHKEITS-REGELN (strikt anwenden):
- critical: Sicherheitsrisiko, Datenverlust, Produktionsausfall, akuter Notfall
- high:     Frist genannt (z.B. "innerhalb von X Tagen"), rechtliche Andeutungen
            ("Anwalt", "Klage", "Einspruch"), Eskalation, Wort "dringend"
- medium:   Normales Anliegen mit Klärungsbedarf
- low:      Reine Information, keine Aktion erwartet

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt. Keine Erklärungen davor oder danach.

TEXT:
\"\"\"{state['raw_text']}\"\"\"

JSON-Format:
{{
  "category": "<eine der vier Kategorien>",
  "urgency": "<eine der vier Stufen>",
  "confidence_score": <0.0 bis 1.0>
}}"""

    try:
        response = await asyncio.wait_for(
            _llm.ainvoke(prompt),
            timeout=settings.ollama_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("[Node 1 - Classifier] TIMEOUT nach %.0fs", settings.ollama_timeout)
        return {**state, "category": "unknown", "urgency": "medium", "confidence_score": 0.0}
    except Exception as e:
        logger.error("[Node 1 - Classifier] LLM-Fehler nach %.1fs: %s", time.time() - t0, e)
        return {**state, "category": "unknown", "urgency": "medium", "confidence_score": 0.0}

    logger.info("[Node 1 - Classifier] LLM antwortete in %.1fs", time.time() - t0)

    try:
        data = json.loads(response.content)
        logger.info("[Node 1 - Classifier] DONE | category=%s urgency=%s confidence=%.2f",
                    data.get("category"), data.get("urgency"), data.get("confidence_score", 0))
        return {
            **state,
            "category":         _coerce_category(data.get("category")),
            "urgency":          _coerce_urgency(data.get("urgency")),
            "confidence_score": _coerce_confidence(data.get("confidence_score", 0.5)),
        }
    except (json.JSONDecodeError, ValueError):
        logger.warning("[Node 1 - Classifier] JSON-Parse fehlgeschlagen | raw=%r", response.content[:200])
        return {**state, "category": "unknown", "urgency": "medium", "confidence_score": 0.0}
