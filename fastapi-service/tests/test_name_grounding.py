"""customer_name: Organisationen verwerfen, Wortgrenzen, snap to text — mit Gegenbeispielen."""
import pytest

from app.graph.postprocess import ground_to_text


def _name(value: str, raw: str) -> str | None:
    return ground_to_text({"customer_name": value}, raw)["customer_name"]


# --- Organisation statt Person -------------------------------------------------

@pytest.mark.parametrize(
    ("value", "raw"),
    [
        ("Einkauf, Röder Maschinenbau GmbH", "Bitte um Angebot.\nMit freundlichen Grüßen\nEinkauf, Röder Maschinenbau GmbH"),
        ("Betriebsrat der Spedition Hollmann", "Ist eine Führung möglich?\nViele Grüße\nBetriebsrat der Spedition Hollmann"),
        ("Buchhaltung", "Rechnung falsch.\nBuchhaltung\nMeyer & Co. KG"),
    ],
)
def test_organisation_is_dropped(value, raw):
    assert _name(value, raw) is None


def test_person_before_department_is_kept():
    raw = "Drucker defekt.\nViele Grüße, Lena Kraus, Einkauf, Muster AG"
    assert _name("Lena Kraus, Einkauf, Muster AG", raw) == "Lena Kraus"


def test_surname_that_looks_like_word_is_kept():
    # Gegenbeispiel: Nachname ohne Organisations-Marker darf nicht verworfen werden.
    assert _name("Tom Teamer", "Gruß, Tom Teamer") == "Tom Teamer"


# --- Wortgrenzen + snap to text --------------------------------------------------

def test_mangled_umlaut_snaps_to_text():
    raw = "Gibt es eine Pressestelle?\nBeste Grüße\nDr. Ulf Grünwald"
    assert _name("Dr. Ulf Grwald", raw) == "Dr. Ulf Grünwald"


def test_truncated_name_snaps_to_full_name():
    raw = "Bitte Kopie mit USt.\nMit freundlichen Grüßen\nDr. Eva Sauerbeck"
    assert _name("Dr. Eva Sauer", raw) == "Dr. Eva Sauerbeck"


def test_exact_match_keeps_llm_spelling():
    assert _name("Eva Lind", "Rechnung falsch. Gruß, EVA LIND") == "Eva Lind"


@pytest.mark.parametrize(
    ("value", "raw"),
    [
        # Gegenbeispiele: erfundener oder fremder Name darf NICHT auf irgendwas schnappen.
        ("Max Mustermann", "Mein Drucker zeigt Fehler E-7031. Viele Grüße, Eva Lind"),
        ("Eva Linder", "Viele Grüße, Anna Lindemann"),
        ("Peter Schmidt", "Bitte melden Sie sich bei Petra Schulze."),
    ],
)
def test_dissimilar_name_is_dropped(value, raw):
    assert _name(value, raw) is None


def test_partial_word_invoice_is_dropped():
    # Wortgrenze gilt auch für andere wörtliche Felder.
    raw = "Rechnung RE-2026-04417 ist falsch."
    assert ground_to_text({"invoice_number": "RE-2026-0441"}, raw)["invoice_number"] is None
    assert ground_to_text({"invoice_number": "RE-2026-04417"}, raw)["invoice_number"] == "RE-2026-04417"
