"""Gemeinsame Test-Helfer. LLM-Aufrufe werden immer gemockt — kein Ollama, kein Netzwerk."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def make_llm():
    """Fabrik für einen Fake-LLM: ainvoke ist ein AsyncMock, dessen Rückgabe wie
    eine LangChain-Message ein .content-Attribut hat."""
    def _make(content: str | None = None, side_effect: object = None) -> MagicMock:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content=content), side_effect=side_effect)
        return llm
    return _make
