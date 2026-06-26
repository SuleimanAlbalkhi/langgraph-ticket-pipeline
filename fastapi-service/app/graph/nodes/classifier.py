from __future__ import annotations

from typing import TYPE_CHECKING
from collections import Counter
import asyncio
import logging
import time

from app.config import get_settings
from app.graph.llm_utils import build_json_llm, parse_json_object
from app.graph.prompt_safety import fence_user_input
from app.models.ticket import TicketCategory, UrgencyLevel

if TYPE_CHECKING:
    from app.graph.orchestrator import GraphState

logger = logging.getLogger(__name__)
settings = get_settings()

# Self-Consistency: Anzahl der Klassifizierungs-Läufe pro Ticket.
# Das Mehrheitsvotum bestimmt category + urgency, die Übereinstimmungsrate
# liefert die Confidence. Ersetzt die alte, unzuverlässige LLM-Selbstauskunft.
N_VOTES = 3

# Singleton — temperature > 0 ist hier Voraussetzung:
# bei temperature=0 wären alle N Läufe identisch und die Confidence immer
# trügerisch 1.0. Etwas Streuung lässt echte Unsicherheit erst sichtbar werden.
_llm = build_json_llm(settings.ollama_fast_model, temperature=0.5)


def _build_prompt(raw_text: str) -> str:
    """Baut den Klassifizierungs-Prompt für einen einzelnen Lauf."""
    return f"""Du bist ein Klassifizierungssystem für Backoffice-Tickets im deutschen B2B-Umfeld.

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
{fence_user_input(raw_text)}

JSON-Format:
{{
  "category": "<eine der vier Kategorien>",
  "urgency": "<eine der vier Stufen>"
}}"""


async def _classify_once(prompt: str, run_idx: int) -> tuple[str, str] | None:
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
    except Exception as exc:
        logger.error("[Node 1 - Classifier] Lauf %d: LLM-Fehler: %s", run_idx, exc)
        return None

    data = parse_json_object(response.content)
    if data is None:
        # Bewusst KEIN roher Modell-Output im Log: er ist aus dem Ticket abgeleitet
        # und kann personenbezogene Daten enthalten (DSGVO). Nur die Länge als Hinweis.
        logger.warning("[Node 1 - Classifier] Lauf %d: JSON-Parse fehlgeschlagen | len=%d",
                       run_idx, len(response.content or ""))
        return None

    # Inter-Node-Coercion: halluzinierte Enum-Werte auf Defaults snappen.
    return (
        TicketCategory.coerce(data.get("category")).value,
        UrgencyLevel.coerce(data.get("urgency")).value,
    )


def _majority_vote(votes: list[tuple[str, str]]) -> tuple[str, str, float]:
    """Mehrheitsvotum über die erfolgreichen Läufe — unabhängig für category
    und urgency. Die Confidence ist der Stimmenanteil der Gewinner-Kategorie an
    ALLEN N_VOTES Läufen, sodass fehlgeschlagene Läufe sie bewusst mitsenken."""
    category_votes = Counter(category for category, _ in votes)
    urgency_votes  = Counter(urgency for _, urgency in votes)
    category, category_count = category_votes.most_common(1)[0]
    urgency, _ = urgency_votes.most_common(1)[0]
    confidence = category_count / N_VOTES
    logger.info("[Node 1 - Classifier] Votes | category=%s urgency=%s confidence=%.2f (votes=%s)",
                category, urgency, confidence, dict(category_votes))
    return category, urgency, confidence


def _fallback_state(state: GraphState) -> GraphState:
    """Sicherer Default, wenn KEIN einziger Lauf verwertbar war."""
    return {**state, "category": "unknown", "urgency": "medium", "confidence_score": 0.0}


async def classify_node(state: GraphState) -> GraphState:
    logger.info("[Node 1 - Classifier] START | ticket_id=%s", state["ticket_id"])
    t0 = time.time()

    prompt = _build_prompt(state["raw_text"])

    # Self-Consistency: N Läufe gleichzeitig abfeuern.
    # Auf einer einzelnen GPU serialisiert Ollama sie (queued); auf Produktions-
    # Hardware mit mehreren GPUs laufen sie echt parallel -> nahezu kostenlos.
    results = await asyncio.gather(
        *(_classify_once(prompt, i + 1) for i in range(N_VOTES))
    )
    votes = [result for result in results if result is not None]
    elapsed = time.time() - t0

    # Kein einziger Lauf erfolgreich -> sicherer Fallback
    if not votes:
        logger.warning("[Node 1 - Classifier] alle %d Läufe fehlgeschlagen | %.1fs",
                       N_VOTES, elapsed)
        return _fallback_state(state)

    category, urgency, confidence = _majority_vote(votes)
    logger.info("[Node 1 - Classifier] DONE | category=%s urgency=%s confidence=%.2f | %.1fs",
                category, urgency, confidence, elapsed)

    return {
        **state,
        "category":         category,
        "urgency":          urgency,
        "confidence_score": confidence,
    }
