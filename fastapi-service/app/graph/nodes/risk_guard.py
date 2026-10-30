from __future__ import annotations

import logging
import re
import time

from app.config import get_settings
from app.graph.llm_utils import LLMFailure, build_json_llm, invoke_json
from app.graph.prompts.risk_guard import build_prompt
from app.graph.state import GraphState

logger = logging.getLogger(__name__)
settings = get_settings()

# Harte Risiko-Keywords = Drohungen/Rechtsbezug, keine Ärger-Wörter: "unzumutbar" und
# "skandal" wurden entfernt (Eval: nur Fehlalarme, z.B. EVAL-027). Teilstring-Match
# bleibt bewusst, damit Komposita wie "Rechtsanwalt" oder "Sammelklage" treffen.
RISK_KEYWORDS = (
    "klage", "anwalt", "rechtlich", "betrug",
    "notfall", "eskalation",
)

# "klage" nicht in "beklagen"/"Beklagte" — der einzige häufige Fehltreffer des Teilstrings.
_KEYWORD_PATTERN = re.compile(
    "|".join(r"(?<!be)klage" if kw == "klage" else re.escape(kw) for kw in RISK_KEYWORDS),
    re.IGNORECASE,
)


def has_risk_keyword(text: str) -> bool:
    return _KEYWORD_PATTERN.search(text) is not None

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

    keyword_hit = has_risk_keyword(state["raw_text"])

    # Kosten-Hotpath: der teure LLM-Call feuert nur bei Keyword-Treffer ODER
    # hoher/kritischer Urgency. Routine-Tickets kürzen direkt ab.
    if not keyword_hit and state.get("urgency") not in ("high", "critical"):
        logger.info("[Node 3 - RiskGuard] SKIP (kein Keyword, keine hohe Urgency) | %.1fs",
                    time.time() - t0)
        return {**state, "risk_flag": False, "risk_reason": None}

    prompt = build_prompt(state["raw_text"], state["category"], state["urgency"])
    data = await invoke_json(_llm, prompt, "Node 3 - RiskGuard")
    if isinstance(data, LLMFailure):
        return _keyword_floor(state, keyword_hit)

    risk_flag, risk_reason = _merge_risk(data, keyword_hit)
    return {**state, "risk_flag": risk_flag, "risk_reason": risk_reason}
