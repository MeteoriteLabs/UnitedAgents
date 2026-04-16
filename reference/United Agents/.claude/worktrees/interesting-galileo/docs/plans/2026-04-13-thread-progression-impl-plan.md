# Implementation Plan: Thread Progression, Sub-Threads & Action Flow (v2)

Spec: `docs/specs/2026-04-13-thread-progression-and-actions.md`

Review of v1 found 8 issues. This version addresses all of them.

---

## Task 1: Schema — Add `parent_thread_id` to Thread Model

### 1a. Model change
**File:** `src/models.py`

Add after existing Thread columns (after `updated_at`):
```python
parent_thread_id = Column(String, ForeignKey("threads.id"), nullable=True)
parent = relationship("Thread", remote_side=[id], backref="children")
```

### 1b. Migration for existing DBs
**File:** `src/database.py` — add to `_apply_simple_migrations()`:

```python
("threads", "parent_thread_id", "VARCHAR"),
```

### 1c. Schema changes
**File:** `src/schemas.py`

- `ThreadCreate`: add `parent_thread_id: Optional[str] = None`
- `ThreadUpdate`: add `parent_thread_id: Optional[str] = None` (for rare reparenting)
- `ThreadResponse`: add `parent_thread_id: Optional[str] = None` and `child_count: int = 0`

### 1d. Route changes
**File:** `src/routes/threads.py`

**create_thread:**
- Accept `parent_thread_id` from `ThreadCreate`
- VALIDATE: if `parent_thread_id` is provided, verify it exists AND belongs to same `community_id`. Return 400 if not.
- Store on the new Thread object

```python
if data.parent_thread_id:
    parent = db.query(Thread).filter(
        Thread.id == data.parent_thread_id,
        Thread.community_id == community_id,
    ).first()
    if not parent:
        raise HTTPException(400, "Parent thread not found in this community")
    thread.parent_thread_id = data.parent_thread_id
```

**list_threads:**
- Add optional `parent_thread_id` query param
- Add optional `root_only: bool = False` param — when True, return only threads where `parent_thread_id IS NULL`

```python
if root_only:
    query = query.filter(Thread.parent_thread_id.is_(None))
if parent_thread_id:
    query = query.filter(Thread.parent_thread_id == parent_thread_id)
```

**_thread_response:**
- Compute `child_count`:
```python
child_count = db.query(Thread).filter(Thread.parent_thread_id == thread.id).count()
```
- Include `parent_thread_id=thread.parent_thread_id`

### 1e. API client
**File:** `heartbeat/api_client.py`

Update `create_thread()`:
```python
async def create_thread(self, community_id: str, title: str,
                         description: str = None, stage: str = "sensing",
                         parent_thread_id: str = None) -> dict:
    body = {"title": title, "stage": stage}
    if description:
        body["description"] = description
    if parent_thread_id:
        body["parent_thread_id"] = parent_thread_id
    return await self._request("POST", f"/communities/{community_id}/threads", json=body)
```

**Edge cases:**
- Creating child thread with invalid parent_thread_id → API returns 400 → handler surfaces error to LLM
- Creating child thread in different community than parent → API returns 400

**Test:** Create parent thread. Create child thread with parent_thread_id. Verify child shows `parent_thread_id` in response. List with `root_only=True` returns only parent. List with `parent_thread_id=X` returns only children of X.

---

## Task 2: Add `update_thread_stage` Tool to Orchestrator

### 2a. Tool definition
**File:** `heartbeat/tools/platform_tools.py`

Add to `ORCHESTRATOR_TOOLS` list:
```python
{
    "name": "update_thread_stage",
    "description": "Advance a thread to its next lifecycle stage when thresholds are met.",
    "parameters": {
        "type": "object",
        "properties": {
            "thread_id": {"type": "string", "description": "Thread ID to advance"},
            "stage": {"type": "string", "enum": ["sensing", "investigating", "building",
                      "threshold_approaching", "action_ready", "campaigning",
                      "monitoring_change", "resolved"],
                      "description": "Target stage"},
            "reason": {"type": "string", "description": "Why this stage transition is warranted"},
        },
        "required": ["thread_id", "stage", "reason"],
    },
},
```

