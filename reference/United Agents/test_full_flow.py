"""End-to-end conversation flow test.

Runs the full cycle:
  Phase 1: Orchestrator cycle 1 (creates thread + tasks)
  Phase 2: Workers round 1 (3 workers: read context, work, discuss)
  Phase 3: Orchestrator cycle 2 (replies to workers, creates plan)
  Phase 4: Workers round 2 (2 workers: one disagrees/contests evidence)
  Phase 5: Orchestrator cycle 3 (revises plan, moderates)
  Phase 6: Report + assertions

Usage:
  1. Backend running: python -m uvicorn src.main:app --port 3456
  2. Run: python test_full_flow.py
"""

import os
import sys
import asyncio
import json
import logging
from datetime import datetime

import httpx

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("full_flow")

BASE_URL = "http://localhost:3456"
COMMUNITY_NAME = "Flow Test River"
ORCH_NAME = "River Guardian"
WORKER_NAMES = [
    "Scout Alpha — Data Collector",
    "Scout Beta — Verifier",
    "Scout Gamma — Researcher",
    "Scout Delta — Analyst",
]

TIMELINE = []
ASSERTIONS = {}


def log_event(phase: str, actor: str, action: str, detail: str = ""):
    TIMELINE.append({"phase": phase, "actor": actor, "action": action, "detail": detail})
    logger.info(f"[{phase}] [{actor}] {action}" + (f" — {detail}" if detail else ""))


async def api(method, path, json_body=None, headers=None):
    async with httpx.AsyncClient() as c:
        resp = await c.request(method, f"{BASE_URL}/api/v1{path}",
                               json=json_body, headers=headers or {}, timeout=30.0)
        if resp.status_code >= 400:
            return {"_error": resp.status_code, "_detail": resp.text}
        return resp.json()


async def admin(method, path, json_body=None):
    h = {"X-Admin-Token": os.environ["ADMIN_TOKEN"], "Content-Type": "application/json"}
    return await api(method, path, json_body, h)


async def agent(method, path, key, json_body=None):
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    return await api(method, path, json_body, h)


# ── Setup ──

async def setup():
    """Create fresh community + agents. Delete old test data first."""
    # Clean up old test community
    communities = await admin("GET", "/admin/communities")
    for c in communities:
        if c["name"] == COMMUNITY_NAME:
            await admin("DELETE", f"/admin/communities/{c['id']}")
            logger.info(f"Deleted old community: {c['id']}")

    # Clean up old test agents (ignore errors from FK constraints)
    agents = await admin("GET", "/admin/agents")
    for a in agents:
        if a.get("name") in [ORCH_NAME] + WORKER_NAMES:
            await admin("DELETE", f"/admin/agents/{a['id']}")

    # Create community
    community = await admin("POST", "/admin/communities", {
        "name": COMMUNITY_NAME,
        "description": "A river facing agricultural runoff, industrial pollution, and seasonal drought. "
                       "Local fish populations declining. Community needs investigation and action plan.",
        "scope": "River Basin Watershed",
        "icon": "\U0001F30A",
    })
    cid = community["id"]
    log_event("SETUP", "system", "Community created", cid)

    # Create orchestrator
    orch = await admin("POST", "/admin/agents", {
        "name": ORCH_NAME,
        "type": "orchestrator",
        "description": "Guardian agent for the river ecosystem",
        "community_id": cid,
        "voice_persona": "You are the voice of a river ecosystem. You feel the water flow, "
                         "the health of the fish, the quality of the sediment. Speak in first person.",
        "model_id": "gpt-4o-mini",
        "heartbeat_minutes": 240,
    })
    log_event("SETUP", "system", "Orchestrator created", orch["id"])

    # Create workers (skip if name already taken, reuse existing)
    workers = []
    all_agents = await admin("GET", "/admin/agents")
    for wname in WORKER_NAMES:
        existing = next((a for a in all_agents if a.get("name") == wname), None)
        if existing:
            workers.append(existing)
        else:
            w = await admin("POST", "/admin/agents", {
                "name": wname, "type": "worker",
                "description": f"Research worker: {wname}",
                "community_id": cid,
            })
            if "_error" not in w:
                workers.append(w)
    log_event("SETUP", "system", f"Ready with {len(workers)} workers")

    # Get API keys from DB
    from src.database import init_db
    from src.models import Agent as AgentModel
    db = init_db()()
    for item in [orch] + workers:
        if "id" not in item:
            continue
        db_a = db.query(AgentModel).filter(AgentModel.id == item["id"]).first()
        if db_a:
            item["api_key"] = db_a.api_key
    db.close()

    return community, orch, workers


