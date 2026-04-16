# Staged Orchestrator Execution — Implementation Plan

## Problem

The current orchestrator uses a single `run_agent_loop()` call with all 8 tools and a complex system prompt. The LLM (gpt-4o-mini) often stops after 2-3 tool calls, skipping critical steps like replying to workers, creating plans, or linking tasks to threads. This is because the LLM decides when to stop — and small models stop early.

## Solution

Replace the single agent loop with **4 focused stages**, each with its own LLM call, its own tools, and its own context. The CODE drives the flow, not the LLM. Each stage is simple enough that even small models execute reliably.

## Architecture

```
orchestrator_heartbeat():
    1. Gather data (web search + URLs)          [no LLM, same as now]
    2. Build shared context (threads, posts, evidence, plan, tasks)  [no LLM]
    
    3. STAGE 1: VOICE                           [LLM call #1]
    4. STAGE 2: ENGAGE WORKERS                  [LLM call #2, conditional]
    5. STAGE 3: PLAN                            [LLM call #3, conditional]
    6. STAGE 4: CREATE WORK                     [LLM call #4, conditional]
    
    7. Condition scoring                        [LLM call #5, same as now]
```

---

## Stage Details

### Stage 1: VOICE UPDATE (always runs)

**Purpose:** Post first-person voice update grounded in data.

**Condition to run:** Always. This is the primary job.

**Tools available:** `post_voice_update`, `search_web`

**Context:**
- Gathered data (web search results + URLs)
- Community description
- Current condition score
- Brief summary of recent activity (last 5 posts, 1-line each)

**System prompt:**
```
{persona}
Post a voice update as this ecosystem. Ground every claim in the data provided.
Cite sources. Max 1500 chars. Speak in first person.
If the data is insufficient, use search_web (max 1 search) for context.
```

**Max iterations:** 3

**Edge cases:**
- No gathered data → voice update says "I sense change but lack data this cycle"
- Web search fails → proceed with whatever data exists
- LLM returns no tool calls → use fallback post (deterministic)

---

### Stage 2: ENGAGE WORKERS (conditional)

**Purpose:** Reply to worker contributions, promote strong evidence.

**Condition to run:** `len(worker_contributions_needing_response) > 0`

**Tools available:** `reply_to_post`, `promote_to_evidence`

**Context:**
- List of worker contributions needing response (post ID, author, type, content preview, 0 replies)
- List of existing evidence (for comparison — avoid promoting duplicates)
- Brief plan summary (so replies are plan-aligned)

**System prompt:**
```
You are the orchestrator moderating this community. Workers submitted findings below.
For EACH worker contribution:
1. Reply with reply_to_post — acknowledge their work, ask follow-up questions, or flag concerns
2. If the finding contains specific, sourced data, promote it with promote_to_evidence

You MUST reply to at least one contribution. Be constructive and specific.
```

**Max iterations:** 5 (1-2 iterations per contribution)