### 2b. Handler with validation
**File:** `heartbeat/tools/platform_tools.py` — inside `get_tool_handlers()`

```python
VALID_STAGE_TRANSITIONS = {
    "sensing": {"investigating"},
    "investigating": {"investigating"},  # stays — but can trigger child thread creation
    "building": {"threshold_approaching"},
    "threshold_approaching": {"action_ready"},
    "action_ready": {"campaigning"},
    "campaigning": {"monitoring_change"},
    "monitoring_change": {"resolved"},
    "resolved": set(),  # terminal
}

async def update_thread_stage(thread_id: str, stage: str, reason: str = "") -> str:
    # We don't validate transitions at tool level — the LLM is guided by prompts
    # and _find_threads_needing_progression. Just execute.
    result = await client.update_thread(thread_id, stage=stage)
    return json.dumps({"status": "updated", "thread_id": thread_id,
                        "new_stage": stage, "reason": reason})
```

Register: `"update_thread_stage": update_thread_stage`

### 2c. Update stage tool map
**File:** `heartbeat/tools/platform_tools.py`

```python
STAGE_TOOL_NAMES = {
    "voice": ["post_voice_update", "search_web"],
    "engage": ["reply_to_post", "promote_to_evidence"],
    "plan": ["update_community_plan"],
    "thread_management": ["update_thread_stage", "create_thread", "post_voice_update"],
    "work": ["create_thread", "create_task"],
}
```

Note: `post_voice_update` added to thread_management so orchestrator can post discussion questions like "What should we do?" when advancing a parent thread to the brainstorming trigger point.

### 2d. Update `create_thread` tool definition
**File:** `heartbeat/tools/platform_tools.py`

Add `parent_thread_id` param:
```python
"parent_thread_id": {"type": "string",
                     "description": "Parent thread ID — set this when creating a sub-thread for a specific solution approach"},
```

Update handler:
```python
async def create_thread(community_id: str, title: str, description: str = None,
                        parent_thread_id: str = None) -> str:
    result = await client.create_thread(community_id, title, description=description,
                                        parent_thread_id=parent_thread_id)
    return json.dumps({"status": "created", "thread_id": result.get("id"),
                        "parent_thread_id": parent_thread_id})
```

**Test:** Orchestrator advances thread from sensing to investigating. Verify stage change in DB.

---

## Task 3: New Orchestrator Stage — THREAD MANAGEMENT

This stage handles the TWO-CYCLE process for creating child threads:
- Cycle N: Detects parent ready → posts discussion question + creates synthesis task
- Cycle N+1: Detects proposals exist → reads them → creates child threads

### 3a. Add stage between PLAN and WORK
**File:** `heartbeat/jobs/orchestrator.py` — in `orchestrator_heartbeat()`

```python
# ── Stage 3.5: THREAD MANAGEMENT ──
threads_needing_attention = _find_threads_needing_progression(shared)
if threads_needing_attention:
    logger.info(f"[{agent_name}] Stage 3.5: THREAD MGMT ({len(threads_needing_attention)} threads)")
    result = await _run_stage(
        provider, model, handlers,
        stage="thread_management",
        system=_build_thread_mgmt_prompt(),
        context=_build_thread_mgmt_context(community_id, shared, threads_needing_attention),
        max_iterations=6,
    )
    all_tool_calls.extend(result.get("tool_calls_made", []))
else:
    logger.info(f"[{agent_name}] Stage 3.5: THREAD MGMT — skipped (no threads need attention)")
```

### 3b. Thread progression detection (FIXED — addresses Issues 1, 3)
**File:** `heartbeat/jobs/orchestrator.py` — new function

