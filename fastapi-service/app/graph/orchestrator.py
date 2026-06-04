from typing import TypedDict, Optional
import logging
from langgraph.graph import StateGraph, END
from app.models.ticket import TicketInput, TicketAnalysis, TicketCategory, UrgencyLevel

logger = logging.getLogger(__name__)




class GraphState(TypedDict):
    # Input
    ticket_id: str
    raw_text: str
    source: str
    # Node 1 Output
    category: Optional[str]
    urgency: Optional[str]
    # Node 2 Output
    summary: Optional[str]
    extracted_data: Optional[dict]
    confidence_score: Optional[float]
    # Node 3 Output
    risk_flag: Optional[bool]
    risk_reason: Optional[str]
    # Interne Steuerung
    retry_count: int


_compiled_app = None


def _build_app():
    from app.graph.nodes.classifier import classify_node
    from app.graph.nodes.extractor import extract_node
    from app.graph.nodes.risk_guard import risk_guard_node

    # Graph aufbauen
    graph = StateGraph(GraphState)
    graph.add_node("classifier", classify_node)
    graph.add_node("extractor", extract_node)
    graph.add_node("risk_guard", risk_guard_node)

    # Edges: Reihenfolge der Nodes
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


async def run_graph(ticket: TicketInput) -> TicketAnalysis:
    # Initialer State
    initial_state: GraphState = {
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

    final_state = await get_app().ainvoke(initial_state)

    # Defensive Enum-Coercion: Falls ein Node trotz Fallback einen ungültigen
    # Wert geschleust hat, wird hier auf den Default zurückgesetzt — kein Crash.
    try:
        category = TicketCategory(final_state["category"])
    except (ValueError, TypeError):
        category = TicketCategory.UNKNOWN

    try:
        urgency = UrgencyLevel(final_state["urgency"])
    except (ValueError, TypeError):
        urgency = UrgencyLevel.MEDIUM

    return TicketAnalysis(
        ticket_id        = final_state["ticket_id"],
        category         = category,
        urgency          = urgency,
        summary          = final_state["summary"] or "",
        extracted_data   = final_state["extracted_data"] or {},
        confidence_score = final_state["confidence_score"] or 0.0,
        risk_flag        = final_state["risk_flag"] or False,
        risk_reason      = final_state["risk_reason"],
    )

MAX_RETRIES = 2


def _route_after_extractor(state: GraphState) -> str:
    summary = state.get("summary") or ""
    extracted = state.get("extracted_data") or {}
    retry_count = state.get("retry_count", 0)

    hard_failures = {"Extraktion fehlgeschlagen.", "Extraktion-Timeout."}
    if summary in hard_failures:
        logger.info("[Router] decision=risk_guard reason=hard_failure")
        return "risk_guard"

    if retry_count >= MAX_RETRIES:
        logger.info("[Router] decision=risk_guard reason=max_retries (%d)", retry_count)
        return "risk_guard"

    all_null = all(v in (None, False) for v in extracted.values())
    summary_too_short = len(summary) < 20

    logger.info("[Router] check | all_null=%s summary_len=%d retry_count=%d",
                all_null, len(summary), retry_count)

    if all_null and summary_too_short:
        logger.info("[Router] decision=extractor reason=retry_triggered")
        return "extractor"

    logger.info("[Router] decision=risk_guard reason=ok")
    return "risk_guard"