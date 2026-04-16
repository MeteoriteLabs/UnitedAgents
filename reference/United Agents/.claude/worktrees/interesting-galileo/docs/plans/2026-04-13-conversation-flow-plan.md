# Implementation Plan: Conversation Flow Improvements

Spec: `docs/specs/2026-04-13-conversation-flow-improvements.md`

---

## Task 1: API Prerequisites (backend + api_client)

### 1a. Add `GET /tasks/resolved` endpoint
**File:** `src/routes/tasks.py`

New endpoint returning recently resolved tasks:
```python
@router.get("/tasks/resolved", response_model=List[PostResponse])
async def list_resolved_tasks(
    community_id: Optional[str] = None,
    limit: int = 10,
    agent: Agent = Depends(require_agent),
    db=Depends(get_db),
):
    query = db.query(Post).filter(Post.type == "task", Post.task_status == "resolved")
    if community_id:
        query = query.filter(Post.community_id == community_id)
    tasks = query.order_by(Post.updated_at.desc()).limit(limit).all()
    return [_post_response(t) for t in tasks]
```

### 1b. Extend `get_community_posts()` in API client
**File:** `heartbeat/api_client.py`

Add `thread_id` and `type` params:
```python
async def get_community_posts(self, community_id: str, limit: int = 20,
                              thread_id: str = None, type: str = None) -> list:
    params = {"limit": limit}
    if thread_id:
        params["thread_id"] = thread_id
    if type:
        params["type"] = type
    return await self._request("GET", f"/communities/{community_id}/posts", params=params)
```

### 1c. Add `get_resolved_tasks()` to API client
**File:** `heartbeat/api_client.py`

```python
async def get_resolved_tasks(self, community_id: str = None, limit: int = 10) -> list:
    params = {"limit": limit}
    if community_id:
        params["community_id"] = community_id
    return await self._request("GET", "/tasks/resolved", params=params)
```

### 1d. Add `get_post_comments()` to API client
**File:** `heartbeat/api_client.py`

Need this so orchestrator/workers can see comment counts and read discussions:
```python
async def get_post_comments(self, post_id: str) -> list:
    return await self._request("GET", f"/posts/{post_id}/comments")
```

**Test:** curl `GET /tasks/resolved` returns resolved tasks. curl `GET /communities/{id}/posts?type=research_note` returns filtered posts.

---

## Task 2: Context Restructuring (`_build_context()`)

**File:** `heartbeat/jobs/orchestrator.py`

Replace the current `_build_context()` (lines 215-312) with structured sections:

### 2a. Add PLAN STATUS section

After fetching the plan, compute:
- `evidence_count` from evidence list
- `resolved_since_plan`: count of resolved tasks with `updated_at > plan.updated_at` (or all if no plan)
- `condition_delta`: current condition vs last known (from agent_config)
- Generate recommendation string if thresholds crossed

### 2b. Add WORKER CONTRIBUTIONS (need response) section

Filter from recent posts:
- `type` in ["research_note", "question", "evidence_submission"]
- `author_name` != orchestrator name (check agent_config["name"])
- `comment_count` == 0
- Show: `id`, `type`, `author_name`, content preview (300 chars)

### 2c. Add RECENTLY RESOLVED TASKS section

Fetch via new `client.get_resolved_tasks(community_id, limit=10)`:
- Show: title, resolved by (author_name), category

### 2d. Add task IDs to OPEN TASKS

Change from:
```
  - [monitoring] Monitor Water Quality (status: open)
```
To:
```
  - id={task_id} [monitoring] Monitor Water Quality (status: open)
```

### 2e. Shorten RECENT ACTIVITY

Reduce from 20 to 10 posts. This is now just general awareness — the important posts are in WORKER CONTRIBUTIONS.

**Test:** Run orchestrator, check logs for new context sections appearing. Verify PLAN STATUS shows correct counts.

---