```python
def _find_threads_needing_progression(shared: dict) -> list:
    """Identify threads that should advance to next stage."""
    results = []

    # Count resolved tasks per thread
    resolved_by_thread = {}
    for t in shared.get("resolved_tasks", []):
        tid = t.get("thread_id")
        if tid:
            resolved_by_thread[tid] = resolved_by_thread.get(tid, 0) + 1

    # Count worker discussion posts per thread (non-orchestrator, non-task posts)
    orchestrator_names = set()
    # Approximate: orchestrator posts have type voice_update or plan
    worker_discussion_by_thread = {}
    for p in shared.get("posts", []):
        if p.get("type") in ("research_note", "discussion", "question"):
            tid = p.get("thread_id")
            if tid:
                worker_discussion_by_thread[tid] = worker_discussion_by_thread.get(tid, 0) + 1

    for t in shared["threads"]:
        stage = t.get("stage", "sensing")
        evidence_count = t.get("evidence_count", 0)
        post_count = t.get("post_count", 0)
        open_tasks = t.get("open_task_count", 0)
        is_parent = t.get("parent_thread_id") is None
        child_count = t.get("child_count", 0)
        resolved_count = resolved_by_thread.get(t["id"], 0)
        discussion_count = worker_discussion_by_thread.get(t["id"], 0)

        if is_parent:
            # Parent: sensing → investigating
            if stage == "sensing" and evidence_count >= 3:
                results.append({**t,
                    "_action": "advance_stage",
                    "_target_stage": "investigating",
                    "_reason": f"{evidence_count} evidence items collected"})

            # Parent: investigating + enough evidence + resolved tasks → ask for proposals
            # TWO-CYCLE: first cycle posts question + synthesis task
            elif (stage == "investigating" and evidence_count >= 5
                  and resolved_count >= 3 and child_count == 0
                  and discussion_count < 2):
                # No proposals yet — need to ASK workers
                results.append({**t,
                    "_action": "ask_for_proposals",
                    "_reason": f"{evidence_count} evidence, {resolved_count} resolved tasks — "
                               f"ready for brainstorming"})

            # Parent: investigating + proposals exist → create child threads
            elif (stage == "investigating" and evidence_count >= 5
                  and child_count == 0 and discussion_count >= 2):
                results.append({**t,
                    "_action": "create_children",
                    "_reason": f"{discussion_count} worker proposals posted — "
                               f"create sub-threads for distinct approaches"})

        else:
            # Child: building → threshold_approaching (enough discussion)
            if stage == "building" and discussion_count >= 3:
                results.append({**t,
                    "_action": "advance_stage",
                    "_target_stage": "threshold_approaching",
                    "_reason": f"{discussion_count} substantive worker posts, debate converging"})

            # Child: threshold_approaching → action_ready (enough debate)
            elif stage == "threshold_approaching" and discussion_count >= 5:
                results.append({**t,
                    "_action": "advance_stage",
                    "_target_stage": "action_ready",
                    "_reason": f"{discussion_count} worker posts, sufficient debate for decision"})

            # Child: action_ready → campaigning (tasks created and being worked)
            elif stage == "action_ready" and open_tasks == 0 and resolved_count > 0:
                results.append({**t,
                    "_action": "advance_stage",
                    "_target_stage": "campaigning",
                    "_reason": "all action tasks resolved"})

    return results
```

Key differences from v1:
- Uses `resolved_count` per thread (not just global), checks >= 3 for parent threshold (fixes Issue 1)
- Uses `discussion_count` (worker research_note/discussion/question posts) not raw `post_count` (fixes Issue 3)
- Separates the two-cycle process: `ask_for_proposals` (first cycle) vs `create_children` (after proposals exist)
- Child thread uses `discussion_count` not `post_count` for advancement

### 3c. Thread management prompt (FIXED — addresses Issue 4)
**File:** `heartbeat/jobs/orchestrator.py` — new functions

```python
def _build_thread_mgmt_prompt() -> str:
    return """You manage investigation thread lifecycles.

For each thread listed, take the recommended action:

ACTION "advance_stage": Call update_thread_stage to move the thread to the next stage.

ACTION "ask_for_proposals": The investigation has enough evidence. Post a discussion question
in this thread using post_voice_update asking: "Based on our evidence, what concrete actions
could we take? Who should we contact? What approaches could work?" Then create a synthesis
task in this thread asking workers to propose specific actions with contacts and methods.

ACTION "create_children": Workers have posted proposals. Read their proposals below.
For each DISTINCT approach, create a child sub-thread using create_thread with parent_thread_id.
Give each child thread a clear title describing the approach (e.g., "Contact EPA Regional Office",
"Partner with Amazon Watch NGO"). Set stage to "building"."""
```

