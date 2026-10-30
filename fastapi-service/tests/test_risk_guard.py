"""Unit-Tests für den zweistufigen Risk-Guard (Keyword-Vorfilter + LLM)."""
import asyncio

import pytest

from app.graph.nodes import risk_guard


def _state(raw_text: str, urgency: str) -> dict:
    return {"raw_text": raw_text, "category": "billing_dispute", "urgency": urgency}


@pytest.mark.asyncio
async def test_keyword_floor_overrides_llm_false(monkeypatch, make_llm):
    llm = make_llm('{"risk_flag": false, "risk_reason": null}')
    monkeypatch.setattr(risk_guard, "_llm", llm)
    result = await risk_guard.risk_guard_node(_state("Mein Anwalt ist informiert.", "medium"))
    llm.ainvoke.assert_awaited_once()
    assert result["risk_flag"] is True
    assert result["risk_reason"]


@pytest.mark.asyncio
async def test_routine_ticket_skips_llm(monkeypatch, make_llm):
    llm = make_llm('{"risk_flag": true, "risk_reason": "x"}')
    monkeypatch.setattr(risk_guard, "_llm", llm)
    result = await risk_guard.risk_guard_node(_state("Wann haben Sie geöffnet?", "low"))
    llm.ainvoke.assert_not_called()
    assert result["risk_flag"] is False
    assert result["risk_reason"] is None


@pytest.mark.asyncio
async def test_llm_timeout_falls_back_to_keyword_floor(monkeypatch, make_llm):
    llm = make_llm(side_effect=asyncio.TimeoutError)
    monkeypatch.setattr(risk_guard, "_llm", llm)
    result = await risk_guard.risk_guard_node(_state("Wir reichen Klage ein.", "high"))
    llm.ainvoke.assert_awaited_once()
    assert result["risk_flag"] is True
