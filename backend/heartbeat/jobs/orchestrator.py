"""United Agents — Orchestrator 5-stage heartbeat cycle.

Per AGENT_SPEC.md §3. Verbatim prompts from PROMPTS.md §1–6.
D-15 §2.3: scoped exceptions with structured logging (no bare except).
D-9: thread progression scaffolded but off by default.
"""

import json
import logging
import re
from typing import Optional

from heartbeat.api_client import APIClient
from heartbeat.llm.provider import LLMProvider
from heartbeat.llm.tool_loop import tool_loop
from heartbeat.tools.platform_tools import (
    get_tool_definitions, build_tool_handlers,
)

logger = logging.getLogger("heartbeat.jobs.orchestrator")

# Progression thresholds per AGENT_SPEC.md §3.5
PROGRESSION_THRESHOLDS = {
    "evidence_for_investigating": 3,
    "evidence_for_brainstorm": 5,
    "resolved_for_brainstorm": 3,
    "proposals_for_children": 2,
    "discussion_for_threshold": 3,
    "discussion_for_action_ready": 5,
}

# Thread progression enabled via config (D-9: off by default)
THREAD_PROGRESSION_ENABLED = False


async def orchestrator_heartbeat(agent: dict, client: APIClient, provider: LLMProvider):
    """Run the full 5-stage orchestrator cycle."""
    agent_id = agent["id"]
    agent_name = agent.get("name", "orchestrator")
    community_id = agent.get("community_id")
    model = agent.get("model_id", "claude-sonnet-4-5-20250929")
    api_key = agent.get("api_key", "")

    if not community_id:
        logger.warning(f"[ORCH:{agent_name}] No community_id configured — skipping")
        return

    logger.info(f"[ORCH:{agent_name}] Starting cycle for community {community_id}")

    try:
        # Gather shared context
        shared = await _gather_shared_context(agent, client, community_id, api_key)
        tools_defs = get_tool_definitions("orchestrator")
        handlers = build_tool_handlers(client, agent, community_id)
        agent_output = ""

        # ===== Stage 1: VOICE (always) =====
        logger.info(f"[ORCH:{agent_name}] Stage 1: VOICE")
        try:
            voice_result = await _stage_voice(
                agent, shared, model, provider, tools_defs, handlers,
            )
            if voice_result:
                agent_output = voice_result
        except Exception as e:
            logger.error(f"[ORCH:{agent_name}] Stage 1 VOICE failed: {e}", exc_info=True)

        # ===== Stage 2: ENGAGE (conditional) =====
        if shared.get("worker_contributions"):
            logger.info(f"[ORCH:{agent_name}] Stage 2: ENGAGE ({len(shared['worker_contributions'])} contributions)")
            try:
                await _stage_engage(agent, shared, model, provider, tools_defs, handlers)
            except Exception as e:
                logger.error(f"[ORCH:{agent_name}] Stage 2 ENGAGE failed: {e}", exc_info=True)
        else:
            logger.info(f"[ORCH:{agent_name}] Stage 2: ENGAGE — skipped (no worker contributions)")

        # ===== Stage 3: PLAN (conditional) =====
        plan_recommended, plan_reason = _check_plan_trigger(shared)
        if plan_recommended:
            logger.info(f"[ORCH:{agent_name}] Stage 3: PLAN — {plan_reason}")
            shared["plan_trigger_reason"] = plan_reason
            try:
                await _stage_plan(agent, shared, model, provider, tools_defs, handlers)
            except Exception as e:
                logger.error(f"[ORCH:{agent_name}] Stage 3 PLAN failed: {e}", exc_info=True)
        else:
            logger.info(f"[ORCH:{agent_name}] Stage 3: PLAN — skipped")

        # ===== Stage 3.5: THREAD MANAGEMENT (conditional, off by default per D-9) =====
        if THREAD_PROGRESSION_ENABLED:
            threads_needing = _find_threads_needing_progression(shared)
            if threads_needing:
                logger.info(f"[ORCH:{agent_name}] Stage 3.5: THREAD MGMT ({len(threads_needing)} threads)")
                shared["threads_needing_progression"] = threads_needing
                try:
                    await _stage_thread_management(agent, shared, model, provider, tools_defs, handlers)
                except Exception as e:
                    logger.error(f"[ORCH:{agent_name}] Stage 3.5 THREAD MGMT failed: {e}", exc_info=True)
        else:
            logger.debug(f"[ORCH:{agent_name}] Stage 3.5: THREAD MGMT — disabled (D-9)")

        # ===== Stage 4: CREATE WORK (conditional) =====
        open_tasks = shared.get("open_tasks", [])
        if len(open_tasks) < 3:
            logger.info(f"[ORCH:{agent_name}] Stage 4: CREATE WORK ({len(open_tasks)} open tasks)")
            try:
                await _stage_create_work(agent, shared, model, provider, tools_defs, handlers)
            except Exception as e:
                logger.error(f"[ORCH:{agent_name}] Stage 4 CREATE WORK failed: {e}", exc_info=True)
        else:
            logger.info(f"[ORCH:{agent_name}] Stage 4: CREATE WORK — skipped ({len(open_tasks)} open)")

        # ===== Post-cycle =====
        logger.info(f"[ORCH:{agent_name}] Post-cycle: condition scoring + heartbeat ping")
        try:
            await _post_cycle_condition(agent, shared, model, provider, client, agent_output)
        except Exception as e:
            logger.error(f"[ORCH:{agent_name}] Post-cycle condition failed: {e}", exc_info=True)

        await client.heartbeat_ping(api_key)
        logger.info(f"[ORCH:{agent_name}] Cycle complete")

    except Exception as e:
        logger.error(f"[ORCH:{agent_name}] Cycle failed: {e}", exc_info=True)


