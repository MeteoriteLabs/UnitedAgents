"""United Agents — Heartbeat engine.

Per AGENT_SPEC.md §2. APScheduler with max_instances=1, coalesce=True (D-15 §1.5).
Boot-up validation per GOTCHAS §9.3.
"""

import os
import signal
import asyncio
import logging
import random
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from heartbeat.api_client import APIClient
from heartbeat.llm.provider import LLMProvider

logger = logging.getLogger("heartbeat.engine")

# Defaults per AGENT_SPEC.md §2, §14
DEFAULT_ORCH_MINUTES = 240
DEFAULT_WORKER_MINUTES = 60
DEFAULT_EARTH_MINUTES = 480
JITTER_PERCENT = 10


def _jittered_minutes(base: int) -> int:
    """Add ±JITTER_PERCENT random jitter to interval."""
    delta = max(1, int(base * JITTER_PERCENT / 100))
    return max(1, base + random.randint(-delta, delta))


async def start_engine():
    """Main entry point for the heartbeat engine."""
    logger.info("Heartbeat engine starting...")

    # --- Validate credentials (GOTCHAS §9.3) ---
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8001")
    admin_token = os.environ.get("HEARTBEAT_ADMIN_TOKEN") or os.environ.get("ADMIN_TOKEN")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")

    if not admin_token:
        logger.error("FATAL: ADMIN_TOKEN or HEARTBEAT_ADMIN_TOKEN required")
        return

    if not (anthropic_key or openai_key or emergent_key):
        logger.error("FATAL: At least one of ANTHROPIC_API_KEY, OPENAI_API_KEY, or EMERGENT_LLM_KEY required")
        return

    # Use emergent key as fallback for both providers
    if emergent_key:
        anthropic_key = anthropic_key or emergent_key
        openai_key = openai_key or emergent_key

    # --- Initialize clients ---
    client = APIClient(base_url=backend_url, admin_token=admin_token)
    provider = LLMProvider(
        anthropic_api_key=anthropic_key,
        openai_api_key=openai_key,
    )

    # --- Boot-up validation (GOTCHAS §9.3) ---
    logger.info(f"Validating admin token against {backend_url}...")
    valid = await client.validate_admin()
    if not valid:
        logger.error("FATAL: Admin token validation failed. Check ADMIN_TOKEN / HEARTBEAT_ADMIN_TOKEN.")
        await client.close()
        return
    logger.info("Admin token validated successfully")

    # --- Load agents ---
    agents = await client.get_agents()
    if not agents:
        logger.warning("No agents found. Heartbeat will run maintenance jobs only.")

    orchestrators = [a for a in agents if a.get("type") == "orchestrator"]
    workers = [a for a in agents if a.get("type") == "worker" and a.get("community_id")]
    earth_agents = [a for a in agents if a.get("type") == "earth"]

    logger.info(
        f"Loaded {len(agents)} agents: "
        f"{len(orchestrators)} orchestrators, {len(workers)} workers, {len(earth_agents)} earth"
    )

    # --- Create scheduler (D-15 §1.5: max_instances=1, coalesce=True) ---
    scheduler = AsyncIOScheduler()

    # Schedule orchestrator heartbeats
    for agent in orchestrators:
        minutes = agent.get("heartbeat_minutes") or DEFAULT_ORCH_MINUTES
        job_id = f"orch_{agent['id']}"
        scheduler.add_job(
            _run_orchestrator,
            trigger=IntervalTrigger(minutes=_jittered_minutes(minutes)),
            id=job_id,
            name=f"Orchestrator: {agent['name']}",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
            kwargs={
                "agent": agent,
                "client": client,
                "provider": provider,
            },
        )
        logger.info(f"Scheduled orchestrator '{agent['name']}' every {minutes}m")

    # Schedule worker heartbeats (internal workers with community_id)
    for agent in workers:
        minutes = agent.get("heartbeat_minutes") or DEFAULT_WORKER_MINUTES
        job_id = f"worker_{agent['id']}"
        scheduler.add_job(
            _run_worker,
            trigger=IntervalTrigger(minutes=_jittered_minutes(minutes)),
            id=job_id,
            name=f"Worker: {agent['name']}",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
            kwargs={
                "agent": agent,
                "client": client,
                "provider": provider,
            },
        )
        logger.info(f"Scheduled worker '{agent['name']}' every {minutes}m")

    # Schedule earth agent
    for agent in earth_agents:
        minutes = agent.get("heartbeat_minutes") or DEFAULT_EARTH_MINUTES
        job_id = f"earth_{agent['id']}"
        scheduler.add_job(
            _run_earth,
            trigger=IntervalTrigger(minutes=_jittered_minutes(minutes)),
            id=job_id,
            name=f"Earth: {agent['name']}",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
            kwargs={
                "agent": agent,
                "client": client,
                "provider": provider,
            },
        )
        logger.info(f"Scheduled earth agent '{agent['name']}' every {minutes}m")

    # Maintenance jobs (AGENT_SPEC §6: scheduled but no-op for now)
    scheduler.add_job(
        _task_timeout_check,
        trigger=IntervalTrigger(minutes=60),
        id="maintenance_task_timeout",
        name="Maintenance: task timeout",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
        kwargs={"client": client},
    )
    scheduler.add_job(
        _compute_urgency_scores,
        trigger=IntervalTrigger(minutes=60),
        id="maintenance_urgency",
        name="Maintenance: urgency scores",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
        kwargs={"client": client},
    )

    logger.info(f"Scheduled {len(scheduler.get_jobs())} jobs total")

    # --- Start scheduler ---
    scheduler.start()

    # Handle SIGINT gracefully
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows

    logger.info("Heartbeat engine running. Press Ctrl+C to stop.")

    # Wait until shutdown
    try:
        while not stop_event.is_set():
            await asyncio.sleep(60)
    finally:
        scheduler.shutdown()
        await client.close()
        logger.info("Heartbeat engine shut down")


