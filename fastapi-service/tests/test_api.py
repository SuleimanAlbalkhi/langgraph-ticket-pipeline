"""API-Tests mit TestClient; run_graph ist gemockt, der Graph läuft nicht."""
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.graph import orchestrator
from app.main import app
from app.models.ticket import TicketAnalysis

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analyze_returns_graph_result(monkeypatch):
    fake = AsyncMock(return_value=TicketAnalysis(
        ticket_id="T-1", category="technical_support", urgency="high",
        summary="Drucker druckt leere Etiketten.", confidence_score=1.0,
    ))
    monkeypatch.setattr(orchestrator, "run_graph", fake)
    resp = client.post("/analyze", json={"ticket_id": "T-1", "raw_text": "Drucker druckt nur leere Etiketten."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "technical_support"
    assert body["risk_flag"] is False
    fake.assert_awaited_once()


def test_too_short_raw_text_is_rejected():
    resp = client.post("/analyze", json={"ticket_id": "T-2", "raw_text": "kurz"})
    assert resp.status_code == 422