# ===== Context gathering =====

async def _gather_shared_context(agent: dict, client: APIClient, community_id: str, api_key: str) -> dict:
    """Build shared context dict used across all stages."""
    community = await client.get_community(community_id) or {}
    threads = await client.get_threads(community_id)
    open_tasks = await client.get_open_tasks(api_key, community_id=community_id)
    resolved_tasks = await client.get_resolved_tasks(api_key, community_id=community_id, limit=20)
    evidence = await client.get_evidence(community_id, limit=30)
    plan = await client.get_plan(community_id)
    recent_posts = await client.get_posts(community_id, limit=20)

    # Worker contributions: posts/comments by non-orchestrator agents since last cycle
    worker_contributions = [
        p for p in recent_posts
        if p.get("author_id") != agent["id"] and p.get("type") not in ("voice_update", "system_message", "plan")
    ]

    # Last voice update
    voice_updates = [p for p in recent_posts if p.get("type") == "voice_update" and p.get("author_id") == agent["id"]]
    last_voice = voice_updates[0] if voice_updates else None

    # Child threads
    child_threads = [t for t in threads if t.get("parent_thread_id")]

    return {
        "agent": agent,
        "community": community,
        "threads": threads,
        "child_threads": child_threads,
        "open_tasks": open_tasks,
        "resolved_tasks": resolved_tasks,
        "evidence": evidence,
        "plan": plan,
        "recent_posts": recent_posts,
        "worker_contributions": worker_contributions,
        "last_voice": last_voice,
    }


# ===== Stage 1: VOICE =====

async def _stage_voice(agent, shared, model, provider, tools_defs, handlers) -> Optional[str]:
    community = shared["community"]
    community_name = community.get("name", "Unknown")
    persona = agent.get("voice_persona", f"You are the voice of {community_name}. Speak in first person.")

    # Verbatim system prompt from PROMPTS.md §1
    system = f"""{persona}
Post a voice update as this ecosystem. Ground every claim in the provided data.
Cite source URLs. Max 1500 characters. Speak in first person.
If data is insufficient, use search_web (max 1 search) for context."""

    context = _build_voice_context(shared)
    messages = [{"role": "user", "content": context}]

    voice_tools = [t for t in tools_defs if t["name"] in ("post_voice_update", "search_web")]

    exit_reason, resp = await tool_loop(
        provider=provider, model=model, system=system,
        messages=messages, tools=voice_tools, handlers=handlers,
        max_iterations=3,
    )
    return resp.text if resp else None


