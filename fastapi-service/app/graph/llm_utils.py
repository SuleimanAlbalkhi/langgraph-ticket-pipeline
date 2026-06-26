from __future__ import annotations

import json

from langchain_ollama import ChatOllama

from app.config import get_settings

# Gemeinsame LLM-Plumbing für die drei Nodes. Hält die identische Client-Konfiguration
# (base_url, format, timeout) und das JSON-Parsing an EINER Stelle — kein Copy-Paste
# über classifier / extractor / risk_guard.


def build_json_llm(model: str, temperature: float) -> ChatOllama:
    """Baut einen ChatOllama-Client mit der projektweiten Standard-Plumbing.
    Nur model + temperature variieren pro Node — Rest kommt aus den Settings."""
    s = get_settings()
    return ChatOllama(
        model=model,
        base_url=s.ollama_base_url,
        temperature=temperature,
        format="json",
        timeout=s.ollama_timeout,
    )


def parse_json_object(content: str | None) -> dict | None:
    """Parst LLM-Output zu einem dict. Gibt None zurück bei kaputtem JSON ODER
    bei Nicht-Objekt (Liste/Skalar) — format='json' garantiert gültiges JSON,
    aber kein Objekt, und ein .get() auf eine Liste würfe sonst AttributeError.

    TypeError wird mitgefangen, falls content wider Erwarten kein str ist (z.B.
    Multimodal-Content als Liste): json.loads würfe dann TypeError statt None."""
    try:
        data = json.loads(content or "")
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None