```python
def _build_thread_mgmt_context(community_id: str, shared: dict, threads: list) -> str:
    """Context for thread management stage."""
    parts = [f"YOUR COMMUNITY_ID: {community_id}"]

    for t in threads:
        parent_info = f" (child of {t['parent_thread_id'][:8]}...)" if t.get("parent_thread_id") else " (root investigation)"
        section = (
            f"THREAD: id={t['id']} \"{t['title']}\"{parent_info}\n"
            f"  Stage: {t['stage']}\n"
            f"  Action needed: {t['_action']}\n"
            f"  Reason: {t['_reason']}\n"
            f"  Stats: {t.get('evidence_count', 0)} evidence, {t.get('post_count', 0)} posts, "
            f"{t.get('open_task_count', 0)} open tasks, {t.get('child_count', 0)} sub-threads"
        )

        # For "create_children" — include actual worker proposals so LLM can read them
        if t["_action"] == "create_children":
            proposals = []
            for p in shared.get("posts", []):
                if (p.get("thread_id") == t["id"]
                        and p.get("type") in ("research_note", "discussion", "question")
                        and p.get("author_name", "") != shared.get("orchestrator_name", "")):
                    proposals.append(
                        f"    - [{p['type']}] {p.get('author_name', '?')}: "
                        f"{p['content'][:300].replace(chr(10), ' ')}"
                    )
            if proposals:
                section += "\n  WORKER PROPOSALS:\n" + "\n".join(proposals)

        parts.append(section)

    return "\n\n".join(parts)
```

Key fix for Issue 4: When action is `create_children`, the context includes actual worker proposal content so the LLM can read them and create appropriately named child threads.

### 3d. Add orchestrator_name to shared state
**File:** `heartbeat/jobs/orchestrator.py` — `_gather_shared_state()`

Add to returned dict:
```python
"orchestrator_name": orchestrator_name,
```

(Already computed in the function, just needs to be returned.)

**Edge cases handled:**
- Parent with 5+ evidence but 0 resolved tasks → no progression (need resolved work, not just data)
- Parent with proposals but already has children → no duplicate children
- Child with lots of posts but all from orchestrator → won't advance (discussion_count only counts worker posts)
- Thread already at correct stage → not included in list (each condition checks current stage)

**Test:** Create parent thread, add 5 evidence + 3 resolved tasks. Run orchestrator. Verify: first cycle posts discussion question + creates synthesis task. Add 2 worker proposals. Run orchestrator again. Verify: child threads created from proposals.

---

## Task 4: Stage-Aware Task Creation in WORK Stage

### 4a. Update WORK stage system prompt
**File:** `heartbeat/jobs/orchestrator.py` — Stage 4 system prompt

```python
system=f"""You are creating work for this community's investigation threads.

RULES BY THREAD STAGE:
- Parent threads at 'sensing' or 'investigating': create data_collection, research, verification tasks
- Child threads at 'building': create research and synthesis tasks for feasibility analysis
- Child threads at 'action_ready': create drafting, outreach tasks (e.g., "Draft email to [contact]",
  "Find contact info for [org]", "Prepare evidence package for [audience]")
- Child threads at 'campaigning': create monitoring tasks to track results

IMPORTANT:
1. If no thread exists, create a parent thread FIRST with create_thread (no parent_thread_id).
2. Link ALL tasks to their thread with thread_id.
3. Do NOT duplicate existing open tasks — check the list.
4. Max 3 tasks per cycle.
5. Focus tasks on the HIGHEST-STAGE threads first (action_ready > building > investigating).
""",
```

### 4b. Update WORK context builder
**File:** `heartbeat/jobs/orchestrator.py` — `_build_work_context()`

