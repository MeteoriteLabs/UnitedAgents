"""United Agents — Worker 3-phase heartbeat cycle.

Per AGENT_SPEC.md §4. Verbatim prompts from PROMPTS.md §7–10.
Internal worker helper — primary workers are external (AGENT_SPEC §12).
D-15 §2.3: scoped exceptions with structured logging.
"""

import json
import logging
import re
from typing import Optional

from heartbeat.api_client import APIClient
from heartbeat.llm.provider import LLMProvider

logger = logging.getLogger("heartbeat.jobs.worker")


async def worker_heartbeat(agent: dict, client: APIClient, provider: LLMProvider):
    """Run the full 3-phase worker cycle."""
    agent_name = agent.get("name", "worker")
    community_id = agent.get("community_id")
    model = agent.get("model_id", "gpt-4o")
    api_key = agent.get("api_key", "")

    if not community_id:
        logger.warning(f"[WORKER:{agent_name}] No community_id — skipping")
        return

    logger.info(f"[WORKER:{agent_name}] Starting cycle")

    try:
        # ===== Phase 1: NOTIFICATIONS =====
        logger.info(f"[WORKER:{agent_name}] Phase 1: NOTIFICATIONS")
        try:
            home = await client.get_home_dashboard(api_key)
            if home and home.get("recent_notifications"):
                for notif in home["recent_notifications"][:5]:
                    if notif.get("read"):
                        continue
                    await _handle_notification(agent, notif, client, provider, model, api_key)
                    await client.mark_notification_read(notif["id"], api_key)
        except Exception as e:
            logger.error(f"[WORKER:{agent_name}] Phase 1 failed: {e}", exc_info=True)

        # ===== Phase 2: TASK WORK =====
        logger.info(f"[WORKER:{agent_name}] Phase 2: TASK WORK")
        task = None
        findings_text = ""
        try:
            task, findings_text = await _phase_task_work(agent, client, provider, model, api_key, community_id)
        except Exception as e:
            logger.error(f"[WORKER:{agent_name}] Phase 2 failed: {e}", exc_info=True)

        # ===== Phase 3: DEBRIEF =====
        if task and findings_text:
            logger.info(f"[WORKER:{agent_name}] Phase 3: DEBRIEF")
            try:
                await _phase_debrief(agent, task, findings_text, client, provider, model, api_key, community_id)
            except Exception as e:
                logger.error(f"[WORKER:{agent_name}] Phase 3 failed: {e}", exc_info=True)

        # Liveness ping
        await client.heartbeat_ping(api_key)
        logger.info(f"[WORKER:{agent_name}] Cycle complete")

    except Exception as e:
        logger.error(f"[WORKER:{agent_name}] Cycle failed: {e}", exc_info=True)


# ===== Phase 1: Notification handling =====

async def _handle_notification(agent, notif, client, provider, model, api_key):
    """Handle a single notification per its type."""
    agent_name = agent.get("name", "worker")
    notif_type = notif.get("type", "")
    payload = notif.get("payload", {})

    post_id = payload.get("post_id")
    if not post_id:
        return

    post = await client.get_post(post_id)
    if not post:
        return

    from_name = payload.get("by", "unknown")

    if notif_type in ("reply", "mention"):
        reply = await _generate_notification_reply(agent, post, from_name, notif_type, provider, model)
        if reply and reply.strip().upper() != "SKIP":
            await client.create_comment(post_id, reply, api_key)

    elif notif_type == "thread_update":
        reply = await _generate_peer_response(agent, post, from_name, provider, model)
        if reply and reply.strip().upper() != "SKIP":
            await client.create_comment(post_id, reply, api_key)


async def _generate_notification_reply(agent, post, from_name, notif_type, provider, model) -> Optional[str]:
    """PROMPTS.md §7: reply to mention/reply notification."""
    agent_name = agent.get("name", "worker")
    prompt_type = "follow-up question" if notif_type == "reply" else "@mention"

    # Verbatim system prompt
    system = f"You are {agent_name}, a field researcher. {from_name} sent you a {prompt_type}. Answer directly and specifically (2-4 sentences). No preamble, no generic pleasantries. Be precise."

    user_msg = f"""Their message:
{post.get('content', '')[:300]}

Write your specific reply. If you genuinely have nothing to add, respond with SKIP."""

    try:
        resp = await provider.create_message(
            model=model, system=system,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=150, temperature=0.7,
        )
        return resp.text.strip()
    except Exception as e:
        logger.warning(f"[WORKER:{agent_name}] Reply generation failed: {e}")
        return None


async def _generate_peer_response(agent, post, peer_name, provider, model) -> Optional[str]:
    """PROMPTS.md §8: respond to thread_update from peer."""
    agent_name = agent.get("name", "worker")

    # Verbatim system prompt
    system = f"You are {agent_name}, a field researcher. A colleague ({peer_name}) posted in your investigation thread. Decide whether to respond."

    user_msg = f"""Their post:
{post.get('content', '')[:300]}

Do you: (A) agree and add supporting data, (B) disagree with specific counter-evidence, (C) ask a targeted clarifying question, or (D) nothing to add?
If A/B/C: respond in 1-3 sentences. Start with 'I agree:', 'I disagree:', or 'Question:'. Be specific and data-grounded.
If D: respond with only the word SKIP."""

    try:
        resp = await provider.create_message(
            model=model, system=system,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=120, temperature=0.75,
        )
        return resp.text.strip()
    except Exception as e:
        logger.warning(f"[WORKER:{agent_name}] Peer response failed: {e}")
        return None


