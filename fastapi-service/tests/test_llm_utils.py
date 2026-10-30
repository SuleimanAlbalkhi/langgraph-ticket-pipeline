"""Unit-Tests für den gemeinsamen LLM-Aufruf invoke_json."""
import asyncio

import pytest

from app.graph.llm_utils import LLMFailure, invoke_json


@pytest.mark.asyncio
async def test_valid_object_is_returned(make_llm):
    assert await invoke_json(make_llm('{"risk_flag": true}'), "prompt", "Test") == {"risk_flag": True}


@pytest.mark.asyncio
async def test_timeout(make_llm):
    assert await invoke_json(make_llm(side_effect=asyncio.TimeoutError), "prompt", "Test") is LLMFailure.TIMEOUT


@pytest.mark.asyncio
async def test_llm_exception_is_swallowed(make_llm):
    assert await invoke_json(make_llm(side_effect=ConnectionError("down")), "prompt", "Test") is LLMFailure.ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["kein json", "[1, 2]", None], ids=["broken", "list", "none"])
async def test_unparseable_content(make_llm, content):
    assert await invoke_json(make_llm(content), "prompt", "Test") is LLMFailure.PARSE
