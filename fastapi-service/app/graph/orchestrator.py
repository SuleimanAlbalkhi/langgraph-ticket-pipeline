from __future__ import annotations

import logging

from langgraph.graph import StateGraph

from app.graph.state import GraphState
from app.models.ticket import TicketAnalysis, TicketCategory, TicketInput, UrgencyLevel

logger = logging.getLogger(__name__)

_compiled_app = None


def _build_app():
    from app.graph.nodes.classifier import classify_node
    from app.graph.nodes.extractor import extract_node
    from app.graph.nodes.risk_guard import risk_guard_node

    graph = StateGraph(GraphState)
    graph.add_node("classifier", classify_node)
    graph.add_node("extractor", extract_node)
    graph.add_node("risk_guard", risk_guard_node)

    # Edges: lineare Reihenfolge. Die frühere Retry-Schleife nach dem Extractor wurde
    # entfernt — sie hat in über 100 Eval-Läufen kein einziges Mal gegriffen.
    graph.set_entry_point("classifier")
    graph.add_edge("classifier", "extractor")
    graph.add_edge("extractor", "risk_guard")

    return graph.compile()


def get_app():
    """Erstellt das Diagramm einmal und verwendet es für alle Anfragen wieder."""
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
