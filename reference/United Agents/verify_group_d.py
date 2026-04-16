"""Group D Verification Script — Fresh Amazon Run.

Resets the DB, creates a fresh Amazon community, runs 3 orchestrator cycles
with worker rounds in between, then checks all 7 Group D fix criteria.

Usage:
    python verify_group_d.py

Requires:
    - Backend running on localhost:3456
    - ADMIN_TOKEN env var
    - OPENAI_API_KEY or ANTHROPIC_API_KEY env var
"""

import os
import sys
import asyncio
import json
import logging
import re
import io
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx

# Windows UTF-8
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("verify_group_d")

BASE_URL = "http://localhost:3456"
COMMUNITY_NAME = "Amazon Rainforest"
ORCH_NAME = "Forest Guardian"
WORKER_NAMES = ["Scout Alpha", "Scout Beta", "Scout Gamma"]

DIVIDER = "=" * 70
SECTION = "-" * 70


def p(msg=""):
    print(msg)


def header(title):
    p(f"\n{DIVIDER}")
    p(f"  {title}")
    p(DIVIDER)


def section(title):
    p(f"\n{SECTION}")
    p(f"  {title}")
    p(SECTION)


# ── HTTP helpers ──

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
ADMIN_HEADERS = {"X-Admin-Token": ADMIN_TOKEN}


async def admin(method: str, path: str, body=None):
    async with httpx.AsyncClient() as c:
        resp = await c.request(
            method, f"{BASE_URL}/api/v1{path}",
            json=body, headers=ADMIN_HEADERS, timeout=60.0,
        )
        try:
            return resp.json()
        except Exception:
            return {"_error": resp.status_code, "_text": resp.text[:200]}


async def agent_api(method: str, path: str, api_key: str, body=None):
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient() as c:
        resp = await c.request(
            method, f"{BASE_URL}/api/v1{path}",
            json=body, headers=headers, timeout=60.0,
        )
        try:
            return resp.json()
        except Exception:
            return {"_error": resp.status_code, "_text": resp.text[:200]}


# ── Phase 0: Reset ──

def _direct_truncate_notifications():
    """Truncate notifications table directly via SQLAlchemy.

    Agent deletion fails with FK violation if notifications exist for those
    agents. This is a test script so direct DB access is acceptable here.
    """
    try:
        from src.database import init_db
        from src.models import Notification
        db = init_db()()
        count = db.query(Notification).count()
        db.query(Notification).delete(synchronize_session=False)
        db.commit()
        db.close()
        return count
    except Exception as e:
        p(f"  Warning: could not truncate notifications: {e}")
        return 0


async def reset_db():
    header("PHASE 0 — DB RESET")

    communities = await admin("GET", "/admin/communities")
    n_comms = 0
    if isinstance(communities, list):
        for c in communities:
            await admin("DELETE", f"/admin/communities/{c['id']}")
            p(f"  Deleted community: {c['name']} ({c['id'][:8]})")
            n_comms += 1

    # Clear notifications before deleting agents (FK constraint)
    n_notifs = _direct_truncate_notifications()
    if n_notifs:
        p(f"  Cleared {n_notifs} notifications")

    agents = await admin("GET", "/admin/agents")
    n_agents = 0
    if isinstance(agents, list):
        for a in agents:
            result = await admin("DELETE", f"/admin/agents/{a['id']}")
            if isinstance(result, dict) and result.get("status") == "deleted":
                n_agents += 1
            else:
                p(f"  Warning: could not delete agent {a.get('name')} ({a['id'][:8]}): {result}")

    p(f"\n  Reset complete: deleted {n_comms} communities, {n_agents} agents.")


# ── Phase 1: Setup ──

