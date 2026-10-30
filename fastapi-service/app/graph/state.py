from __future__ import annotations

from typing import TypedDict

# Fallback-Zusammenfassungen bei harten Fehlern des Extractors (Timeout / LLM- oder
# Parse-Fehler). Feste Strings, damit Konsumenten (z.B. eval/report.py) sie erkennen.
SUMMARY_TIMEOUT = "Extraktion-Timeout."
SUMMARY_FAILED  = "Extraktion fehlgeschlagen."


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
