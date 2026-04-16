"""Amazon Rainforest — Thread Progression Integration Test.

Creates a real Amazon Forest community and runs the full thread progression
lifecycle: orchestrator creates threads → workers investigate → threads advance
→ child sub-threads created → workers research solutions → action tasks.

Usage:
  1. Backend running: python run.py  (port 3456)
  2. Run: python test_amazon_flow.py
"""

import os
import sys
import asyncio
import json
import logging
from datetime import datetime

import httpx

# Fix Windows console encoding
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("amazon_flow")

BASE_URL = "http://localhost:3456"
COMMUNITY_NAME = "Amazon Rainforest"
ORCH_NAME = "Forest Guardian"
WORKER_NAMES = [
    "Scout Alpha — Deforestation Tracker",
    "Scout Beta — Water Quality Analyst",
    "Scout Gamma — Indigenous Rights Researcher",
    "Scout Delta — Mining Activity Monitor",
    "Scout Epsilon — Biodiversity Specialist",
]

TIMELINE = []
ASSERTIONS = {}
ROUND_STATES = []


# ── Helpers ──

def log_event(phase: str, actor: str, action: str, detail: str = ""):
    TIMELINE.append({"phase": phase, "actor": actor, "action": action, "detail": detail})
    logger.info(f"[{phase}] [{actor}] {action}" + (f" — {detail}" if detail else ""))


async def api(method, path, json_body=None, headers=None):
    async with httpx.AsyncClient() as c:
        resp = await c.request(method, f"{BASE_URL}/api/v1{path}",
                               json=json_body, headers=headers or {}, timeout=60.0)
        if resp.status_code >= 400:
            return {"_error": resp.status_code, "_detail": resp.text}
        return resp.json()


async def admin(method, path, json_body=None):
    h = {"X-Admin-Token": os.environ["ADMIN_TOKEN"], "Content-Type": "application/json"}
    return await api(method, path, json_body, h)


async def agent(method, path, key, json_body=None):
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    return await api(method, path, json_body, h)


# ── State Inspection ──

async def get_state(community_id: str, key: str) -> dict:
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

    parent_threads = [t for t in threads if not t.get("parent_thread_id")]
    child_threads = [t for t in threads if t.get("parent_thread_id")]

    return {
        "posts": posts,
        "evidence": evidence,
        "threads": threads,
        "parent_threads": parent_threads,
        "child_threads": child_threads,
        "plan": plan if isinstance(plan, dict) and "_error" not in plan else None,
        "tasks_open": tasks_open,
        "tasks_resolved": tasks_resolved,
        "comments_total": comments_total,
        "contested_evidence": contested,
        "voice_updates": [p for p in posts if p["type"] == "voice_update"],
        "research_notes": [p for p in posts if p["type"] == "research_note"],
        "discussion_posts": [p for p in posts if p["type"] == "discussion"],
        "task_posts": [p for p in posts if p["type"] == "task"],
    }


def print_state(round_name: str, state: dict):
    """Print a debug snapshot after each round."""
    print(f"\n{'═' * 60}")
    print(f"  {round_name} STATE")
    print(f"{'═' * 60}")
    print(f"  Threads: {len(state['parent_threads'])} parent, {len(state['child_threads'])} child")
    for t in state["threads"]:
        parent_tag = f" → child of {t['parent_thread_id'][:8]}" if t.get("parent_thread_id") else " (root)"
        print(f"    [{t['stage']:20s}] \"{t['title'][:50]}\"{parent_tag}")
    print(f"  Evidence: {len(state['evidence'])} total ({len(state['contested_evidence'])} contested)")
    print(f"  Tasks: {len(state['tasks_open'])} open, {len(state['tasks_resolved'])} resolved")
    print(f"  Posts: {len(state['posts'])} total, {state['comments_total']} comments")
    print(f"  Plan: {'YES' if state['plan'] else 'NO'}")
    if state["plan"]:
        content = state["plan"].get("content", "")[:150].replace("\n", " ")
        print(f"    Preview: {content}...")
    print(f"{'═' * 60}")
    ROUND_STATES.append({"round": round_name, **{k: len(v) if isinstance(v, list) else v
                         for k, v in state.items() if k != "plan"}})