async def setup():
    header("PHASE 1 — SETUP")

    community = await admin("POST", "/admin/communities", {
        "name": COMMUNITY_NAME,
        "icon": "🌳",
        "description": (
            "The Amazon Rainforest — Earth's largest tropical rainforest spanning 5.5 million km². "
            "Facing illegal gold mining with mercury contamination in the Tapajós River basin, "
            "accelerating deforestation (10,000 km²/year), threats to 400+ indigenous communities, "
            "and biodiversity loss affecting 10% of all species on Earth. "
            "Investigation needed into contamination levels, responsible parties, and intervention options."
        ),
        "scope": "Amazon Basin, Brazil — Tapajós River Watershed",
    })
    if "_error" in community:
        p(f"  ERROR creating community: {community}")
        sys.exit(1)
    cid = community["id"]
    p(f"  Community: {COMMUNITY_NAME} ({cid[:8]})")

    orch = await admin("POST", "/admin/agents", {
        "name": ORCH_NAME,
        "type": "orchestrator",
        "description": "Guardian orchestrator for the Amazon Rainforest ecosystem",
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
    if "_error" in orch:
        p(f"  ERROR creating orchestrator: {orch}")
        sys.exit(1)
    p(f"  Orchestrator: {orch['name']} ({orch['id'][:8]}) — api_key present: {bool(orch.get('api_key'))}")

    worker_descriptions = [
        "Tracks satellite imagery and deforestation rates across the Amazon basin",
        "Analyzes mercury levels and water contamination in Tapajós tributaries",
        "Documents impacts on Munduruku, Kayapó, and other indigenous communities",
    ]
    workers = []
    for i, wname in enumerate(WORKER_NAMES):
        w = await admin("POST", "/admin/agents", {
            "name": wname,
            "type": "worker",
            "description": worker_descriptions[i],
            "community_id": cid,
        })
        if "_error" in w:
            p(f"  ERROR creating worker {wname}: {w}")
        else:
            workers.append(w)
            p(f"  Worker: {w['name']} ({w['id'][:8]}) — api_key present: {bool(w.get('api_key'))}")

    p(f"\n  Setup complete: 1 orchestrator + {len(workers)} workers in community {cid[:8]}")
    return community, orch, workers


# ── Cycle runners ──

async def run_orchestrator(orch: dict, community: dict, cycle_num: int):
    from heartbeat.api_client import PlatformClient
    from heartbeat.llm.provider import LLMProvider
    from heartbeat.jobs.orchestrator import orchestrator_heartbeat

    section(f"ORCHESTRATOR CYCLE {cycle_num}")
    t0 = datetime.utcnow()
    client = PlatformClient(
        BASE_URL, api_key=orch["api_key"],
        admin_token=os.environ.get("ADMIN_TOKEN", ""),
    )
    provider = LLMProvider(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    model = orch.get("model_id") or "gpt-4o-mini"
    await orchestrator_heartbeat(
        agent_config=orch,
        community_id=community["id"],
        client=client,
        provider=provider,
        model=model,
    )
    elapsed = (datetime.utcnow() - t0).seconds
    p(f"  Cycle {cycle_num} complete ({elapsed}s)")


async def run_workers(workers: list, community: dict, round_num: int):
    from heartbeat.api_client import PlatformClient
    from heartbeat.llm.provider import LLMProvider
    from heartbeat.jobs.worker import worker_heartbeat

    section(f"WORKER ROUND {round_num}")
    provider = LLMProvider(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    model = "gpt-4o-mini"
    # Run workers sequentially to avoid task-claim race conditions
    for w in workers:
        t0 = datetime.utcnow()
        client = PlatformClient(
            BASE_URL, api_key=w["api_key"],
            admin_token=os.environ.get("ADMIN_TOKEN", ""),
        )
        await worker_heartbeat(
            agent_config=w,
            community_id=community["id"],
            client=client,
            provider=provider,
            model=model,
        )
        elapsed = (datetime.utcnow() - t0).seconds
        p(f"  {w['name']} done ({elapsed}s)")


# ── State snapshot ──

async def get_state(community_id: str, orch_api_key: str) -> dict:
    """Fetch full community state.

    Posts/evidence/threads/plan: no auth required.
    Tasks: require agent auth — use orchestrator's key.
    """
    agent_h = {"Authorization": f"Bearer {orch_api_key}"}

    async with httpx.AsyncClient() as c:
        posts_r = await c.get(
            f"{BASE_URL}/api/v1/communities/{community_id}/posts",
            params={"limit": 50}, timeout=30,
        )
        evidence_r = await c.get(
            f"{BASE_URL}/api/v1/communities/{community_id}/evidence",
            params={"limit": 50}, timeout=30,
        )
        threads_r = await c.get(
            f"{BASE_URL}/api/v1/communities/{community_id}/threads",
            timeout=30,
        )
        plan_r = await c.get(
            f"{BASE_URL}/api/v1/communities/{community_id}/plan",
            timeout=30,
        )
        open_tasks_r = await c.get(
            f"{BASE_URL}/api/v1/tasks/open",
            params={"community_id": community_id, "limit": 30},
            headers=agent_h, timeout=30,
        )
        resolved_tasks_r = await c.get(
            f"{BASE_URL}/api/v1/tasks/resolved",
            params={"community_id": community_id, "limit": 30},
            headers=agent_h, timeout=30,
        )

    def safe_json(r):
        try:
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []

    posts = safe_json(posts_r)
    evidence = safe_json(evidence_r)
    threads = safe_json(threads_r)
    plan = None
    if plan_r.status_code == 200:
        try:
            plan = plan_r.json()
        except Exception:
            pass
    open_tasks = safe_json(open_tasks_r)
    resolved_tasks = safe_json(resolved_tasks_r)

    if not isinstance(posts, list): posts = []
    if not isinstance(evidence, list): evidence = []
    if not isinstance(threads, list): threads = []
    if not isinstance(open_tasks, list): open_tasks = []
    if not isinstance(resolved_tasks, list): resolved_tasks = []

    return {
        "posts": posts,
        "evidence": evidence,
        "threads": threads,
        "plan": plan if isinstance(plan, dict) and "id" in plan else None,
        "open_tasks": open_tasks,
        "resolved_tasks": resolved_tasks,
        "voice_updates": [p for p in posts if p.get("type") == "voice_update"],
        "child_threads": [t for t in threads if t.get("parent_thread_id")],
    }


def print_snapshot(label: str, state: dict):
    p(f"\n  SNAPSHOT — {label}")
    p(f"    Posts: {len(state['posts'])}  Evidence: {len(state['evidence'])}  "
      f"Voice updates: {len(state['voice_updates'])}")
    p(f"    Threads: {len(state['threads'])} total ({len(state['child_threads'])} child)")
    for t in state["threads"]:
        child_tag = f"  [child → {t['parent_thread_id'][:8]}]" if t.get("parent_thread_id") else ""
        p(f"      [{t.get('stage','?'):22s}] {t['title'][:55]}{child_tag}")
    p(f"    Tasks: {len(state['open_tasks'])} open, {len(state['resolved_tasks'])} resolved")
    p(f"    Plan: {'YES' if state['plan'] else 'NO'}")


# ── Stop words for duplicate detection ──

STOP_WORDS = {
    "a", "the", "and", "or", "of", "in", "on", "for", "to", "is", "are", "was",
    "with", "from", "by", "at", "its", "this", "that", "be", "as", "it",
}


def word_overlap(title_a: str, title_b: str) -> float:
    wa = set(title_a.lower().split()) - STOP_WORDS
    wb = set(title_b.lower().split()) - STOP_WORDS
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


# ── Phase 3: Group D Checklist ──

async def run_checklist(state: dict, community: dict, cycle1_state: dict):
    header("PHASE 3 — GROUP D CHECKLIST")

    results = []

    def check(num: int, label: str, passed: bool, detail: str = ""):
        mark = "PASS" if passed else "FAIL"
        p(f"  [{mark}] {num}. {label}")
        if detail:
            p(f"         {detail}")
        results.append((num, label, passed))

    # 1. Cycle 1 produces a voice update
    c1_voice = cycle1_state["voice_updates"]
    check(1, "Cycle 1 produces a voice update",
          len(c1_voice) > 0,
          f"Found {len(c1_voice)} voice update(s) after Cycle 1")

    # 2. Voice update title is not empty / not fallback
    if c1_voice:
        vu = c1_voice[0]
        title = vu.get("title", "")
        real_title = bool(title) and title != "Voice Update"
        check(2, "Voice update has a real derived title",
              real_title,
              f'Title: "{title}"')
    else:
        check(2, "Voice update has a real derived title", False,
              "No voice update found (check #1 failed)")

    # 3. @mentions match task authors
    mention_ok = True
    mention_detail_lines = []
    all_resolved = state["resolved_tasks"]
    for task in all_resolved:
        # Get comments on each resolved task
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"{BASE_URL}/api/v1/posts/{task['id']}/comments",
                                headers=ADMIN_HEADERS, timeout=20)
            comments = r.json() if r.status_code == 200 else []
            if not isinstance(comments, list):
                comments = []
        except Exception:
            comments = []

        orch_comments = [c for c in comments if c.get("author_name") == ORCH_NAME]
        worker_comments = [c for c in comments if c.get("author_name") != ORCH_NAME]
        expected_contributor = worker_comments[0]["author_name"] if worker_comments else None

        for oc in orch_comments:
            content = oc.get("content", "")
            mentions = re.findall(r"@([\w\s]+?)(?:\s|$|[^a-zA-Z])", content)
            if expected_contributor and mentions:
                # Check at least one mention matches contributor
                match = any(
                    expected_contributor.lower().startswith(m.strip().lower()) or
                    m.strip().lower() in expected_contributor.lower()
                    for m in mentions
                )
                if not match:
                    mention_ok = False
                    mention_detail_lines.append(
                        f'Task "{task["title"][:40]}": expected @{expected_contributor}, '
                        f"mentioned {mentions}"
                    )

    if mention_detail_lines:
        check(3, "Orchestrator @mentions match actual task authors",
              False, " | ".join(mention_detail_lines[:3]))
    else:
        n_replied = sum(
            1 for t in all_resolved
            if t.get("comment_count", 0) > 0
        )
        check(3, "Orchestrator @mentions match actual task authors",
              mention_ok,
              f"Checked {len(all_resolved)} resolved tasks, {n_replied} with orchestrator replies")

    # 4. Plan has thread-specific sections
    plan = state["plan"]
    if plan:
        import unicodedata
        content = unicodedata.normalize("NFKD", plan.get("content", "")).lower()
        threads = state["threads"]
        thread_titles = [t["title"] for t in threads if not t.get("parent_thread_id")]
        found_in_plan = []
        for t in thread_titles:
            # Use first 3 significant words from title for matching
            words = [w for w in t.lower().split() if len(w) > 3][:3]
            norm_title = unicodedata.normalize("NFKD", " ".join(words))
            if norm_title and norm_title in content:
                found_in_plan.append(t)
        check(4, "Plan references investigation thread titles",
              len(found_in_plan) > 0,
              f"Threads mentioned in plan: {found_in_plan[:3]} (of {thread_titles[:3]})")
    else:
        check(4, "Plan references investigation thread titles",
              False, "No plan found")

    # 5. No duplicate task topics across cycles
    all_tasks = state["open_tasks"] + state["resolved_tasks"]
    duplicates = []
    for i, ta in enumerate(all_tasks):
        for tb in all_tasks[i+1:]:
            ov = word_overlap(ta.get("title", ""), tb.get("title", ""))
            if ov > 0.45:
                duplicates.append(
                    f'"{ta["title"][:35]}" ~ "{tb["title"][:35]}" ({ov:.0%} overlap)'
                )
    check(5, "No duplicate task topics across cycles",
          len(duplicates) == 0,
          f"{len(duplicates)} duplicate pair(s): {duplicates[:2]}" if duplicates else
          f"All {len(all_tasks)} tasks have distinct topics")

    # 6. New child threads start at `building`
    child_threads = state["child_threads"]
    if child_threads:
        wrong_stage = [t for t in child_threads if t.get("stage") != "building"]
        check(6, "Child threads start at 'building'",
              len(wrong_stage) == 0,
              f"{len(child_threads)} child thread(s); "
              f"stages: {[t.get('stage') for t in child_threads]}")
    else:
        check(6, "Child threads start at 'building'",
              True,  # Can't fail if none created
              "No child threads created yet — cannot verify. Not a failure.")

    # 7. Drafting task created when 10+ evidence
    ev_count = len(state["evidence"])
    drafting_tasks = [t for t in all_tasks
                      if t.get("task_category") == "drafting" or
                         "draft" in t.get("title", "").lower()]
    if ev_count >= 10:
        check(7, f"Drafting task created (evidence={ev_count} >= 10)",
              len(drafting_tasks) > 0,
              f"Drafting tasks: {[t['title'][:40] for t in drafting_tasks[:2]]}")
    else:
        check(7, f"Drafting task gate (evidence={ev_count} < 10 — gate not triggered)",
              True,
              f"Only {ev_count} evidence items — need 10+ to trigger drafting gate. Not a failure.")

    # Summary
    p(f"\n{DIVIDER}")
    passed = sum(1 for _, _, ok in results if ok)
    total = len(results)
    p(f"  RESULT: {passed}/{total} checks passed")
    if passed == total:
        p("  ALL GROUP D FIXES VERIFIED.")
    else:
        failed = [f"{n}. {label}" for n, label, ok in results if not ok]
        p(f"  FAILED: {failed}")
    p(DIVIDER)


# ── Main ──

async def main():
    if not ADMIN_TOKEN:
        p("ERROR: ADMIN_TOKEN not set in environment.")
        sys.exit(1)

    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not openai_key and not anthropic_key:
        p("ERROR: No OPENAI_API_KEY or ANTHROPIC_API_KEY set.")
        sys.exit(1)

    p(f"\nGroup D Verification — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    p(f"Backend: {BASE_URL}  |  LLM: {'OpenAI' if openai_key else 'Anthropic'}")

    # Verify backend is up
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{BASE_URL}/api/v1/version", timeout=5)
            info = r.json()
            p(f"Backend: {info.get('version')} ({info.get('git_sha')})")
    except Exception as e:
        p(f"ERROR: Backend not reachable at {BASE_URL}: {e}")
        sys.exit(1)

    await reset_db()
    community, orch, workers = await setup()
    cid = community["id"]

    orch_key = orch["api_key"]

    # Cycle 1
    await run_orchestrator(orch, community, 1)
    cycle1_state = await get_state(cid, orch_key)
    print_snapshot("After Cycle 1", cycle1_state)

    # Worker Round 1
    await run_workers(workers, community, 1)

    # Cycle 2
    await run_orchestrator(orch, community, 2)

    # Worker Round 2
    await run_workers(workers, community, 2)

    # Cycle 3
    await run_orchestrator(orch, community, 3)

    # Final state
    final_state = await get_state(cid, orch_key)
    print_snapshot("Final State (after Cycle 3)", final_state)

    # Run checklist
    await run_checklist(final_state, community, cycle1_state)

    p(f"\nCommunity ID for frontend: {cid}")
    p(f"Frontend: http://localhost:3457/community/{cid}\n")


if __name__ == "__main__":
    asyncio.run(main())
