from __future__ import annotations

import asyncio
import json
import logging
import time
from enum import Enum

from langchain_ollama import ChatOllama

from app.config import get_settings

# Gemeinsame LLM-Plumbing für die drei Nodes. Hält die identische Client-Konfiguration
# (base_url, format, timeout), den Aufruf mit Timeout und das JSON-Parsing an EINER
# Stelle — kein Copy-Paste über classifier / extractor / risk_guard.

logger = logging.getLogger(__name__)


class LLMFailure(Enum):
    """Warum ein LLM-Aufruf kein verwertbares JSON-Objekt geliefert hat. Jede Node
    mappt das auf ihren eigenen sicheren Fallback."""
    TIMEOUT = "timeout"
    ERROR   = "error"
    PARSE   = "parse"


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


async def invoke_json(llm: ChatOllama, prompt: str, label: str) -> dict | LLMFailure:
    """Ein LLM-Aufruf mit Timeout und JSON-Parsing. Wirft nie: jeder Fehler wird
    als LLMFailure zurückgegeben. `label` ist das Log-Präfix der Node.
    Bei Parse-Fehlern wird bewusst KEIN roher Modell-Output geloggt: er ist aus dem
    Ticket abgeleitet und kann personenbezogene Daten enthalten (DSGVO)."""
    timeout = get_settings().ollama_timeout
    t0 = time.time()
    try:
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=timeout)
    except TimeoutError:
        logger.error("[%s] TIMEOUT nach %.0fs", label, timeout)
        return LLMFailure.TIMEOUT
    except Exception as exc:  # noqa: BLE001 — jeder LLM-Fehler soll in den sicheren Fallback, nicht in einen 500
        logger.error("[%s] LLM-Fehler nach %.1fs: %s", label, time.time() - t0, exc)
        return LLMFailure.ERROR

    logger.info("[%s] LLM antwortete in %.1fs", label, time.time() - t0)
    data = parse_json_object(response.content)
    if data is None:
        logger.warning("[%s] JSON-Parse fehlgeschlagen | len=%d", label, len(response.content or ""))
        return LLMFailure.PARSE
    return data
