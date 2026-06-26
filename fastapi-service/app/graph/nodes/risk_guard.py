from __future__ import annotations

from typing import TYPE_CHECKING
import asyncio
import logging
import time

from app.config import get_settings
from app.graph.llm_utils import build_json_llm, parse_json_object
from app.graph.prompt_safety import fence_user_input

if TYPE_CHECKING:
    from app.graph.orchestrator import GraphState

logger = logging.getLogger(__name__)
settings = get_settings()

RISK_KEYWORDS = (
    "klage", "anwalt", "rechtlich", "betrug",
    "notfall", "eskalation", "unzumutbar", "skandal",
)

# Singleton — einmal beim Import gebaut
_llm = build_json_llm(settings.ollama_smart_model, temperature=0)


def _keyword_floor(state: GraphState, keyword_hit: bool) -> GraphState:
    """Fail-safe-Fallback: Steht ein hartes Risiko-Keyword im Text, wird auch
    dann eskaliert, wenn der LLM-Call scheitert (Timeout/Fehler/kaputtes JSON).
    Das deterministische Signal darf nicht durch ein LLM-Problem verloren gehen."""
    return {
        **state,
        "risk_flag":   keyword_hit,
        "risk_reason": "Risiko-Schlüsselwort im Text erkannt." if keyword_hit else None,
    }


def _build_prompt(state: GraphState) -> str:
    """Baut den Risikobewertungs-Prompt für ein Ticket."""
    return f"""Du bist ein Risikobewertungs-System für Support-Tickets.
Prüfe ob der folgende Text kritische Inhalte enthält.

Text:
{fence_user_input(state['raw_text'])}
Kategorie: {state['category']}
Dringlichkeit: {state['urgency']}

Kritische Inhalte sind: rechtliche Drohungen, Betrugsvorwürfe,
Sicherheitsrisiken, extrem verärgerte Kunden mit Eskalationsabsicht.

Antworte NUR mit diesem JSON-Format:
{{
  "risk_flag": true oder false,
  "risk_reason": "Begründung wenn risk_flag true, sonst null"
}}"""


def _merge_risk(data: dict, keyword_hit: bool) -> tuple[bool, str | None]:
    """Keyword-Floor: das deterministische Keyword-Signal setzt eine Untergrenze.
    Der LLM kann nur zusätzlich eskalieren, ein "false" aber nicht überstimmen,
    wenn ein hartes Risiko-Keyword im Text steht (schützt vor Modell-Fehlern und
    Prompt-Injection im Ticket-Text)."""
    llm_flag = bool(data.get("risk_flag", False))
    risk_flag = llm_flag or keyword_hit
    risk_reason = data.get("risk_reason")
    if risk_flag and not risk_reason:
        risk_reason = ("Risiko-Schlüsselwort im Text erkannt." if keyword_hit
                       else "Als kritisch eingestuft.")
    logger.info("[Node 3 - RiskGuard] DONE | risk_flag=%s (llm=%s, keyword=%s)",
                risk_flag, llm_flag, keyword_hit)
    return risk_flag, risk_reason


async def risk_guard_node(state: GraphState) -> GraphState:
    logger.info("[Node 3 - RiskGuard] START | urgency=%s", state["urgency"])
    t0 = time.time()

    text_lower = state["raw_text"].lower()
    keyword_hit = any(keyword in text_lower for keyword in RISK_KEYWORDS)

    # Kosten-Hotpath: der teure LLM-Call feuert nur bei Keyword-Treffer ODER
    # hoher/kritischer Urgency. Routine-Tickets kürzen direkt ab.
    if not keyword_hit and state.get("urgency") not in ("high", "critical"):
        logger.info("[Node 3 - RiskGuard] SKIP (kein Keyword, keine hohe Urgency) | %.1fs",
                    time.time() - t0)
        return {**state, "risk_flag": False, "risk_reason": None}

    try:
        response = await asyncio.wait_for(
            _llm.ainvoke(_build_prompt(state)),
            timeout=settings.ollama_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("[Node 3 - RiskGuard] TIMEOUT nach %.0fs", settings.ollama_timeout)
        return _keyword_floor(state, keyword_hit)
    except Exception as exc:
        logger.error("[Node 3 - RiskGuard] LLM-Fehler nach %.1fs: %s", time.time() - t0, exc)
        return _keyword_floor(state, keyword_hit)

    logger.info("[Node 3 - RiskGuard] LLM antwortete in %.1fs", time.time() - t0)

    data = parse_json_object(response.content)
    if data is None:
        logger.warning("[Node 3 - RiskGuard] JSON-Parse fehlgeschlagen")
        return _keyword_floor(state, keyword_hit)

    risk_flag, risk_reason = _merge_risk(data, keyword_hit)
    return {**state, "risk_flag": risk_flag, "risk_reason": risk_reason}
