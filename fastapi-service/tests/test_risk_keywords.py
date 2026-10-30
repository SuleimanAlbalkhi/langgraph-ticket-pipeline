"""Unit-Tests für den Keyword-Vorfilter des Risk-Guards."""
import pytest

from app.graph.nodes.risk_guard import has_risk_keyword


@pytest.mark.parametrize(
    "text",
    [
        "Mein Anwalt ist informiert.",
        "Ich habe einen Rechtsanwalt eingeschaltet.",       # Kompositum
        "Wir reichen KLAGE ein.",
        "Wir prüfen eine Sammelklage.",                     # Kompositum
        "Das ist Betrug.",
        "Wir leiten rechtliche Schritte ein.",
    ],
)
def test_threats_are_detected(text):
    assert has_risk_keyword(text)


@pytest.mark.parametrize(
    "text",
    [
        "Ich beklage mich über den Service.",              # war bekannte Schwäche
        "Das ist einfach unzumutbar!",                      # Ärger, keine Drohung
        "Ein Skandal, wie lange das dauert.",
        "Bitte prüfen Sie die Rechnung.",
    ],
)
def test_anger_without_threat_is_no_keyword(text):
    assert not has_risk_keyword(text)