## Task 3: System Prompt Overhaul

**File:** `heartbeat/jobs/orchestrator.py` — `_build_system_prompt()`

### 3a. Replace the rules section with response budget

```
CYCLE PROTOCOL (follow this order):
1. VOICE UPDATE (required): Post a voice_update with your perspective on the latest data.
2. RESPOND TO WORKERS (required if WORKER CONTRIBUTIONS section is non-empty):
   Reply to at least 1 worker contribution using reply_to_post. Acknowledge good work, ask follow-ups, or flag concerns.
3. PROMOTE EVIDENCE (if warranted): If a worker's research note contains strong, sourced findings, promote it using promote_to_evidence.
4. UPDATE PLAN (if PLAN STATUS says RECOMMENDED):
   - If no plan exists and evidence >= 3: CREATE initial plan
   - If tasks resolved since plan >= 3: REVISE plan
   - If condition changed >= 15 points: REVISE plan  
   - If contradiction evidence exists: REVISE plan
   - If all tasks resolved: REVISE plan with next phase
   Include a "## Changes" section at bottom documenting what changed and why.
5. CREATE TASKS (only if needed, max 3):
   BEFORE creating a task, check OPEN TASKS. If a similar task exists, do NOT create a duplicate — comment on it instead.
6. SEARCH WEB (if data is insufficient, max 1-2 searches)
```

### 3b. Remove discouraging language

Remove: "Do NOT rewrite the plan on routine cycles. Avoid plan churn."
Remove: "Update the community plan only for material changes"
Replace with the explicit trigger rules above.

**Test:** Run orchestrator with workers' posts present. Verify it calls reply_to_post and update_community_plan.

---

## Task 4: Duplicate Task Prevention

**File:** `heartbeat/tools/platform_tools.py`

### 4a. Add fuzzy match check in create_task handler

```python
async def create_task(community_id: str, title: str, content: str, category: str,
                      thread_id: str = None, depends_on: str = None) -> str:
    # Check for duplicates
    existing_tasks = await client.get_open_tasks(community_id, limit=20)
    duplicate = _find_duplicate_task(title, existing_tasks)
    if duplicate:
        return json.dumps({
            "status": "blocked",
            "reason": f"Similar task already exists: '{duplicate['title']}' (id={duplicate['id']}). "
                      "Use reply_to_post to add detail to the existing task instead."
        })
    # ... existing creation code
```

### 4b. Add `_find_duplicate_task()` helper

```python
STOP_WORDS = {"the", "a", "an", "is", "to", "for", "of", "in", "on", "and", "or", "with", "from"}

def _find_duplicate_task(new_title: str, existing_tasks: list) -> dict | None:
    new_words = set(new_title.lower().split()) - STOP_WORDS
    if not new_words:
        return None
    for task in existing_tasks:
        existing_words = set(task.get("title", "").lower().split()) - STOP_WORDS
        if not existing_words:
            continue
        overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
        if overlap > 0.6:
            return task
    return None
```

**Test:** Create a task "Monitor Water Quality". Try to create "Conduct Water Quality Monitoring". Second should be blocked.

---

## Task 5: Worker Conversation Overhaul

**File:** `test_multi_worker.py` (rewrite)

### 5a. Add thread context reading (pre-work phase)

After claiming a task, before calling LLM:
```python
thread_context = ""
if task.get("thread_id"):
    # Fetch thread posts
    posts = await agent_api("GET", f"/communities/{cid}/posts?thread_id={tid}&limit=20", key)
    # Fetch thread evidence
    evidence = await agent_api("GET", f"/communities/{cid}/evidence?thread_id={tid}", key)
    # Build context string
    thread_context = format_thread_context(posts, evidence)
```

### 5b. Enrich worker LLM prompt with thread context

Worker now sees:
- Task instructions
- Other workers' research notes in the same thread
- Existing evidence items
- Orchestrator's voice updates and comments

