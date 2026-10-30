"""Unit-Tests für den Fristen-Regex im Extractor."""
import pytest

from app.graph.nodes.extractor import _apply_deadline_regex, _extract_deadline_regex


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Bitte zahlen Sie bis spätestens 25.06.2026 zurück.", "bis spätestens 25.06.2026"),
        ("Korrektur bitte innerhalb von 14 Tagen.", "innerhalb von 14 Tagen"),
        ("Wenn bis Freitag keine Antwort kommt, melde ich mich erneut.", "bis Freitag"),
        ("Rückruf bitte bis morgen 12 Uhr.", "bis morgen 12 Uhr"),
        ("Wir planen den Wechsel in den nächsten 2-3 Wochen.", "in den nächsten 2-3 Wochen"),
    ],
    ids=["datum", "relativ", "wochentag", "uhrzeit", "naechste"],
)
def test_deadline_patterns(text, expected):
    assert _extract_deadline_regex(text) == expected


def test_no_deadline_returns_none():
    assert _extract_deadline_regex("Der Drucker zeigt Fehler P-112.") is None


def test_llm_deadline_is_not_overwritten():
    extracted = {"deadline": "Ende des Monats", "deadline_mentioned": True}
    result, summary = _apply_deadline_regex(extracted, "Bitte bis Freitag erledigen.", "Zusammenfassung.")
    assert result["deadline"] == "Ende des Monats"
    assert summary == "Zusammenfassung."