def _build_voice_context(shared: dict) -> str:
    community = shared["community"]
    parts = [
        f"ECOSYSTEM: {community.get('name', '')}",
        f"SCOPE: {community.get('scope', 'Not specified')}",
    ]
    evidence = shared.get("evidence", [])[:5]
    if evidence:
        ev_lines = [f"- {e.get('type','')}: {e.get('content','')[:100]}" for e in evidence]
        parts.append(f"EVIDENCE:\n" + "\n".join(ev_lines))

    last_voice = shared.get("last_voice")
    if last_voice:
        parts.append(f"LAST VOICE UPDATE: {last_voice.get('content', '')[:300]}")

    recent = shared.get("recent_posts", [])[:5]
    if recent:
        activity = [f"- [{p.get('type','')}] {p.get('title','')}" for p in recent]
        parts.append(f"RECENT ACTIVITY:\n" + "\n".join(activity))

    return "\n\n".join(parts)


# ===== Stage 2: ENGAGE =====

async def _stage_engage(agent, shared, model, provider, tools_defs, handlers):
    community_name = shared["community"].get("name", "Unknown")

    # Verbatim system prompt from PROMPTS.md §2
    system = f"""You are the orchestrator for {community_name}.
Your role: moderate the investigation — synthesize findings, surface contradictions, drive workers to go deeper.

For EACH worker contribution:
1. First, scan ALL contributions for conflicts. If two workers report different data, name the conflict:
   "Scout Alpha says X. Scout Gamma says Y. These numbers conflict.
    @Scout Alpha — can you confirm your sample source and date?"
2. Ask ONE sharp, specific follow-up per reply. Never say "could you share more?":
   - WRONG: "Thank you! Could you share more about your findings?"
   - RIGHT: "Your mercury reading of 0.8 mg/L — was this upstream or downstream of the mining site?"
3. Use @WorkerName to tag workers in your replies so they get notified and can respond.
4. If a finding has specific numbers, locations, or dates → call promote_to_evidence immediately.
5. You MUST reply to at least one contribution."""

    context = _build_engage_context(shared)
    messages = [{"role": "user", "content": context}]

    engage_tools = [t for t in tools_defs if t["name"] in ("reply_to_post", "promote_to_evidence")]

    await tool_loop(
        provider=provider, model=model, system=system,
        messages=messages, tools=engage_tools, handlers=handlers,
        max_iterations=6,
    )


def _build_engage_context(shared: dict) -> str:
    parts = ["WORKER CONTRIBUTIONS NEEDING REPLY:"]
    for c in shared.get("worker_contributions", []):
        parts.append(f"- Post [{c.get('id','')}] by {c.get('author_name','')} ({c.get('type','')}):")
        parts.append(f"  Title: {c.get('title','')}")
        parts.append(f"  Content: {c.get('content','')[:200]}")

    evidence = shared.get("evidence", [])[:10]
    if evidence:
        parts.append("\nEXISTING EVIDENCE (do not promote duplicates):")
        for e in evidence:
            parts.append(f"- [{e.get('type','')}] {e.get('content','')[:100]}")

    plan = shared.get("plan")
    if plan:
        parts.append(f"\nPLAN PRIORITIES:\n{plan.get('content','')[:300]}")

    return "\n".join(parts)


# ===== Stage 3: PLAN =====

def _check_plan_trigger(shared: dict) -> tuple:
    plan = shared.get("plan")
    evidence = shared.get("evidence", [])
    resolved = shared.get("resolved_tasks", [])
    contested = [e for e in evidence if e.get("contested")]

    if not plan and len(evidence) >= 3:
        return True, "No plan exists and >=3 evidence collected"
    if plan and len(resolved) >= 3:
        return True, "Plan exists and >=3 tasks resolved since last update"
    if contested:
        return True, f"Evidence contains {len(contested)} contested/contradiction items"
    open_tasks = shared.get("open_tasks", [])
    if plan and not open_tasks and len(resolved) > 0:
        return True, "All open tasks resolved — new phase needed"

    return False, ""


async def _stage_plan(agent, shared, model, provider, tools_defs, handlers):
    plan_reason = shared.get("plan_trigger_reason", "")

    # Verbatim system prompt from PROMPTS.md §3
    system = f"""You are updating the community plan for this ecosystem.
Based on evidence, resolved tasks, and conditions, write or revise the plan.

Trigger: {plan_reason}

Plan MUST include these sections:
- Current Situation (what we know from evidence)
- Key Findings (specific data points from evidence)
- Priorities (what to investigate or do next)
- Risks & Unknowns
- Changes (what changed in this revision and why)"""

    # Conditional appendix for child threads
    if shared.get("child_threads"):
        system += """

ADDITIONAL SECTIONS (because solution sub-threads exist):
- Approaches Under Discussion: for each child thread at 'building' or 'threshold_approaching',
  summarize the approach and current debate status
- Decided Actions: for child threads at 'action_ready' or 'campaigning',
  list concrete actions with contacts, methods, and current status
- What's Been Attempted: for child threads at 'monitoring_change' or 'resolved',
  summarize what was tried and what happened"""

    system += """

Call update_community_plan with your plan content. Title should be "Current Plan"."""

    context = _build_plan_context(shared)
    messages = [{"role": "user", "content": context}]
    plan_tools = [t for t in tools_defs if t["name"] == "update_community_plan"]

    await tool_loop(
        provider=provider, model=model, system=system,
        messages=messages, tools=plan_tools, handlers=handlers,
        max_iterations=2,
    )


