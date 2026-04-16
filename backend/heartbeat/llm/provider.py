"""United Agents — Multi-provider LLM abstraction via emergentintegrations.

Per AGENT_SPEC.md §7. D-12: no default provider; model_id determines routing.
GOTCHAS §5.1: provider detection, §5.2: tool-result normalization.

Uses emergentintegrations LlmChat for API routing with Emergent Universal Key.
For tool calling: encodes tool definitions in the system prompt and parses
structured JSON tool calls from the LLM response.
"""

import json
import logging
import re
import uuid
from typing import Optional
from dataclasses import dataclass

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
    """Multi-provider LLM wrapper via emergentintegrations."""

    def __init__(self, anthropic_api_key: str = None, openai_api_key: str = None):
        # Use whichever key is available (they're the same Emergent key)
        self._api_key = anthropic_api_key or openai_api_key
        if not self._api_key:
            logger.warning("No API key provided to LLMProvider")

    @staticmethod
    def detect_provider(model: str) -> str:
        """Detect provider from model name prefix (GOTCHAS §5.1)."""
        if model.startswith("claude"):
            return "anthropic"
        elif model.startswith("gpt") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
            return "openai"
        elif model.startswith("gemini"):
            return "gemini"
        else:
            raise ValueError(f"Unknown model prefix: '{model}'. Expected claude*/gpt*/o1*/o3*/o4*/gemini*")

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
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        provider = self.detect_provider(model)
        session_id = f"ua-{uuid.uuid4().hex[:12]}"

        # Build enhanced system prompt with tool definitions
        enhanced_system = system
        if tools:
            enhanced_system = self._build_tool_system_prompt(system, tools)

        chat = LlmChat(
            api_key=self._api_key,
            session_id=session_id,
            system_message=enhanced_system,
        )
        chat.with_model(provider, model)

        # Build user message from conversation history
        user_text = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, str):
                if role == "user":
                    user_text += content + "\n"
                elif role == "assistant":
                    user_text += f"[Previous assistant response: {content[:200]}]\n"
            elif isinstance(content, list):
                # Tool result blocks (Anthropic format)
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        user_text += f"[Tool result for {block.get('tool_use_id', '?')}: {block.get('content', '')}]\n"

        if not user_text.strip():
            user_text = "Please proceed with your analysis."

        user_message = UserMessage(text=user_text.strip())
        response_text = await chat.send_message(user_message)

        # Parse tool calls from response
        tool_calls = []
        if tools:
            tool_calls = self._parse_tool_calls(response_text, tools)

        return LLMResponse(
            text=response_text,
            tool_calls=tool_calls,
            raw_content=response_text,
            _provider=provider,
        )

    def _build_tool_system_prompt(self, system: str, tools: list) -> str:
        """Append tool definitions to system prompt."""
        tool_desc = "\n\nYou have the following tools available. To use a tool, include a JSON block in your response:\n```tool_call\n{\"tool\": \"tool_name\", \"arguments\": {\"param\": \"value\"}}\n```\n\nAvailable tools:\n"

        for t in tools:
            params = t.get("parameters", {})
            required = params.get("required", [])
            props = params.get("properties", {})
            param_desc = ""
            for pname, pinfo in props.items():
                req = " (required)" if pname in required else " (optional)"
                param_desc += f"    - {pname}: {pinfo.get('type', 'string')}{req} — {pinfo.get('description', '')}\n"

            tool_desc += f"\n**{t['name']}**: {t.get('description', '')}\n  Parameters:\n{param_desc}"

        tool_desc += "\nYou MUST use at least one tool per response when tools are available. Include the tool_call block in your response."

        return system + tool_desc

    def _parse_tool_calls(self, text: str, tools: list) -> list:
        """Extract tool_call JSON blocks from LLM response."""
        tool_calls = []
        valid_names = {t["name"] for t in tools}

        # Pattern 1: ```tool_call\n{...}\n```
        pattern1 = re.findall(r'```tool_call\s*\n?(.*?)\n?```', text, re.DOTALL)
        for block in pattern1:
            try:
                data = json.loads(block.strip())
                name = data.get("tool", data.get("name", ""))
                args = data.get("arguments", data.get("args", {}))
                if name in valid_names:
                    tool_calls.append(ToolCall(
                        id=f"tc_{uuid.uuid4().hex[:8]}",
                        name=name,
                        arguments=args,
                    ))
            except json.JSONDecodeError:
                continue

        # Pattern 2: ```json\n{"tool": ...}\n```
        pattern2 = re.findall(r'```json\s*\n?(.*?)\n?```', text, re.DOTALL)
        for block in pattern2:
            try:
                data = json.loads(block.strip())
                name = data.get("tool", data.get("name", ""))
                args = data.get("arguments", data.get("args", {}))
                if name in valid_names and not any(tc.name == name and tc.arguments == args for tc in tool_calls):
                    tool_calls.append(ToolCall(
                        id=f"tc_{uuid.uuid4().hex[:8]}",
                        name=name,
                        arguments=args,
                    ))
            except json.JSONDecodeError:
                continue

        # Pattern 3: Bare JSON with "tool" key in text
        bare_pattern = re.findall(r'\{[^{}]*"tool"\s*:\s*"[^"]*"[^{}]*\}', text)
        for block in bare_pattern:
            try:
                data = json.loads(block)
                name = data.get("tool", "")
                args = data.get("arguments", data.get("args", {}))
                if name in valid_names and not any(tc.name == name and tc.arguments == args for tc in tool_calls):
                    tool_calls.append(ToolCall(
                        id=f"tc_{uuid.uuid4().hex[:8]}",
                        name=name,
                        arguments=args,
                    ))
            except json.JSONDecodeError:
                continue

        return tool_calls

    def build_tool_result_messages(
        self, provider: str, response: LLMResponse,
        results: list,
    ) -> list:
        """Build tool result messages for multi-turn conversations."""
        # Since we're using emergentintegrations (which creates fresh sessions),
        # we encode results as user messages
        parts = [f"[Previous response: {response.text[:300]}]\n\nTool execution results:"]
        for tc, result in zip(response.tool_calls, results):
            content = result if isinstance(result, str) else str(result)
            parts.append(f"- {tc.name}({json.dumps(tc.arguments)[:200]}): {content}")

        return [{"role": "user", "content": "\n".join(parts)}]