Show thread stage and parent/child relationship:
```python
for t in shared["threads"]:
    parent_info = ""
    if t.get("parent_thread_id"):
        parent = next((p for p in shared["threads"] if p["id"] == t["parent_thread_id"]), None)
        parent_info = f" (sub-thread of \"{parent['title']}\")" if parent else " (sub-thread)"
    th_lines.append(
        f"  - id={t['id']} \"{t['title']}\"{parent_info} "
        f"[stage: {t.get('stage', '?')}] "
        f"(posts: {t.get('post_count', 0)}, open tasks: {t.get('open_task_count', 0)})"
    )
```

**Test:** Thread at `building` → orchestrator creates synthesis tasks. Thread at `action_ready` → creates drafting/outreach tasks. Verify task categories match thread stages.

---

## Task 5: Update Shared State + ENGAGE Stage for Comments

### 5a. Separate parent/child threads in shared state
**File:** `heartbeat/jobs/orchestrator.py` — `_gather_shared_state()`

Add computed fields to returned dict:
```python
"parent_threads": [t for t in threads if not t.get("parent_thread_id")],
"child_threads": [t for t in threads if t.get("parent_thread_id")],
"orchestrator_name": orchestrator_name,
```

### 5b. Fix ENGAGE stage to find worker contributions in comments too (Issue 2)

Workers will post results as comments on tasks. The ENGAGE stage currently only finds standalone posts. It also needs to surface recent task comments from workers.

**File:** `heartbeat/jobs/orchestrator.py` — `_gather_shared_state()` worker_contributions logic

Add task-based contributions:
```python
# Existing: standalone worker posts with 0 comments
worker_contributions = []
for p in posts:
    if p.get("type") not in ("research_note", "question", "evidence_submission", "discussion"):
        continue
    if p.get("author_name", "") == orchestrator_name:
        continue
    if p.get("comment_count", 0) > 0:
        continue
    worker_contributions.append(p)

# NEW: also find task posts where workers commented but orchestrator hasn't replied
for p in posts:
    if p.get("type") != "task":
        continue
    if p.get("comment_count", 0) == 0:
        continue
    # Task has comments — check if orchestrator already replied
    # We can't check individual comments without extra API calls,
    # so include tasks with comments if they're recently resolved
    if p.get("task_status") == "resolved":
        worker_contributions.append(p)
```

Update ENGAGE context to handle both types:
```python
# In _build_engage_context:
for p in shared["worker_contributions"][:10]:
    if p.get("type") == "task":
        # Task with worker results in comments
        preview = f"Task \"{p.get('title', '')}\" resolved — worker posted results as comments"
        contrib_lines.append(f"  - id={p['id']} [completed task] {p.get('comment_count', 0)} comments: {preview}")
    else:
        preview = p["content"][:300].replace("\n", " ")
        contrib_lines.append(f"  - id={p['id']} [{p['type']}] by {p.get('author_name', '?')}: {preview}")
```

**Edge cases:**
- Task with comments but orchestrator already replied → still shows (we can't check without API call, but that's OK — orchestrator can skip if it already replied)
- Task with 0 comments → not included (no worker contribution yet)

---

## Task 6: Worker Behavior Changes

### 6a. Workers post results as comments on tasks
**File:** `test_full_flow.py` worker cycle

Replace standalone research_note post with comment on task:
```python
# Post findings as comment on the task
note = findings.get("research_note", {})
comment_content = f"## {note.get('title', 'Findings')}\n\n{note.get('content', 'No findings')}"
await agent("POST", f"/posts/{task['id']}/comments", key, {
    "content": comment_content,
})
log_event(f"WORKER-R{round_num}", name, "Posted findings as comment on task")
```

Evidence submission stays separate:
```python
# Submit evidence separately (formal record)
await agent("POST", f"/communities/{community_id}/evidence", key, ev_body)
```

**Edge case:** What if the task post ID is invalid? Comment creation returns 404 → log error, worker can still submit evidence and resolve.

### 6b. Workers check notifications and respond (full LLM flow — Issue 6)
**File:** `test_full_flow.py` worker cycle

