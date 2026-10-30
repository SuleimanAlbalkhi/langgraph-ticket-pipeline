"""Unit-Tests für das Self-Consistency-Mehrheitsvotum."""
import pytest

from app.graph.nodes.classifier import _majority_vote


def test_unanimous_vote_gives_full_confidence():
    votes = [("billing_dispute", "high")] * 3
    assert _majority_vote(votes) == ("billing_dispute", "high", 1.0)


def test_two_of_three_gives_067():
    votes = [("billing_dispute", "high"), ("billing_dispute", "medium"), ("general_inquiry", "medium")]
    category, urgency, confidence = _majority_vote(votes)
    assert category == "billing_dispute"
    assert urgency == "medium"
    assert confidence == pytest.approx(0.67, abs=0.01)


def test_failed_runs_lower_confidence():
    # Nur 1 von 3 Läufen erfolgreich: Fehlläufe senken die Confidence mit.
    category, _, confidence = _majority_vote([("technical_support", "low")])
    assert category == "technical_support"
    assert confidence == pytest.approx(0.33, abs=0.01)