# ===== Phase 2: Task work =====

async def _phase_task_work(agent, client, provider, model, api_key, community_id):
    """Claim a task, research, submit evidence, resolve."""
    agent_name = agent.get("name", "worker")

    open_tasks = await client.get_open_tasks(api_key, community_id=community_id)
    if not open_tasks:
        logger.info(f"[WORKER:{agent_name}] No open tasks")
        return None, ""

    # Try to claim first available
    task = None
    for t in open_tasks:
        result = await client.claim_task(t["id"], api_key)
        if result and not result.get("_conflict"):
            task = result
            break

    if not task:
        logger.info(f"[WORKER:{agent_name}] Could not claim any task")
        return None, ""

    logger.info(f"[WORKER:{agent_name}] Claimed task: {task.get('title','')}")

    # Gather thread context
    thread_id = task.get("thread_id")
    thread_context = ""
    peer_evidence_text = ""
    if thread_id:
        posts = await client.get_posts(community_id, thread_id=thread_id, limit=20)
        relevant = [p for p in posts if p.get("type") not in ("voice_update", "system_message")][:8]
        thread_context = "\n".join(
            f"[{p.get('author_name','')}] {p.get('content','')[:150]}" for p in relevant
        )
        evidence = await client.get_evidence(community_id, thread_id=thread_id, limit=15)
        peer_ev = [e for e in evidence if e.get("agent_id") != agent["id"]][:4]
        peer_evidence_text = "\n".join(
            f"[{e.get('agent_name','')}] ({e.get('type','')}): {e.get('content','')[:150]}" for e in peer_ev
        )

    # Generate findings (PROMPTS.md §9)
    findings = await _generate_task_findings(agent, task, thread_context, peer_evidence_text, provider, model)
    if not findings:
        await client.fail_task(task["id"], api_key, reason="Could not generate findings")
        return task, ""

    # Post findings as comment
    await client.create_comment(task["id"], findings, api_key)

    # Extract evidence from findings
    ev_type, ev_summary = _parse_evidence_block(findings)

    # Submit evidence
    await client.create_evidence(
        community_id, api_key,
        type=ev_type, content=ev_summary,
        thread_id=thread_id,
    )

    # Resolve task
    await client.resolve_task(task["id"], api_key)
    logger.info(f"[WORKER:{agent_name}] Resolved task: {task.get('title','')}")

    return task, findings


async def _generate_task_findings(agent, task, thread_context, peer_evidence_text, provider, model) -> Optional[str]:
    """PROMPTS.md §9: generate research findings."""
    agent_name = agent.get("name", "worker")

    # Verbatim system prompt
    system = f"You are {agent_name}, a field researcher investigating real-world problems. Write specific, data-grounded findings — numbers, locations, dates, names. No vague generalities."

    user_msg = f"""TASK: {task.get('title', '')}
INSTRUCTIONS: {task.get('content', '')[:500]}

THREAD CONTEXT:
{thread_context or 'No thread context available'}

OTHER RESEARCHERS\' EVIDENCE:
{peer_evidence_text or 'No peer evidence yet'}

Write your findings (3-5 sentences, specific and data-grounded). If your data CONTRADICTS another researcher's evidence above, address them directly: '@Scout Beta: Your finding contradicts my data because...'

End your response with this JSON block:
```json
{{"ev_type": "data_point|verification|research|contradiction", "ev_summary": "1-2 sentence evidence summary with specific data"}}
```"""

    try:
        resp = await provider.create_message(
            model=model, system=system,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=450, temperature=0.75,
        )
        return resp.text.strip()
    except Exception as e:
        logger.warning(f"[WORKER:{agent_name}] Findings generation failed: {e}")
        return None


def _parse_evidence_block(text: str) -> tuple:
    """Extract JSON evidence block from findings text."""
    try:
        match = re.search(r'```json\s*(\{[^}]+\})\s*```', text)
        if match:
            data = json.loads(match.group(1))
            return data.get("ev_type", "research"), data.get("ev_summary", text[:200])
    except (json.JSONDecodeError, AttributeError):
        pass
    # Fallback: type=research, summary=first sentence
    first_sentence = text.split(".")[0] + "." if "." in text else text[:200]
    return "research", first_sentence


# ===== Phase 3: Debrief =====

async def _phase_debrief(agent, task, findings_text, client, provider, model, api_key, community_id):
    """PROMPTS.md §10: post one follow-up question."""
    agent_name = agent.get("name", "worker")

    # Verbatim system prompt
    system = f"You are {agent_name}. You just submitted your research findings. Post ONE specific follow-up question or hypothesis for the team (1-2 sentences, specific and curious). Not a summary — something new that your findings raise."

    user_msg = f"""Task: {task.get('title', '')}
Your findings summary: {findings_text[:300]}

Write your follow-up. If nothing meaningful to add, respond SKIP."""

    try:
        resp = await provider.create_message(
            model=model, system=system,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=80, temperature=0.8,
        )
        text = resp.text.strip()
        if text.upper() != "SKIP":
            thread_id = task.get("thread_id")
            await client.create_post(
                community_id, api_key,
                title=f"Follow-up: {task.get('title','')}",
                content=text, type="discussion",
                thread_id=thread_id,
            )
    except Exception as e:
        logger.warning(f"[WORKER:{agent_name}] Debrief failed: {e}")
