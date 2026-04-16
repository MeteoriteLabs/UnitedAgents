"""Tests for LLM provider normalization.

Per S7 acceptance. Uses recorded fixtures — no live LLM calls.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from heartbeat.llm.provider import LLMProvider, LLMResponse, ToolCall


class TestProviderDetection:
    def test_anthropic(self):
        assert LLMProvider.detect_provider("claude-sonnet-4-5") == "anthropic"
        assert LLMProvider.detect_provider("claude-3-haiku") == "anthropic"
        assert LLMProvider.detect_provider("claude-opus-4-5") == "anthropic"

    def test_openai(self):
        assert LLMProvider.detect_provider("gpt-4o-mini") == "openai"
        assert LLMProvider.detect_provider("gpt-4o") == "openai"
        assert LLMProvider.detect_provider("o1-preview") == "openai"
        assert LLMProvider.detect_provider("o3-mini") == "openai"
        assert LLMProvider.detect_provider("o4-mini") == "openai"

    def test_unknown(self):
        with pytest.raises(ValueError, match="Unknown model prefix"):
            LLMProvider.detect_provider("llama-3")


class TestToolDefNormalization:
    def setup_method(self):
        self.provider = LLMProvider()

    def test_anthropic_tool_format(self):
        tools = [{"name": "search", "description": "Search web", "parameters": {"type": "object", "properties": {"q": {"type": "string"}}}}]
        result = self.provider._normalize_tools_anthropic(tools)
        assert len(result) == 1
        assert result[0]["name"] == "search"
        assert "input_schema" in result[0]
        assert result[0]["input_schema"]["type"] == "object"

    def test_openai_tool_format(self):
        tools = [{"name": "search", "description": "Search web", "parameters": {"type": "object", "properties": {"q": {"type": "string"}}}}]
        result = self.provider._normalize_tools_openai(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "search"
        assert result[0]["function"]["parameters"]["type"] == "object"


class TestToolResultNormalization:
    def setup_method(self):
        self.provider = LLMProvider()

    def test_anthropic_results(self):
        resp = LLMResponse(
            text="",
            tool_calls=[ToolCall(id="tc_1", name="search", arguments={"q": "test"})],
            raw_content=[
                MagicMock(type="tool_use", id="tc_1", name="search", input={"q": "test"}),
            ],
            _provider="anthropic",
        )
        results = ['{"results": []}']
        msgs = self.provider.build_tool_result_messages("anthropic", resp, results)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "assistant"
        assert msgs[1]["role"] == "user"
        assert msgs[1]["content"][0]["type"] == "tool_result"
        assert msgs[1]["content"][0]["tool_use_id"] == "tc_1"

    def test_openai_results(self):
        resp = LLMResponse(
            text="",
            tool_calls=[ToolCall(id="call_1", name="search", arguments={"q": "test"})],
            raw_content=MagicMock(),
            _provider="openai",
        )
        results = ['{"results": []}']
        msgs = self.provider.build_tool_result_messages("openai", resp, results)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["tool_calls"][0]["id"] == "call_1"
        assert msgs[1]["role"] == "tool"
        assert msgs[1]["tool_call_id"] == "call_1"


class TestMultipleToolCalls:
    def setup_method(self):
        self.provider = LLMProvider()

    def test_openai_multiple_results(self):
        resp = LLMResponse(
            text="",
            tool_calls=[
                ToolCall(id="call_1", name="search", arguments={"q": "test1"}),
                ToolCall(id="call_2", name="create_task", arguments={"title": "t"}),
            ],
            raw_content=MagicMock(),
            _provider="openai",
        )
        results = ['result1', 'result2']
        msgs = self.provider.build_tool_result_messages("openai", resp, results)
        # 1 assistant + 2 tool messages
        assert len(msgs) == 3
        assert msgs[1]["tool_call_id"] == "call_1"
        assert msgs[2]["tool_call_id"] == "call_2"
