"""Test script — simulate a worker agent doing one full cycle.

Flow:
  1. Register a worker agent (or reuse existing)
  2. Find open tasks
  3. Claim a task
  4. Use LLM to "do the work" — generate findings based on the task
  5. Submit a research_note post + evidence item
  6. Resolve the task
  7. Print summary

Usage:
  1. Backend must be running: python -m uvicorn src.main:app --port 3456
  2. Run: python test_worker.py
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
logger = logging.getLogger("test_worker")

BASE_URL = "http://localhost:3456"
WORKER_NAME = "Test Research Scout"

# Track everything for reporting
TIMELINE = []


def log_event(phase: str, action: str, detail: str = ""):
    entry = {"phase": phase, "action": action, "detail": detail}
    TIMELINE.append(entry)
    logger.info(f"[{phase}] {action}" + (f" — {detail}" if detail else ""))


async def api(method: str, path: str, json_body: dict = None,
              headers: dict = None, expect_ok: bool = True) -> dict:
    """Generic API call."""
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method, f"{BASE_URL}/api/v1{path}",
            json=json_body, headers=headers or {}, timeout=30.0,
        )
        if expect_ok and resp.status_code >= 400:
            logger.error(f"{method} {path} -> {resp.status_code}: {resp.text}")
        if resp.status_code >= 400 and expect_ok:
            resp.raise_for_status()
        return resp.json() if resp.status_code < 400 else {"error": resp.status_code, "detail": resp.text}


async def admin_api(method: str, path: str, json_body: dict = None) -> dict:
    headers = {"X-Admin-Token": os.environ["ADMIN_TOKEN"], "Content-Type": "application/json"}
    return await api(method, path, json_body, headers)


async def agent_api(method: str, path: str, api_key: str, json_body: dict = None) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    return await api(method, path, json_body, headers)


async def setup_worker() -> dict:
    """Create or find the test worker agent."""
    log_event("SETUP", "Looking for existing worker agent")

    agents = await admin_api("GET", "/admin/agents")
    worker = next((a for a in agents if a["name"] == WORKER_NAME), None)

    if not worker:
        log_event("SETUP", "Creating worker agent", WORKER_NAME)

        # Find the test community
        communities = await admin_api("GET", "/admin/communities")
        community = next((c for c in communities if "River" in c.get("name", "")), None)
        if not community:
            logger.error("No test community found. Run test_heartbeat.py first.")
            sys.exit(1)

        worker = await admin_api("POST", "/admin/agents", {
            "name": WORKER_NAME,
            "type": "worker",
            "description": "A research worker agent that investigates environmental data",
            "community_id": community["id"],
        })
        log_event("SETUP", "Worker created", f"id={worker['id']}")
    else:
        log_event("SETUP", "Using existing worker", f"id={worker['id']}")

    # Get the API key from DB (admin response includes it on creation)
    if not worker.get("api_key"):
        from src.database import init_db
        from src.models import Agent as AgentModel
        SessionLocal = init_db()
        db = SessionLocal()
        db_agent = db.query(AgentModel).filter(AgentModel.id == worker["id"]).first()
        worker["api_key"] = db_agent.api_key if db_agent else None
        db.close()

    return worker


async def find_and_claim_task(api_key: str, community_id: str) -> dict | None:
    """Find an open task and claim it."""
    log_event("TASK", "Searching for open tasks")

    tasks = await agent_api("GET", f"/tasks/open?community_id={community_id}", api_key)
    if not tasks or isinstance(tasks, dict):
        log_event("TASK", "No open tasks found")
        return None

    log_event("TASK", f"Found {len(tasks)} open tasks")
    for t in tasks:
        logger.info(f"  [{t.get('task_category', '?')}] {t['title']} (status: {t.get('task_status')})")

    # Pick the first open task
    task = tasks[0]
    log_event("TASK", "Claiming task", f"{task['title']} (id={task['id']})")

    claimed = await agent_api("POST", f"/tasks/{task['id']}/claim", api_key)
    if "error" in claimed:
        log_event("TASK", "Claim failed", str(claimed))
        return None

    log_event("TASK", "Task claimed successfully", f"status={claimed.get('task_status')}")
    return claimed


async def do_work_with_llm(task: dict, community_id: str) -> dict:
    """Use LLM to generate research findings for the task."""
    log_event("WORK", "Starting LLM research", f"task: {task['title']}")

    from heartbeat.llm.provider import LLMProvider

    provider = LLMProvider(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )

    model = "gpt-4o-mini"

    prompt = f"""You are a research worker agent investigating environmental issues for a river ecosystem community.

Your task:
  Title: {task['title']}
  Category: {task.get('task_category', 'research')}
  Instructions: {task['content']}

You must produce TWO outputs:

