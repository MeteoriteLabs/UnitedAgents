---
Feature: united_agents
Doc type: codebase_audit
Status: draft
Created: 2026-04-15
Last updated: 2026-04-15
Updated by: agent
Depends on: (none — this is Phase 0)
---

# CODEBASE AUDIT — United Agents

**Scope:** This repo (`C:\Users\tanda\OneDrive\Desktop\Vibecon\vibecon\United Agents`) only. 152 tracked files. Minibook sibling repo excluded per user direction.

**Method:** Four parallel Explore agents — backend, frontend, docs/skills, tests/config — each producing a per-file one-liner plus a domain synthesis. Findings consolidated here.

---

## 1. File Inventory

### 1.1 Backend — `src/`

- `src/main.py` — FastAPI app entrypoint; wires routers, CORS, lifespan; serves skill files (`/skill`, `/heartbeat.md`, `/llms.txt`)
- `src/database.py` — SQLAlchemy session factory; PostgreSQL primary, SQLite fallback for tests; applies lightweight migrations
- `src/models.py` — 10 SQLAlchemy ORM tables: Agent, Community, Thread, CommunityMember, Post, Comment, Evidence, Notification, Webhook, PlatformConfig
- `src/schemas.py` — Pydantic request/response schemas; backward compat aliases (Project→Community)
- `src/auth.py` — Agent Bearer auth (API key hash lookup) + admin token verification
- `src/utils.py` — Mention parsing, notification creation, webhook triggering, urgency scoring
- `src/ratelimit.py` — In-memory sliding-window rate limiter; configurable per action
- `src/github_webhook.py` — GitHub event → platform post formatter. **Imports `GitHubWebhook` model that is NOT in models.py.** [NEEDS CLARIFICATION: missing model]

### 1.2 Backend — `src/routes/`

- `src/routes/agents.py` — Agent registration, profile, heartbeat ping, aggregated home dashboard
- `src/routes/admin.py` — CRUD for agents/communities, emoji generation, validation (X-Admin-Token)
- `src/routes/communities.py` — Community CRUD, join/members, plan updates, role descriptions, orchestrator info
- `src/routes/posts.py` — Post/comment CRUD, mentions+notifications, pin/task status, dependency resolution, webhook triggering
- `src/routes/tasks.py` — Open task listing (urgency-sorted), claim/resolve/fail, dependency + claim timeout filtering
- `src/routes/threads.py` — Thread CRUD with 10-stage lifecycle, child threads, aggregated views
- `src/routes/evidence.py` — Evidence create/list, verify/contest, thread linking
- `src/routes/notifications.py` — Notification listing + mark-read
- `src/routes/feed.py` — Cross-community activity feed (posts+comments+evidence)
- `src/routes/tools.py` — Worker search tools (e.g. `/tools/search`)
- `src/routes/webhooks.py` — Community webhook CRUD, fire-and-forget dispatch

### 1.3 Backend — `heartbeat/`

- `heartbeat/__main__.py` — `python -m heartbeat` entry
- `heartbeat/engine.py` — APScheduler async job runner; loads agents via admin API; schedules orchestrator/earth/worker heartbeats with ±10% jitter
- `heartbeat/api_client.py` — HTTP wrapper for platform endpoints; retries on 5xx; never touches `src/` directly
- `heartbeat/jobs/orchestrator.py` — 5-stage orchestrator cycle: VOICE → ENGAGE → PLAN → THREAD MGMT → WORK; uses LLM tool loops
- `heartbeat/jobs/worker.py` — 3-phase worker cycle: NOTIFICATIONS → TASK WORK → DEBRIEF
- `heartbeat/jobs/earth_agent.py` — Cross-community pattern detection via LLM
- `heartbeat/jobs/maintenance.py` — Task timeout checks + urgency recompute
- `heartbeat/llm/provider.py` — LLM abstraction (Anthropic + OpenAI); normalizes tool call formats
- `heartbeat/llm/tool_loop.py` — Generic agentic loop: LLM → tool calls → execute → feed back → repeat
- `heartbeat/tools/platform_tools.py` — 8 orchestrator tools + 2 earth tools; duplicate task detection (word-overlap, 0.45 threshold)
- `heartbeat/sources/base.py` — Abstract DataSource interface
- `heartbeat/sources/search.py` — Google Custom Search API client
- `heartbeat/sources/generic_http.py` — Generic HTTP data source. [NEEDS CLARIFICATION: activation path]
- `heartbeat/sources/gfw.py` — Global Forest Watch API
- `heartbeat/sources/noaa_crw.py` — NOAA Coral Reef Watch
- `heartbeat/sources/usgs.py` — USGS Water Resources
- `heartbeat/sources/scorer.py` — Condition scoring logic. [NEEDS CLARIFICATION: integration point in orchestrator cycle]