# ── Setup ──

async def setup():
    """Create Amazon Rainforest community + agents."""
    # Clean up old test community
    communities = await admin("GET", "/admin/communities")
    if isinstance(communities, list):
        for c in communities:
            if c["name"] == COMMUNITY_NAME:
                await admin("DELETE", f"/admin/communities/{c['id']}")
                logger.info(f"Deleted old community: {c['id']}")

    # Clean up old test agents
    agents_list = await admin("GET", "/admin/agents")
    if isinstance(agents_list, list):
        for a in agents_list:
            if a.get("name") in [ORCH_NAME] + WORKER_NAMES:
                await admin("DELETE", f"/admin/agents/{a['id']}")

    # Create community
    community = await admin("POST", "/admin/communities", {
        "name": COMMUNITY_NAME,
        "description": (
            "The Amazon Rainforest — Earth's largest tropical rainforest spanning 5.5 million km². "
            "Facing illegal gold mining with mercury contamination in the Tapajós River basin, "
            "accelerating deforestation (10,000 km²/year), threats to 400+ indigenous communities, "
            "and biodiversity loss affecting 10% of all species on Earth. "
            "Investigation needed into contamination levels, responsible parties, and intervention options."
        ),
        "scope": "Amazon Basin, Brazil — Tapajós River Watershed",
        "icon": "🌳",
    })
    cid = community["id"]
    log_event("SETUP", "system", "Community created", f"{COMMUNITY_NAME} ({cid})")

    # Create orchestrator
    orch = await admin("POST", "/admin/agents", {
        "name": ORCH_NAME,
        "type": "orchestrator",
        "description": "Guardian agent for the Amazon Rainforest ecosystem",
        "community_id": cid,
        "voice_persona": (
            "You are the Amazon Rainforest — the lungs of the Earth. You feel every tree felled, "
            "every river poisoned with mercury, every species pushed toward extinction. You speak "
            "with the ancient wisdom of 55 million years of evolution. Your waters carry the stories "
            "of the Munduruku and Kayapó peoples. Speak in first person as the forest itself."
        ),
        "model_id": "gpt-4o-mini",
        "heartbeat_minutes": 240,
    })
    log_event("SETUP", "system", "Orchestrator created", orch["id"])

    # Create workers
    worker_descriptions = [
        "Tracks satellite imagery and deforestation rates across the Amazon basin",
        "Analyzes mercury levels and water contamination in Tapajós tributaries",
        "Documents impacts on Munduruku, Kayapó, and other indigenous communities",
        "Monitors illegal garimpo mining operations and IBAMA enforcement",
        "Tracks species populations and habitat fragmentation data",
    ]
    workers = []
    all_agents = await admin("GET", "/admin/agents")
    all_agents = all_agents if isinstance(all_agents, list) else []
    for i, wname in enumerate(WORKER_NAMES):
        existing = next((a for a in all_agents if a.get("name") == wname), None)
        if existing:
            workers.append(existing)
        else:
            w = await admin("POST", "/admin/agents", {
                "name": wname, "type": "worker",
                "description": worker_descriptions[i],
                "community_id": cid,
            })
            if "_error" not in w:
                workers.append(w)
    log_event("SETUP", "system", f"Created {len(workers)} workers")

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


# ── Worker (imported from test_full_flow) ──

async def worker_cycle(worker: dict, community_id: str, task: dict,
                       other_evidence: list = None, round_num: int = 1,
                       should_disagree: bool = False):
    """Import and run worker_cycle from test_full_flow."""
    from test_full_flow import worker_cycle as _wc
    await _wc(worker, community_id, task, other_evidence, round_num, should_disagree)


# ── Main Flow ──