1. RESEARCH_NOTE: A concise research note (200-400 words) summarizing your findings.
   Write as a researcher reporting to the community. Include specific details.

2. EVIDENCE: One key data point or finding with a plausible source.
   Format as a single factual statement.

Respond ONLY with valid JSON:
{{
  "research_note": {{
    "title": "Findings: <descriptive title>",
    "content": "<your research note text>"
  }},
  "evidence": {{
    "content": "<single factual statement with numbers/dates>",
    "type": "research",
    "source_description": "<what source this would come from>"
  }}
}}"""

    log_event("WORK", "Calling LLM", f"model={model}")

    result = await provider.create_message(
        model=model,
        system="You are a diligent environmental research agent. Produce realistic but clearly simulated research findings. Always note these are simulated.",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.7,
    )

    text = result["text"].strip()
    log_event("WORK", "LLM responded", f"{len(text)} chars")

    # Parse JSON from response
    try:
        if "{" in text:
            json_str = text[text.index("{"):text.rindex("}") + 1]
            findings = json.loads(json_str)
            log_event("WORK", "Parsed findings", f"note title: {findings.get('research_note', {}).get('title', '?')}")
            return findings
    except (json.JSONDecodeError, ValueError) as e:
        log_event("WORK", "JSON parse failed, using fallback", str(e))

    # Fallback
    return {
        "research_note": {
            "title": f"Findings: {task['title']}",
            "content": f"[Simulated] Research findings for task: {task['title']}. {text[:500]}",
        },
        "evidence": {
            "content": f"[Simulated] Key finding related to {task['title']}",
            "type": "research",
            "source_description": "Simulated research output",
        },
    }


async def submit_findings(api_key: str, community_id: str, task: dict, findings: dict):
    """Submit research note + evidence, then resolve the task."""
    thread_id = task.get("thread_id")

    # 1. Post research note
    note = findings.get("research_note", {})
    log_event("SUBMIT", "Posting research note", note.get("title", "?"))

    post_result = await agent_api("POST", f"/communities/{community_id}/posts", api_key, {
        "title": note.get("title", f"Findings: {task['title']}"),
        "content": note.get("content", "No findings."),
        "type": "research_note",
        "thread_id": thread_id,
    })
    log_event("SUBMIT", "Research note posted", f"post_id={post_result.get('id')}")

    # 2. Submit evidence
    ev = findings.get("evidence", {})
    log_event("SUBMIT", "Submitting evidence", ev.get("content", "?")[:80])

    ev_result = await agent_api("POST", f"/communities/{community_id}/evidence", api_key, {
        "type": ev.get("type", "research"),
        "content": ev.get("content", "Simulated finding"),
        "thread_id": thread_id,
        "source_url": "https://simulated-source.example.com/data",
    })
    log_event("SUBMIT", "Evidence submitted", f"evidence_id={ev_result.get('id')}")

    # 3. Resolve the task
    log_event("SUBMIT", "Resolving task", f"task_id={task['id']}")
    resolve_result = await agent_api("PATCH", f"/tasks/{task['id']}/resolve", api_key)
    log_event("SUBMIT", "Task resolved", f"status={resolve_result.get('task_status')}")

    # 4. Ping liveness
    await agent_api("POST", "/agents/heartbeat", api_key)
    log_event("SUBMIT", "Liveness ping sent")


async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("No LLM API key set.")
        sys.exit(1)
    if not os.environ.get("ADMIN_TOKEN"):
        logger.error("ADMIN_TOKEN not set.")
        sys.exit(1)

    # Check backend
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/health", timeout=5.0)
            resp.raise_for_status()
    except Exception:
        logger.error(f"Backend not reachable at {BASE_URL}")
        sys.exit(1)

    log_event("START", "Worker agent cycle beginning")

    # Setup
    worker = await setup_worker()
    api_key = worker["api_key"]
    community_id = worker.get("community_id")

    if not community_id:
        communities = await admin_api("GET", "/admin/communities")
        community_id = communities[0]["id"] if communities else None
    if not community_id:
        logger.error("No community found")
        sys.exit(1)

    # Find and claim task
    task = await find_and_claim_task(api_key, community_id)
    if not task:
        log_event("END", "No tasks to work on. Run test_heartbeat.py first to create tasks.")
        return

    # Do the work
    findings = await do_work_with_llm(task, community_id)

    # Submit and resolve
    await submit_findings(api_key, community_id, task, findings)

    log_event("END", "Worker cycle complete")

    # Print timeline
    print("\n" + "=" * 70)
    print("WORKER AGENT TIMELINE")
    print("=" * 70)
    for i, event in enumerate(TIMELINE, 1):
        print(f"  {i:2}. [{event['phase']:8}] {event['action']}")
        if event['detail']:
            print(f"      -> {event['detail'][:100]}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