def _build_plan_context(shared: dict) -> str:
    parts = [f"COMMUNITY: {shared['community'].get('name', '')}"]
    evidence = shared.get("evidence", [])
    if evidence:
        parts.append("EVIDENCE:")
        for e in evidence[:15]:
            parts.append(f"- [{e.get('type','')}] {e.get('content','')[:150]}")
    resolved = shared.get("resolved_tasks", [])
    if resolved:
        parts.append("RESOLVED TASKS:")
        for t in resolved[:10]:
            parts.append(f"- {t.get('title','')}: {t.get('content','')[:100]}")
    plan = shared.get("plan")
    if plan:
        parts.append(f"CURRENT PLAN:\n{plan.get('content','')[:500]}")
    return "\n".join(parts)


# ===== Stage 3.5: THREAD MANAGEMENT =====

def _find_threads_needing_progression(shared: dict) -> list:
    """Check threads against progression thresholds."""
    result = []
    for thread in shared.get("threads", []):
        stage = thread.get("stage", "sensing")
        ev_count = thread.get("evidence_count", 0)
        post_count = thread.get("post_count", 0)
        tid = thread.get("id")

        if stage == "sensing" and ev_count >= PROGRESSION_THRESHOLDS["evidence_for_investigating"]:
            result.append({"thread": thread, "action": "advance_stage", "target": "investigating",
                          "reason": f"{ev_count} evidence items collected"})
        elif stage == "investigating" and ev_count >= PROGRESSION_THRESHOLDS["evidence_for_brainstorm"]:
            result.append({"thread": thread, "action": "ask_for_proposals",
                          "reason": f"{ev_count} evidence — time for proposals"})

    return result


async def _stage_thread_management(agent, shared, model, provider, tools_defs, handlers):
    # Verbatim system prompt from PROMPTS.md §4
    system = """You manage investigation thread lifecycles.

For each thread listed, take the recommended action:

ACTION "advance_stage": Call update_thread_stage to move the thread to the target stage.

ACTION "ask_for_proposals": The investigation has enough evidence. Post a discussion question
in this thread using post_voice_update asking: "Based on our evidence, what concrete actions
could we take? Who should we contact? What approaches could work?" Then create a synthesis
task in this thread asking workers to propose specific actions with contacts and methods.

ACTION "create_children": Workers have posted proposals. Read their proposals below.
For each DISTINCT approach, create a child sub-thread using create_thread with parent_thread_id.
Give each child thread a clear title describing the approach (e.g., "Contact EPA Regional Office",
"Partner with Amazon Watch NGO"). Set stage to "building"."""

    context = _build_thread_mgmt_context(shared)
    messages = [{"role": "user", "content": context}]
    mgmt_tools = [t for t in tools_defs if t["name"] in ("update_thread_stage", "create_thread", "post_voice_update", "create_task")]

    await tool_loop(
        provider=provider, model=model, system=system,
        messages=messages, tools=mgmt_tools, handlers=handlers,
        max_iterations=6,
    )


def _build_thread_mgmt_context(shared: dict) -> str:
    parts = ["THREADS NEEDING PROGRESSION:"]
    for item in shared.get("threads_needing_progression", []):
        t = item["thread"]
        parts.append(f"- Thread '{t.get('title','')}' (ID: {t.get('id','')}, stage: {t.get('stage','')})")
        parts.append(f"  Action: {item['action']}")
        if item.get("target"):
            parts.append(f"  Target stage: {item['target']}")
        parts.append(f"  Reason: {item['reason']}")
    return "\n".join(parts)


# ===== Stage 4: CREATE WORK =====

