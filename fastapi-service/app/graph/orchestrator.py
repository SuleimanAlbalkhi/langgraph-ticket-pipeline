from __future__ import annotations

from typing import TypedDict
import logging

from langgraph.graph import StateGraph

from app.graph.nodes.extractor import HARD_FAILURE_SUMMARIES
from app.models.ticket import TicketInput, TicketAnalysis, TicketCategory, UrgencyLevel

logger = logging.getLogger(__name__)

# retry_count ist ein Versuchszähler — MAX_RETRIES=2 erlaubt max. 2 Extractor-
# Läufe (1 echter Retry), bevor der Router zwingend zu risk_guard weitergeht.
MAX_RETRIES = 2

# Eine Extraktion gilt als "leer" und retry-würdig, wenn die summary zu kurz ist.
_MIN_SUMMARY_LEN = 20


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


_compiled_app = None


def _build_app():
    from app.graph.nodes.classifier import classify_node
    from app.graph.nodes.extractor import extract_node
    from app.graph.nodes.risk_guard import risk_guard_node

    graph = StateGraph(GraphState)
    graph.add_node("classifier", classify_node)
    graph.add_node("extractor", extract_node)
    graph.add_node("risk_guard", risk_guard_node)

    # Edges: Reihenfolge der Nodes. Einzige Verzweigung ist die Retry-Schleife
    # nach dem Extractor (_route_after_extractor).
    graph.set_entry_point("classifier")
    graph.add_edge("classifier", "extractor")
    graph.add_conditional_edges(
        "extractor",
        _route_after_extractor,
        {
            "extractor":  "extractor",
            "risk_guard": "risk_guard",
        },
    )

    return graph.compile()


def get_app():
    """Compile the graph once and reuse it across requests."""
    global _compiled_app
    if _compiled_app is None:
        _compiled_app = _build_app()
    return _compiled_app


def _initial_state(ticket: TicketInput) -> GraphState:
    """Baut den Start-State aus dem eingehenden Ticket."""
    return {
        "ticket_id":        ticket.ticket_id,
        "raw_text":         ticket.raw_text,
        "source":           ticket.source,
        "category":         None,
        "urgency":          None,
        "summary":          None,
        "extracted_data":   {},
        "confidence_score": 0.0,
        "risk_flag":        False,
        "risk_reason":      None,
        "retry_count":      0,
    }


async def run_graph(ticket: TicketInput) -> TicketAnalysis:
    final_state = await get_app().ainvoke(_initial_state(ticket))

    # Defensive Enum-Coercion am Egress: Falls ein Node trotz Fallback einen
    # ungültigen Wert geschleust hat, snappt coerce() ihn auf den Default — kein Crash.
    return TicketAnalysis(
        ticket_id        = final_state["ticket_id"],
        category         = TicketCategory.coerce(final_state["category"]),
        urgency          = UrgencyLevel.coerce(final_state["urgency"]),
        summary          = final_state["summary"] or "",
        extracted_data   = final_state["extracted_data"] or {},
        confidence_score = final_state["confidence_score"] or 0.0,
        risk_flag        = final_state["risk_flag"] or False,
        risk_reason      = final_state["risk_reason"],
    )


def _extraction_is_empty(extracted: dict, summary: str) -> bool:
    """Eine Extraktion ist retry-würdig, wenn ALLE Werte leer sind UND die
    summary zu kurz ausfiel. `is None`/`is False` statt `in (None, False)`
    vermeidet, dass 0/0.0 wegen 0 == False fälschlich als "leer" zählt."""
    all_null = all(value is None or value is False for value in extracted.values())
    summary_too_short = len(summary) < _MIN_SUMMARY_LEN
    logger.info("[Router] check | all_null=%s summary_len=%d", all_null, len(summary))
    return all_null and summary_too_short


def _route_after_extractor(state: GraphState) -> str:
    summary = state.get("summary") or ""
    extracted = state.get("extracted_data") or {}
    retry_count = state.get("retry_count", 0)

    # Harte Fehler (Timeout/LLM-Fehler) überspringen den Retry direkt.
    if summary in HARD_FAILURE_SUMMARIES:
        logger.info("[Router] decision=risk_guard reason=hard_failure")
        return "risk_guard"

    if retry_count >= MAX_RETRIES:
        logger.info("[Router] decision=risk_guard reason=max_retries (%d)", retry_count)
        return "risk_guard"

    if _extraction_is_empty(extracted, summary):
        logger.info("[Router] decision=extractor reason=retry_triggered (retry_count=%d)", retry_count)
        return "extractor"

    logger.info("[Router] decision=risk_guard reason=ok")
    return "risk_guard"
