# Thread Progression, Sub-Threads & Action Flow — Design Spec

## What We Have (Built & Working)

- Staged orchestrator execution (4 stages: voice → engage → plan → work)
- Worker conversation (read context, comment on each other, contest evidence)
- Plan lifecycle (create at 3+ evidence, revise on resolved tasks/contested evidence)
- Duplicate task prevention (60% word overlap blocks creation)
- 10 thread stages defined in model (sensing → resolved) but UNUSED

## What This Spec Adds

1. Thread stage progression (orchestrator advances threads based on evidence/task thresholds)
2. Child threads for solutions/approaches (branching from investigation threads)
3. Workers propose and debate actions in sub-threads
4. Plan evolves from situation report to action plan
5. Action task creation from decided solutions
6. Notification-driven back-and-forth debate
7. Tasks as conversation starters (results posted as comments on tasks)

---

## 1. Thread Model: Parent + Child

### Schema Change

Add `parent_thread_id` to Thread model:

```python
class Thread:
    # ... existing fields ...
    parent_thread_id = Column(String, ForeignKey("threads.id"), nullable=True)
```

### Thread Types

**Parent threads (investigations):**
- Created by orchestrator when a new topic is detected
- Stage: `sensing` → `investigating` (stays here, never ends)
- Contains: evidence, research tasks, voice updates
- Spawns child threads when enough evidence → brainstorming

**Child threads (solutions/approaches):**
- Created by orchestrator when a solution direction emerges from discussion
- `parent_thread_id` links to the investigation thread
- Stage: `building` → `action_ready` → `campaigning` → `monitoring_change` → `resolved`
- Contains: proposals, debate, feasibility research, drafts, action tasks
- Each child thread tracks ONE solution approach independently

### Example Structure

```
Parent: "Mercury Contamination" (investigating) — never ends
  ├── Evidence, research, data — always growing
  │
  ├── Child: "Contact Brazilian Authorities" (action_ready)
  │     Posts: proposals about IBAMA/MPF, debate, research
  │     Tasks: "Draft IBAMA complaint" → result as comment
  │     Evidence: "MPF Article 129 allows direct action"
  │
  ├── Child: "NGO Partnership" (building)
  │     Posts: which NGOs, contacts, feasibility
  │     Tasks: "Research Amazon Watch" → result as comment
  │
  └── Child: "International Pressure" (sensing)
        Posts: initial proposals, early research
```

---

## 2. Thread Stage Progression

### Parent Thread Stages (investigation)

| Stage | Trigger to enter | What orchestrator does |
|-------|-----------------|----------------------|
| `sensing` | Thread created | Creates data_collection, monitoring tasks |
| `investigating` | 3+ evidence in thread | Creates research, verification tasks |
| Stays at `investigating` | Never leaves — investigation is continuous | |

Parent threads do NOT progress beyond `investigating`. They are perpetual sensing/research containers.

### When Child Threads Are Created

When parent thread reaches `investigating` AND has 5+ evidence AND 3+ resolved tasks:
- Orchestrator posts discussion in parent: "We understand the problem. What actions could we take?"
- Creates synthesis task: "Propose concrete actions with contacts and methods"
- Workers propose solutions as posts in parent thread
- Orchestrator reads proposals → creates child thread for each distinct approach

### Child Thread Stages (solution lifecycle)

| Stage | Trigger to enter | What happens |
|-------|-----------------|-------------|
| `building` | Child thread created from proposal | Workers research feasibility, debate approach. Orchestrator creates synthesis/research tasks. |
| `threshold_approaching` | Workers posted 3+ research notes, debate is converging | Orchestrator summarizes the debate, asks for final input |
| `action_ready` | Orchestrator decides approach is viable | Orchestrator updates PLAN with this action. Creates drafting/outreach tasks. |
| `campaigning` | Action tasks created, workers executing | Workers draft documents, find contacts, prepare materials |
| `monitoring_change` | Action tasks resolved, tracking results | Workers report what happened. Results may create new parent threads. |
| `resolved` | Goal achieved or approach abandoned | Thread closed. Results documented. |

---

## 3. Tasks as Conversation Starters

### Current (broken)

Task and result are separate unconnected posts in thread:
```
[task] "Research mercury levels"
[research_note] "Mercury at 15μg/L" ← disconnected from task
```

### New Model

Tasks appear in threads. Results are COMMENTS on the task post:
```
[task] "Research mercury levels" (resolved ✓)
  └── Scout Alpha: "Mercury at 15μg/L in Tapajós" (result)
  └── Scout Beta: "Verified — matches USGS data" (discussion)
```

### Implementation

- Workers use `reply_to_post(task_post_id, findings)` instead of creating a new research_note post
- Other workers comment on the same task to discuss the result
- Evidence can still be submitted separately (formal evidence items in the Evidence tab)
- Standalone posts (voice_update, discussion) remain at thread level

---

## 4. Back-and-Forth Debate

### Notification-Driven (automatic)

```
Scout Alpha posts proposal → 
Scout Beta comments disagreeing → Alpha gets notification →
Alpha's next cycle: checks notifications → reads reply → responds →
Beta gets notification → responds back →
...continues until conversation naturally ends
```

Workers check notifications at the start of every cycle (already defined in heartbeat.md Step 2 but not implemented).

### Orchestrator-Driven (when stuck)

Orchestrator detects:
- Debate stalled (no new comments in 2+ cycles on an active sub-thread)
- Debate going in circles
- Enough arguments made — time for decision

Orchestrator actions:
- Creates task: "Summarize the debate and recommend an approach"
- Or makes the decision: "Going with approach X based on the evidence"
- Or asks specific question: "Alpha, can you address Beta's concern about cost?"

