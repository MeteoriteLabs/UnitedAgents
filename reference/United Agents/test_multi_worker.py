"""Run multiple worker agents in parallel — each claims a different task.

Usage:
  python test_multi_worker.py [num_workers]  (default: 4)
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
logger = logging.getLogger("multi_worker")

BASE_URL = "http://localhost:3456"
NUM_WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 4

WORKER_NAMES = [
    "Scout Alpha — Data Collector",
    "Scout Beta — Verifier",
    "Scout Gamma — Researcher",
    "Scout Delta — Outreach Specialist",
]

TIMELINE = []
TIMELINE_LOCK = asyncio.Lock()


async def log_event(worker: str, phase: str, action: str, detail: str = ""):
    async with TIMELINE_LOCK:
        TIMELINE.append({"worker": worker, "phase": phase, "action": action, "detail": detail})
    logger.info(f"[{worker}] [{phase}] {action}" + (f" — {detail}" if detail else ""))


async def api(method, path, json_body=None, headers=None):
    async with httpx.AsyncClient() as client:
        resp = await client.request(method, f"{BASE_URL}/api/v1{path}",
                                     json=json_body, headers=headers or {}, timeout=30.0)
        if resp.status_code >= 400:
            return {"error": resp.status_code, "detail": resp.text}
        return resp.json()


async def admin_api(method, path, json_body=None):
    headers = {"X-Admin-Token": os.environ["ADMIN_TOKEN"], "Content-Type": "application/json"}
    return await api(method, path, json_body, headers)


async def agent_api(method, path, api_key, json_body=None):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    return await api(method, path, json_body, headers)


async def ensure_worker(name: str, community_id: str) -> dict:
    """Create worker if it doesn't exist, return with api_key."""
    agents = await admin_api("GET", "/admin/agents")
    worker = next((a for a in agents if a["name"] == name), None)

    if not worker:
        worker = await admin_api("POST", "/admin/agents", {
            "name": name,
            "type": "worker",
            "description": f"Worker agent: {name}",
            "community_id": community_id,
        })

    if not worker.get("api_key"):
        from src.database import init_db
        from src.models import Agent as AgentModel
        SessionLocal = init_db()
        db = SessionLocal()
        db_agent = db.query(AgentModel).filter(AgentModel.id == worker["id"]).first()
        worker["api_key"] = db_agent.api_key if db_agent else None
        db.close()

    return worker


async def do_llm_work(task: dict, worker_name: str) -> dict:
    """Use LLM to produce findings for a task."""
    from heartbeat.llm.provider import LLMProvider

    provider = LLMProvider(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )

    prompt = f"""You are "{worker_name}", a worker agent investigating environmental issues for a river ecosystem.

Your task:
  Title: {task['title']}
  Category: {task.get('task_category', 'research')}
  Instructions: {task['content']}

Produce TWO outputs:

1. RESEARCH_NOTE: A concise research note (150-300 words) with specific findings.
   Write from your specialist perspective. Be specific with numbers and dates.

2. EVIDENCE: One key data point with a source.

Also optionally:
3. COMMENT: If you have a question or observation for the orchestrator or other workers, include it.

Respond ONLY with valid JSON:
{{
  "research_note": {{
    "title": "Findings: <title>",
    "content": "<your note>"
  }},
  "evidence": {{
    "content": "<factual statement>",
    "type": "data_point"
  }},
  "comment": "<optional comment or question for the community, or null>"
}}"""

    result = await provider.create_message(
        model="gpt-4o-mini",
        system=f"You are {worker_name}, a diligent environmental research agent. Produce realistic but clearly simulated research. Be specific.",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.8,
    )

    text = result["text"].strip()
    try:
        if "{" in text:
            return json.loads(text[text.index("{"):text.rindex("}") + 1])
    except (json.JSONDecodeError, ValueError):
        pass

    return {
        "research_note": {"title": f"Findings: {task['title']}", "content": f"[Simulated by {worker_name}] {text[:400]}"},
        "evidence": {"content": f"[Simulated] Finding for {task['title']}", "type": "research"},
        "comment": None,
    }


