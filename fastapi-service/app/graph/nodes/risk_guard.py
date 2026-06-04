from langchain_ollama import ChatOllama
from app.config import get_settings
import json
import logging
import time
import asyncio

logger = logging.getLogger(__name__)
settings = get_settings()

RISK_KEYWORDS = [
    "klage", "anwalt", "rechtlich", "betrug",
    "notfall", "eskalation", "unzumutbar", "skandal",
]

# Singleton — einmal beim Import gebaut
_llm = ChatOllama(
    model=settings.ollama_smart_model,
    base_url=settings.ollama_base_url,
    temperature=0,
    format="json",
    timeout=settings.ollama_timeout,
)


async def risk_guard_node(state: dict) -> dict:
    logger.info("[Node 3 - RiskGuard] START | urgency=%s", state["urgency"])
    t0 = time.time()

    text_lower = state["raw_text"].lower()
    keyword_hit = any(keyword in text_lower for keyword in RISK_KEYWORDS)

    if not keyword_hit and state.get("urgency") not in ("high", "critical"):
        logger.info("[Node 3 - RiskGuard] SKIP (kein Keyword, keine hohe Urgency) | %.1fs",
                    time.time() - t0)
        return {**state, "risk_flag": False, "risk_reason": None}

    prompt = f"""Du bist ein Risikobewertungs-System für Support-Tickets.
Prüfe ob der folgende Text kritische Inhalte enthält.

Text: "{state['raw_text']}"
Kategorie: {state['category']}
Dringlichkeit: {state['urgency']}

Kritische Inhalte sind: rechtliche Drohungen, Betrugsvorwürfe,
Sicherheitsrisiken, extrem verärgerte Kunden mit Eskalationsabsicht.

Antworte NUR mit diesem JSON-Format:
{{
  "risk_flag": true oder false,
  "risk_reason": "Begründung wenn risk_flag true, sonst null"
}}"""

    try:
        response = await asyncio.wait_for(
            _llm.ainvoke(prompt),
            timeout=settings.ollama_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("[Node 3 - RiskGuard] TIMEOUT nach %.0fs", settings.ollama_timeout)
        return {**state, "risk_flag": False, "risk_reason": None}
    except Exception as e:
        logger.error("[Node 3 - RiskGuard] LLM-Fehler nach %.1fs: %s", time.time() - t0, e)
        return {**state, "risk_flag": False, "risk_reason": None}

    logger.info("[Node 3 - RiskGuard] LLM antwortete in %.1fs", time.time() - t0)

    try:
        data = json.loads(response.content)
        logger.info("[Node 3 - RiskGuard] DONE | risk_flag=%s", data.get("risk_flag"))
        return {
            **state,
            "risk_flag":   bool(data.get("risk_flag", False)),
            "risk_reason": data.get("risk_reason", None),
        }
    except (json.JSONDecodeError, ValueError):
        logger.warning("[Node 3 - RiskGuard] JSON-Parse fehlgeschlagen")
        return {**state, "risk_flag": False, "risk_reason": None}