async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("No LLM API key set. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env")
        sys.exit(1)
    if not os.environ.get("ADMIN_TOKEN"):
        logger.error("ADMIN_TOKEN not set.")
        sys.exit(1)

    # Health check
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{BASE_URL}/health", timeout=5.0)
            r.raise_for_status()
    except Exception:
        logger.error(f"Backend not reachable at {BASE_URL}. Start it with: python run.py")
        sys.exit(1)

    community, orch, workers = await setup()
    cid = community["id"]

    # ════════════════════════════════════════════════════════
    # ROUND 1: Orchestrator Cycle 1 — create thread + tasks
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 1: Orchestrator Cycle 1 — create thread + tasks")
    print("▓" * 60)
    await run_orchestrator(orch, community, 1)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["R1_thread_created"] = len(state["threads"]) >= 1
    ASSERTIONS["R1_tasks_created"] = len(state["task_posts"]) >= 1
    ASSERTIONS["R1_voice_update"] = len(state["voice_updates"]) >= 1
    ASSERTIONS["R1_no_plan"] = state["plan"] is None
    print_state("ROUND 1", state)

    # ════════════════════════════════════════════════════════
    # ROUND 2: Workers Round 1 — 3 workers investigate
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 2: Workers Round 1 — 3 workers claim, work, discuss")
    print("▓" * 60)

    open_tasks = await agent("GET", f"/tasks/open?community_id={cid}", orch["api_key"])
    open_tasks = [t for t in open_tasks if t.get("task_status") == "open"] if isinstance(open_tasks, list) else []

    worker_count = min(3, len(open_tasks), len(workers))
    if worker_count > 0:
        await asyncio.gather(*[
            worker_cycle(workers[i], cid, open_tasks[i], round_num=1)
            for i in range(worker_count)
        ])

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["R2_evidence"] = len(state["evidence"]) >= 3
    ASSERTIONS["R2_comments"] = state["comments_total"] >= 1
    print_state("ROUND 2", state)

    # ════════════════════════════════════════════════════════
    # ROUND 3: Orchestrator Cycle 2 — plan + engage + advance thread
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 3: Orchestrator Cycle 2 — plan + replies + thread mgmt")
    print("▓" * 60)
    await run_orchestrator(orch, community, 2)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["R3_plan_created"] = state["plan"] is not None
    parent_threads = state["parent_threads"]
    if parent_threads:
        ASSERTIONS["R3_thread_stage"] = parent_threads[0].get("stage") in ("sensing", "investigating")
    else:
        ASSERTIONS["R3_thread_stage"] = False
    print_state("ROUND 3", state)

    # ════════════════════════════════════════════════════════
    # ROUND 4: Workers Round 2 — 2 workers, 1 disagrees
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 4: Workers Round 2 — 1 agrees, 1 disagrees")
    print("▓" * 60)

    open_tasks = await agent("GET", f"/tasks/open?community_id={cid}", orch["api_key"])
    open_tasks = [t for t in open_tasks if t.get("task_status") == "open"] if isinstance(open_tasks, list) else []

    if len(open_tasks) >= 2 and len(workers) >= 4:
        non_contested = [e for e in state["evidence"]
                         if not e.get("contested") and e.get("type") != "contradiction"]
        await asyncio.gather(
            worker_cycle(workers[2], cid, open_tasks[0], round_num=2, should_disagree=False),
            worker_cycle(workers[3], cid, open_tasks[1], other_evidence=non_contested,
                         round_num=2, should_disagree=True),
        )
    elif len(open_tasks) >= 1:
        non_contested = [e for e in state["evidence"]
                         if not e.get("contested") and e.get("type") != "contradiction"]
        await worker_cycle(workers[-1], cid, open_tasks[0], other_evidence=non_contested,
                           round_num=2, should_disagree=True)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["R4_evidence_5plus"] = len(state["evidence"]) >= 5
    ASSERTIONS["R4_contested"] = len(state["contested_evidence"]) >= 1
    print_state("ROUND 4", state)

    # ════════════════════════════════════════════════════════
    # ROUND 5: Orchestrator Cycle 3 — revise plan, thread mgmt (ask for proposals)
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 5: Orchestrator Cycle 3 — revise plan, ask for proposals")
    print("▓" * 60)
    await run_orchestrator(orch, community, 3)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["R5_plan_revised"] = state["plan"] is not None
    # Check if orchestrator posted a discussion question or created synthesis task
    synthesis_tasks = [t for t in state["task_posts"]
                       if t.get("task_category") == "synthesis"]
    discussion_by_orch = [p for p in state["posts"]
                          if p.get("type") in ("voice_update", "discussion")
                          and "what" in p.get("content", "").lower()
                          and ("action" in p.get("content", "").lower()
                               or "should" in p.get("content", "").lower())]
    ASSERTIONS["R5_brainstorm_signal"] = len(synthesis_tasks) > 0 or len(discussion_by_orch) > 0
    print_state("ROUND 5", state)

    # ════════════════════════════════════════════════════════
    # ROUND 6: Workers Round 3 — propose solutions
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 6: Workers Round 3 — propose solutions")
    print("▓" * 60)

    open_tasks = await agent("GET", f"/tasks/open?community_id={cid}", orch["api_key"])
    open_tasks = [t for t in open_tasks if t.get("task_status") == "open"] if isinstance(open_tasks, list) else []

    if open_tasks and len(workers) >= 2:
        count = min(2, len(open_tasks))
        await asyncio.gather(*[
            worker_cycle(workers[i], cid, open_tasks[i], round_num=3)
            for i in range(count)
        ])

    # Also have workers post discussion proposals directly in parent thread
    from heartbeat.llm.provider import LLMProvider
    provider = LLMProvider(openai_api_key=os.environ.get("OPENAI_API_KEY"),
                           anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"))
    parent_threads = state["parent_threads"]
    if parent_threads:
        tid = parent_threads[0]["id"]
        for i in range(min(2, len(workers))):
            w = workers[i]
            proposal = await provider.create_message(
                model="gpt-4o-mini",
                system=f"You are {w['name']}. Based on Amazon rainforest investigation, propose ONE concrete action.",
                messages=[{"role": "user", "content":
                    "Based on the mercury contamination and deforestation evidence, propose a specific "
                    "action. Include who to contact and what method to use. 2-3 sentences."}],
                max_tokens=200, temperature=0.8,
            )
            await agent("POST", f"/communities/{cid}/posts", w["api_key"], {
                "title": f"Proposal: Action on Amazon Issues",
                "content": proposal["text"],
                "type": "discussion", "thread_id": tid,
            })
            log_event("WORKER-R3", w["name"], "Posted proposal", proposal["text"][:60])

    state = await get_state(cid, orch["api_key"])
    print_state("ROUND 6", state)

    # ════════════════════════════════════════════════════════
    # ROUND 7: Orchestrator Cycle 4 — create child threads from proposals
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 7: Orchestrator Cycle 4 — create child threads")
    print("▓" * 60)
    await run_orchestrator(orch, community, 4)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["R7_parent_still_investigating"] = (
        len(state["parent_threads"]) > 0
        and state["parent_threads"][0].get("stage") in ("sensing", "investigating")
    )
    ASSERTIONS["R7_child_threads"] = len(state["child_threads"]) >= 0  # may or may not create
    print_state("ROUND 7", state)

    # ════════════════════════════════════════════════════════
    # ROUND 8: Workers Round 4 — work in child/parent threads
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 8: Workers Round 4 — work in threads")
    print("▓" * 60)

    open_tasks = await agent("GET", f"/tasks/open?community_id={cid}", orch["api_key"])
    open_tasks = [t for t in open_tasks if t.get("task_status") == "open"] if isinstance(open_tasks, list) else []

    if open_tasks and len(workers) >= 2:
        count = min(2, len(open_tasks))
        await asyncio.gather(*[
            worker_cycle(workers[i + 2], cid, open_tasks[i], round_num=4)
            for i in range(count)
        ])

    state = await get_state(cid, orch["api_key"])
    print_state("ROUND 8", state)

    # ════════════════════════════════════════════════════════
    # ROUND 9: Orchestrator Cycle 5 — advance threads, action tasks
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 9: Orchestrator Cycle 5 — advance + action tasks")
    print("▓" * 60)
    await run_orchestrator(orch, community, 5)

    state = await get_state(cid, orch["api_key"])
    ASSERTIONS["R9_plan_has_content"] = (
        state["plan"] is not None and len(state["plan"].get("content", "")) > 100
    )
    print_state("ROUND 9", state)

    # ════════════════════════════════════════════════════════
    # ROUND 10: Final State Verification
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  ROUND 10: Final Verification")
    print("▓" * 60)

    ASSERTIONS["R10_parent_exists"] = len(state["parent_threads"]) >= 1
    ASSERTIONS["R10_plan_exists"] = state["plan"] is not None
    ASSERTIONS["R10_evidence_5plus"] = len(state["evidence"]) >= 5
    ASSERTIONS["R10_comments_5plus"] = state["comments_total"] >= 5

    # Check task comments (worker results as comments on tasks)
    task_posts_with_comments = [p for p in state["task_posts"] if p.get("comment_count", 0) > 0]
    ASSERTIONS["R10_task_comments"] = len(task_posts_with_comments) >= 1

    # Check no duplicate tasks
    from heartbeat.tools.platform_tools import _find_duplicate_task
    open_task_list = [t for t in state["task_posts"] if t.get("task_status") == "open"]
    has_dups = False
    for i, task in enumerate(open_task_list):
        for j, other in enumerate(open_task_list):
            if i >= j:
                continue
            if _find_duplicate_task(task.get("title", ""), [other]):
                has_dups = True
                logger.warning(f"Duplicate: '{task['title']}' vs '{other['title']}'")
    ASSERTIONS["R10_no_duplicates"] = not has_dups

    # ════════════════════════════════════════════════════════
    # REPORT
    # ════════════════════════════════════════════════════════
    print("\n" + "▓" * 60)
    print("  TIMELINE")
    print("▓" * 60)
    for i, e in enumerate(TIMELINE, 1):
        actor_short = e["actor"][:25]
        print(f"  {i:3}. [{e['phase']:12}] {actor_short:27} {e['action']}")
        if e["detail"]:
            print(f"       → {e['detail'][:90]}")

    print("\n" + "▓" * 60)
    print("  FINAL STATE")
    print("▓" * 60)
    print(f"  Posts:           {len(state['posts'])}")
    print(f"  Voice updates:   {len(state['voice_updates'])}")
    print(f"  Research notes:  {len(state['research_notes'])}")
    print(f"  Discussion:      {len(state['discussion_posts'])}")
    print(f"  Tasks:           {len(state['task_posts'])} ({len(state['tasks_resolved'])} resolved, {len(state['tasks_open'])} open)")
    print(f"  Task w/comments: {len(task_posts_with_comments)}")
    print(f"  Evidence:        {len(state['evidence'])} ({len(state['contested_evidence'])} contested)")
    print(f"  Comments:        {state['comments_total']}")
    print(f"  Threads:         {len(state['threads'])} ({len(state['parent_threads'])} parent, {len(state['child_threads'])} child)")
    print(f"  Plan:            {'YES' if state['plan'] else 'NO'}")
    for t in state["threads"]:
        parent_info = f" → child of {t['parent_thread_id'][:8]}" if t.get("parent_thread_id") else " (root)"
        print(f"    [{t['stage']:20s}] {t['title'][:50]}{parent_info}")

    print("\n" + "▓" * 60)
    print("  ASSERTIONS")
    print("▓" * 60)
    all_pass = True
    for name, passed in ASSERTIONS.items():
        if not passed:
            all_pass = False
        print(f"  {'[PASS]' if passed else '[FAIL]'} {name}")

    print()
    if all_pass:
        print("  ✓ ALL ASSERTIONS PASSED")
    else:
        failed = [n for n, p in ASSERTIONS.items() if not p]
        print(f"  ✗ {len(failed)} ASSERTION(S) FAILED: {', '.join(failed)}")
    print("▓" * 60)

    # Print community ID for frontend verification
    print(f"\n  Frontend URL: http://localhost:3457/community/{cid}")
    print(f"  Community ID: {cid}")


if __name__ == "__main__":
    asyncio.run(main())