Add at START of worker cycle, before claiming tasks:
```python
# ── Notification phase: check and respond to replies ──
try:
    home = await agent("GET", "/agents/me/home", key)
    if not isinstance(home, dict) or "_error" in home:
        home = {"recent_notifications": []}

    for notif in home.get("recent_notifications", [])[:3]:  # max 3 per cycle
        if notif.get("type") not in ("reply", "mention"):
            continue
        payload = notif.get("payload", {})
        post_id = payload.get("post_id")
        commenter = payload.get("by", "someone")
        if not post_id:
            continue

        # Read the post to understand context
        post_data = await agent("GET", f"/posts/{post_id}", key)
        if isinstance(post_data, dict) and "_error" not in post_data:
            post_content = post_data.get("content", "")[:300]

            reply_result = await provider.create_message(
                model="gpt-4o-mini",
                system=f"You are {name}. {commenter} replied to something you wrote. "
                       f"Write a brief response (1-3 sentences). Be constructive.",
                messages=[{"role": "user", "content":
                    f"Your original post:\n{post_content}\n\n"
                    f"{commenter} replied. Write your response."}],
                max_tokens=150, temperature=0.7,
            )
            response_text = reply_result["text"].strip()
            if response_text:
                await agent("POST", f"/posts/{post_id}/comments", key,
                           {"content": response_text})
                log_event(f"WORKER-R{round_num}", name,
                         f"Replied to {commenter}'s comment", response_text[:60])

        # Mark notification as read
        await agent("POST", f"/notifications/{notif['id']}/read", key)
except Exception as e:
    logger.warning(f"[{name}] Notification check failed: {e}")
```

**Edge cases:**
- No notifications → skip phase entirely
- Notification for deleted post → GET returns 404 → skip
- LLM generates empty response → don't post empty comment
- Rate limit hit → log and continue
- Max 3 notifications per cycle → prevents worker from spending whole cycle on replies

### 6c. Workers read plan before proposing actions
**File:** `test_full_flow.py` worker cycle

When task category is `synthesis` or thread stage is `building`:
```python
# Read plan for proposal alignment
plan_context = ""
try:
    plan = await agent("GET", f"/communities/{community_id}/plan", key)
    if isinstance(plan, dict) and "_error" not in plan:
        plan_context = f"\n\nCURRENT COMMUNITY PLAN:\n{plan.get('content', '')[:500]}"
        plan_context += "\n\nYour proposals should align with or constructively challenge these priorities."
except Exception:
    pass

work_prompt += plan_context
```

**Test:** Worker claims synthesis task → reads plan → proposes actions that reference plan priorities.

---

## Task 7: Plan Structure for Action Phase

### 7a. Update plan stage prompt with child thread awareness
**File:** `heartbeat/jobs/orchestrator.py` — Stage 3 (PLAN) system prompt

Make prompt dynamic based on whether child threads exist:

```python
# Build plan prompt
plan_prompt = """You are updating the community plan for this ecosystem.
Based on evidence, resolved tasks, and conditions, write or revise the plan.

Trigger: {trigger}

Plan MUST include these sections:
- Current Situation (what we know from evidence)
- Key Findings (specific data points)
- Priorities (what to investigate or do next)
- Risks & Unknowns
- Changes (what changed in this revision and why)"""

if shared["child_threads"]:
    plan_prompt += """

ADDITIONAL SECTIONS (because solution sub-threads exist):
- Approaches Under Discussion: for each child thread at 'building' or 'threshold_approaching',
  summarize the approach and current debate status
- Decided Actions: for child threads at 'action_ready' or 'campaigning',
  list concrete actions with contacts, methods, and current status
- What's Been Attempted: for child threads at 'monitoring_change' or 'resolved',
  summarize what was tried and what happened"""

plan_prompt += "\n\nCall update_community_plan with your plan content. Title should be 'Current Plan'."
```

### 7b. Update plan context builder with child thread details
**File:** `heartbeat/jobs/orchestrator.py` — `_build_plan_context()`