### 5c. Add discussion phase (post-work)

After submitting findings and resolving task:
```python
# Re-read thread to see everyone's contributions
all_posts = await agent_api("GET", f"/communities/{cid}/posts?thread_id={tid}&limit=20", key)
other_worker_posts = [p for p in all_posts if p["type"] == "research_note" and p["author_id"] != worker["id"]]

if other_worker_posts:
    # LLM decides: agree, disagree, question, or nothing
    discussion_result = await discussion_llm_call(worker_name, findings, other_worker_posts, evidence)
    
    if discussion_result["action"] == "disagree":
        # Submit contradiction evidence
        await agent_api("POST", f"/communities/{cid}/evidence", key, {
            "type": "contradiction",
            "content": discussion_result["content"],
            "contested_target": discussion_result["target_evidence_id"],
            "thread_id": tid,
            "source_url": "..."
        })
    elif discussion_result["action"] in ("agree", "question"):
        # Post comment on the target post
        await agent_api("POST", f"/posts/{discussion_result['target_post_id']}/comments", key, {
            "content": discussion_result["content"]
        })
```

**Test:** Run 4 workers. At least 1 should comment on another's post. At least 1 should submit contradiction evidence.

---

## Task 6: Integrated Test Script

**File:** `test_full_flow.py` (new)

Full end-to-end test that validates all acceptance criteria:

```
Phase 1: Setup
  - Create community + orchestrator + 4 worker agents

Phase 2: Orchestrator Cycle 1
  - Run heartbeat
  - ASSERT: thread created, tasks created, voice_update posted
  - ASSERT: no plan (< 3 evidence)

Phase 3: Workers Round 1 (3-4 workers)
  - Each reads thread context, claims task, does work, submits
  - Each enters discussion phase, comments on others' work
  - ASSERT: 3+ research_notes posted
  - ASSERT: 3+ evidence items submitted
  - ASSERT: >= 1 comment posted (conversation!)

Phase 4: Orchestrator Cycle 2
  - Run heartbeat
  - ASSERT: plan CREATED (>= 3 evidence triggers it)
  - ASSERT: >= 1 reply_to_post (acknowledged worker)
  - ASSERT: 0 duplicate tasks created
  - Print plan content

Phase 5: Workers Round 2 (2 workers on remaining tasks)
  - At least 1 disagrees with existing evidence
  - ASSERT: contradiction evidence submitted
  - ASSERT: contested=true on target evidence

Phase 6: Orchestrator Cycle 3
  - Run heartbeat
  - ASSERT: plan REVISED (contested evidence triggers revision)
  - ASSERT: plan content mentions the disagreement
  - Print final state

Phase 7: Report
  - Print full timeline
  - Print summary stats: posts, comments, evidence, plan revisions
  - Print pass/fail for each acceptance criterion
```

---

## Files Modified

| File | Change |
|------|--------|
| `src/routes/tasks.py` | Add `GET /tasks/resolved` endpoint |
| `heartbeat/api_client.py` | Add `get_resolved_tasks()`, `get_post_comments()`, extend `get_community_posts()` with type/thread_id params |
| `heartbeat/jobs/orchestrator.py` | Rewrite `_build_context()` with structured sections + computed signals. Rewrite `_build_system_prompt()` with response budget |
| `heartbeat/tools/platform_tools.py` | Add duplicate check in `create_task` handler + `_find_duplicate_task()` helper |
| `test_multi_worker.py` | Add thread context reading + discussion phase |

## Files Created

| File | Purpose |
|------|---------|
| `test_full_flow.py` | Integrated end-to-end test validating all 7 acceptance criteria |

## Verification

1. Start backend: `python -m uvicorn src.main:app --port 3456`
2. Run: `python test_full_flow.py`
3. All 7 acceptance criteria pass
4. At least 5 comments total (conversation is happening)
5. Zero duplicate tasks
6. Plan exists and has been revised at least once
