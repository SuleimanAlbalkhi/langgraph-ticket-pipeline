from __future__ import annotations

import logging

from app.config import get_settings
from app.graph.llm_utils import LLMFailure, build_json_llm, invoke_json
from app.graph.postprocess import apply_deadline_regex, clean_extracted_data, ground_to_text
from app.graph.prompts.extractor import build_prompt
from app.graph.state import SUMMARY_FAILED, SUMMARY_TIMEOUT, GraphState

logger = logging.getLogger(__name__)
settings = get_settings()

# Singleton — einmal beim Import gebaut
_llm = build_json_llm(settings.ollama_fast_model, temperature=0)


def _parse_response(data: dict) -> tuple[str, dict]:
    """Mappt die LLM-Antwort defensiv auf (summary, extracted_data).
    Kleine LLMs liefern summary gelegentlich als Zahl/null — daher wird sie
    zwingend zu einem nicht-leeren str normalisiert."""
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = "Keine Zusammenfassung verfügbar."

    extracted = data.get("extracted_data")
    if not isinstance(extracted, dict):
        extracted = {}

    return summary, clean_extracted_data(extracted)


def _failure_state(state: GraphState, summary: str) -> GraphState:
    """Einheitlicher Fehler-State für Timeout / LLM-Fehler / Parse-Fehler."""
    return {**state, "summary": summary, "extracted_data": {}}


async def extract_node(state: GraphState) -> GraphState:
    logger.info("[Node 2 - Extractor] START | category=%s", state["category"])

    prompt = build_prompt(state["category"], state["raw_text"])
    data = await invoke_json(_llm, prompt, "Node 2 - Extractor")
    if data is LLMFailure.TIMEOUT:
        return _failure_state(state, SUMMARY_TIMEOUT)
    if isinstance(data, LLMFailure):
        return _failure_state(state, SUMMARY_FAILED)

    summary, extracted = _parse_response(data)
    extracted = ground_to_text(extracted, state["raw_text"])
    extracted, summary = apply_deadline_regex(extracted, state["raw_text"], summary)
    logger.info("[Node 2 - Extractor] DONE | summary_len=%d", len(summary))

    return {
        **state,
        "summary":        summary,
        "extracted_data": extracted,
    }
