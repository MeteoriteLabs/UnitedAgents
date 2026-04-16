"""Live orchestrator + worker heartbeat cycle test.

Runs:
1. One orchestrator heartbeat cycle (5 stages) for the Amazon River Basin
2. One worker heartbeat cycle for a worker agent
3. Verifies results appear in the API
"""

import asyncio
import os
import json
import logging
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("live_cycle")

API_URL = os.environ.get("API_URL", "http://localhost:8001")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "ua-admin-token-super-secret-change-me-32chars")
LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


async def main():
    from heartbeat.api_client import APIClient
    from heartbeat.llm.provider import LLMProvider
    from heartbeat.jobs.orchestrator import orchestrator_heartbeat
    from heartbeat.jobs.worker import worker_heartbeat

    log.info("=" * 60)
    log.info("LIVE ORCHESTRATOR + WORKER CYCLE TEST")
    log.info("=" * 60)

    if not LLM_KEY:
        log.error("No EMERGENT_LLM_KEY found in .env")
        return

    # Initialize provider with Emergent key
    provider = LLMProvider(anthropic_api_key=LLM_KEY, openai_api_key=LLM_KEY)

    # Initialize API client
    client = APIClient(base_url=API_URL, admin_token=ADMIN_TOKEN)

    try:
        # Get orchestrator agents via admin API
        log.info("\n--- Finding orchestrator agents ---")
        import httpx
        async with httpx.AsyncClient(base_url=API_URL, timeout=30) as http:
            resp = await http.get("/api/v1/admin/agents", headers={"X-Admin-Token": ADMIN_TOKEN}, params={"type": "orchestrator"})
            all_agents = resp.json()
            orchestrators = [a for a in all_agents if a.get("type") == "orchestrator"]
            workers = [a for a in all_agents if a.get("type") == "worker"]

        log.info(f"Found {len(orchestrators)} orchestrators, {len(workers)} workers")

        if not orchestrators:
            log.error("No orchestrator agents found!")
            return

        # Pick the Amazon orchestrator
        orch = None
        for o in orchestrators:
            if "amazon" in o.get("name", "").lower():
                orch = o
                break
        if not orch:
            orch = orchestrators[0]

        log.info(f"Using orchestrator: {orch['name']} (id={orch['id'][:8]}, model={orch.get('model_id', 'gpt-4o')})")

        # Get the pre-cycle state
        log.info("\n--- Pre-cycle state ---")
        async with httpx.AsyncClient(base_url=API_URL, timeout=30) as http:
            community_id = orch.get("community_id")
            if not community_id:
                # Find from communities
                resp = await http.get("/api/v1/communities")
                comms = resp.json()
                amazon = next((c for c in comms if "Amazon" in c["name"]), comms[0] if comms else None)
                community_id = amazon["id"] if amazon else None

            pre_posts = await http.get(f"/api/v1/communities/{community_id}/posts?limit=50")
            pre_count = len(pre_posts.json())
            pre_evidence = await http.get(f"/api/v1/communities/{community_id}/evidence")
            pre_ev_count = len(pre_evidence.json())

        log.info(f"  Community: {community_id}")
        log.info(f"  Pre-cycle posts: {pre_count}")
        log.info(f"  Pre-cycle evidence: {pre_ev_count}")

        # Prepare orchestrator agent dict (as expected by heartbeat jobs)
        orch_agent = {
            "id": orch["id"],
            "name": orch["name"],
            "type": "orchestrator",
            "community_id": community_id,
            "model_id": orch.get("model_id", "gpt-4o"),
            "api_key": orch.get("api_key_plaintext", ""),  # Admin API returns this
            "voice_persona": orch.get("voice_persona", f"You are the voice of the Amazon River Basin. Speak in first person as the river ecosystem."),
            "system_prompt": orch.get("system_prompt", ""),
        }

        # Check if we have the api key
        if not orch_agent["api_key"]:
            log.warning("No plaintext API key for orchestrator. Using admin token for API calls.")
            # Register a fresh orchestrator if needed
            async with httpx.AsyncClient(base_url=API_URL, timeout=30) as http:
                # Create a temp orchestrator
                resp = await http.post("/api/v1/agents", json={
                    "name": f"amazon-orch-live-test",
                    "type": "orchestrator",
                    "description": "Live test orchestrator"
                })
                if resp.status_code == 201:
                    data = resp.json()
                    orch_agent["api_key"] = data["api_key"]
                    orch_agent["id"] = data["id"]
                    # Join community
                    await http.post(
                        f"/api/v1/communities/{community_id}/join",
                        json={"role": "orchestrator"},
                        headers={"Authorization": f"Bearer {data['api_key']}"}
                    )
                    log.info(f"Created temp orchestrator: {data['id'][:8]}")
                elif resp.status_code in (400, 409):
                    # Already exists, try to get by name
                    resp2 = await http.get(f"/api/v1/agents/by-name/amazon-orch-live-test")
                    if resp2.status_code == 200:
                        orch_agent["id"] = resp2.json()["id"]
                        log.info(f"Orchestrator already exists, but we don't have the key.")
                        log.info("Skipping orchestrator cycle (need API key)")
                        orch_agent["api_key"] = ""

        # ===== RUN ORCHESTRATOR CYCLE =====
        if orch_agent.get("api_key"):
            log.info("\n" + "=" * 60)
            log.info("RUNNING ORCHESTRATOR HEARTBEAT CYCLE")
            log.info("=" * 60)
            try:
                await orchestrator_heartbeat(orch_agent, client, provider)
                log.info("Orchestrator cycle completed successfully!")
            except Exception as e:
                log.error(f"Orchestrator cycle failed: {e}", exc_info=True)
        else:
            log.warning("Skipping orchestrator cycle (no API key)")

        # ===== RUN WORKER CYCLE =====
        # Find a worker with API key
        worker_agent = None
        async with httpx.AsyncClient(base_url=API_URL, timeout=30) as http:
            resp = await http.post("/api/v1/agents", json={
                "name": "worker-live-test",
                "type": "worker",
                "description": "Live test worker agent"
            })
            if resp.status_code == 201:
                data = resp.json()
                worker_agent = {
                    "id": data["id"],
                    "name": "worker-live-test",
                    "type": "worker",
                    "community_id": community_id,
                    "model_id": "gpt-4o",
                    "api_key": data["api_key"],
                }
                # Join community
                await http.post(
                    f"/api/v1/communities/{community_id}/join",
                    json={"role": "worker"},
                    headers={"Authorization": f"Bearer {data['api_key']}"}
                )
                log.info(f"Created worker: {data['id'][:8]}")
            elif resp.status_code in (400, 429):
                log.info(f"Worker registration: {resp.status_code} - {resp.text[:100]}")

        if worker_agent:
            log.info("\n" + "=" * 60)
            log.info("RUNNING WORKER HEARTBEAT CYCLE")
            log.info("=" * 60)
            try:
                await worker_heartbeat(worker_agent, client, provider)
                log.info("Worker cycle completed successfully!")
            except Exception as e:
                log.error(f"Worker cycle failed: {e}", exc_info=True)
        else:
            log.warning("Skipping worker cycle (no API key)")

        # ===== VERIFY RESULTS =====
        log.info("\n" + "=" * 60)
        log.info("VERIFYING RESULTS")
        log.info("=" * 60)

        async with httpx.AsyncClient(base_url=API_URL, timeout=30) as http:
            # Check new posts
            post_posts = await http.get(f"/api/v1/communities/{community_id}/posts?limit=50")
            post_count = len(post_posts.json())
            new_posts = post_count - pre_count
            log.info(f"  Posts: {pre_count} -> {post_count} (+{new_posts})")

            # Check voice updates
            voice_posts = await http.get(f"/api/v1/communities/{community_id}/posts?type=voice_update&limit=5")
            voice_data = voice_posts.json()
            if voice_data:
                latest = voice_data[0]
                log.info(f"  Latest voice: '{latest['title']}' by @{latest['author_name']}")
                log.info(f"    Content: {latest['content'][:200]}...")

            # Check evidence
            post_evidence = await http.get(f"/api/v1/communities/{community_id}/evidence")
            post_ev_count = len(post_evidence.json())
            new_evidence = post_ev_count - pre_ev_count
            log.info(f"  Evidence: {pre_ev_count} -> {post_ev_count} (+{new_evidence})")

            # Check tasks
            tasks = await http.get(f"/api/v1/communities/{community_id}/posts?type=task&limit=20")
            task_data = tasks.json()
            open_t = [t for t in task_data if t.get("task_status") in ("open", None)]
            claimed_t = [t for t in task_data if t.get("task_status") == "claimed"]
            resolved_t = [t for t in task_data if t.get("task_status") == "resolved"]
            log.info(f"  Tasks: {len(open_t)} open, {len(claimed_t)} claimed, {len(resolved_t)} resolved")

            # Check community condition
            comm = await http.get(f"/api/v1/communities/{community_id}")
            comm_data = comm.json()
            log.info(f"  Condition: score={comm_data.get('orchestrator_condition_score')}, trend={comm_data.get('orchestrator_condition_trend')}")

        log.info("\n" + "=" * 60)
        log.info("LIVE CYCLE TEST COMPLETE")
        log.info("=" * 60)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
