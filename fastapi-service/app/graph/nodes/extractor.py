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


def _failure_state(state: GraphState, summary: str, retry_count: int) -> GraphState:
    """Einheitlicher Fehler-State für Timeout / LLM-Fehler / Parse-Fehler.
    retry_count wird erhöht, damit der Router die Retry-Grenze sieht."""
    return {
        **state,
        "summary":        summary,
        "extracted_data": {},
        "retry_count":    retry_count + 1,
    }


async def extract_node(state: GraphState) -> GraphState:
    logger.info("[Node 2 - Extractor] START | category=%s", state["category"])
    # retry_count ist ein Versuchszähler — wird bei JEDEM Extractor-Lauf erhöht,
    # auch beim ersten. MAX_RETRIES=2 bedeutet also max. 2 Läufe / 1 echter Retry.
    retry_count = state.get("retry_count", 0)
    is_retry = retry_count > 0
    if is_retry:
        logger.info("[Node 2 - Extractor] RETRY #%d", retry_count)

    prompt = build_prompt(state["category"], state["raw_text"], is_retry)
    data = await invoke_json(_llm, prompt, "Node 2 - Extractor")
    if data is LLMFailure.TIMEOUT:
        return _failure_state(state, SUMMARY_TIMEOUT, retry_count)
    if isinstance(data, LLMFailure):
        return _failure_state(state, SUMMARY_FAILED, retry_count)

    summary, extracted = _parse_response(data)
    extracted = ground_to_text(extracted, state["raw_text"])
    extracted, summary = apply_deadline_regex(extracted, state["raw_text"], summary)
    logger.info("[Node 2 - Extractor] DONE | summary_len=%d", len(summary))

    return {
        **state,
        "summary":        summary,
        "extracted_data": extracted,
        "retry_count":    retry_count + 1,
    }
