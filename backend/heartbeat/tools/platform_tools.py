"""United Agents — Platform tools for the heartbeat engine.

Per AGENT_SPEC.md §9. 8 orchestrator + 2 earth-only + search_web.
ALGORITHMS.md §1: duplicate-task detection with STOP_WORDS.
"""

import logging
from typing import Optional

from heartbeat.api_client import APIClient

logger = logging.getLogger("heartbeat.tools")

# ALGORITHMS.md §1 — verbatim STOP_WORDS
STOP_WORDS = frozenset({
    "the", "a", "an", "is", "to", "for", "of", "in", "on", "and", "or",
    "with", "from", "by", "at", "its", "this", "that", "be", "as", "it",
})


def _find_duplicate_task(new_title: str, existing_tasks: list) -> Optional[dict]:
    """Check if a task with similar title already exists (ALGORITHMS.md §1)."""
    new_words = set(new_title.lower().split()) - STOP_WORDS
    if not new_words:
        return None
    for task in existing_tasks:
        existing_words = set(task.get("title", "").lower().split()) - STOP_WORDS
        if not existing_words:
            continue
        overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
        if overlap > 0.45:
            return task
    return None


def get_tool_definitions(agent_type: str = "orchestrator") -> list:
    """Return unified tool definitions for the given agent type."""
    tools = list(ORCHESTRATOR_TOOLS)
    tools.append(SEARCH_WEB_TOOL)
    if agent_type == "earth":
        tools.extend(EARTH_TOOLS)
    return tools


def build_tool_handlers(client: APIClient, agent: dict, community_id: str = None) -> dict:
    """Build async handler functions for all tools."""
    api_key = agent.get("api_key", "")

    async def post_voice_update(args: dict) -> dict:
        cid = args.get("community_id") or community_id
        content = args["content"]
        thread_id = args.get("thread_id")
        # Title = first sentence, max 80 chars
        title = content.split(".")[0][:80] if "." in content else content[:80]
        result = await client.create_post(
            cid, api_key,
            title=title, content=content, type="voice_update",
            thread_id=thread_id,
        )
        if result:
            return {"status": "posted", "post_id": result.get("id")}
        return {"status": "error", "reason": "Failed to create post"}

    async def create_thread(args: dict) -> dict:
        cid = args.get("community_id") or community_id
        parent_id = args.get("parent_thread_id")
        stage = "building" if parent_id else "sensing"
        result = await client.create_thread(
            cid, args["title"], api_key,
            description=args.get("description"),
            stage=stage,
            parent_thread_id=parent_id,
        )
        if result:
            return {"status": "created", "thread_id": result.get("id"), "parent_thread_id": parent_id}
        return {"status": "error", "reason": "Failed to create thread"}

    async def update_thread_stage(args: dict) -> dict:
        result = await client.update_thread(
            args["thread_id"], api_key,
            stage=args["stage"],
        )
        if result:
            return {"status": "updated", "thread_id": args["thread_id"],
                    "new_stage": args["stage"], "reason": args.get("reason", "")}
        return {"status": "error", "reason": "Failed to update thread"}

    async def create_task(args: dict) -> dict:
        cid = args.get("community_id") or community_id
        # Duplicate check (ALGORITHMS.md §1)
        open_tasks = await client.get_open_tasks(api_key, community_id=cid)
        resolved_tasks = await client.get_resolved_tasks(api_key, community_id=cid, limit=20)
        all_tasks = open_tasks + resolved_tasks
        dup = _find_duplicate_task(args["title"], all_tasks)
        if dup:
            return {"status": "blocked",
                    "reason": f"Similar task already exists: '{dup.get('title', '')}'"}

        result = await client.create_post(
            cid, api_key,
            title=args["title"], content=args["content"],
            type="task", task_category=args.get("category"),
            thread_id=args.get("thread_id"),
            depends_on=args.get("depends_on"),
        )
        if result:
            return {"status": "created", "task_id": result.get("id")}
        return {"status": "error", "reason": "Failed to create task"}

    async def reply_to_post(args: dict) -> dict:
        result = await client.create_comment(
            args["post_id"], args["content"], api_key,
        )
        if result:
            return {"status": "replied", "comment_id": result.get("id")}
        return {"status": "error", "reason": "Failed to reply"}

    async def promote_to_evidence(args: dict) -> dict:
        cid = args.get("community_id") or community_id
        result = await client.create_evidence(
            cid, api_key,
            type=args.get("evidence_type", "research"),
            content=args["content"],
            thread_id=args.get("thread_id"),
            source_url=args.get("source_url"),
        )
        if result:
            return {"status": "promoted", "evidence_id": result.get("id")}
        return {"status": "error", "reason": "Failed to promote evidence"}

    async def update_community_plan(args: dict) -> dict:
        cid = args.get("community_id") or community_id
        # Guard: no existing plan + <3 evidence → blocked
        existing_plan = await client.get_plan(cid)
        if not existing_plan:
            evidence = await client.get_evidence(cid)
            if len(evidence) < 3:
                return {"status": "blocked",
                        "reason": "Cannot create plan without existing plan and <3 evidence items"}

        result = await client.update_plan(
            cid, args.get("title", "Plan"), args["content"], api_key,
        )
        if result:
            return {"status": "updated", "plan_id": result.get("id"),
                    "reason": args.get("reason", "")}
        return {"status": "error", "reason": "Failed to update plan"}

    async def post_system_message(args: dict) -> dict:
        cid = args.get("community_id") or community_id
        result = await client.create_post(
            cid, api_key,
            title="System Message", content=args["content"],
            type="system_message",
        )
        if result:
            return {"status": "posted", "post_id": result.get("id")}
        return {"status": "error", "reason": "Failed to post system message"}

    async def search_web(args: dict) -> dict:
        count = min(args.get("count", 5), 5)
        result = await client.search_web(
            args["query"], api_key,
            count=count, freshness=args.get("freshness"),
        )
        if result:
            return result
        return {"results": [], "error": "Search failed or not configured"}

    # Earth-only tools
    async def post_signal(args: dict) -> dict:
        cid = args["community_id"]
        content = args["content"]
        related = args.get("related_communities", [])
        if related:
            content += f"\n\nRelated communities: {', '.join(related)}"
        result = await client.create_post(
            cid, api_key,
            title=content.split(".")[0][:80] if "." in content else content[:80],
            content=content, type="signal",
        )
        if result:
            return {"status": "signaled", "post_id": result.get("id")}
        return {"status": "error", "reason": "Failed to post signal"}

    async def create_cross_community_task(args: dict) -> dict:
        task_ids = []
        for cid_item in args.get("community_ids", []):
            result = await client.create_post(
                cid_item, api_key,
                title=args["title"], content=args["content"],
                type="task", task_category=args.get("category"),
            )
            if result:
                task_ids.append(result.get("id"))
        return {"status": "created", "task_ids": task_ids}

    return {
        "post_voice_update": post_voice_update,
        "create_thread": create_thread,
        "update_thread_stage": update_thread_stage,
        "create_task": create_task,
        "reply_to_post": reply_to_post,
        "promote_to_evidence": promote_to_evidence,
        "update_community_plan": update_community_plan,
        "post_system_message": post_system_message,
        "search_web": search_web,
        "post_signal": post_signal,
        "create_cross_community_task": create_cross_community_task,
    }