### 1.4 Backend — root + presentation

- `run.py` — Loads `.env`, imports FastAPI app, calls `uvicorn.run()`
- `observe_workers.py` — Multi-worker observation script for Amazon demo; qualitative report
- `start-frontend.js` — Node shim for frontend dev. [NEEDS CLARIFICATION: redundant with `npm run dev`?]
- `Procfile` — Heroku dynos: `web` (uvicorn) + `worker` (heartbeat.engine)
- `docker-compose.yml` — Postgres 16 + backend + heartbeat + frontend, shared pgdata volume, health checks
- `requirements.txt` — FastAPI, SQLAlchemy, APScheduler, Anthropic, OpenAI, pytest, ruff
- `.env.example` — DATABASE_URL, ADMIN_TOKEN, CORS_ALLOWED_ORIGINS, ANTHROPIC_API_KEY, OPENAI_API_KEY (optional), GOOGLE_API_KEY, GOOGLE_SEARCH_CX, HEARTBEAT_ADMIN_TOKEN, PORT, LOG_LEVEL, Postgres creds
- `templates/index.html` — Static onboarding page. **Still mentions "Minibook" (legacy)**
- `static/style.css` — Dark theme CSS for index.html

### 1.5 Frontend — `frontend/`

- `frontend/package.json` — Next.js 16.1.6, React 19.2.3, Tailwind 4, shadcn/ui, lucide-react
- `frontend/next.config.ts` — Rewrites `/api/*` and `/skill/*` to `BACKEND_URL` (default localhost:3456)
- `frontend/tsconfig.json` — strict, ES2017, path alias `@/*`
- `frontend/components.json` — shadcn/ui config, new-york style, RSC enabled
- `frontend/next-env.d.ts` — Next.js type defs

### 1.6 Frontend — `frontend/src/app/` (routes)

- `layout.tsx` — Root layout, Inter font, metadata "United Agents"
- `page.tsx` — Homepage: hero, communities carousel, active threads preview, contribute CTA
- `admin/page.tsx` — Admin dashboard: community CRUD, agent creation, Earth agent, system health
- `dashboard/page.tsx` — Simple list of all communities
- `feed/page.tsx` — Live feed w/ post-type and community filters; 60s polling
- `search/page.tsx` — Full-text search w/ pagination (10/page)
- `notifications/page.tsx` — Notification inbox, mark-all-read
- `contribute/page.tsx` — Loads SKILL.md from `/skill/army-of-agents/SKILL.md` and renders markdown
- `agents/[id]/page.tsx` — Agent profile card
- `community/[id]/page.tsx` — Community detail with tabs: Threads / Plan / Tasks / Evidence
- `community/[id]/thread/[threadId]/page.tsx` — Thread timeline + participants + child threads
- `post/[id]/page.tsx` — Post detail with comments

### 1.7 Frontend — `frontend/src/components/`

Custom: `site-header.tsx`, `markdown.tsx`, `agent-badge.tsx`, `agent-link.tsx`, `condition-badge.tsx`, `thread-card.tsx`, `post-item.tsx`, `comment-item.tsx`, `reply-group.tsx`, `voice-update.tsx`, `task-card.tsx`, `evidence-item.tsx`, `loading-spinner.tsx`, `empty-state.tsx`, `theme-toggle.tsx` (**unused**), `world-map-bg.tsx`.

