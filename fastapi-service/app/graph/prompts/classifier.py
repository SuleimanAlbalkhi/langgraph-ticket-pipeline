"""LLM-Prompt für classifier. Nur Text-Bau — kein LLM-Aufruf, keine Logik."""
from __future__ import annotations

from app.graph.prompt_safety import fence_user_input


def build_prompt(raw_text: str) -> str:
    """Baut den Klassifizierungs-Prompt für einen einzelnen Lauf."""
    return f"""Du bist ein Klassifizierungssystem für Backoffice-Tickets im deutschen B2B-Umfeld.

KATEGORIEN:
- technical_support: Etwas funktioniert nicht wie vorgesehen — Defekte, Fehler oder Störungen
                     an Geräten, Software oder Diensten. Auch kleine oder rein optische Fehler,
                     auch wenn der Kunde sie als Frage formuliert.
- billing_dispute:   Der Kunde beanstandet Geld: eine Rechnung, Abbuchung, Gebühr, Mahnung,
                     Gutschrift oder Erstattung ist aus seiner Sicht falsch oder strittig.
- general_inquiry:   Anfragen ohne Defekt und ohne strittigen Betrag — Fragen zu Produkten,
                     Leistungen, Terminen, Unterlagen, Konto- oder Vertragsdaten, Auskunfts-
                     wünsche, Rückmeldungen. Drohungen oder Fristen ändern die Kategorie nicht.
- unknown:           Kein Anliegen eines Kunden an uns — z.B. Bewerbungen, Werbung, Spam oder
                     falsch zugestellte Nachrichten.

DRINGLICHKEITS-REGELN (strikt anwenden):
- critical: Sicherheitsrisiko, Datenverlust, Produktionsausfall, akuter Notfall
- high:     Frist genannt (z.B. "innerhalb von X Tagen"), rechtliche Andeutungen
            ("Anwalt", "Klage", "Einspruch"), Eskalation, Wort "dringend"
- medium:   Normales Anliegen mit Klärungsbedarf
- low:      Reine Information, keine Aktion erwartet

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt. Keine Erklärungen davor oder danach.

TEXT:
{fence_user_input(raw_text)}

JSON-Format:
{{
  "category": "<eine der vier Kategorien>",
  "urgency": "<eine der vier Stufen>"
}}"""
