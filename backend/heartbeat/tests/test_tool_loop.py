"""Tests for tool loop."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from heartbeat.llm.provider import LLMProvider, LLMResponse, ToolCall
from heartbeat.llm.tool_loop import tool_loop


@pytest.fixture
def mock_provider():
    return MagicMock(spec=LLMProvider)


class TestToolLoop:
    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_finished(self, mock_provider):
        resp = LLMResponse(text="Done!", tool_calls=[], raw_content=None, _provider="openai")
        mock_provider.create_message = AsyncMock(return_value=resp)

        exit_reason, final = await tool_loop(
            provider=mock_provider, model="gpt-4o", system="test",
            messages=[], tools=[], handlers={}, max_iterations=3,
        )
        assert exit_reason == "finished"
        assert final.text == "Done!"

    @pytest.mark.asyncio
    async def test_tool_call_then_finish(self, mock_provider):
        # First call returns tool_call, second returns text
        resp1 = LLMResponse(
            text="",
            tool_calls=[ToolCall(id="c1", name="search", arguments={"q": "test"})],
            raw_content=MagicMock(), _provider="openai",
        )
        resp2 = LLMResponse(text="Final answer", tool_calls=[], raw_content=None, _provider="openai")
        mock_provider.create_message = AsyncMock(side_effect=[resp1, resp2])
        mock_provider.build_tool_result_messages = MagicMock(return_value=[
            {"role": "assistant", "content": None, "tool_calls": []},
            {"role": "tool", "tool_call_id": "c1", "content": "result"},
        ])

        handler = AsyncMock(return_value={"results": []})
        exit_reason, final = await tool_loop(
            provider=mock_provider, model="gpt-4o", system="test",
            messages=[], tools=[], handlers={"search": handler}, max_iterations=5,
        )
        assert exit_reason == "finished"
        assert final.text == "Final answer"
        handler.assert_called_once_with({"q": "test"})

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, mock_provider):
        resp1 = LLMResponse(
            text="",
            tool_calls=[ToolCall(id="c1", name="unknown_tool", arguments={})],
            raw_content=MagicMock(), _provider="openai",
        )
        resp2 = LLMResponse(text="Okay", tool_calls=[], raw_content=None, _provider="openai")
        mock_provider.create_message = AsyncMock(side_effect=[resp1, resp2])
        mock_provider.build_tool_result_messages = MagicMock(return_value=[
            {"role": "assistant", "content": None, "tool_calls": []},
            {"role": "tool", "tool_call_id": "c1", "content": "error"},
        ])

        exit_reason, final = await tool_loop(
            provider=mock_provider, model="gpt-4o", system="test",
            messages=[], tools=[], handlers={}, max_iterations=5,
        )
        assert exit_reason == "finished"

    @pytest.mark.asyncio
    async def test_max_iterations(self, mock_provider):
        resp = LLMResponse(
            text="",
            tool_calls=[ToolCall(id="c1", name="search", arguments={})],
            raw_content=MagicMock(), _provider="openai",
        )
        mock_provider.create_message = AsyncMock(return_value=resp)
        mock_provider.build_tool_result_messages = MagicMock(return_value=[
            {"role": "assistant", "content": None, "tool_calls": []},
            {"role": "tool", "tool_call_id": "c1", "content": "result"},
        ])
        handler = AsyncMock(return_value="ok")

        exit_reason, _ = await tool_loop(
            provider=mock_provider, model="gpt-4o", system="test",
            messages=[], tools=[], handlers={"search": handler}, max_iterations=2,
        )
        assert exit_reason == "max_iterations"
        assert handler.call_count == 2

    @pytest.mark.asyncio
    async def test_handler_exception_caught(self, mock_provider):
        resp1 = LLMResponse(
            text="",
            tool_calls=[ToolCall(id="c1", name="bad_tool", arguments={})],
            raw_content=MagicMock(), _provider="openai",
        )
        resp2 = LLMResponse(text="Recovered", tool_calls=[], raw_content=None, _provider="openai")
        mock_provider.create_message = AsyncMock(side_effect=[resp1, resp2])
        mock_provider.build_tool_result_messages = MagicMock(return_value=[
            {"role": "assistant", "content": None, "tool_calls": []},
            {"role": "tool", "tool_call_id": "c1", "content": "error"},
        ])

        async def bad_handler(args):
            raise ValueError("Something broke!")

        exit_reason, final = await tool_loop(
            provider=mock_provider, model="gpt-4o", system="test",
            messages=[], tools=[], handlers={"bad_tool": bad_handler}, max_iterations=5,
        )
        assert exit_reason == "finished"
        assert final.text == "Recovered"
