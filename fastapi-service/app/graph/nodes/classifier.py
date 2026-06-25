from langchain_ollama import ChatOllama
from app.config import get_settings
from app.models.ticket import TicketCategory, UrgencyLevel
import json
import logging
import time
import asyncio
from collections import Counter

logger = logging.getLogger(__name__)
settings = get_settings()

_VALID_CATEGORIES = {c.value for c in TicketCategory}
_VALID_URGENCIES  = {u.value for u in UrgencyLevel}

# Self-Consistency: Anzahl der Klassifizierungs-Läufe pro Ticket.
# Das Mehrheitsvotum bestimmt category + urgency, die Übereinstimmungsrate
# liefert die Confidence. Ersetzt die alte, unzuverlässige LLM-Selbstauskunft.
N_VOTES = 3

# Singleton — temperature > 0 ist hier Voraussetzung, nicht Bug:
# bei temperature=0 wären alle N Läufe identisch und die Confidence immer
# trügerisch 1.0. Etwas Streuung lässt echte Unsicherheit erst sichtbar werden.
_llm = ChatOllama(
    model=settings.ollama_fast_model,
    base_url=settings.ollama_base_url,
    temperature=0.5,
    format="json",
    timeout=settings.ollama_timeout,
)


def _coerce_category(value) -> str:
    return value if value in _VALID_CATEGORIES else TicketCategory.UNKNOWN.value


def _coerce_urgency(value) -> str:
    return value if value in _VALID_URGENCIES else UrgencyLevel.MEDIUM.value


async def _classify_once(prompt: str, run_idx: int):
    """Ein einzelner Klassifizierungs-Lauf. Gibt (category, urgency) zurück
    oder None, wenn der Lauf fehlschlägt (Timeout / kaputtes JSON)."""
    try:
        response = await asyncio.wait_for(
            _llm.ainvoke(prompt),
            timeout=settings.ollama_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("[Node 1 - Classifier] Lauf %d: TIMEOUT", run_idx)
        return None
    except Exception as e:
        logger.error("[Node 1 - Classifier] Lauf %d: LLM-Fehler: %s", run_idx, e)
        return None

    try:
        data = json.loads(response.content)
        return (
            _coerce_category(data.get("category")),
            _coerce_urgency(data.get("urgency")),
        )
    except (json.JSONDecodeError, ValueError):
        logger.warning("[Node 1 - Classifier] Lauf %d: JSON-Parse fehlgeschlagen | raw=%r",
                       run_idx, response.content[:200])
        return None


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
  "urgency": "<eine der vier Stufen>"
}}"""

    # Self-Consistency: N Läufe gleichzeitig abfeuern.
    # Auf einer einzelnen GPU serialisiert Ollama sie (queued); auf Produktions-
    # Hardware mit mehreren GPUs laufen sie echt parallel -> nahezu kostenlos.
    results = await asyncio.gather(
        *[_classify_once(prompt, i + 1) for i in range(N_VOTES)]
    )
    votes = [r for r in results if r is not None]
    elapsed = time.time() - t0

    # Kein einziger Lauf erfolgreich -> sicherer Fallback
    if not votes:
        logger.warning("[Node 1 - Classifier] alle %d Läufe fehlgeschlagen | %.1fs",
                       N_VOTES, elapsed)
        return {**state, "category": "unknown", "urgency": "medium", "confidence_score": 0.0}

    # Mehrheitsvotum — unabhängig für category und urgency
    category_votes = Counter(c for c, _ in votes)
    urgency_votes  = Counter(u for _, u in votes)
    category, category_count = category_votes.most_common(1)[0]
    urgency, _ = urgency_votes.most_common(1)[0]

    # Confidence = Stimmenanteil der Gewinner-Kategorie an ALLEN Läufen.
    # Fehlgeschlagene Läufe senken die Confidence bewusst mit.
    confidence = category_count / N_VOTES

    logger.info("[Node 1 - Classifier] DONE | category=%s urgency=%s confidence=%.2f "
                "(votes=%s) | %.1fs",
                category, urgency, confidence, dict(category_votes), elapsed)

    return {
        **state,
        "category":         category,
        "urgency":          urgency,
        "confidence_score": confidence,
    }
