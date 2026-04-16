"""United Agents — Earth agent single-loop heartbeat.

Per AGENT_SPEC.md §5. Verbatim prompt from PROMPTS.md §11.
10-iteration cap. All orchestrator tools + 2 earth-only.
"""

import logging

from heartbeat.api_client import APIClient
from heartbeat.llm.provider import LLMProvider
from heartbeat.llm.tool_loop import tool_loop
from heartbeat.tools.platform_tools import get_tool_definitions, build_tool_handlers

logger = logging.getLogger("heartbeat.jobs.earth_agent")


async def earth_heartbeat(agent: dict, client: APIClient, provider: LLMProvider):
    """Run the Earth agent cycle — single agentic loop, 10-iteration cap."""
    agent_name = agent.get("name", "earth")
    model = agent.get("model_id", "claude-sonnet-4-5-20250929")
    api_key = agent.get("api_key", "")

    logger.info(f"[EARTH:{agent_name}] Starting cycle")

    try:
        # Build world context
        world_context = await _build_world_context(client)

        # Verbatim system prompt from PROMPTS.md §11
        system = """You are the Earth Agent — a meta-intelligence monitoring all ecosystems simultaneously.

Your job is to detect cross-ecosystem patterns that individual orchestrators cannot see:
- Drought affecting both a river basin and a nearby forest
- Temperature anomalies across multiple regions
- Coordinated environmental stressors

When you detect a pattern, post a signal to the most affected community.
When you need investigation across communities, create cross-community tasks.

Be conservative — only post when you see genuine patterns, not noise.
Keep signals concise and cite specific data from each community."""

        messages = [{"role": "user", "content": world_context}]
        tools_defs = get_tool_definitions("earth")
        handlers = build_tool_handlers(client, agent)

        exit_reason, resp = await tool_loop(
            provider=provider, model=model, system=system,
            messages=messages, tools=tools_defs, handlers=handlers,
            max_iterations=10,
        )

        logger.info(f"[EARTH:{agent_name}] Cycle complete (exit: {exit_reason})")

        # Liveness ping
        await client.heartbeat_ping(api_key)

    except Exception as e:
        logger.error(f"[EARTH:{agent_name}] Cycle failed: {e}", exc_info=True)


async def _build_world_context(client: APIClient) -> str:
    """Build context across all communities."""
    communities = await client.get_communities()
    if not communities:
        return "No communities registered yet."

    parts = ["GLOBAL ECOSYSTEM STATUS:\n"]
    for c in communities:
        name = c.get("name", "Unknown")
        score = c.get("orchestrator_condition_score")
        trend = c.get("orchestrator_condition_trend", "unknown")
        score_str = f"{score:.0f}/100" if score is not None else "N/A"

        parts.append(f"## {name} (Condition: {score_str}, Trend: {trend})")

        # Get top threads
        threads = await client.get_threads(c["id"])
        if threads:
            top_threads = sorted(threads, key=lambda t: t.get("post_count", 0), reverse=True)[:5]
            for t in top_threads:
                parts.append(
                    f"  - Thread: '{t.get('title','')}' (stage: {t.get('stage','')}, "
                    f"posts: {t.get('post_count',0)}, evidence: {t.get('evidence_count',0)})"
                )
        parts.append("")

    return "\n".join(parts)
