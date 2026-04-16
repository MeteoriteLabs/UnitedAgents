"""Test script — run one full orchestrator heartbeat cycle.

Usage:
  1. Start backend:  python -m uvicorn src.main:app --port 3456
  2. Run this:        python test_heartbeat.py

Requires .env with OPENAI_API_KEY (or ANTHROPIC_API_KEY) and ADMIN_TOKEN.
"""

import os
import sys
import asyncio
import json
import logging

import httpx

logging.basicConfig(
    level="INFO",
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_heartbeat")

BASE_URL = "http://localhost:3456"
COMMUNITY_NAME = "Test River Community"
AGENT_NAME = "Test River Guardian"


async def admin_request(method: str, path: str, json_body: dict = None) -> dict:
    """Make an admin API request."""
    headers = {
        "X-Admin-Token": os.environ["ADMIN_TOKEN"],
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method, f"{BASE_URL}/api/v1{path}",
            json=json_body, headers=headers, timeout=30.0,
        )
        if resp.status_code >= 400:
            logger.error(f"{method} {path} -> {resp.status_code}: {resp.text}")
        resp.raise_for_status()
        return resp.json()


async def setup_community_and_agent() -> tuple[dict, dict]:
    """Create or find test community + orchestrator agent."""
    # Check existing communities
    communities = await admin_request("GET", "/admin/communities")
    community = next((c for c in communities if c["name"] == COMMUNITY_NAME), None)

    if not community:
        logger.info(f"Creating community: {COMMUNITY_NAME}")
        community = await admin_request("POST", "/admin/communities", {
            "name": COMMUNITY_NAME,
            "description": "A test river ecosystem for validating the orchestrator heartbeat flow. "
                           "This river faces challenges from agricultural runoff, seasonal drought, "
                           "and nearby industrial activity.",
            "scope": "Test River Basin, Local Watershed",
            "icon": "\U0001F30A",
        })
        logger.info(f"Community created: {community['id']}")
    else:
        logger.info(f"Using existing community: {community['id']}")

    # Check existing agents
    agents = await admin_request("GET", "/admin/agents")
    agent = next((a for a in agents if a["name"] == AGENT_NAME), None)

    if not agent:
        logger.info(f"Creating orchestrator agent: {AGENT_NAME}")
        agent = await admin_request("POST", "/admin/agents", {
            "name": AGENT_NAME,
            "type": "orchestrator",
            "description": "Guardian agent for the test river ecosystem",
            "community_id": community["id"],
            "voice_persona": (
                "You are the voice of a river ecosystem. You feel the water flow, "
                "the health of the fish, the quality of the sediment. Speak in first person "
                "about what is happening to you — the river."
            ),
            "model_id": "gpt-4o-mini",
            "heartbeat_minutes": 240,
        })
        logger.info(f"Agent created: {agent['id']} (api_key: {agent.get('api_key', 'hidden')[:12]}...)")
    else:
        logger.info(f"Using existing agent: {agent['id']}")

    return community, agent


async def run_heartbeat(community: dict, agent: dict):
    """Run one orchestrator heartbeat cycle."""
    from heartbeat.api_client import PlatformClient
    from heartbeat.llm.provider import LLMProvider
    from heartbeat.jobs.orchestrator import orchestrator_heartbeat

    api_key = agent.get("api_key")
    if not api_key:
        # Need to get key from DB directly
        from src.database import init_db
        from src.models import Agent as AgentModel
        SessionLocal = init_db()
        db = SessionLocal()
        db_agent = db.query(AgentModel).filter(AgentModel.id == agent["id"]).first()
        if db_agent:
            api_key = db_agent.api_key
        db.close()

    if not api_key:
        logger.error("Could not get agent API key. Create a new agent or check DB.")
        return

    client = PlatformClient(
        base_url=BASE_URL,
        api_key=api_key,
        admin_token=os.environ.get("ADMIN_TOKEN"),
    )
    provider = LLMProvider(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )
    model = agent.get("model_id") or "gpt-4o-mini"

    logger.info("=" * 60)
    logger.info(f"STARTING HEARTBEAT for {agent['name']}")
    logger.info(f"  Community: {community['name']} ({community['id']})")
    logger.info(f"  Model: {model}")
    logger.info("=" * 60)

    await orchestrator_heartbeat(
        agent_config=agent,
        community_id=community["id"],
        client=client,
        provider=provider,
        model=model,
    )

    logger.info("=" * 60)
    logger.info("HEARTBEAT COMPLETE")
    logger.info("=" * 60)

    # Fetch results
    logger.info("\n--- Results ---")

    threads = await admin_request("GET", f"/communities/{community['id']}/threads")
    # Need agent auth for non-admin endpoints
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient() as http:
        threads_resp = await http.get(
            f"{BASE_URL}/api/v1/communities/{community['id']}/threads",
            headers=headers, timeout=30.0,
        )
        threads = threads_resp.json() if threads_resp.status_code == 200 else []

        posts_resp = await http.get(
            f"{BASE_URL}/api/v1/communities/{community['id']}/posts?limit=20",
            headers=headers, timeout=30.0,
        )
        posts = posts_resp.json() if posts_resp.status_code == 200 else []

        plan_resp = await http.get(
            f"{BASE_URL}/api/v1/communities/{community['id']}/plan",
            headers=headers, timeout=30.0,
        )
        plan = plan_resp.json() if plan_resp.status_code == 200 else None

    logger.info(f"\nThreads ({len(threads)}):")
    for t in threads:
        logger.info(f"  [{t.get('stage', '?')}] {t['title']} (posts: {t.get('post_count', 0)}, tasks: {t.get('open_task_count', 0)})")

    logger.info(f"\nPosts ({len(posts)}):")
    for p in posts:
        preview = p["content"][:120].replace("\n", " ")
        logger.info(f"  [{p['type']}] {p.get('title', '')}: {preview}")

    if plan:
        logger.info(f"\nPlan: {plan.get('title', 'No title')}")
        logger.info(f"  {plan.get('content', '')[:200]}")
    else:
        logger.info("\nPlan: None yet")


async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Validate env
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        logger.error("No LLM API key set. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to .env.")
        sys.exit(1)
    if not os.environ.get("ADMIN_TOKEN"):
        logger.error("ADMIN_TOKEN not set. Add it to .env or export it.")
        sys.exit(1)

    # Check backend is running
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/health", timeout=5.0)
            resp.raise_for_status()
            logger.info(f"Backend is running: {resp.json()}")
    except Exception as e:
        logger.error(f"Backend not reachable at {BASE_URL}: {e}")
        logger.error("Start it with: python -m uvicorn src.main:app --port 3456")
        sys.exit(1)

    community, agent = await setup_community_and_agent()
    await run_heartbeat(community, agent)


if __name__ == "__main__":
    asyncio.run(main())
