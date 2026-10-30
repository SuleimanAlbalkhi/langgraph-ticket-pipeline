from __future__ import annotations

from typing import TypedDict

# Fallback-Zusammenfassungen bei harten Fehlern. Hier statt im Extractor, weil
# der Router (orchestrator._route_after_extractor) sie als Hard-Failure-Signal
# erkennen muss — Single Source of Truth ohne Import-Zyklus orchestrator <-> extractor.
SUMMARY_TIMEOUT = "Extraktion-Timeout."
SUMMARY_FAILED  = "Extraktion fehlgeschlagen."
HARD_FAILURE_SUMMARIES: frozenset[str] = frozenset({SUMMARY_TIMEOUT, SUMMARY_FAILED})


class GraphState(TypedDict):
    # Input
    ticket_id: str
    raw_text: str
    source: str
    # Node 1 Output
    category: str | None
    urgency: str | None
    # Node 2 Output
    summary: str | None
    extracted_data: dict | None
    confidence_score: float | None
    # Node 3 Output
    risk_flag: bool | None
    risk_reason: str | None
    # Interne Steuerung
    retry_count: int
