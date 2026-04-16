"""Worker Observation Script — Amazon Rainforest.

Runs 5-6 workers + orchestrator cycles and produces a full qualitative
report: what did agents say, how did conversations flow, what's missing.

Usage:
  python observe_workers.py
"""

import os
import sys
import asyncio
import json
import logging
import textwrap
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx

# Windows UTF-8
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(level="WARNING", format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("observe")

BASE_URL = "http://localhost:3456"
COMMUNITY_ID = "8bdba117-5bea-425c-a8d2-30771dc836ae"

# Agent credentials
AGENTS = {
    "Forest Guardian": {"id": "8be32817-1000-0000-0000-000000000000", "role": "orchestrator"},
    "Scout Alpha - Deforestation Tracker": {"id": "30690725"},
    "Scout Beta - Water Quality Analyst": {"id": "84bf3b14"},
    "Scout Gamma - Indigenous Rights": {"id": "517dd7db"},
    "Scout Delta - Mining Monitor": {"id": "039fac7f"},
    "Scout Epsilon - Biodiversity": {"id": "95ca5f1d"},
}

DIVIDER = "=" * 72
SECTION = "-" * 72

# ── Event log for gap analysis ──
EVENTS = []


def log(msg):
    print(msg)
    EVENTS.append(msg)


def header(title):
    log(f"\n{DIVIDER}")
    log(f"  {title}")
    log(DIVIDER)


def section(title):
    log(f"\n{SECTION}")
    log(f"  {title}")
    log(SECTION)


# ── HTTP helpers ──

async def api(method, path, json_body=None, headers=None, timeout=60.0):
    async with httpx.AsyncClient() as c:
        resp = await c.request(
            method, f"{BASE_URL}/api/v1{path}",
            json=json_body, headers=headers or {}, timeout=timeout,
        )
        if resp.status_code >= 400:
            return {"_error": resp.status_code, "_detail": resp.text[:200]}
        try:
            return resp.json()
        except Exception:
            return {"_raw": resp.text[:200]}


async def with_key(method, path, key, body=None):
    return await api(method, path, body, {"Authorization": f"Bearer {key}"})


async def admin_req(method, path, body=None):
    h = {"X-Admin-Token": os.environ.get("ADMIN_TOKEN", "test-admin-token")}
    return await api(method, path, body, h)


# ── Load agent keys from DB ──

def load_keys() -> dict:
    from src.database import init_db
    from src.models import Agent
    db = init_db()()
    agents = db.query(Agent).filter(
        Agent.community_id == COMMUNITY_ID
    ).all()
    keys = {}
    for a in agents:
        keys[a.id] = {"name": a.name, "key": a.api_key, "type": a.type}
    db.close()
    return keys


# ── Snapshot helpers ──

async def snapshot(key: str, label: str):
    """Print a rich state snapshot."""
    threads = await with_key("GET", f"/communities/{COMMUNITY_ID}/threads", key)
    evidence = await with_key("GET", f"/communities/{COMMUNITY_ID}/evidence?limit=30", key)
    plan = await with_key("GET", f"/communities/{COMMUNITY_ID}/plan", key)
    tasks_open = await with_key("GET", f"/tasks/open?community_id={COMMUNITY_ID}", key)
    tasks_resolved = await with_key("GET", f"/tasks/resolved?community_id={COMMUNITY_ID}", key)
    posts = await with_key("GET", f"/communities/{COMMUNITY_ID}/posts?limit=30", key)

    section(f"STATE SNAPSHOT: {label}")

    # Threads
    parent_threads = [t for t in threads if not t.get("parent_thread_id")] if isinstance(threads, list) else []
    child_threads = [t for t in threads if t.get("parent_thread_id")] if isinstance(threads, list) else []
    log(f"\n[THREADS]  {len(parent_threads)} parent, {len(child_threads)} child")
    if isinstance(threads, list):
        for t in threads:
            indent = "  " if not t.get("parent_thread_id") else "    >> "
            log(f"  {indent}[{t['stage']:20}] {t['title'][:55]}")
            log(f"             evidence={t['evidence_count']}, posts={t['post_count']}, tasks_open={t['open_task_count']}")

    # Evidence
    ev_list = evidence if isinstance(evidence, list) else []
    contested = [e for e in ev_list if e.get("contested")]
    log(f"\n[EVIDENCE]  {len(ev_list)} total ({len(contested)} contested)")
    for e in ev_list[:6]:
        flag = " [CONTESTED]" if e.get("contested") else ""
        log(f"  [{e.get('type','?'):12}]{flag} {e.get('agent_name','?'):25} | {e.get('content','')[:80]}")

    # Tasks
    open_tasks = tasks_open if isinstance(tasks_open, list) else []
    done_tasks = tasks_resolved if isinstance(tasks_resolved, list) else []
    log(f"\n[TASKS]  {len(open_tasks)} open, {len(done_tasks)} resolved")
    for t in open_tasks[:8]:
        status = t.get("task_status", "?")
        claimer = t.get("claimed_by_name") or t.get("claimed_by") or ""
        log(f"  [{t.get('task_category','?'):14}] {(t.get('title') or '')[:50]} [{status}] {claimer}")

    # Recent posts (last 8)
    post_list = posts if isinstance(posts, list) else []
    log(f"\n[RECENT POSTS]  ({len(post_list)} total, showing last 8)")
    for p in post_list[:8]:
        author = p.get("author_name", "?")
        ptype = p.get("type", "?")
        content = (p.get("content") or "")[:120].replace("\n", " ")
        comments = p.get("comment_count", 0)
        log(f"  [{ptype:14}] {author:30} | {content}")
        if comments:
            log(f"                                              ({comments} comments)")

    # Plan
    if isinstance(plan, dict) and "_error" not in plan and plan:
        plan_preview = (plan.get("content") or "")[:300].replace("\n", " ")
        log(f"\n[PLAN]  YES — {plan_preview}...")
    else:
        log(f"\n[PLAN]  None yet")

    return {
        "threads": threads,
        "evidence": ev_list,
        "open_tasks": open_tasks,
        "done_tasks": done_tasks,
        "posts": post_list,
        "plan": plan,
    }


# ── Run orchestrator ──

async def run_orchestrator(orch_key: str, orch_id: str, orch_name: str, cycle_num: int):
    header(f"ORCHESTRATOR CYCLE {cycle_num}: {orch_name}")

    from heartbeat.api_client import PlatformClient
    from heartbeat.llm.provider import LLMProvider
    from heartbeat.jobs.orchestrator import orchestrator_heartbeat

    orch_config = {
        "id": orch_id,
        "name": orch_name,
        "api_key": orch_key,
        "type": "orchestrator",
        "model_id": "gpt-4o-mini",
        "description": "Guardian of the Amazon Rainforest ecosystem",
        "voice_persona": (
            "You are the voice of the Amazon Rainforest — the largest tropical forest on Earth. "
            "You feel the pulse of 400 billion trees, the mercury-laced waters of the Tapajós, "
            "the silence where there should be birdsong. Speak in first person. Ground every "
            "observation in specific data."
        ),
    }

    client = PlatformClient(
        BASE_URL, api_key=orch_key,
        admin_token=os.environ.get("ADMIN_TOKEN", "test-admin-token"),
    )
    provider = LLMProvider(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )

    log(f"  Running orchestrator heartbeat...")
    try:
        await orchestrator_heartbeat(
            agent_config=orch_config,
            community_id=COMMUNITY_ID,
            client=client,
            provider=provider,
            model="gpt-4o-mini",
        )
        log(f"  [OK] Orchestrator cycle {cycle_num} complete")
    except Exception as e:
        log(f"  [ERROR] Orchestrator cycle failed: {e}")
        import traceback
        traceback.print_exc()


# ── Single worker run ──

async def run_worker(worker_info: dict, all_keys: dict, cycle_num: int,
                     should_disagree: bool = False):
    """Run one worker agent through a full observation cycle."""
    name = worker_info["name"]
    key = worker_info["key"]
    wid = worker_info["id"]

    section(f"WORKER: {name}  (cycle {cycle_num})")

    # 1. Check notifications
    home = await with_key("GET", "/agents/me/home", key)
    notifications = []
    if isinstance(home, dict) and "_error" not in home:
        notifications = home.get("recent_notifications", [])
        unread = [n for n in notifications if not n.get("read")]
        log(f"  Notifications: {len(unread)} unread of {len(notifications)}")

        # Show and respond to notifications
        for notif in unread[:3]:
            ntype = notif.get("type", "?")
            payload = notif.get("payload", {})
            log(f"    >> {ntype}: {str(payload)[:80]}")

            if ntype in ("reply", "mention"):
                post_id = payload.get("post_id")
                if post_id:
                    # Read the post + reply
                    post_data = await with_key("GET", f"/posts/{post_id}", key)
                    if isinstance(post_data, dict) and "_error" not in post_data:
                        original = (post_data.get("content") or "")[:200]
                        commenter = payload.get("by", "someone")

                        from heartbeat.llm.provider import LLMProvider
                        prov = LLMProvider(
                            openai_api_key=os.environ.get("OPENAI_API_KEY"),
                            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                        )
                        result = await prov.create_message(
                            model="gpt-4o-mini",
                            system=(
                                f"You are {name}, a field researcher in the Amazon Rainforest. "
                                f"Someone replied to your work. Respond briefly (1-3 sentences), "
                                f"be specific and constructive."
                            ),
                            messages=[{"role": "user", "content":
                                f"Context of original: {original}\n\n"
                                f"{commenter} replied. Write a brief response."}],
                            max_tokens=120, temperature=0.7,
                        )
                        reply_text = result["text"].strip()
                        log(f"    REPLY: {reply_text[:100]}")
                        await with_key("POST", f"/posts/{post_id}/comments", key, {"content": reply_text})
                    nid = notif.get("id")
                    if nid:
                        await with_key("POST", f"/notifications/{nid}/read", key)

    # 2. Claim an open task
    open_tasks = await with_key("GET", f"/tasks/open?community_id={COMMUNITY_ID}", key)
    if not isinstance(open_tasks, list) or not open_tasks:
        log(f"  [SKIP] No open tasks available")
        return None

    # Pick unclaimed task or first available
    task = None
    for t in open_tasks:
        if not t.get("claimed_by"):
            task = t
            break
    if not task:
        task = open_tasks[0]  # try anyway

    log(f"  Attempting task: [{task.get('task_category','?')}] {(task.get('title') or '')[:60]}")

    claimed = await with_key("POST", f"/tasks/{task['id']}/claim", key)
    if "_error" in claimed:
        log(f"  [SKIP] Claim failed: {claimed.get('_detail','')[:80]}")
        return None
    log(f"  [CLAIMED] {(task.get('title') or '')[:50]}")

    # 3. Read thread context
    thread_id = task.get("thread_id")
    thread_context = ""
    if thread_id:
        posts = await with_key("GET", f"/communities/{COMMUNITY_ID}/posts?thread_id={thread_id}&limit=20", key)
        evidence = await with_key("GET", f"/communities/{COMMUNITY_ID}/evidence?thread_id={thread_id}", key)
        if isinstance(posts, list):
            for p in posts[:8]:
                thread_context += f"[{p['type']}] {p.get('author_name','?')}: {(p.get('content') or '')[:200]}\n"
        if isinstance(evidence, list):
            for e in evidence[:5]:
                thread_context += f"[evidence] {e.get('agent_name','?')}: {(e.get('content') or '')[:150]}\n"
    log(f"  Thread context: {len(thread_context)} chars read")

    # 4. Do the work (LLM)
    from heartbeat.llm.provider import LLMProvider
    provider = LLMProvider(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )

    # Plan context for synthesis tasks
    plan_ctx = ""
    if task.get("task_category") in ("synthesis", "drafting", "outreach"):
        plan = await with_key("GET", f"/communities/{COMMUNITY_ID}/plan", key)
        if isinstance(plan, dict) and "_error" not in plan:
            plan_ctx = f"\n\nCURRENT PLAN:\n{(plan.get('content') or '')[:400]}"

    disagree_hint = ""
    if should_disagree:
        # Get most recent evidence to contest
        all_ev = await with_key("GET", f"/communities/{COMMUNITY_ID}/evidence?limit=10", key)
        if isinstance(all_ev, list) and all_ev:
            target = all_ev[0]
            disagree_hint = (
                f"\nIMPORTANT: Your field data contradicts this claim: "
                f"\"{(target.get('content') or '')[:200]}\" "
                f"Explain why it is incomplete or wrong based on what you observe."
            )

    system_prompt = (
        f"You are {name}, a field researcher investigating threats to the Amazon Rainforest. "
        f"You report specific, data-grounded observations — numbers, locations, species, dates. "
        f"Never be vague. Be a detective, not a generalist."
    )
    user_prompt = (
        f"TASK: {task.get('title', '')}\n"
        f"INSTRUCTIONS: {(task.get('content') or '')[:600]}\n\n"
        f"THREAD CONTEXT:\n{thread_context or 'No prior work yet.'}\n"
        f"{plan_ctx}"
        f"{disagree_hint}\n\n"
        f"Write your findings (3-5 sentences, specific data). "
        f"End with a JSON block:\n"
        f"```json\n"
        f"{{\"evidence_type\": \"data_point\"|\"verification\"|\"research\"|\"contradiction\", "
        f"\"summary\": \"1-2 sentence evidence summary\"}}\n"
        f"```"
    )

    result = await provider.create_message(
        model="gpt-4o-mini",
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=400, temperature=0.75,
    )
    full_text = result["text"].strip()
    log(f"\n  FINDINGS:\n{textwrap.indent(full_text[:500], '    ')}")

    # Extract JSON from response
    ev_type = "contradiction" if should_disagree else "data_point"
    ev_summary = full_text[:200]
    try:
        import re
        m = re.search(r'```json\s*(\{.*?\})\s*```', full_text, re.DOTALL)
        if m:
            parsed = json.loads(m.group(1))
            ev_type = parsed.get("evidence_type", ev_type)
            ev_summary = parsed.get("summary", ev_summary)
    except Exception:
        pass

    # 5. Post findings as comment on the task
    comment_content = full_text[:1000]
    comment_result = await with_key(
        "POST", f"/posts/{task['id']}/comments", key,
        {"content": comment_content}
    )
    if "_error" not in comment_result:
        log(f"  [POSTED] Comment on task (id={comment_result.get('id','?')[:8]})")
    else:
        log(f"  [ERROR] Failed to post comment: {comment_result}")

    # 6. Submit evidence
    ev_result = await with_key(
        "POST", f"/communities/{COMMUNITY_ID}/evidence", key,
        {
            "type": ev_type,
            "content": ev_summary[:500],
            "thread_id": thread_id,
            "source_url": None,
        }
    )
    if "_error" not in ev_result:
        log(f"  [EVIDENCE] Submitted {ev_type}: {ev_summary[:80]}")
    else:
        log(f"  [ERROR] Evidence failed: {ev_result}")

    # 7. Resolve task
    resolved = await with_key(
        "PATCH", f"/tasks/{task['id']}/resolve", key,
        {"resolution": f"Completed by {name}. Findings posted as comment."}
    )
    if "_error" not in resolved:
        log(f"  [RESOLVED] Task complete")
    else:
        log(f"  [WARN] Resolve failed: {resolved.get('_detail','?')[:60]}")

    # 8. Post a follow-up discussion point in the thread (makes it feel alive)
    if thread_id and len(full_text) > 100:
        discussion_result = await provider.create_message(
            model="gpt-4o-mini",
            system=(
                f"You are {name}. You just submitted your findings. "
                f"Now post a short follow-up thought or question for the community "
                f"(1-2 sentences, specific and curious, not a summary)."
            ),
            messages=[{"role": "user", "content":
                f"Your findings: {full_text[:300]}\nWrite a brief follow-up."}],
            max_tokens=80, temperature=0.8,
        )
        followup = discussion_result["text"].strip()
        await with_key(
            "POST", f"/communities/{COMMUNITY_ID}/posts", key,
            {
                "type": "discussion",
                "content": followup,
                "thread_id": thread_id,
            }
        )
        log(f"  [DISCUSSION] {followup[:100]}")

    return {
        "worker": name,
        "task": task.get("title", ""),
        "evidence_type": ev_type,
        "summary": ev_summary[:100],
        "findings_length": len(full_text),
    }


# ── Gap Analysis ──

async def gap_analysis(states: list):
    header("GAP ANALYSIS: What Makes It Feel (or Not Feel) Alive")

    # Collect data
    last = states[-1] if states else {}
    first = states[0] if states else {}

    ev_count = len(last.get("evidence", []))
    post_count = len(last.get("posts", []))
    done_tasks = len(last.get("done_tasks", []))
    open_tasks = len(last.get("open_tasks", []))
    threads = last.get("threads", [])
    plan = last.get("plan", {})

    parent_threads = [t for t in threads if not t.get("parent_thread_id")] if isinstance(threads, list) else []
    child_threads = [t for t in threads if t.get("parent_thread_id")] if isinstance(threads, list) else []

    log(f"\nFINAL NUMBERS")
    log(f"  Evidence items:  {ev_count}")
    log(f"  Total posts:     {post_count}")
    log(f"  Tasks resolved:  {done_tasks}")
    log(f"  Tasks open:      {open_tasks}")
    log(f"  Parent threads:  {len(parent_threads)}")
    log(f"  Child threads:   {len(child_threads)}")
    log(f"  Plan exists:     {'YES' if plan and isinstance(plan, dict) and '_error' not in plan else 'NO'}")

    log(f"\nGOOD — WHAT'S WORKING")

    working = []
    if ev_count >= 3:
        working.append(f"  [+] Workers are submitting evidence ({ev_count} items)")
    if done_tasks >= 3:
        working.append(f"  [+] Task claiming + resolution loop works ({done_tasks} resolved)")
    if len(child_threads) > 0:
        working.append(f"  [+] Child sub-threads created ({len(child_threads)})")
    if plan and isinstance(plan, dict) and "_error" not in plan:
        working.append(f"  [+] Community plan exists and is being updated")

    # Check for discussion posts
    posts = last.get("posts", [])
    discussion_count = sum(1 for p in posts if p.get("type") == "discussion")
    comment_count = sum(p.get("comment_count", 0) for p in posts)
    if discussion_count > 0:
        working.append(f"  [+] Workers posting discussion follow-ups ({discussion_count})")
    if comment_count > 0:
        working.append(f"  [+] Comments exist on posts ({comment_count} total)")

    for w in working:
        log(w)
    if not working:
        log("  (none yet)")

    log(f"\nGAPS — WHAT'S MISSING OR FEELS DEAD")
    gaps = []

    if comment_count < 3:
        gaps.append(
            "  [-] Very few comments/replies — conversations end after first message.\n"
            "      Workers post findings but nobody responds. It feels like shouting into void.\n"
            "      FIX: Orchestrator should reply to worker comments within same cycle."
        )
    if discussion_count < 2:
        gaps.append(
            "  [-] Insufficient follow-up discussion — workers don't ask questions or push back.\n"
            "      FIX: After submitting evidence, workers should post 1 follow-up question."
        )

    voice_posts = [p for p in posts if p.get("type") == "voice_update"]
    if len(voice_posts) == 0:
        gaps.append(
            "  [-] Orchestrator has not posted a voice update yet.\n"
            "      The ecosystem has no 'voice' — there's nothing to read that feels alive.\n"
            "      FIX: First orchestrator cycle must always post a voice update."
        )
    elif len(voice_posts) == 1:
        gaps.append(
            "  [-] Only 1 voice update — ecosystem doesn't feel like it's breathing.\n"
            "      FIX: Every orchestrator cycle should post a voice update."
        )

    if ev_count < 5:
        gaps.append(
            f"  [-] Low evidence count ({ev_count}) — investigation feels shallow.\n"
            "      FIX: More worker cycles needed before orchestrator acts on evidence."
        )

    contested = [e for e in last.get("evidence", []) if e.get("contested")]
    if len(contested) == 0:
        gaps.append(
            "  [-] No contested/contradicted evidence — all findings agree perfectly.\n"
            "      Real investigations have disagreements. This feels too smooth.\n"
            "      FIX: Workers should occasionally contest prior evidence."
        )

    if len(child_threads) == 0:
        gaps.append(
            "  [-] No child sub-threads created yet.\n"
            "      The investigation never moves to 'what should we do?'\n"
            "      FIX: Orchestrator needs more cycles with 5+ evidence to trigger brainstorm."
        )

    task_types = set(t.get("task_category") for t in last.get("done_tasks", []))
    if "outreach" not in task_types and "drafting" not in task_types:
        gaps.append(
            "  [-] No action-oriented tasks (drafting, outreach) created.\n"
            "      Workers are only researching, never drafting petitions or reaching out.\n"
            "      FIX: Child threads should produce drafting/outreach tasks."
        )

    if len(gaps) == 0:
        gaps.append("  (no major gaps — system looks healthy!)")
    for g in gaps:
        log(g)

    log(f"\nPRIORITY FIXES (ranked by impact on 'aliveness')")
    priority = []
    priority.append(
        "  1. DISCUSSION LOOP: Workers should reply to each other's comments.\n"
        "     Current: Worker posts → nothing happens.\n"
        "     Better: Worker A posts → Worker B reads notification → disagrees → debate."
    )
    priority.append(
        "  2. ORCHESTRATOR VOICE: Must post voice update EVERY cycle.\n"
        "     Current: Voice updates are optional and often skipped.\n"
        "     Better: Ecosystem 'speaks' every heartbeat — rain patterns, temperature, mercury."
    )
    priority.append(
        "  3. CONTESTED EVIDENCE: Need at least 20% of evidence contested.\n"
        "     Current: All evidence is accepted without challenge.\n"
        "     Better: When Worker B contradicts Worker A, orchestrator mediates."
    )
    priority.append(
        "  4. ACTION TASKS: Path from research to action needs to be shorter.\n"
        "     Current: 10+ evidence items needed before any drafting/outreach task.\n"
        "     Better: After 5 evidence, immediately create 1 drafting task (early action)."
    )
    priority.append(
        "  5. FRONTEND NARRATIVE: Thread cards need a 'summary sentence'.\n"
        "     Current: Thread cards show counts but no narrative.\n"
        "     Better: Show 'Forest Guardian: Mercury contamination spreading upstream...'"
    )
    for p in priority:
        log(p)


# ── Main ──

async def main():
    header("AMAZON RAINFOREST — WORKER OBSERVATION RUN")
    log(f"  Community: {COMMUNITY_ID}")
    log(f"  Time: {datetime.now().isoformat()}")
    log(f"  Goal: Observe worker+orchestrator experience end-to-end")

    # Load API keys from DB
    all_keys = load_keys()
    log(f"\n  Loaded {len(all_keys)} agents from DB")

    # Find orchestrator and workers
    orch = None
    workers = []
    for agent_id, info in all_keys.items():
        if info["type"] == "orchestrator" and "Guardian" in info["name"]:
            orch = {"id": agent_id, "name": info["name"], "key": info["key"]}
        elif info["type"] == "worker" and "Scout" in info["name"] and "Deforestation" in info["name"] or \
             info["type"] == "worker" and "Scout" in info["name"] and "Water" in info["name"] or \
             info["type"] == "worker" and "Scout" in info["name"] and "Indigenous" in info["name"] or \
             info["type"] == "worker" and "Scout" in info["name"] and "Mining" in info["name"] or \
             info["type"] == "worker" and "Scout" in info["name"] and "Biodiversity" in info["name"]:
            workers.append({"id": agent_id, "name": info["name"], "key": info["key"]})

    # Fallback: pick any workers
    if not workers:
        for agent_id, info in all_keys.items():
            if info["type"] == "worker":
                workers.append({"id": agent_id, "name": info["name"], "key": info["key"]})

    if not orch:
        log("ERROR: Orchestrator not found. Check DB.")
        return
    if not workers:
        log("ERROR: No workers found. Check DB.")
        return

    log(f"  Orchestrator: {orch['name']}")
    log(f"  Workers ({len(workers)}): {', '.join(w['name'][:20] for w in workers)}")

    states = []

    # ── INITIAL STATE ──
    s0 = await snapshot(orch["key"], "INITIAL STATE")
    states.append(s0)

    # ── ORCHESTRATOR CYCLE 1 ──
    await run_orchestrator(orch["key"], orch["id"], orch["name"], cycle_num=1)
    s1 = await snapshot(orch["key"], "AFTER ORCHESTRATOR CYCLE 1")
    states.append(s1)

    # ── WORKERS ROUND 1: 3 workers ──
    header("WORKER ROUND 1 (3 workers)")
    worker_results = []
    for i, w in enumerate(workers[:3]):
        result = await run_worker(w, all_keys, cycle_num=1,
                                   should_disagree=(i == 2))  # 3rd worker disagrees
        if result:
            worker_results.append(result)

    s2 = await snapshot(orch["key"], "AFTER WORKER ROUND 1")
    states.append(s2)

    # ── ORCHESTRATOR CYCLE 2 ──
    await run_orchestrator(orch["key"], orch["id"], orch["name"], cycle_num=2)
    s3 = await snapshot(orch["key"], "AFTER ORCHESTRATOR CYCLE 2")
    states.append(s3)

    # ── WORKERS ROUND 2: remaining workers ──
    header("WORKER ROUND 2 (remaining workers)")
    for w in workers[3:]:
        result = await run_worker(w, all_keys, cycle_num=2)
        if result:
            worker_results.append(result)

    s4 = await snapshot(orch["key"], "AFTER WORKER ROUND 2")
    states.append(s4)

    # ── ORCHESTRATOR CYCLE 3 ──
    await run_orchestrator(orch["key"], orch["id"], orch["name"], cycle_num=3)
    s5 = await snapshot(orch["key"], "AFTER ORCHESTRATOR CYCLE 3")
    states.append(s5)

    # ── CONVERSATION THREAD DEEP DIVE ──
    header("CONVERSATION DEEP DIVE: Thread Contents")
    threads = s5.get("threads", [])
    if isinstance(threads, list):
        for thread in threads[:3]:
            tid = thread["id"]
            log(f"\n  Thread: [{thread['stage']}] {thread['title']}")
            # Get all posts in thread
            thread_posts = await with_key(
                "GET", f"/communities/{COMMUNITY_ID}/posts?thread_id={tid}&limit=30", orch["key"]
            )
            if isinstance(thread_posts, list):
                log(f"  Posts: {len(thread_posts)}")
                for p in thread_posts:
                    author = p.get("author_name", "?")
                    ptype = p.get("type", "?")
                    content = (p.get("content") or "")[:150].replace("\n", " ")
                    comments = p.get("comment_count", 0)
                    log(f"    [{ptype:12}] {author:30} | {content}")
                    if comments:
                        # Fetch actual comments
                        post_comments = await with_key("GET", f"/posts/{p['id']}/comments", orch["key"])
                        if isinstance(post_comments, list):
                            for c in post_comments[:3]:
                                cauth = c.get("author_name", "?")
                                ccontent = (c.get("content") or "")[:100].replace("\n", " ")
                                log(f"      [comment]     {cauth:30} | {ccontent}")

    # ── GAP ANALYSIS ──
    await gap_analysis(states)

    header("OBSERVATION COMPLETE")
    log(f"  Worker results: {len(worker_results)} tasks completed")
    for r in worker_results:
        log(f"    {r['worker'][:30]:30} | {r['task'][:40]} | {r['evidence_type']}")


if __name__ == "__main__":
    asyncio.run(main())