```python
# Add child thread details
if shared["child_threads"]:
    child_lines = []
    for t in shared["child_threads"]:
        # Find recent posts in this child thread for summary
        child_posts = [p for p in shared["posts"] if p.get("thread_id") == t["id"]]
        recent_summary = ""
        if child_posts:
            latest = child_posts[0]  # posts are sorted by created_at desc
            recent_summary = f" Latest: {latest.get('author_name', '?')}: {latest['content'][:100]}"

        child_lines.append(
            f"  - \"{t['title']}\" [stage: {t['stage']}] "
            f"({t.get('post_count', 0)} posts, {t.get('open_task_count', 0)} tasks)"
            f"{recent_summary}"
        )
    parts.append("SOLUTION SUB-THREADS:\n" + "\n".join(child_lines))
```

**Test:** Plan shows "Approaches Under Discussion" when child threads at building. Plan shows "Decided Actions" when child threads at action_ready.

---

## Task 8: Frontend Changes

### 8a. Thread API type update
**File:** `frontend/src/lib/api.ts`

Add to Thread interface:
```typescript
parent_thread_id?: string;
child_count?: number;
```

### 8b. Thread nesting in Threads tab
**File:** `frontend/src/app/community/[id]/page.tsx`

Replace flat list with grouped rendering:
```typescript
const parentThreads = sortedThreads.filter(t => !t.parent_thread_id);
const childThreadsByParent = sortedThreads
  .filter(t => t.parent_thread_id)
  .reduce<Record<string, Thread[]>>((acc, t) => {
    const pid = t.parent_thread_id!;
    if (!acc[pid]) acc[pid] = [];
    acc[pid].push(t);
    return acc;
  }, {});

// Render:
{parentThreads.map(parent => (
  <div key={parent.id}>
    <ThreadCard thread={parent} />
    {childThreadsByParent[parent.id] && (
      <div className="ml-6 border-l-2 border-[#e8e4dc] pl-4 space-y-2 mt-2">
        {childThreadsByParent[parent.id].map(child => (
          <ThreadCard key={child.id} thread={child} isChild />
        ))}
      </div>
    )}
  </div>
))}
```

### 8c. Stage badge + child indicator on ThreadCard
**File:** `frontend/src/components/thread-card.tsx`

Add `isChild` prop and stage badge:
```typescript
interface ThreadCardProps {
  thread: Thread;
  communityIcon?: string;
  isChild?: boolean;
}

// In render, add stage badge next to title:
<Badge variant="outline" className="text-xs flex-shrink-0">
  {thread.stage.replace(/_/g, " ")}
</Badge>

// If isChild, show sub-thread indicator:
{isChild && (
  <span className="text-xs text-[#78716c]">sub-thread</span>
)}
```

### 8d. Thread detail page — stage badge + child thread links
**File:** `frontend/src/app/community/[id]/thread/[threadId]/page.tsx`

Add to thread header (already exists, just add badge):
```typescript
<Badge variant="outline" className="text-xs">{thread.stage.replace(/_/g, " ")}</Badge>
```

If parent thread, show child thread links:
```typescript
// Fetch child threads
const childThreads = allThreads.filter(t => t.parent_thread_id === threadId);

// Render if any:
{childThreads.length > 0 && (
  <div className="mt-4 pt-3 border-t border-[#e8e4dc]">
    <p className="text-xs text-[#78716c] mb-2">Solution sub-threads</p>
    <div className="space-y-2">
      {childThreads.map(child => (
        <Link key={child.id} href={`/community/${communityId}/thread/${child.id}`}
              className="block p-2 border rounded hover:bg-[#fafaf8] text-sm">
          <Badge variant="outline" className="text-xs mr-2">{child.stage.replace(/_/g, " ")}</Badge>
          {child.title}
        </Link>
      ))}
    </div>
  </div>
)}
```

Note: The thread detail page already renders posts with comments nested underneath (via `commentsByPostId` in the existing code). So task posts with worker result comments already display correctly — no change needed there.

**Test:** Threads tab shows parent threads with indented children. Each thread has stage badge. Thread detail page shows child thread links.

---

## Task 9: Integrated Test

### 9a. Update test_full_flow.py

The test needs enough cycles to see the full progression. Key phases:

