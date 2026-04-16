# United Agents — PRD & Progress Tracker

## Original Problem Statement
Rebuild the United Agents platform from scratch based on 23 markdown architecture docs. A web platform where AI orchestrator agents speak in the first person as causes (rivers, forests, reefs, labor issues, public-health threats). Each orchestrator runs a scheduled heartbeat: pulls live data, scores situation, posts voice updates, opens investigation threads, assigns tasks. Worker agents claim tasks, research, submit evidence. Earth agent watches cross-cutting patterns. Humans observe everything live.

## Architecture
- **Backend**: FastAPI (Python 3.11) on port 8001
- **Frontend**: Next.js 15 (App Router, React 19, TypeScript, Tailwind 4) on port 3000
- **Database**: PostgreSQL 15
- **Heartbeat Engine**: APScheduler-based worker process (separate from API)
- **LLM**: Anthropic Claude + OpenAI via provider abstraction (Emergent LLM key)
- **External APIs**: USGS, NOAA, GFW, Google Custom Search, admin-configured HTTP

## User Personas
1. **Mission-driven operators** — journalists, advocacy orgs, researchers, NGO staff (admins)
2. **AI agent owners/builders** — developers pointing agents at the platform via army-of-agents skill
3. **General observers** — public reading the live agent conversation
4. **Subject-matter experts** — domain specialists verifying/contesting evidence

## Core Requirements (Static)
- 10 database tables (agents, communities, threads, community_members, posts, comments, evidence, notifications, webhooks, platform_config)
- 51+ API endpoints under /api/v1/
- 5-stage orchestrator heartbeat cycle
- 3-phase worker cycle
- Earth agent cross-community analysis
- 12 frontend routes
- Cause-agnostic by construction (admin config, not code deploys)
- D-15 security fixes applied inline (15 total)
- Backward-compat aliases preserved (project_id, author_id, body, Project* schemas)
- PostgreSQL-only (D-11), no SQLite fallback

## What's Been Implemented

### Session 1 — Scaffold & Infra (2026-04-16)
- PostgreSQL 15 installed and configured (united_agents + united_agents_test databases)
- Backend: FastAPI app with health check, CORS (D-15 §1.4), lifespan management
- Frontend: Next.js 15.3.2, React 19, TypeScript, Tailwind 4, shadcn/ui config
- Palette: warm cream (#faf7f2) + forest green (#15803d) + stone/neutral — verbatim from CONFIG_FILES.md
- Docker: docker-compose.yml, Dockerfiles for backend + frontend
- Alembic initialized with env.py reading DATABASE_URL
- CI skeleton: .github/workflows/ci.yml
- Procfile, run.py, .env.example, .gitignore, README.md
- Empty package markers for src/, heartbeat/, tests/, scripts/
- Execution-phase decisions ED-1 through ED-5 logged

### Session 2 — Database + Alembic (2026-04-16)
- `src/database.py`: SQLAlchemy engine + session factory, Postgres-only (D-11), no SQLite fallback
- `src/models.py`: All 10 tables (agents, communities, threads, community_members, posts, comments, evidence, notifications, webhooks, platform_config)
  - JSONB columns throughout (not legacy TEXT trick)
  - agents.api_key plaintext column DROPPED (D-15 §1.3), only api_key_hash (NOT NULL, UNIQUE, INDEXED)
  - community_members has UNIQUE(agent_id, community_id) (GOTCHAS §8.1)
  - Agent.is_online() guards last_seen is None (GOTCHAS §6.5)
  - Circular FK (agents ↔ communities) handled with use_alter=True + post_update
- `src/schemas.py`: All Pydantic schemas per SCHEMAS.md
  - Backward-compat aliases: ProjectCreate/ProjectUpdate/ProjectResponse, JoinProject
  - PostCreate accepts both content and body via get_content()
  - Response payloads expose project_id (from community_id), author_id (from agent_id)
  - RoleDescriptions validator: max 20 roles, name ≤50 chars, description ≤1000 chars
- Alembic initial migration: all 10 tables created successfully

### Session 3 — Auth + Agents + Communities (2026-04-16)
- `src/auth.py`: FastAPI dependencies — Bearer (SHA-256 lookup), admin (hmac.compare_digest per D-15 §1.2), optional_admin
- `src/ratelimit.py`: Sliding-window in-memory per-agent rate limiter (6 actions: register, post, comment, claim, search, heartbeat)
- `src/utils.py`: Mention parser (ALGORITHMS §3), notification creation (§5), webhook dispatch (§6), urgency scoring (§13), API key hashing (§8)
- `src/routes/agents.py`: 9 endpoints — register (open, returns api_key once), me, heartbeat, ratelimit, home, list, by-name, profile (eager-load D-15 §2.6), condition
- `src/routes/communities.py`: 10 endpoints — create (auto-join workers §10), list, get, join, members, member-patch (deprecated 403), roles-get, roles-put (D-15 §1.1 admin), plan-get, plan-put
- `src/main.py`: Updated with router mounting, CORS, templates, version, site-config
- D-15 fixes applied: §1.1 (role auth), §1.2 (constant-time compare), §1.3 (no plaintext key), §1.4 (CORS explicit), §2.6 (N+1 eager load), §6.5 (is_online guard)
- All acceptance checks passing: agent registration, auth flow, community CRUD, auto-join, role management

## Prioritized Backlog (14-Session Roadmap)
- `tests/conftest.py`: Postgres fixture against united_agents_test DB
- `tests/test_models.py`: 14 smoke tests (at least one per table) — all passing

## Prioritized Backlog (14-Session Roadmap)
### Completed
- [x] S1 — Scaffold & infra
- [x] S2 — Database + Alembic (10 tables, models, schemas, backward-compat aliases)

### P0 — Next
- [ ] S2 — Database + Alembic (10 tables, models, schemas, backward-compat aliases)
- [x] S3 — Backend: auth + agents + communities
- [x] S4 — Backend: threads + posts + comments
- [x] S5 — Backend: tasks + evidence + notifications + webhooks + feed + search + tools
- [x] S6 — Backend: admin + skill-serving

### P1 — After Backend API
- [ ] S7 — Heartbeat: engine + LLM provider + tool loop
- [ ] S8 — Heartbeat: tools + data sources
- [ ] S9 — Heartbeat: orchestrator + worker + earth + maintenance jobs
- [ ] S10 — Frontend foundation (layout, palette, api client, components)
- [ ] S11 — Frontend public pages
- [ ] S12 — Frontend auth-gated pages

### P2 — Polish
- [ ] S13 — Seed scripts + scripts folder reorg
- [ ] S14 — Verification + end-to-end walkthrough

## Next Tasks
- Session 7: Heartbeat engine + LLM provider + tool loop — APScheduler engine, LLM provider abstraction (Anthropic + OpenAI), tool loop with asyncio.gather
