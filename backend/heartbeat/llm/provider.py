"""United Agents — Multi-provider LLM abstraction.

Per AGENT_SPEC.md §7. D-12: no default provider; model_id determines routing.
GOTCHAS §5.1: provider detection, §5.2: tool-result normalization.
"""

import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("heartbeat.llm.provider")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str
    tool_calls: list  # List[ToolCall]
    raw_content: object
    _provider: str


class LLMProvider:
    """Multi-provider LLM wrapper: Anthropic + OpenAI."""

    def __init__(self, anthropic_api_key: str = None, openai_api_key: str = None):
        self._anthropic_client = None
        self._openai_client = None

        if anthropic_api_key:
            try:
                import anthropic
                self._anthropic_client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.warning("anthropic package not installed")

        if openai_api_key:
            try:
                import openai
                self._openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("openai package not installed")

    @staticmethod
    def detect_provider(model: str) -> str:
        """Detect provider from model name prefix (GOTCHAS §5.1)."""
        if model.startswith("claude"):
            return "anthropic"
        elif model.startswith("gpt") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
            return "openai"
        else:
            raise ValueError(f"Unknown model prefix: '{model}'. Expected claude*/gpt*/o1*/o3*/o4*")

    def _normalize_tools_anthropic(self, tools: list) -> list:
        """Unified tool defs → Anthropic format."""
        result = []
        for t in tools:
            result.append({
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {}),
            })
        return result

    def _normalize_tools_openai(self, tools: list) -> list:
        """Unified tool defs → OpenAI format."""
        result = []
        for t in tools:
            result.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {}),
                },
            })
        return result

    async def create_message(
        self,
        model: str,
        system: str,
        messages: list,
        tools: list = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a message to the appropriate provider and return normalized response."""
        prov = self.detect_provider(model)

        if prov == "anthropic":
            return await self._call_anthropic(model, system, messages, tools, max_tokens, temperature)
        elif prov == "openai":
            return await self._call_openai(model, system, messages, tools, max_tokens, temperature)
        else:
            raise ValueError(f"Unsupported provider: {prov}")

    async def _call_anthropic(self, model, system, messages, tools, max_tokens, temperature):
        if not self._anthropic_client:
            raise RuntimeError("Anthropic client not initialized (no API key?)")

        kwargs = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = self._normalize_tools_anthropic(tools)

        resp = await self._anthropic_client.messages.create(**kwargs)

        # Parse response
        text_parts = []
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                ))

        return LLMResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            raw_content=resp.content,
            _provider="anthropic",
        )

    async def _call_openai(self, model, system, messages, tools, max_tokens, temperature):
        if not self._openai_client:
            raise RuntimeError("OpenAI client not initialized (no API key?)")

        oai_messages = [{"role": "system", "content": system}]
        for m in messages:
            oai_messages.append(m)

        kwargs = {
            "model": model,
            "messages": oai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = self._normalize_tools_openai(tools)

        resp = await self._openai_client.chat.completions.create(**kwargs)

        choice = resp.choices[0]
        text = choice.message.content or ""
        tool_calls = []

        if choice.message.tool_calls:
            import json
            for tc in choice.message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            raw_content=choice.message,
            _provider="openai",
        )

    def build_tool_result_messages(
        self, provider: str, response: LLMResponse,
        results: list,
    ) -> list:
        """Build provider-specific tool result messages (GOTCHAS §5.2)."""
        if provider == "anthropic":
            return self._build_anthropic_tool_results(response, results)
        elif provider == "openai":
            return self._build_openai_tool_results(response, results)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _build_anthropic_tool_results(self, response: LLMResponse, results: list) -> list:
        """Anthropic: assistant turn with raw_content + user turn with tool_result blocks."""
        # Assistant turn (contains the tool_use blocks)
        assistant_msg = {"role": "assistant", "content": response.raw_content}

        # Tool result turn
        tool_result_blocks = []
        for tc, result in zip(response.tool_calls, results):
            content = result if isinstance(result, str) else str(result)
            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": content,
            })

        user_msg = {"role": "user", "content": tool_result_blocks}
        return [assistant_msg, user_msg]

    def _build_openai_tool_results(self, response: LLMResponse, results: list) -> list:
        """OpenAI: assistant message + array of tool messages."""
        import json

        # Assistant turn
        tool_calls_raw = []
        for tc in response.tool_calls:
            tool_calls_raw.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            })

        assistant_msg = {
            "role": "assistant",
            "content": response.text or None,
            "tool_calls": tool_calls_raw,
        }

        # Tool result messages
        tool_msgs = []
        for tc, result in zip(response.tool_calls, results):
            content = result if isinstance(result, str) else str(result)
            tool_msgs.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": content,
            })

        return [assistant_msg] + tool_msgs
