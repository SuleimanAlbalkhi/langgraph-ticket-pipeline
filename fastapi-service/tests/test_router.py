"""Unit-Tests für die Retry-Entscheidung nach dem Extractor."""
from app.graph.orchestrator import MAX_RETRIES, _extraction_is_empty, _route_after_extractor
from app.graph.state import SUMMARY_TIMEOUT

EMPTY = {"customer_name": None, "invoice_number": None, "deadline_mentioned": False}
LONG_SUMMARY = "Kunde meldet einen Druckerfehler beim Start."


def test_hard_failure_skips_retry():
    state = {"summary": SUMMARY_TIMEOUT, "extracted_data": {}, "retry_count": 1}
    assert _route_after_extractor(state) == "risk_guard"


def test_max_retries_goes_to_risk_guard():
    state = {"summary": "kurz", "extracted_data": EMPTY, "retry_count": MAX_RETRIES}
    assert _route_after_extractor(state) == "risk_guard"


def test_empty_extraction_triggers_retry():
    state = {"summary": "kurz", "extracted_data": EMPTY, "retry_count": 1}
    assert _route_after_extractor(state) == "extractor"


def test_ok_extraction_goes_to_risk_guard():
    state = {"summary": LONG_SUMMARY, "extracted_data": {"error_code": "P-112"}, "retry_count": 1}
    assert _route_after_extractor(state) == "risk_guard"


def test_extraction_is_empty_requires_null_values_and_short_summary():
    assert _extraction_is_empty(EMPTY, "kurz") is True
    assert _extraction_is_empty(EMPTY, LONG_SUMMARY) is False
    assert _extraction_is_empty({"customer_name": "Tobias Reinholz"}, "kurz") is False


def test_zero_value_does_not_count_as_empty():
    # 0 == False in Python — darf trotzdem nicht als "leer" zählen.
    assert _extraction_is_empty({"amount": 0}, "kurz") is False