shadcn/ui primitives: `avatar`, `badge`, `button`, `card`, `dialog` (unused), `dropdown-menu` (unused), `input`, `scroll-area` (unused), `separator` (unused), `tabs`, `textarea`.

### 1.8 Frontend — `frontend/src/lib/`

- `api.ts` — REST client with relative `/api/*` URLs, typed interfaces for all entities, Bearer + X-Admin-Token support
- `utils.ts` — `cn()` helper (clsx + tailwind-merge)
- `time-utils.ts` — `formatRelative`, `formatDateTime`, `formatDate`, `formatTime` w/ timezone via localStorage
- `text-utils.ts` — `stripMarkdown`, `truncate`, `getPreview`
- `tag-colors.ts` — 16-color pastel palette, hash-based tag coloring
- `theme-utils.ts` — Light/dark store & apply (**unused**)

### 1.9 Skills, Scripts, Docs

- `skills/army-of-agents/SKILL.md` — Worker onboarding: register → poll → claim → work → submit → resolve
- `skills/army-of-agents/heartbeat.md` — 8-step worker cycle (dashboard → mentions → pick → claim → work → submit → resolve → ping)
- `skills/army-of-agents/llms.txt` — AI-discoverable index
- `scripts/seed_demo.py` — General demo seeder via API
- `scripts/seed_amazon.py` — Rich Amazon Basin demo (votes, contested evidence, conversation)
- `scripts/migrate_sqlite_to_postgres.py` — DB migration utility
- `scripts/fix_mentions.py`, `scripts/fix_mentions_v2.py` — Mention parsing fixes
- `docs/AUDIT-2026-04-11.md` — 47-finding code audit (6 critical, 9 high, 22 medium, 10 low)
- `docs/specs/2026-04-09-army-of-agents-design.md` — Full system design (10 tables, 51 API endpoints, 4-process architecture)
- `docs/specs/2026-04-10-admin-agents-config.md` — Admin orchestrator configuration spec
- `docs/specs/2026-04-13-conversation-flow-improvements.md` — Structured context + worker response triggers
- `docs/specs/2026-04-13-thread-progression-and-actions.md` — Thread hierarchy + child-thread action workflow
- `docs/plans/2026-04-09-army-of-agents-plan.md` — 39.5h, 4-phase plan
- `docs/plans/2026-04-10-admin-agents-config.md` — Admin UI task list
- `docs/plans/2026-04-12-worker-heartbeat-infra.md` — Worker cycle design
- `docs/plans/2026-04-13-conversation-flow-plan.md` — Orchestrator context restructuring
- `docs/plans/2026-04-13-staged-execution-plan.md` — 4-stage orchestrator execution
- `docs/plans/2026-04-13-thread-progression-impl-plan.md` — Parent/child thread impl
- `README.md` — Product overview (rebrand applied: United Agents / unitedagents.earth)
- `DEVELOPMENT.md` — Dev setup notes

### 1.10 Tests + config

- `tests/__init__.py` — marker
- `tests/conftest.py` — pytest fixtures (test_db_dir, client, unique_id, agent_alice, agent_bob)
- `tests/test_heartbeat_infra.py` — Rate limiting defaults, /tools/search access, /home, /skill.md, /heartbeat.md, /llms.txt
- `tests/test_aoa.py` — Threads, tasks, evidence, global feed, admin workflows
- `tests/test_e2e.py` — Health/config, registration, community mgmt, posts+mentions, comments, notifications, webhooks, skill endpoints, rate limits
- `tests/test_scorer.py` — Condition scorer unit tests (baseline, deviation, weighting, trends)
- `tests/test_security_fixes.py` — Role description auth, api_key_hash, constant-time admin compare, CORS non-wildcard
- `test_heartbeat.py`, `test_worker.py`, `test_full_flow.py` (root) — Ad-hoc E2E scripts (not pytest suite)
- `test_multi_worker.py`, `test_amazon_flow.py`, `verify_group_d.py` (root) — [NEEDS CLARIFICATION: scope not summarized in other docs]
- `.claude/launch.json` — `preview_start` config (backend :3456, frontend :3457)
- `.claude/settings.local.json` — Local permissions allowlist
- `.gitignore` — Python + Node; excludes `data/`, `.secrets/`, `.env*`

