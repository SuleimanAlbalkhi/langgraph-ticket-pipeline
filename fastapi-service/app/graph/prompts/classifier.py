"""LLM-Prompt für classifier. Nur Text-Bau — kein LLM-Aufruf, keine Logik."""
from __future__ import annotations

from app.graph.prompt_safety import fence_user_input


def build_prompt(raw_text: str) -> str:
    """Baut den Klassifizierungs-Prompt für einen einzelnen Lauf."""
    return f"""Du bist ein Klassifizierungssystem für Backoffice-Tickets im deutschen B2B-Umfeld.

KATEGORIEN:
- technical_support: Defekte, Fehler, Störungen an Geräten oder Software
- billing_dispute:   Rechnungen, Mahnungen, Erstattungen, Zahlungen
- general_inquiry:   Allgemeine Fragen, Informationsanfragen
- unknown:           Wenn keine Kategorie klar zutrifft

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
