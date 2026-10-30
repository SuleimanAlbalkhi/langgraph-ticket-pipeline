"""Listen statt Strings in Extraktionsfeldern dürfen keinen HTTP 500 auslösen."""
from app.graph.postprocess import ground_to_text
from app.models.ticket import ExtractedData, TicketAnalysis

RAW = "Die Rechnungen RE-2026-1001 und RE-2026-1002 sind doppelt abgebucht. Gruß, Ida Brenner"


def test_grounding_keeps_all_list_items_found_in_text():
    result = ground_to_text({"invoice_number": ["RE-2026-1001", "RE-2026-1002"]}, RAW)
    assert result["invoice_number"] == "RE-2026-1001, RE-2026-1002"


def test_grounding_drops_list_items_not_in_text():
    result = ground_to_text({"invoice_number": ["RE-2026-1001", "RE-9999-0000"]}, RAW)
    assert result["invoice_number"] == "RE-2026-1001"
    assert ground_to_text({"error_code": ["E-1", "E-2"]}, RAW)["error_code"] is None


def test_grounding_takes_first_name_from_list():
    assert ground_to_text({"customer_name": ["Ida Brenner", "Max Muster"]}, RAW)["customer_name"] == "Ida Brenner"


def test_egress_joins_list_instead_of_crashing():
    data = ExtractedData(invoice_number=["RE-2026-1001", "RE-2026-1002"], amount=[None, "n/a"])
    assert data.invoice_number == "RE-2026-1001, RE-2026-1002"
    assert data.amount is None
    analysis = TicketAnalysis(ticket_id="T-1", category="billing_dispute", urgency="high", summary="x",
                              extracted_data={"invoice_number": ["RE-2026-1001", "RE-2026-1002"]})
    assert analysis.extracted_data.invoice_number == "RE-2026-1001, RE-2026-1002"