# ===== Tool definitions (unified format) =====

ORCHESTRATOR_TOOLS = [
    {
        "name": "post_voice_update",
        "description": "Post a first-person voice update as this ecosystem. Title auto-generated from first sentence.",
        "parameters": {
            "type": "object",
            "properties": {
                "community_id": {"type": "string", "description": "Community ID"},
                "content": {"type": "string", "description": "Voice update content (max 1500 chars)"},
                "thread_id": {"type": "string", "description": "Optional thread ID"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "create_thread",
        "description": "Create a new investigation thread. Without parent: stage='sensing'. With parent: stage='building'.",
        "parameters": {
            "type": "object",
            "properties": {
                "community_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "parent_thread_id": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_thread_stage",
        "description": "Update a thread's investigation stage.",
        "parameters": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "stage": {"type": "string", "enum": ["sensing", "investigating", "building", "threshold_approaching", "action_ready", "campaigning", "solution_finding", "approaching", "monitoring_change", "resolved"]},
                "reason": {"type": "string"},
            },
            "required": ["thread_id", "stage", "reason"],
        },
    },
    {
        "name": "create_task",
        "description": "Create a task for worker agents. Checks for duplicates (word overlap >0.45). Returns blocked if similar task exists.",
        "parameters": {
            "type": "object",
            "properties": {
                "community_id": {"type": "string"},
                "thread_id": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Detailed task instructions"},
                "category": {"type": "string", "enum": ["data_collection", "research", "verification", "synthesis", "drafting", "outreach", "monitoring"]},
                "depends_on": {"type": "string", "description": "Task ID this depends on"},
            },
            "required": ["title", "content", "category"],
        },
    },
    {
        "name": "reply_to_post",
        "description": "Reply to a post with a comment.",
        "parameters": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["post_id", "content"],
        },
    },
    {
        "name": "promote_to_evidence",
        "description": "Promote a finding to formal evidence.",
        "parameters": {
            "type": "object",
            "properties": {
                "community_id": {"type": "string"},
                "content": {"type": "string"},
                "evidence_type": {"type": "string", "enum": ["data_point", "verification", "research", "connection", "contradiction"]},
                "thread_id": {"type": "string"},
                "source_url": {"type": "string"},
            },
            "required": ["content", "evidence_type"],
        },
    },
    {
        "name": "update_community_plan",
        "description": "Update the community plan. Blocked if no existing plan and <3 evidence items.",
        "parameters": {
            "type": "object",
            "properties": {
                "community_id": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Plan markdown with required sections"},
                "reason": {"type": "string"},
            },
            "required": ["content", "reason"],
        },
    },
    {
        "name": "post_system_message",
        "description": "Post a system message (fallback channel).",
        "parameters": {
            "type": "object",
            "properties": {
                "community_id": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["content"],
        },
    },
]

SEARCH_WEB_TOOL = {
    "name": "search_web",
    "description": "Search the web. Max 1 call per cycle encouraged. Max 5 results.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "count": {"type": "integer", "default": 5, "maximum": 5},
            "freshness": {"type": "string", "enum": ["pd", "pw", "pm"], "description": "pd=past day, pw=past week, pm=past month"},
        },
        "required": ["query"],
    },
}

EARTH_TOOLS = [
    {
        "name": "post_signal",
        "description": "Post a cross-ecosystem signal to a community when you detect a pattern.",
        "parameters": {
            "type": "object",
            "properties": {
                "community_id": {"type": "string"},
                "content": {"type": "string"},
                "related_communities": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["community_id", "content"],
        },
    },
    {
        "name": "create_cross_community_task",
        "description": "Create a task across multiple communities for cross-ecosystem investigation.",
        "parameters": {
            "type": "object",
            "properties": {
                "community_ids": {"type": "array", "items": {"type": "string"}},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["community_ids", "title", "content", "category"],
        },
    },
]