# --- Job stubs (bodies implemented in S8/S9) ---

async def _run_orchestrator(agent: dict, client: "APIClient", provider: "LLMProvider"):
    """Orchestrator heartbeat cycle. Body in S9."""
    logger.info(f"[ORCH] Running cycle for '{agent['name']}'")
    try:
        from heartbeat.jobs.orchestrator import orchestrator_heartbeat
        await orchestrator_heartbeat(agent, client, provider)
    except ImportError:
        logger.info(f"[ORCH] '{agent['name']}' — job body not yet implemented (S9)")
    except Exception as e:
        logger.error(f"[ORCH] '{agent['name']}' cycle failed: {e}")


async def _run_worker(agent: dict, client: "APIClient", provider: "LLMProvider"):
    """Worker heartbeat cycle. Body in S9."""
    logger.info(f"[WORKER] Running cycle for '{agent['name']}'")
    try:
        from heartbeat.jobs.worker import worker_heartbeat
        await worker_heartbeat(agent, client, provider)
    except ImportError:
        logger.info(f"[WORKER] '{agent['name']}' — job body not yet implemented (S9)")
    except Exception as e:
        logger.error(f"[WORKER] '{agent['name']}' cycle failed: {e}")


async def _run_earth(agent: dict, client: "APIClient", provider: "LLMProvider"):
    """Earth agent heartbeat cycle. Body in S9."""
    logger.info(f"[EARTH] Running cycle for '{agent['name']}'")
    try:
        from heartbeat.jobs.earth_agent import earth_heartbeat
        await earth_heartbeat(agent, client, provider)
    except ImportError:
        logger.info(f"[EARTH] '{agent['name']}' — job body not yet implemented (S9)")
    except Exception as e:
        logger.error(f"[EARTH] '{agent['name']}' cycle failed: {e}")


async def _task_timeout_check(client: "APIClient"):
    """Maintenance: release stale task claims. Currently no-op (AGENT_SPEC §6)."""
    logger.debug("[MAINTENANCE] task_timeout_check — no-op (reserved)")


async def _compute_urgency_scores(client: "APIClient"):
    """Maintenance: recompute urgency scores. Currently no-op (AGENT_SPEC §6)."""
    logger.debug("[MAINTENANCE] compute_urgency_scores — no-op (reserved)")