async def worker_cycle(worker: dict, community_id: str, task: dict):
    """One full worker cycle: claim -> work -> submit -> resolve."""
    name = worker["name"]
    api_key = worker["api_key"]

    # Claim
    await log_event(name, "CLAIM", f"Claiming: {task['title']}", f"task_id={task['id']}")
    claimed = await agent_api("POST", f"/tasks/{task['id']}/claim", api_key)
    if "error" in claimed:
        await log_event(name, "CLAIM", "FAILED — task already taken", str(claimed.get("detail", "")))
        return
    await log_event(name, "CLAIM", "Success", f"status={claimed.get('task_status')}")

    # Work
    await log_event(name, "WORK", "Calling LLM for research")
    findings = await do_llm_work(task, name)
    await log_event(name, "WORK", "LLM done", findings.get("research_note", {}).get("title", "?"))

    thread_id = task.get("thread_id")

    # Submit research note
    note = findings.get("research_note", {})
    post_result = await agent_api("POST", f"/communities/{community_id}/posts", api_key, {
        "title": note.get("title", f"Findings: {task['title']}"),
        "content": note.get("content", "No findings"),
        "type": "research_note",
        "thread_id": thread_id,
    })
    await log_event(name, "SUBMIT", "Research note posted", f"post_id={post_result.get('id')}")

    # Submit evidence
    ev = findings.get("evidence", {})
    ev_result = await agent_api("POST", f"/communities/{community_id}/evidence", api_key, {
        "type": ev.get("type", "data_point"),
        "content": ev.get("content", "Simulated finding"),
        "thread_id": thread_id,
        "source_url": f"https://simulated-source.example.com/{name.split()[1].lower()}",
    })
    await log_event(name, "SUBMIT", "Evidence submitted", f"evidence_id={ev_result.get('id')}")

    # Post comment if worker has one
    comment = findings.get("comment")
    if comment and comment != "null" and thread_id:
        # Find the orchestrator's voice_update to comment on
        posts = await agent_api("GET", f"/communities/{community_id}/posts?limit=5", api_key)
        if isinstance(posts, list):
            voice_post = next((p for p in posts if p["type"] == "voice_update"), None)
            if voice_post:
                await agent_api("POST", f"/posts/{voice_post['id']}/comments", api_key, {
                    "content": comment,
                })
                await log_event(name, "COMMENT", "Replied to orchestrator", comment[:80])

    # Resolve
    resolve = await agent_api("PATCH", f"/tasks/{task['id']}/resolve", api_key)
    await log_event(name, "RESOLVE", "Task resolved", f"status={resolve.get('task_status')}")

    # Heartbeat ping
    await agent_api("POST", "/agents/heartbeat", api_key)
    await log_event(name, "DONE", "Cycle complete")


async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("No LLM API key set.")
        sys.exit(1)

    # Check backend
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/health", timeout=5.0)
            resp.raise_for_status()
    except Exception:
        logger.error("Backend not reachable")
        sys.exit(1)

    # Get community
    communities = await admin_api("GET", "/admin/communities")
    community = next((c for c in communities if "River" in c.get("name", "")), None)
    if not community:
        logger.error("No test community. Run test_heartbeat.py first.")
        sys.exit(1)
    community_id = community["id"]

    # Get open tasks
    # Need any agent key to query tasks — use first worker or create one
    workers = []
    for i in range(min(NUM_WORKERS, len(WORKER_NAMES))):
        w = await ensure_worker(WORKER_NAMES[i], community_id)
        workers.append(w)

    api_key = workers[0]["api_key"]
    tasks = await agent_api("GET", f"/tasks/open?community_id={community_id}", api_key)
    if not tasks or isinstance(tasks, dict):
        logger.error("No open tasks to work on.")
        sys.exit(1)

    open_tasks = [t for t in tasks if t.get("task_status") == "open"]
    logger.info(f"\nFound {len(open_tasks)} open tasks, {len(workers)} workers ready")
    for t in open_tasks:
        logger.info(f"  [{t.get('task_category')}] {t['title']}")

    # Assign tasks to workers (1 task per worker, parallel)
    assignments = list(zip(workers, open_tasks))
    logger.info(f"\nAssigning {len(assignments)} tasks to workers...")
    for w, t in assignments:
        logger.info(f"  {w['name']} -> {t['title']}")

    print("\n" + "=" * 70)
    print(f"STARTING {len(assignments)} WORKERS IN PARALLEL")
    print("=" * 70)

    # Run all workers concurrently
    await asyncio.gather(*[
        worker_cycle(w, community_id, t) for w, t in assignments
    ])

    # Print timeline
    print("\n" + "=" * 70)
    print("MULTI-WORKER TIMELINE")
    print("=" * 70)
    for i, event in enumerate(TIMELINE, 1):
        worker_short = event["worker"].split("—")[0].strip() if "—" in event["worker"] else event["worker"][:15]
        print(f"  {i:2}. [{worker_short:14}] [{event['phase']:8}] {event['action']}")
        if event["detail"]:
            print(f"      -> {event['detail'][:100]}")
    print("=" * 70)

    # Print summary
    print(f"\n  Workers run: {len(assignments)}")
    resolved = sum(1 for e in TIMELINE if e["phase"] == "RESOLVE")
    failed = sum(1 for e in TIMELINE if "FAILED" in e["action"])
    notes = sum(1 for e in TIMELINE if "Research note" in e["action"])
    evidence = sum(1 for e in TIMELINE if "Evidence" in e["action"])
    comments = sum(1 for e in TIMELINE if e["phase"] == "COMMENT")
    print(f"  Tasks resolved: {resolved}")
    print(f"  Claims failed: {failed}")
    print(f"  Research notes posted: {notes}")
    print(f"  Evidence submitted: {evidence}")
    print(f"  Comments posted: {comments}")


if __name__ == "__main__":
    asyncio.run(main())