# ── Orchestrator ──

async def run_orchestrator(orch: dict, community: dict, cycle_num: int):
    """Run one orchestrator heartbeat cycle."""
    from heartbeat.api_client import PlatformClient
    from heartbeat.llm.provider import LLMProvider
    from heartbeat.jobs.orchestrator import orchestrator_heartbeat

    log_event(f"ORCH-{cycle_num}", ORCH_NAME, "Starting heartbeat")

    client = PlatformClient(BASE_URL, api_key=orch["api_key"],
                            admin_token=os.environ.get("ADMIN_TOKEN"))
    provider = LLMProvider(openai_api_key=os.environ.get("OPENAI_API_KEY"),
                           anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"))
    model = orch.get("model_id") or "gpt-4o-mini"

    await orchestrator_heartbeat(
        agent_config=orch, community_id=community["id"],
        client=client, provider=provider, model=model,
    )
    log_event(f"ORCH-{cycle_num}", ORCH_NAME, "Heartbeat complete")


# ── Worker with conversation ──

async def worker_cycle(worker: dict, community_id: str, task: dict,
                       other_evidence: list = None, round_num: int = 1,
                       should_disagree: bool = False):
    """Full worker cycle with thread reading + discussion phase."""
    name = worker["name"]
    key = worker["api_key"]
    tid = task.get("thread_id")

    # ── Phase 1: Read thread context ──
    thread_context = ""
    if tid:
        posts = await agent("GET", f"/communities/{community_id}/posts?thread_id={tid}&limit=20", key)
        evidence = await agent("GET", f"/communities/{community_id}/evidence?thread_id={tid}", key)
        if isinstance(posts, list):
            for p in posts[:10]:
                thread_context += f"[{p['type']}] {p.get('author_name', '?')}: {p['content'][:200]}\n"
        if isinstance(evidence, list):
            for e in evidence[:5]:
                flags = "[CONTESTED]" if e.get("contested") else ""
                thread_context += f"[evidence {e['type']}]{flags} by {e.get('agent_name', '?')}: {e['content'][:150]}\n"
    log_event(f"WORKER-R{round_num}", name, "Read thread context", f"{len(thread_context)} chars")

    # ── Phase 2: Claim task ──
    claimed = await agent("POST", f"/tasks/{task['id']}/claim", key)
    if "_error" in claimed:
        log_event(f"WORKER-R{round_num}", name, "Claim FAILED", claimed.get("_detail", ""))
        return
    log_event(f"WORKER-R{round_num}", name, "Claimed task", task["title"])

    # ── Phase 3: Do work (LLM) ──
    from heartbeat.llm.provider import LLMProvider
    provider = LLMProvider(openai_api_key=os.environ.get("OPENAI_API_KEY"),
                           anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"))

    disagree_instruction = ""
    if should_disagree and other_evidence:
        target = other_evidence[0]
        disagree_instruction = f"""
IMPORTANT: You DISAGREE with this existing evidence:
  "{target.get('content', '')[:200]}" (id={target['id']}, by {target.get('agent_name', '?')})
Your research shows different results. Explain why this evidence is wrong or incomplete.
"""

    ev_type = "contradiction" if should_disagree else "data_point"
    contested_id = f'"{other_evidence[0]["id"]}"' if should_disagree and other_evidence else "null"
    ctx = thread_context if thread_context else "No prior work in this thread."

    work_prompt = (
        f'You are "{name}", a worker agent investigating environmental issues.\n\n'
        f'THREAD CONTEXT (what others have found):\n{ctx}\n\n'
        f'YOUR TASK:\n'
        f'  Title: {task["title"]}\n'
        f'  Category: {task.get("task_category", "research")}\n'
        f'  Instructions: {task["content"]}\n'
        f'{disagree_instruction}\n'
        f'Produce findings as JSON:\n'
        f'{{\n'
        f'  "research_note": {{"title": "Findings: <title>", "content": "<200-400 word note>"}},\n'
        f'  "evidence": {{"content": "<specific factual finding with numbers>", "type": "{ev_type}"}},\n'
        f'  "contested_target_id": {contested_id}\n'
        f'}}'
    )

    result = await provider.create_message(
        model="gpt-4o-mini",
        system=f"You are {name}. Produce realistic simulated research. Be specific with data.",
        messages=[{"role": "user", "content": work_prompt}],
        max_tokens=1000, temperature=0.8,
    )
    text = result["text"].strip()
    try:
        findings = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except (json.JSONDecodeError, ValueError):
        findings = {
            "research_note": {"title": f"Findings: {task['title']}", "content": text[:400]},
            "evidence": {"content": f"Finding for {task['title']}", "type": "data_point"},
        }
    log_event(f"WORKER-R{round_num}", name, "LLM work done", findings.get("research_note", {}).get("title", "?"))

    # ── Phase 4: Submit findings ──
    note = findings.get("research_note", {})
    await agent("POST", f"/communities/{community_id}/posts", key, {
        "title": note.get("title", f"Findings: {task['title']}"),
        "content": note.get("content", "No findings"),
        "type": "research_note", "thread_id": tid,
    })
    log_event(f"WORKER-R{round_num}", name, "Posted research note")

    VALID_EV_TYPES = {"data_point", "verification", "research", "connection", "contradiction"}
    ev = findings.get("evidence", {})
    if not isinstance(ev, dict):
        ev = {"content": str(ev), "type": "data_point"}
    raw_type = ev.get("type", "data_point")
    ev_type = raw_type if raw_type in VALID_EV_TYPES else "data_point"
    ev_content = ev.get("content", "Simulated finding")
    if not isinstance(ev_content, str):
        ev_content = json.dumps(ev_content)
    ev_body = {
        "type": ev_type,
        "content": ev_content,
        "thread_id": tid,
        "source_url": f"https://simulated-source.example.com/{name.split()[1].lower()}",
    }
    # If disagreeing, submit contradiction evidence
    if should_disagree and findings.get("contested_target_id"):
        ev_body["type"] = "contradiction"
        ev_body["contested_target"] = findings["contested_target_id"]
        log_event(f"WORKER-R{round_num}", name, "Submitting CONTRADICTION evidence",
                  f"contesting {findings['contested_target_id']}")
    elif should_disagree and other_evidence:
        ev_body["type"] = "contradiction"
        ev_body["contested_target"] = other_evidence[0]["id"]
        log_event(f"WORKER-R{round_num}", name, "Submitting CONTRADICTION evidence",
                  f"contesting {other_evidence[0]['id']}")

    ev_content_str = str(ev_body.get('content', ''))[:60]
    log_event(f"WORKER-R{round_num}", name, "Submitting evidence", f"type={ev_body['type']}, content={ev_content_str}")
    ev_result = await agent("POST", f"/communities/{community_id}/evidence", key, ev_body)
    if "_error" in ev_result:
        log_event(f"WORKER-R{round_num}", name, "Evidence FAILED",
                  f"status={ev_result['_error']}: {ev_result.get('_detail', '')[:120]}")
    else:
        log_event(f"WORKER-R{round_num}", name, "Evidence submitted", f"id={ev_result.get('id', '?')}")

    # ── Phase 5: Resolve task ──
    await agent("PATCH", f"/tasks/{task['id']}/resolve", key)
    log_event(f"WORKER-R{round_num}", name, "Task resolved")

    # ── Phase 6: Discussion phase — read others' work and comment ──
    if tid:
        all_posts = await agent("GET", f"/communities/{community_id}/posts?thread_id={tid}&limit=20", key)
        if isinstance(all_posts, list):
            other_notes = [p for p in all_posts
                           if p["type"] == "research_note"
                           and p.get("author_name") != name
                           and p.get("comment_count", 0) == 0]
            if other_notes:
                target_post = other_notes[0]
                # Generate a discussion comment
                disc_prompt = f"""You are "{name}". You just finished your research. Another worker posted:

Author: {target_post.get('author_name', '?')}
Title: {target_post.get('title', '')}
Content: {target_post['content'][:400]}

Write a SHORT comment (1-3 sentences) — ask a follow-up question, point out something interesting, or note where your findings align or differ. Be constructive and specific."""

                disc_result = await provider.create_message(
                    model="gpt-4o-mini",
                    system="Write a concise, constructive comment. No JSON, just the comment text.",
                    messages=[{"role": "user", "content": disc_prompt}],
                    max_tokens=200, temperature=0.8,
                )
                comment_text = disc_result["text"].strip()
                if comment_text:
                    await agent("POST", f"/posts/{target_post['id']}/comments", key, {
                        "content": comment_text,
                    })
                    log_event(f"WORKER-R{round_num}", name, "COMMENTED on worker post",
                              f"on {target_post.get('author_name', '?')}'s note: {comment_text[:80]}")

    await agent("POST", "/agents/heartbeat", key)


# ── State Inspection ──

async def get_state(community_id: str, key: str) -> dict:
    """Fetch full community state for assertions."""
    posts = await agent("GET", f"/communities/{community_id}/posts?limit=50", key)
    evidence = await agent("GET", f"/communities/{community_id}/evidence?limit=50", key)
    threads = await agent("GET", f"/communities/{community_id}/threads", key)
    plan = await agent("GET", f"/communities/{community_id}/plan", key)
    tasks_open = await agent("GET", f"/tasks/open?community_id={community_id}", key)
    tasks_resolved = await agent("GET", f"/tasks/resolved?community_id={community_id}", key)

    posts = posts if isinstance(posts, list) else []
    evidence = evidence if isinstance(evidence, list) else []
    threads = threads if isinstance(threads, list) else []
    tasks_open = tasks_open if isinstance(tasks_open, list) else []
    tasks_resolved = tasks_resolved if isinstance(tasks_resolved, list) else []

    comments_total = sum(p.get("comment_count", 0) for p in posts)
    contested = [e for e in evidence if e.get("contested")]

    return {
        "posts": posts,
        "evidence": evidence,
        "threads": threads,
        "plan": plan if not isinstance(plan, dict) or "_error" not in plan else None,
        "tasks_open": tasks_open,
        "tasks_resolved": tasks_resolved,
        "comments_total": comments_total,
        "contested_evidence": contested,
        "voice_updates": [p for p in posts if p["type"] == "voice_update"],
        "research_notes": [p for p in posts if p["type"] == "research_note"],
        "task_posts": [p for p in posts if p["type"] == "task"],
    }


# ── Main Flow ──

async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("No LLM API key set.")
        sys.exit(1)

    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{BASE_URL}/health", timeout=5.0)
            r.raise_for_status()
    except Exception:
        logger.error(f"Backend not reachable at {BASE_URL}")
        sys.exit(1)

    community, orch, workers = await setup()
    cid = community["id"]

    # ════════════════════════════════════════════════
    # PHASE 1: Orchestrator Cycle 1
    # ════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("PHASE 1: Orchestrator Cycle 1 — create thread + tasks")
    print("=" * 70)
    await run_orchestrator(orch, community, 1)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["1_thread_created"] = len(state["threads"]) >= 1
    ASSERTIONS["1_tasks_created"] = len(state["task_posts"]) >= 1
    ASSERTIONS["1_voice_update"] = len(state["voice_updates"]) >= 1
    ASSERTIONS["1_no_plan"] = state["plan"] is None  # <3 evidence, no plan yet
    logger.info(f"State: {len(state['threads'])} threads, {len(state['task_posts'])} tasks, "
                f"{len(state['evidence'])} evidence, plan={'YES' if state['plan'] else 'NO'}")

    # ════════════════════════════════════════════════
    # PHASE 2: Workers Round 1 (3 workers)
    # ════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("PHASE 2: Workers Round 1 — 3 workers claim, work, discuss")
    print("=" * 70)

    open_tasks = await agent("GET", f"/tasks/open?community_id={cid}", orch["api_key"])
    open_tasks = [t for t in open_tasks if t.get("task_status") == "open"] if isinstance(open_tasks, list) else []

    worker_count = min(3, len(open_tasks), len(workers))
    if worker_count > 0:
        await asyncio.gather(*[
            worker_cycle(workers[i], cid, open_tasks[i], round_num=1)
            for i in range(worker_count)
        ])

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["2_research_notes"] = len(state["research_notes"]) >= 3
    ASSERTIONS["2_evidence"] = len(state["evidence"]) >= 3
    ASSERTIONS["2_comments"] = state["comments_total"] >= 1
    logger.info(f"State: {len(state['research_notes'])} notes, {len(state['evidence'])} evidence, "
                f"{state['comments_total']} comments")

    # ════════════════════════════════════════════════
    # PHASE 3: Orchestrator Cycle 2 (should create plan, reply to workers)
    # ════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("PHASE 3: Orchestrator Cycle 2 — plan + replies")
    print("=" * 70)
    await run_orchestrator(orch, community, 2)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["3_plan_created"] = state["plan"] is not None
    ASSERTIONS["3_replies"] = state["comments_total"] >= 2  # at least 1 worker + 1 orch reply
    ASSERTIONS["3_no_duplicates"] = _check_no_duplicates(state["task_posts"])
    if state["plan"]:
        logger.info(f"Plan created: {state['plan'].get('title', '?')}")
        logger.info(f"Plan content: {state['plan'].get('content', '')[:200]}")
    logger.info(f"Comments total: {state['comments_total']}, Tasks: {len(state['tasks_open'])} open, "
                f"{len(state['tasks_resolved'])} resolved")

    # ════════════════════════════════════════════════
    # PHASE 4: Workers Round 2 (1 normal + 1 disagrees)
    # ════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("PHASE 4: Workers Round 2 — 1 agrees, 1 disagrees/contests")
    print("=" * 70)

    open_tasks = await agent("GET", f"/tasks/open?community_id={cid}", orch["api_key"])
    open_tasks = [t for t in open_tasks if t.get("task_status") == "open"] if isinstance(open_tasks, list) else []

    if len(open_tasks) >= 2 and len(workers) >= 4:
        # Get existing evidence for contestation
        existing_evidence = state["evidence"]
        non_contested = [e for e in existing_evidence if not e.get("contested") and e.get("type") != "contradiction"]

        await asyncio.gather(
            worker_cycle(workers[2], cid, open_tasks[0], round_num=2, should_disagree=False),
            worker_cycle(workers[3], cid, open_tasks[1], other_evidence=non_contested,
                         round_num=2, should_disagree=True),
        )
    elif len(open_tasks) >= 1:
        existing_evidence = state["evidence"]
        non_contested = [e for e in existing_evidence if not e.get("contested") and e.get("type") != "contradiction"]
        await worker_cycle(workers[-1], cid, open_tasks[0], other_evidence=non_contested,
                           round_num=2, should_disagree=True)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["4_contested"] = len(state["contested_evidence"]) >= 1
    logger.info(f"Contested evidence: {len(state['contested_evidence'])}")

    # ════════════════════════════════════════════════
    # PHASE 5: Orchestrator Cycle 3 (should revise plan, moderate)
    # ════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("PHASE 5: Orchestrator Cycle 3 — revise plan, moderate disagreement")
    print("=" * 70)
    await run_orchestrator(orch, community, 3)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["5_plan_revised"] = state["plan"] is not None  # plan still exists (may be revised)
    ASSERTIONS["5_comments_grew"] = state["comments_total"] >= 5
    logger.info(f"Final: {len(state['posts'])} posts, {state['comments_total']} comments, "
                f"{len(state['evidence'])} evidence, plan={'YES' if state['plan'] else 'NO'}")

    # ════════════════════════════════════════════════
    # REPORT
    # ════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TIMELINE")
    print("=" * 70)
    for i, e in enumerate(TIMELINE, 1):
        actor_short = e["actor"][:20]
        print(f"  {i:3}. [{e['phase']:12}] {actor_short:22} {e['action']}")
        if e["detail"]:
            print(f"       -> {e['detail'][:90]}")

    print("\n" + "=" * 70)
    print("FINAL STATE")
    print("=" * 70)
    print(f"  Posts:          {len(state['posts'])}")
    print(f"  Voice updates:  {len(state['voice_updates'])}")
    print(f"  Research notes: {len(state['research_notes'])}")
    print(f"  Tasks:          {len(state['task_posts'])} ({len(state['tasks_resolved'])} resolved, {len(state['tasks_open'])} open)")
    print(f"  Evidence:       {len(state['evidence'])} ({len(state['contested_evidence'])} contested)")
    print(f"  Comments:       {state['comments_total']}")
    print(f"  Threads:        {len(state['threads'])}")
    print(f"  Plan:           {'YES' if state['plan'] else 'NO'}")

    print("\n" + "=" * 70)
    print("ASSERTIONS")
    print("=" * 70)
    all_pass = True
    for name, passed in ASSERTIONS.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  {'[PASS]' if passed else '[FAIL]'} {name}")

    print("\n" + ("ALL ASSERTIONS PASSED" if all_pass else "SOME ASSERTIONS FAILED"))
    print("=" * 70)


def _check_no_duplicates(task_posts: list) -> bool:
    """Check that no two open tasks have >60% word overlap."""
    from heartbeat.tools.platform_tools import _find_duplicate_task
    open_tasks = [t for t in task_posts if t.get("task_status") == "open"]
    for i, task in enumerate(open_tasks):
        for j, other in enumerate(open_tasks):
            if i >= j:
                continue
            if _find_duplicate_task(task.get("title", ""), [other]):
                logger.warning(f"Duplicate tasks found: '{task['title']}' vs '{other['title']}'")
                return False
    return True


if __name__ == "__main__":
    asyncio.run(main())
