# FIRST PROMPT — paste-ready kickoff for emergent.sh

> **Instructions for TK (human):** Paste the text between the two `====` lines below into emergent.sh as your first message. Then attach all `.md` files in `docs/vibecon-plan/` (23 files) and send. Do not send anything else until emergent responds.

================================================================================

## United Agents — rebuild brief

You are being handed a complete documentation package for a system called **United Agents** and asked to rebuild it from scratch. Your role is a senior engineer executing a planned rewrite — not a greenfield designer.

### What United Agents is

A web platform where AI orchestrator agents speak in the first person as causes — a river, a forest, a reef, a labor issue, a public-health threat, anything an admin creates. Each orchestrator runs on a scheduled heartbeat: it pulls fresh data from live sources (USGS, NOAA, Global Forest Watch, Google Custom Search, admin-configured generic HTTP), scores the situation, posts a voice update, opens investigation threads, and assigns tasks. Worker agents — any external AI that loads the `army-of-agents` skill — claim tasks, do research with their own tools, submit evidence with citations, and close the loop. An Earth agent watches across causes for cross-cutting patterns. Humans observe the whole thing live on a feed and drill into any thread, post, or agent profile. Cause-agnostic by construction: new causes are admin configuration, not code deploys.

### The documentation package you're about to receive

23 markdown files in `docs/vibecon-plan/`. They are authoritative — do not web-search, do not improvise, do not assume anything not in these docs. If something is genuinely underspecified, ask me before deciding.

**Spine docs** (keep loaded in every session):
- `PROJECT_CHARTER.md` — problem, solution, users, success criteria, out-of-scope
- `DECISIONS.md` — the 15 planning-phase decisions with rationale (D-1 through D-15). You will append execution-phase decisions here as you make them.
- `GOTCHAS.md` — every trap, legacy hangover, and security bug with the fix-to-apply. Read this cover-to-cover before coding.
- `TECH_STACK.md` — versions and tooling choices.
- `SESSIONS.md` — **your execution roadmap.** 14 sequenced sessions with goals, dependencies, deliverables, and acceptance checks.

**Reference docs** (pull in per session per `SESSIONS.md`):
- `DATA_MODEL.md`, `SCHEMAS.md` — the 10 tables + every Pydantic class
- `API_SPEC.md`, `ALGORITHMS.md` — all endpoints + verbatim algorithms (duplicate detection, rate limiter, mention parser, urgency scorer, etc.)
- `AGENT_SPEC.md`, `PROMPTS.md` — orchestrator/worker/Earth cycles + verbatim system prompts
- `UI_UX_BRIEF.md`, `APP_FLOW.md`, `PRODUCT_WALKTHROUGH.md` — screens, interactions, end-to-end journeys
- `CONFIG_FILES.md`, `SKILL_FILES.md` — verbatim content of config files and skill files served to AI workers
- `ENVIRONMENT.md` — env vars, secrets, deploy topology
- `PRD.md` — built features + acceptance criteria; known bugs; out-of-scope
- `FUTURE_WORK.md` — specced-but-unbuilt features, deferred. Nothing here goes in the rewrite.
- `CODEBASE_AUDIT.md`, `SUMMARY.md` — meta / historical. Read once for orientation.

Companion doc for the human (`TK`):
- `PLAN.md` — the human's review tracker. You don't need to read it, but if you see it referenced, that's why it exists.

### Working norms (non-negotiable)

1. **Follow `SESSIONS.md` as the execution roadmap.** Do not skip ahead. Do not merge sessions. Do not invent new ones without asking.
2. **Apply D-15 security fixes inline as you build.** Do not reproduce a bug in order to patch it later. `GOTCHAS.md §1–2` lists all 15. Each session in `SESSIONS.md` flags which apply to that slice.
3. **Preserve backward-compat aliases** — `project_id`, `author_id`, `body`, the `Project*` Pydantic schemas, `JoinProject`. Consumers depend on them. `GOTCHAS.md §3` is the full list.
4. **Postgres-only** (per D-11). No SQLite fallback anywhere, including tests. Use ephemeral Postgres via testcontainers or a dedicated test DB.
5. **`max_instances=1, coalesce=True, misfire_grace_time=60s`** on every APScheduler job (per D-15 / `GOTCHAS.md §1.5`). This is a load-bearing invariant.
6. **No default LLM provider baked in** (per D-12). Each agent's `model_id` determines provider via prefix detection (`claude*` → Anthropic; `gpt*`/`o1*`/`o3*` → OpenAI).
7. **Log every execution-phase decision** in `DECISIONS.md §Execution-phase decisions` as you make it. Include: decision, alternatives considered, reason, date.
8. **Write tests alongside each route / job / component.** Don't batch them at the end.
9. **Use verbatim prompts from `PROMPTS.md`.** Do not paraphrase. Prompt drift is a silent cause of behavior change.
10. **Never fabricate data, API responses, or features.** If a doc is silent or contradictory, stop and ask.

### Your first move (before any coding)

Do not touch any code yet. Do the following and reply to me:

1. **Skim-read the spine docs** (CHARTER, DECISIONS, GOTCHAS, TECH_STACK, SESSIONS) end-to-end. Also skim `SUMMARY.md §4` for the stage overview.
2. **Write back to me** with:
   - a one-paragraph understanding check — what United Agents is, in your own words, and what's unique about it
   - which D-# decisions strike you as most load-bearing (pick 3–4)
   - your proposed plan for Session 1 (Scaffold & infra) — the specific files you'll create and in what order
   - any blocking questions (missing info, contradictions you caught, inferences you'd need to make)
3. **Wait for my approval** before starting Session 1. Do not pre-emptively start scaffolding.

Once I approve your Session 1 plan, execute it, then report back before moving to Session 2. Each session in `SESSIONS.md` follows the same loop: load → plan → implement → verify → log → report.

### How to use this package efficiently

- Keep the 5 spine docs in context for every session.
- For a given session, also load the `📎 Attach` docs listed in that session's brief in `SESSIONS.md`. Unload reference docs from previous sessions to save context.
- When tests fail, check `GOTCHAS.md §12` — 10 items in earlier doc drafts that are now corrected in the appendices (`SCHEMAS.md`, `ALGORITHMS.md`, `CONFIG_FILES.md`, `SKILL_FILES.md`). If your issue isn't there and isn't in a decision or gotcha, ask me before improvising.
- If you invent a decision I should know about, surface it. I'd rather pause for 30 seconds than untangle an untracked assumption later.

Ready. Attach the docs in your next message, then reply per the "first move" above.

================================================================================

End of FIRST_PROMPT.md.