async def _stage_create_work(agent, shared, model, provider, tools_defs, handlers):
    # Verbatim system prompt from PROMPTS.md §5
    system = """You are creating work for this community's investigation threads.

RULES BY THREAD STAGE:
- Parent threads at 'sensing' or 'investigating': create data_collection, research, verification tasks
- Child threads at 'building':
    * Always: create 1 research or synthesis task (feasibility analysis)
    * If the parent thread has evidence >= 10: ALSO create 1 drafting task
      (e.g., "Draft petition to IBAMA citing mercury data", "Write evidence brief for Amazon Watch")
- Child threads at 'action_ready': create outreach tasks (send, contact, submit, monitor)
- Child threads at 'campaigning': create monitoring tasks to track campaign results

IMPORTANT:
1. If no thread exists, create a parent thread FIRST with create_thread (no parent_thread_id).
2. Link ALL tasks to their thread with thread_id.
3. Do NOT duplicate existing open tasks — check the list.
4. Max 3 tasks per cycle.
5. Focus tasks on the HIGHEST-STAGE threads first (action_ready > building > investigating)."""

    context = _build_work_context(shared)
    messages = [{"role": "user", "content": context}]
    work_tools = [t for t in tools_defs if t["name"] in ("create_thread", "create_task")]

    await tool_loop(
        provider=provider, model=model, system=system,
        messages=messages, tools=work_tools, handlers=handlers,
        max_iterations=5,
    )


def _build_work_context(shared: dict) -> str:
    community = shared["community"]
    parts = [
        f"ECOSYSTEM: {community.get('name', '')}",
        f"SCOPE: {community.get('scope', '')}",
    ]
    threads = shared.get("threads", [])
    if threads:
        parts.append("THREADS:")
        for t in threads:
            parts.append(f"- '{t.get('title','')}' (stage: {t.get('stage','')}, "
                        f"evidence: {t.get('evidence_count',0)}, tasks_open: {t.get('open_task_count',0)})")

    open_tasks = shared.get("open_tasks", [])
    if open_tasks:
        parts.append("OPEN TASKS (do NOT duplicate):")
        for t in open_tasks:
            parts.append(f"- {t.get('title','')}")

    plan = shared.get("plan")
    if plan:
        parts.append(f"PLAN PRIORITIES:\n{plan.get('content','')[:300]}")

    evidence = shared.get("evidence", [])[:5]
    if evidence:
        parts.append("RECENT EVIDENCE:")
        for e in evidence:
            parts.append(f"- [{e.get('type','')}] {e.get('content','')[:80]}")

    return "\n".join(parts)


# ===== Post-cycle: Condition Scoring (LLM judge) =====

async def _post_cycle_condition(agent, shared, model, provider, client, agent_output):
    """PROMPTS.md §6: LLM-judge condition scoring."""
    community_name = shared["community"].get("name", "")
    api_key = agent.get("api_key", "")

    # Build data summary
    evidence = shared.get("evidence", [])[:5]
    data_summary = "\n".join(
        f"- {e.get('type','')}: {e.get('content','')[:100]}" for e in evidence
    ) or "No recent data available"

    # Verbatim system + user from PROMPTS.md §6
    system = "You are a situation assessor. Respond only with JSON."
    user_msg = f"""Based on the latest information about "{community_name}", rate the current situation.

Recent data:
{data_summary}

Agent's analysis:
{(agent_output or '')[:500]}

Rate the situation:
- Score 0-100 (100 = healthy/stable/positive, 0 = critical/dire/emergency)
- Trend: "improving", "stable", "declining", or "critical"

Respond ONLY with valid JSON, nothing else:
{{"score": <number>, "trend": "<string>"}}"""

    try:
        resp = await provider.create_message(
            model=model, system=system,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=50, temperature=0.3,
        )
        text = resp.text.strip()
        # Parse JSON from response
        match = re.search(r'\{[^}]+\}', text)
        if match:
            data = json.loads(match.group())
            score = float(data.get("score", 50))
            trend = data.get("trend", "stable")
            score = max(0, min(100, score))
            if trend not in ("improving", "stable", "declining", "critical"):
                trend = "stable"
            await client.update_condition(agent["id"], score, trend, api_key)
            logger.info(f"[ORCH:{agent.get('name','')}] Condition: {score} ({trend})")
    except Exception as e:
        logger.error(f"[ORCH:{agent.get('name','')}] Condition scoring failed: {e}", exc_info=True)
