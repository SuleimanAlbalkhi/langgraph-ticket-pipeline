"""LLM-Prompt für risk_guard. Nur Text-Bau — kein LLM-Aufruf, keine Logik."""
from __future__ import annotations

from app.graph.prompt_safety import fence_user_input


def build_prompt(raw_text: str, category: str | None, urgency: str | None) -> str:
    """Baut den Risikobewertungs-Prompt für ein Ticket."""
    return f"""Du bist ein Risikobewertungs-System für Support-Tickets.
Prüfe ob der folgende Text kritische Inhalte enthält.

Text:
{fence_user_input(raw_text)}
Kategorie: {category}
Dringlichkeit: {urgency}

Kritische Inhalte sind: rechtliche Drohungen, Betrugsvorwürfe,
Sicherheitsrisiken, extrem verärgerte Kunden mit Eskalationsabsicht.

Antworte NUR mit diesem JSON-Format:
{{
  "risk_flag": true oder false,
  "risk_reason": "Begründung wenn risk_flag true, sonst null"
}}"""