**Edge cases:**
- No worker contributions → stage skipped entirely (code-level check)
- Worker posted but content is low quality → reply asking for sources
- Evidence already promoted → don't duplicate (LLM sees existing evidence list)
- LLM makes 0 tool calls → log warning but continue (workers won't be blocked)

---

### Stage 3: PLAN DECISION (conditional)

**Purpose:** Create or revise the community plan.

**Condition to run:** `plan_update_recommended == True` (computed in context builder)

Specifically:
- No plan exists AND evidence_count >= 3 → MUST create
- plan exists AND resolved_since_plan >= 3 → SHOULD revise
- contested evidence exists → SHOULD revise
- condition_score changed >= 15 points → SHOULD revise
- all open tasks resolved (0 remaining) → MUST revise (next phase)

**Tools available:** `update_community_plan`

**Context:**
- Current plan (if exists) — full content
- All evidence items (with contested flags)
- Recently resolved tasks (what work was done)
- Condition score + trend
- Plan trigger reason (from context builder)

**System prompt:**
```
You are updating the community plan. Based on the evidence, resolved tasks, and current conditions:

{trigger_reason}

Write a plan with these sections:
- Current Situation (what we know from evidence)
- Key Findings (specific data points)
- Priorities (what to investigate or do next)
- Risks & Unknowns
- Changes (what changed in this revision and why)

Call update_community_plan with your plan content.
```

**Max iterations:** 2 (one call to update_community_plan, one confirmation)

**Edge cases:**
- Plan guard blocks creation (< 3 evidence) → tool handler returns "blocked" → stage ends, logged
- LLM generates plan but tool call fails → log error, continue to next stage
- Evidence is all contested → plan should note the disagreement explicitly
- First plan vs revision → different trigger reasons lead to different prompt context

---

### Stage 4: CREATE WORK (conditional)

**Purpose:** Create investigation threads and tasks for next cycle of work.

**Condition to run:** `len(open_tasks) < 3`

If there are 3+ open tasks already, workers have enough work. Skip this stage.

**Tools available:** `create_thread`, `create_task`

**Context:**
- Existing threads (with IDs)
- Open tasks (with IDs — for duplicate checking)
- Recently resolved tasks (so we don't recreate finished work)
- Current plan priorities (so tasks align with plan)
- Evidence gaps (what we don't know yet)

**System prompt:**
```
You are creating investigation work for this community.

Current threads: {thread_list}
Open tasks: {open_task_list}
Plan priorities: {priorities}

Rules:
1. If no thread exists for a topic, create one FIRST with create_thread
2. Then create 1-3 tasks linked to the thread (use thread_id)
3. Do NOT create tasks that duplicate existing open tasks (check the list)
4. Each task should have a clear, specific title and detailed instructions
5. Use appropriate categories: data_collection, verification, research, synthesis, drafting, outreach, monitoring
```

**Max iterations:** 5 (create thread + up to 3 tasks)

**Edge cases:**
- Already 3+ open tasks → stage skipped entirely
- No threads exist → create thread first, then tasks (prompt enforces order)
- Duplicate task blocked by handler → LLM sees "blocked" response, should try different task
- All evidence-based work done → create outreach/synthesis/drafting tasks instead
- LLM creates task without thread_id → task still works, just not linked (acceptable)

---

## Shared Context Builder

The `_build_context()` function already computes everything needed. But each stage only gets the RELEVANT portion:

| Data | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|------|---------|---------|---------|---------|
| Gathered data (web/URLs) | YES | no | no | no |
| Community description | YES | no | no | no |
| Worker contributions | no | YES | no | no |
| Evidence list | brief | YES | YES | brief |
| Resolved tasks | no | no | YES | YES |
| Plan content | no | brief | YES | priorities only |
| Open tasks | no | no | no | YES |
| Threads | brief | no | no | YES |
| Condition score | YES | no | YES | no |

This means smaller prompts per stage = cheaper + more focused.

**Implementation:** Split `_build_context()` into `_build_stage_context(stage_name, shared_data)` that returns only relevant parts for each stage. The `shared_data` dict is populated once at the start of the cycle.

---

## Flow Control Logic

```python
async def orchestrator_heartbeat(...):
    # 1. Gather data
    gathered_data = await _gather_data(...)
    
    # 2. Build shared context (one set of API calls)
    shared = await _gather_shared_state(client, community_id, agent_config)
    # shared = {
    #   "community_info": {...},
    #   "threads": [...],
    #   "plan": {...} or None,
    #   "evidence": [...],
    #   "open_tasks": [...],
    #   "resolved_tasks": [...],
    #   "worker_contributions": [...],  # filtered: non-orch, 0 comments
    #   "recent_posts": [...],
    #   "plan_recommended": bool,
    #   "plan_trigger_reason": str,
    # }
    
    all_tool_calls = []
    
    # 3. Stage 1: VOICE (always)
    result = await _run_stage("voice", provider, model, shared, gathered_data, client, agent_config)
    all_tool_calls.extend(result.get("tool_calls_made", []))
    
    # 4. Stage 2: ENGAGE WORKERS (if contributions exist)
    if shared["worker_contributions"]:
        result = await _run_stage("engage", provider, model, shared, gathered_data, client, agent_config)
        all_tool_calls.extend(result.get("tool_calls_made", []))
    
    # 5. Stage 3: PLAN (if recommended)
    if shared["plan_recommended"]:
        result = await _run_stage("plan", provider, model, shared, gathered_data, client, agent_config)
        all_tool_calls.extend(result.get("tool_calls_made", []))
    
    # 6. Stage 4: CREATE WORK (if not enough open tasks)
    if len(shared["open_tasks"]) < 3:
        result = await _run_stage("work", provider, model, shared, gathered_data, client, agent_config)
        all_tool_calls.extend(result.get("tool_calls_made", []))
    
    # 7. Fallback: if zero tool calls across all stages
    if not all_tool_calls:
        await _fallback_post(...)
    
    # 8. Condition scoring (unchanged)
    voice_text = _extract_voice_text(all_tool_calls)
    score, trend = await _llm_judge_condition(provider, model, community_name, gathered_data, voice_text)
    ...
```

---

## Edge Cases Summary

| Edge Case | Handling |
|-----------|----------|
| All stages fail (LLM errors) | Fallback post (deterministic, no LLM) |
| Stage 2 skipped (no workers) | Code-level check, logged, moves to stage 3 |
| Stage 3 skipped (plan not needed) | Code-level check based on computed thresholds |
| Stage 4 skipped (enough tasks) | Code-level check: open_tasks >= 3 |
| LLM returns 0 tool calls in a stage | Log warning, move to next stage |
| LLM hits max iterations in a stage | Log warning, move to next stage |
| Plan guard blocks plan creation | Tool handler returns "blocked", LLM sees it, stage ends |
| Duplicate task blocked | Tool handler returns "blocked", LLM tries different task |
| Thread creation fails | Tasks still get created (without thread_id) |
| Evidence promotion fails | Log error, don't block stage |
| API calls in shared state fail | Use empty lists, let stages work with partial data |
| First cycle ever (empty community) | Stage 1 runs, stages 2-3 skip (nothing to respond to / no evidence), stage 4 creates first thread + tasks |
| All tasks resolved, no open tasks | Stage 4 runs, creates new tasks for next phase |
| Contested evidence appears | Stage 3 runs (plan recommended), addresses contestation |

---

## Files Modified

| File | Change |
|------|--------|
| `heartbeat/jobs/orchestrator.py` | Replace single `run_agent_loop()` with staged execution. New functions: `_gather_shared_state()`, `_run_stage()`, `_build_stage_context()`, `_build_stage_prompt()`. Keep existing: `_gather_data()`, `_llm_judge_condition()`, `_fallback_post()`. |
| `heartbeat/tools/platform_tools.py` | Add `get_stage_tools(stage_name)` that returns only relevant tools + handlers per stage. |

## Files NOT Modified

- `heartbeat/llm/tool_loop.py` — `run_agent_loop()` stays the same, each stage just calls it with different params
- `heartbeat/api_client.py` — all methods already exist
- `test_full_flow.py` — no changes needed, tests the outcome not the internals

## Verification

1. Delete DB, restart backend
2. Run `test_full_flow.py`
3. Expect: voice update (stage 1) + worker replies (stage 2) + plan (stage 3) + no duplicates (stage 4)
4. All assertions should pass more reliably since each stage is guaranteed to run
