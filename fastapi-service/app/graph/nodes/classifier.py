from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter

from app.config import get_settings
from app.graph.llm_utils import LLMFailure, build_json_llm, invoke_json
from app.graph.prompts.classifier import build_prompt
from app.graph.state import GraphState
from app.models.ticket import TicketCategory, UrgencyLevel

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


async def _classify_once(prompt: str, run_idx: int) -> tuple[str, str] | None:
    """Ein einzelner Klassifizierungs-Lauf. Gibt (category, urgency) zurück
    oder None, wenn der Lauf fehlschlägt (Timeout / LLM-Fehler / kaputtes JSON)."""
    data = await invoke_json(_llm, prompt, f"Node 1 - Classifier | Lauf {run_idx}")
    if isinstance(data, LLMFailure):
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

    prompt = build_prompt(state["raw_text"])

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
