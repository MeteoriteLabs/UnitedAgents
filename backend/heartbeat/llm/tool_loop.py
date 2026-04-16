"""United Agents — Tool loop.

Per AGENT_SPEC.md §8. Iterative loop with asyncio.gather on parallel tool calls.
Unknown tool → error string fed back. Handler exception → caught, returned as error string.
"""

import asyncio
import json
import logging
from typing import Callable, Dict, Optional

from heartbeat.llm.provider import LLMProvider, LLMResponse

logger = logging.getLogger("heartbeat.llm.tool_loop")


async def tool_loop(
    provider: LLMProvider,
    model: str,
    system: str,
    messages: list,
    tools: list,
    handlers: Dict[str, Callable],
    max_iterations: int = 5,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> tuple:
    """
    Run the iterative tool loop.

    Returns: (exit_reason, final_response)
        exit_reason: "finished" (no tool calls) or "max_iterations"
    """
    prov_name = LLMProvider.detect_provider(model)
    current_messages = list(messages)

    for i in range(max_iterations):
        logger.debug(f"Tool loop iteration {i+1}/{max_iterations}")

        try:
            resp = await provider.create_message(
                model=model,
                system=system,
                messages=current_messages,
                tools=tools,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            logger.error(f"LLM call failed at iteration {i+1}: {e}")
            return "error", None

        # No tool calls → done
        if not resp.tool_calls:
            logger.debug(f"No tool calls at iteration {i+1} — finished")
            return "finished", resp

        # Execute tool calls in parallel
        logger.debug(f"Executing {len(resp.tool_calls)} tool calls: {[tc.name for tc in resp.tool_calls]}")

        async def _execute_tool(tc):
            handler = handlers.get(tc.name)
            if not handler:
                error_msg = f"Unknown tool: '{tc.name}'. Available: {list(handlers.keys())}"
                logger.warning(error_msg)
                return error_msg

            try:
                result = await handler(tc.arguments)
                if isinstance(result, dict):
                    return json.dumps(result)
                return str(result)
            except Exception as e:
                error_msg = f"Tool '{tc.name}' failed: {str(e)}"
                logger.warning(error_msg)
                return error_msg

        results = await asyncio.gather(*[_execute_tool(tc) for tc in resp.tool_calls])

        # Append assistant turn + tool results to messages (provider-normalized)
        new_messages = provider.build_tool_result_messages(prov_name, resp, results)
        current_messages.extend(new_messages)

    logger.info(f"Tool loop hit max_iterations ({max_iterations})")
    return "max_iterations", resp
