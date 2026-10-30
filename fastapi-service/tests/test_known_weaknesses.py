"""Bekannte Schwächen, als strikte xfail dokumentiert.

Jeder Test prüft das GEWÜNSCHTE Verhalten und schlägt mit dem aktuellen Code fehl.
strict=True: Wird eine Schwäche behoben, wird der Test XPASS und damit rot —
dann den xfail-Marker entfernen.
"""
import pytest

from app.graph import postprocess
from app.graph.nodes import extractor, risk_guard
from app.graph.orchestrator import _route_after_extractor


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="Fristen-Regex kennt 'bis zum <Datum>' nicht")
def test_bis_zum_datum_is_found():
    assert postprocess.extract_deadline_regex("Bitte zahlen Sie bis zum 25.06.2026.") is not None


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="Fallback-Summary ist länger als _MIN_SUMMARY_LEN, Retry greift nie")
@pytest.mark.asyncio
async def test_missing_summary_triggers_retry(monkeypatch, make_llm):
    monkeypatch.setattr(extractor, "_llm", make_llm('{"extracted_data": {}}'))
    state = {"category": "general_inquiry", "raw_text": "Wann haben Sie geöffnet?", "retry_count": 0}
    result = await extractor.extract_node(state)
    assert _route_after_extractor(result) == "extractor"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="'Verbraucherzentrale' ist kein Keyword; bei urgency medium wird das LLM übersprungen")
@pytest.mark.asyncio
async def test_verbraucherzentrale_reaches_risk_llm(monkeypatch, make_llm):
    llm = make_llm('{"risk_flag": true, "risk_reason": "Drohung mit Verbraucherzentrale"}')
    monkeypatch.setattr(risk_guard, "_llm", llm)
    state = {"raw_text": "Ich gehe zur Verbraucherzentrale.", "category": "billing_dispute", "urgency": "medium"}
    result = await risk_guard.risk_guard_node(state)
    llm.ainvoke.assert_awaited_once()
    assert result["risk_flag"] is True
