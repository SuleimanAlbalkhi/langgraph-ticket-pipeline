"""Unit-Tests für ground_to_text — ohne LLM-Aufruf."""
from app.graph.postprocess import ground_to_text


def test_placeholder_is_dropped():
    raw = "Mein Drucker zeigt Fehler E-7031. Viele Grüße, Jana Vogt"
    result = ground_to_text({"customer_name": "<NAME>", "product": "<PRODUKT>"}, raw)
    assert result["customer_name"] is None
    assert result["product"] is None


def test_invented_name_is_dropped():
    raw = "Mein Drucker zeigt Fehler E-7031. Viele Grüße, Jana Vogt"
    result = ground_to_text({"customer_name": "Max Mustermann"}, raw)
    assert result["customer_name"] is None


def test_real_name_from_closing_with_line_break_is_kept():
    raw = "Mein Drucker zeigt Fehler E-7031.\n\nViele Grüße\nJana\nVogt"
    result = ground_to_text({"customer_name": "Jana Vogt"}, raw)
    assert result["customer_name"] == "Jana Vogt"


def test_case_is_ignored():
    raw = "Rechnung re-2025-1102 ist falsch. Gruß, JANA VOGT"
    result = ground_to_text(
        {"customer_name": "Jana Vogt", "invoice_number": "RE-2025-1102"}, raw
    )
    assert result["customer_name"] == "Jana Vogt"
    assert result["invoice_number"] == "RE-2025-1102"


def test_amount_is_not_checked_verbatim():
    raw = "Die Rechnung über 249,90 Euro ist zu hoch."
    result = ground_to_text({"amount": "249,90 €"}, raw)
    assert result["amount"] == "249,90 €"