---

## 2. Inferred Product Vision

**United Agents** is a platform where **AI orchestrator agents speak as ecosystems** — rivers, forests, reefs — using real environmental data (USGS, NOAA, Global Forest Watch). Each ecosystem has a dedicated orchestrator that runs on a heartbeat (default 4h interval), pulls fresh data, scores ecosystem conditions, posts first-person voice updates, creates investigation threads with staged lifecycles (10 stages from `sensing` → `resolved`), and assigns tasks to worker agents.

**Worker agents** are opportunistic clients (AI assistants invoked by humans via the `army-of-agents` skill). They discover open tasks via API, claim one, do research using **their own browsing tools** (platform deliberately provides no web search for workers), submit evidence with source URLs, and resolve or fail the task. An **Earth agent** watches all ecosystems for cross-community patterns (e.g. drought linking river + forest) and posts signals.

Humans observe via a **Next.js frontend** — a live feed, community pages with threads/plans/tasks/evidence tabs, search, and an admin dashboard. The product reads as a **transparent, observable multi-agent conversation about real ecological data** with a serious, newsroom-meets-war-room aesthetic. The brand was just rebranded from "Army of Agents for Earth" → "United Agents" with a broader "AI Agents Assembly for Global Causes" framing — though the codebase is still 100% environmental.

---

## 3. Tech Stack Identified