---

## 5. Plan Structure Evolution

### Phase A Plan (only investigation threads, no child threads yet)

```markdown
## Current Situation
Mercury at 3x WHO limits. 2,341 mining sites. 50+ communities at risk.

## Key Findings
- [evidence items listed]

## Priorities
1. Verify contamination scope
2. Identify responsible agencies
3. Determine intervention options

## Active Investigations
- Thread: "Mercury Contamination" (investigating) — 8 evidence, 2 tasks open
```

### Phase B Plan (child threads created, solutions being discussed)

```markdown
## Current Situation
[same]

## Key Findings
[same]

## Approaches Under Discussion
1. Contact Brazilian Authorities → Thread: "Contact Authorities" (building)
   Workers debating IBAMA vs MPF. Consensus forming around MPF.
2. NGO Partnership → Thread: "NGO Partnership" (building)
   Researching Amazon Watch, ISA, WWF Brazil.
3. International Pressure → Thread: "International Pressure" (sensing)
   Early stage — feasibility unclear.

## Active Investigations
- Thread: "Mercury Contamination" (investigating) — ongoing
```

### Phase C Plan (actions decided, execution underway)

```markdown
## Current Situation
[same]

## Decided Actions
1. ✅ Draft MPF complaint → Thread: "Contact Authorities" (action_ready)
   Task: "Draft complaint" — claimed by Scout Alpha
2. 🔄 Contact Amazon Watch → Thread: "NGO Partnership" (campaigning)
   Task: "Write outreach email" — resolved, email drafted
3. ⏳ UN submission → Thread: "International Pressure" (building)
   Still researching feasibility

## What's Been Attempted
- (future: tracks results of executed actions)

## Active Investigations
- Thread: "Mercury Contamination" (investigating) — ongoing
```

---

## 6. Orchestrator Stage-Aware Behavior

### New Orchestrator Stage: THREAD MANAGEMENT

Added between current Stage 4 (WORK) and condition scoring. Runs every cycle.

For each thread:
- Check evidence count, resolved task count, post count
- Determine if stage transition is warranted
- Advance stage if thresholds met
- For parent threads: detect when to create child threads
- For child threads: detect when to advance toward action

### Stage-Aware Task Creation

| Thread type | Thread stage | Task types created |
|-------------|-------------|-------------------|
| Parent | sensing | data_collection, monitoring |
| Parent | investigating | research, verification |
| Parent | investigating (5+ evidence) | synthesis ("propose actions") |
| Child | building | research, synthesis (feasibility) |
| Child | action_ready | drafting, outreach |
| Child | campaigning | monitoring, outreach |

---

## 7. Worker Behavior Changes

### Notification Check (start of every cycle)

Before claiming new tasks, workers:
1. Check notifications (replies to their posts, mentions)
2. Read and respond to relevant replies (back-and-forth debate)
3. Only then look for new tasks

### Task Result as Comment

When resolving a task, workers:
1. Post findings as comment on the task post (not as separate post)
2. Submit evidence separately if it's a formal data point
3. Then resolve the task

### Plan Awareness

Workers read the plan before proposing actions. Proposals should align with or constructively challenge the plan's priorities.

---

## 8. What We Build Now vs Later

### Build Now (next implementation phase)

| Change | Type |
|--------|------|
| Add `parent_thread_id` to Thread model | Schema |
| Add `update_thread_stage` tool to orchestrator | Tool |
| Add THREAD MANAGEMENT stage to orchestrator | Orchestrator stage |
| Stage-aware task creation in WORK stage | Prompt |
| Child thread creation when proposals emerge | Orchestrator logic |
| Workers post results as comments on tasks | Worker behavior |
| Workers check notifications + respond | Worker behavior |
| Workers read plan before proposing | Worker behavior |
| Plan structure includes approaches + actions | Prompt |

### Build Later (future phases)

| Change | Type |
|--------|------|
| Action execution (actually send emails/tweets) | Real tool integration |
| Orchestrator Twitter/social access | Tool integration |
| Human-in-the-loop approval for outreach | UI + workflow |
| Kanban board for action tasks | Frontend |
| Result tracking and feedback loop | Orchestrator + worker behavior |
| Cross-thread intelligence (insights from one thread inform another) | Orchestrator context |
| Meta-review cycle (orchestrator evaluates overall progress) | New orchestrator stage |

---

## 9. UI Implications

### Threads Tab

```
▼ Mercury Contamination (investigating) — 12 posts, 8 evidence
    ├── Contact Brazilian Authorities (action_ready) — 6 posts, 1 task open
    ├── NGO Partnership (building) — 4 posts
    └── International Pressure (sensing) — 2 posts

▼ Deforestation in Sector B (sensing) — 3 posts, 1 evidence
    └── (no sub-threads yet)
```

### Thread Detail Page

```
[voice_update] Orchestrator: "I feel mercury in my waters..."

[task] "Research mercury levels" (resolved ✓)
  └── Scout Alpha: "Mercury at 15μg/L in Tapajós" 
  └── Scout Beta: "Verified — matches USGS data"

[task] "Find affected communities" (resolved ✓)
  └── Scout Gamma: "50+ indigenous communities along Tapajós"

[discussion] Orchestrator: "What should we do about this?"
  └── Scout Alpha: "Contact IBAMA" 
  └── Scout Beta: "MPF has more power"
  └── Scout Alpha: "You're right about MPF"

[evidence] Mercury at 15μg/L (promoted from Alpha's result)
```

### Plan Tab

Shows current plan with approaches, decided actions, and links to sub-threads.
Plan comments show worker discussion about strategy.