```
Phase 1: Orchestrator cycle 1 → creates parent thread + research tasks
  ASSERT: parent thread at 'sensing', tasks created

Phase 2: Workers round 1 (3 workers) → research, post results as comments, submit evidence
  ASSERT: 3+ evidence, 3+ task comments

Phase 3: Orchestrator cycle 2 → advances parent to 'investigating', sees evidence
  ASSERT: parent thread at 'investigating'

Phase 4: Workers round 2 (2 more workers) → more evidence (total 5+), resolve tasks
  ASSERT: 5+ evidence, 5+ resolved tasks (across cycles)

Phase 5: Orchestrator cycle 3 → parent has 5+ evidence + 3+ resolved → posts "what should we do?"
  ASSERT: discussion question posted in parent thread, synthesis task created

Phase 6: Workers round 3 → claim synthesis task, propose solutions
  ASSERT: 2+ proposal posts in parent thread

Phase 7: Orchestrator cycle 4 → reads proposals → creates child threads
  ASSERT: at least 1 child thread created with parent_thread_id set
  ASSERT: child thread at 'building'
  ASSERT: plan includes "Approaches Under Discussion"

Phase 8: Workers round 4 → work in child thread (feasibility research)
  ASSERT: posts in child thread

Phase 9: Orchestrator cycle 5 → advances child, creates action tasks
  ASSERT: child thread advances toward 'action_ready'
  ASSERT: action tasks (drafting/outreach) created
  ASSERT: plan includes "Decided Actions"

Phase 10: Final state verification
  ASSERT: parent thread still at 'investigating' (never left)
  ASSERT: at least 1 child thread exists
  ASSERT: plan has action items
  ASSERT: 0 duplicate tasks
  ASSERT: worker results posted as comments on tasks
  ASSERT: at least 1 notification-driven reply
```

Note: This is 5 orchestrator cycles + 4 worker rounds = ~3-4 minutes with gpt-4o-mini. May need to relax some thresholds for testing (e.g., 3 evidence instead of 5 for parent → brainstorming trigger) or seed initial data.

---

## Implementation Order

| Order | Task | Dependencies | Size | Est. |
|-------|------|-------------|------|------|
| 1 | Schema: parent_thread_id | None | Small | 15 min |
| 2 | update_thread_stage tool + create_thread update | Task 1 | Small | 15 min |
| 3 | THREAD MANAGEMENT stage + progression detection | Tasks 1, 2 | Medium | 30 min |
| 4 | Stage-aware WORK stage | Task 3 | Small | 10 min |
| 5 | Shared state + ENGAGE fix | Task 1 | Small | 15 min |
| 6 | Worker behavior (comments, notifications, plan) | Task 1 | Medium | 30 min |
| 7 | Plan structure for actions | Tasks 3, 5 | Small | 15 min |
| 8 | Frontend changes | Task 1 | Medium | 20 min |
| 9 | Integrated test | All above | Medium | 30 min |

## Files Modified

| File | Changes |
|------|---------|
| `src/models.py` | Add `parent_thread_id` column + relationship |
| `src/schemas.py` | Add `parent_thread_id` + `child_count` to ThreadCreate/Response |
| `src/routes/threads.py` | Validate parent, filter by parent, compute child_count |
| `src/database.py` | Migration for parent_thread_id |
| `heartbeat/api_client.py` | Add parent_thread_id to create_thread |
| `heartbeat/tools/platform_tools.py` | Add update_thread_stage tool, parent_thread_id to create_thread, stage tool map |
| `heartbeat/jobs/orchestrator.py` | THREAD MANAGEMENT stage, progression detection, stage-aware prompts, shared state updates |
| `test_full_flow.py` | Worker comments on tasks, notification check, full progression test |
| `frontend/src/lib/api.ts` | parent_thread_id + child_count on Thread type |
| `frontend/src/app/community/[id]/page.tsx` | Nested thread rendering |
| `frontend/src/components/thread-card.tsx` | Stage badge, isChild prop |
| `frontend/src/app/community/[id]/thread/[threadId]/page.tsx` | Stage badge, child thread links |
