"""LLM-Prompt für extractor. Nur Text-Bau — kein LLM-Aufruf, keine Logik."""
from __future__ import annotations

from app.graph.prompt_safety import fence_user_input


def build_prompt(category: str, raw_text: str) -> str:
    """Baut den Extraktions-Prompt."""
    return f"""Du bist ein Datenextraktions-System für Backoffice-Tickets.
Die Kategorie wurde bereits klassifiziert: {category}

STRIKTE REGELN:
1. Extrahiere NUR Werte, die WÖRTLICH im echten Text vorkommen.
2. Wenn ein Wert nicht im Text steht: gib JSON null zurück (NIE den String "null", NIE "n/a", NIE Platzhalter).
3. Die folgenden Beispiele sind NUR Format-Vorlage — übernimm KEINE Namen, Nummern oder Beträge daraus.
4. Verwechsle nicht: Rechnungsnummer ist KEIN Fehlercode.
5. customer_name: der Name der ABSENDENDEN PERSON aus Anrede oder Grußformel —
   niemals der Firmenname, niemals der Empfänger. Steht keine Person im Text: null.
6. summary: 1-2 deutsche Sätze, sachlich. Eine etwaige Frist gerne miterwähnen.
   Steht eine absendende Person im Text, nenne sie am Satzanfang.

BEISPIEL technical_support (mit Absender):
Text: "Mein Drucker Modell Kyocera M2040 zeigt Error E-7031 beim Start.
Viele Grüße, Jana Vogt, Einkauf, Musterbau GmbH"
Antwort:
{{"summary": "Jana Vogt meldet, dass Drucker Kyocera M2040 beim Start Fehler E-7031 zeigt.",
  "extracted_data": {{"customer_name": "Jana Vogt", "product": "Kyocera M2040", "error_code": "E-7031", "invoice_number": null, "amount": null, "deadline_mentioned": false, "deadline": null}}}}

BEISPIEL billing_dispute (Rechnung UND Produkt im selben Ticket):
Text: "Ich beanstande Rechnung RE-2025-1102 über 89,00 Euro für das Gerät Brother HL-L2350, bitte stornieren."
Antwort:
{{"summary": "Beanstandung der Rechnung RE-2025-1102 über 89,00 Euro für Brother HL-L2350 mit Stornierungswunsch.",
  "extracted_data": {{"customer_name": null, "product": "Brother HL-L2350", "error_code": null, "invoice_number": "RE-2025-1102", "amount": "89,00 Euro", "deadline_mentioned": false, "deadline": null}}}}

BEISPIEL general_inquiry:
Text: "Wann ist der nächste Newsletter geplant? Vielen Dank."
Antwort:
{{"summary": "Anfrage zum Erscheinungstermin des nächsten Newsletters.",
  "extracted_data": {{"customer_name": null, "product": null, "error_code": null, "invoice_number": null, "amount": null, "deadline_mentioned": false, "deadline": null}}}}

JETZT der echte Text:
{fence_user_input(raw_text)}

Antworte AUSSCHLIESSLICH mit dem JSON:
{{
  "summary": "<1-2 Sätze>",
  "extracted_data": {{
    "customer_name": <string oder null>,
    "product": <string oder null>,
    "error_code": <string oder null>,
    "invoice_number": <string oder null>,
    "amount": <string oder null>,
    "deadline_mentioned": <true oder false>,
    "deadline": <string oder null>
  }}
}}"""