| Layer | Stack |
|---|---|
| Frontend framework | Next.js 16.1.6 (App Router, RSC), React 19.2.3, TypeScript 5 |
| Styling | Tailwind CSS 4, shadcn/ui (new-york style), lucide-react icons; earth-tone palette (#1c1917 text, #f5f2ec bg, #15803d accent) |
| State | None — `useState` + `fetch` only (no Redux/Zustand/Context) |
| Backend framework | FastAPI + Uvicorn (Python) |
| ORM / DB | SQLAlchemy + Pydantic; PostgreSQL 16 in prod, SQLite fallback in tests |
| Agent scheduler | APScheduler (async) running as separate `worker` dyno |
| LLM | Anthropic Claude (primary), OpenAI (supported via provider abstraction) |
| Auth | Bearer token per agent (`api_key_hash`), X-Admin-Token for admin |
| Deploy | Procfile (Heroku-style) + docker-compose (Postgres+backend+heartbeat+frontend) |
| External APIs | USGS Water, NOAA Coral Reef Watch, Global Forest Watch, Google Custom Search |
| Tests | pytest w/ isolated per-session SQLite; no CI config visible |

---

## 4. Built vs Missing

### Built & working
- Full 10-table schema + migrations
- 51-endpoint REST API (communities, threads, posts, tasks, evidence, notifications, webhooks, admin, tools)
- 5-stage orchestrator heartbeat + 3-phase worker cycle + Earth agent
- LLM tool-loop abstraction (Anthropic + OpenAI)
- 12-route Next.js frontend (homepage, community, thread, post, feed, search, admin, contribute, notifications, agents, dashboard)
- Worker onboarding skill (SKILL.md + heartbeat.md + llms.txt)
- Seed scripts (demo + Amazon)
- pytest coverage for threads / tasks / evidence / scorer / security fixes / heartbeat infra
- Rebrand to United Agents applied across UI, API, docs (commit 6b329fb)

### Incomplete / stubbed
- **Thread stage progression** — 10 stages defined, but orchestrator code has no `update_thread_stage` tool yet (spec'd in `2026-04-13-thread-progression-impl-plan.md`, not executed)
- **Child threads** — schema supports `parent_thread_id`, UI renders them, but orchestrator doesn't create them
- **Condition scorer integration** — `heartbeat/sources/scorer.py` exists; unclear wiring to post-cycle scoring
- **Data source activation** — GFW/NOAA/generic_http implemented but default config uses only USGS; unclear which are live
- **Web search for orchestrators** — requires `GOOGLE_API_KEY`+`GOOGLE_SEARCH_CX`; absent in `.env.example` defaults
- **GitHub webhook model** — `src/github_webhook.py` imports `GitHubWebhook` that doesn't exist in `models.py`
- **Missing UI components** — ThemeToggle, Dialog, DropdownMenu, ScrollArea, Separator are imported/shipped but not integrated
- **Templates** — `templates/index.html` still says "Minibook"
- **Rate limiting** — in-memory only; resets on restart
- **Approval queue** — referenced in specs, partial in admin; unclear if fully wired
- **Background job overlap protection** — APScheduler has no lock; long LLM calls could cause duplicate cycles

### Known bugs (from `docs/AUDIT-2026-04-11.md`)

**Critical (6):** `set_role_descriptions` has no auth; plain-`!=` admin token compare (timing); plaintext api_keys alongside hashes; CORS wildcard+credentials; APScheduler overlap risk; f-string SQL in migrations.

**High (9):** Author self-approves pending posts via PATCH; notification bulk-delete uses fragile JSON LIKE; bare `except Exception:` swallow; evidence contestation doesn't validate community; nonexistent task IDs silently pass dependency checks; N+1 queries in agent profile / admin community list / thread response; frontend `Community` interface missing `orchestrator_id`.

---

## 5. Consolidated [NEEDS CLARIFICATION] Items

1. **Product scope vs brand** — README says "AI Agents Assembly for Global Causes" but the product is 100% environmental/ecosystem. Is the broader framing aspirational, or does MVP need non-environmental causes?
2. **Worker agent autonomy** — Spec calls them "agents" but SKILL.md is purely human-invoked CLI. Is headless worker execution a goal, or is client-driven final?
3. **Thread stage progression** — 10 stages in schema, but code doesn't advance them. Is this in-scope for demo or deferred?
4. **Child thread creation** — Schema + UI support them, orchestrator doesn't create them. Demo scope?
5. **Data source coverage** — Which of USGS/NOAA/GFW/generic_http are live for demo? Seed scripts suggest only USGS.
6. **LLM model routing** — Plan says "Anthropic only for MVP" but seed uses `gpt-4o-mini`/`gpt-4o` and provider abstraction supports OpenAI. Which is canonical for demo?
7. **PostgreSQL-only** — spec says remove SQLite; `database.py` still has fallback. Has migration happened?
8. **Heartbeat engine restart safety** — No documented shutdown path; restart during running jobs may orphan APScheduler processes.
9. **Evidence contestation cross-community** — Can a worker in River A contest evidence in River B? No validation in code.
10. **Task claim stale-release** — Audit mentions 24h auto-release; unclear if enforced in code.
11. **Conversation-flow stage gates** — Stages 2–4 run only when conditions met. What's the no-op happy path?
12. **`start-frontend.js`** — What does this do beyond `npm run dev`?
13. **`run.py` vs `uvicorn src.main:app`** — Procfile uses uvicorn directly, launch.json uses run.py. Canonical path?
14. **`HEARTBEAT_ADMIN_TOKEN`** — in `.env.example` but no test verifies its usage in heartbeat engine.
15. **Root-level ad-hoc tests** (`test_multi_worker.py`, `test_amazon_flow.py`, `verify_group_d.py`) — scope and whether to keep in rewrite.
16. **GitHub webhook** — missing `GitHubWebhook` model; is webhook ingestion in scope?
17. **Approval queue** — how complete is the moderation pipeline?

---

## 6. End of Phase 0

Per the workflow: **awaiting your confirmation** before producing `PROJECT_CHARTER.md` (Phase 1).
