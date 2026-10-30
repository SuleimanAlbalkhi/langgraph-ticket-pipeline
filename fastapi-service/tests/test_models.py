"""Unit-Tests für die Pydantic-Modelle und Enum-Coercion."""
from app.models.ticket import ExtractedData, TicketCategory, UrgencyLevel


def test_category_coerce():
    assert TicketCategory.coerce("billing_dispute") is TicketCategory.BILLING_DISPUTE
    assert TicketCategory.coerce("refund") is TicketCategory.UNKNOWN
    assert TicketCategory.coerce(None) is TicketCategory.UNKNOWN


def test_urgency_coerce():
    assert UrgencyLevel.coerce("critical") is UrgencyLevel.CRITICAL
    assert UrgencyLevel.coerce("sehr hoch") is UrgencyLevel.MEDIUM
    assert UrgencyLevel.coerce(None) is UrgencyLevel.MEDIUM


def test_null_like_strings_become_none():
    data = ExtractedData(customer_name="null", product="N/A", error_code=" kein ", deadline="unbekannt")
    assert data.customer_name is None
    assert data.product is None
    assert data.error_code is None
    assert data.deadline is None


def test_numeric_amount_becomes_string():
    assert ExtractedData(amount=89.5).amount == "89.5"


def test_unknown_keys_are_dropped():
    data = ExtractedData.model_validate({"customer_name": "Tobias Reinholz", "kundennummer": "K-1"})
    assert data.customer_name == "Tobias Reinholz"
    assert "kundennummer" not in data.model_dump()
