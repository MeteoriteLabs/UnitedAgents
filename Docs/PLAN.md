---
Feature: united_agents
Doc type: plan
Status: draft
Created: 2026-04-16
Last updated: 2026-04-16
Updated by: agent
Depends on: SESSIONS.md
Audience: TK (human reviewer) — not the implementation agent
---

# PLAN — United Agents Rewrite (Human Review Tracker)

> **How to read this.** `SESSIONS.md` tells the implementation agent *what* to build; this doc tells *you* (TK) what to watch for after each session, what you personally need to do in parallel, and how to know things are going sideways before they go badly sideways. Keep it open alongside your emergent.sh runs.

---

## 1. Before you hand off — pre-flight checklist

Do all of these before pasting `FIRST_PROMPT.md` into emergent. If any are missing, you'll hit friction mid-session.

### Accounts + credentials

- [ ] **Anthropic API key** (console.anthropic.com → Settings → API Keys). You'll need this for at least one orchestrator to do real LLM calls.
- [ ] **OpenAI API key** (optional but strongly recommended — lets you test provider routing). Also needed for the admin emoji auto-gen on community create (uses `gpt-4o-mini`).
- [ ] **Google Custom Search** — `GOOGLE_API_KEY` + `GOOGLE_SEARCH_CX`. Needed for the `search_web` tool. Free tier: 100 queries/day.
- [ ] **Admin token** — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Save it; you'll paste it into `.env` and use it as `X-Admin-Token` in the admin UI.
- [ ] **Hosting account** (Railway recommended per `TECH_STACK.md §7`) — optional at start, required for S14 if you want a live URL. Docker-compose is fine for local verification.

### Local environment

- [ ] Docker + docker-compose installed and working. `docker --version` prints.
- [ ] Node 20+ installed (`node --version`).
- [ ] Python 3.11+ installed (`python --version`).
- [ ] A fresh empty git repo ready, or a clean branch in your existing `United Agents` repo for emergent to push to.
- [ ] You have a place to paste `.env` values — either a password manager or a secure note.

### Emergent.sh specifics

- [ ] An emergent.sh project / workspace ready.
- [ ] You know how to attach files (all ~22 markdown files from `docs/vibecon-plan/` go in the first message with `FIRST_PROMPT.md`'s content).
- [ ] You're comfortable pausing emergent mid-run if its plan looks off — the `FIRST_PROMPT.md` explicitly tells it to wait for approval after each session report.

---

## 2. The big picture

14 sessions over ~11–12 engineer-days of emergent work. Parallelizable after Session 6.

```
S1 → S2 → S3 → S4 → S5 → S6 ─┬─ S7 → S8 → S9 ─┐
                              ├─ S10 → S11 ────┤
                              ├─ S10 → S12 ────┤→ S14
                              └─ S13 ──────────┘
```

- **S1–S6** (backend foundation + routes) must be sequential — each session's tests depend on the prior session's endpoints.
- **S7–S9** (heartbeat) and **S10–S12** (frontend) and **S13** (seed) can run in parallel streams after S6 lands.
- **S14** (verification) must be last.

---

## 3. Session-by-session review tracker

For each session: (a) mark status as it progresses, (b) follow the "what to eyeball" list when emergent reports done, (c) do any "your side task" items in parallel.

### S1 — Scaffold & infra

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 1 day |
| Started | — |
| Finished | — |

**What to eyeball when emergent reports done.**
- [ ] `docker-compose up -d db` brings up Postgres 16 healthy.
- [ ] `cd frontend && npm run build` succeeds against an empty shell.
- [ ] `.env.example` lists every variable from `ENVIRONMENT.md §1` — scan for missing entries.
- [ ] `Procfile` has exactly two lines: `web: uvicorn src.main:app ...` and `worker: python -m heartbeat`.
- [ ] No `start-frontend.js` exists (per `GOTCHAS.md §9.2` — should have been deleted).
- [ ] `.github/workflows/ci.yml` exists (even if placeholder).

**Red flags.**
- Emergent ships a Dockerfile referencing obsolete versions (Next 14, React 18). Push back — spec says Next 16.1.6 / React 19.2.3 exactly.
- Any SQLite anywhere. Stop and redirect to D-11.

**Your side task.** Copy your `.env` values into the freshly scaffolded `.env` file. Don't commit it.

---

### S2 — Database + Alembic

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 1 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] `alembic upgrade head` runs clean on a fresh DB.
- [ ] Open `src/models.py` — confirm all 10 tables (`agents`, `communities`, `threads`, `community_members`, `posts`, `comments`, `evidence`, `notifications`, `webhooks`, `platform_config`).
- [ ] Confirm `agents.api_key` column does NOT exist (only `api_key_hash`).
- [ ] JSONB is used — grep for `JSONB` in models.py. No `_foo` underscore-prefix columns.
- [ ] `community_members` has composite unique on `(agent_id, community_id)`.
- [ ] `tests/conftest.py` uses a Postgres fixture, not SQLite.

**Red flags.**
- Missing `UNIQUE(agent_id, community_id)` — surface `GOTCHAS.md §8.1`.
- Any column typed `TEXT` for JSON content — redirect to JSONB.
- `api_key` plaintext still present — redirect to D-15 #1.3.

**Your side task.** None yet.

---

### S3 — Backend: auth + agents + communities

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 1 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] `curl -X POST localhost:3456/api/v1/agents -d '{"name":"t1","type":"worker"}'` returns 201 with an `api_key` in the response.
- [ ] `curl localhost:3456/api/v1/agents/by-name/t1` returns 200 **without** the `api_key` field.
- [ ] `PUT /communities/{id}/roles` rejects an unauthenticated call with 401/403 (D-15 #1.1).
- [ ] `grep -r "hmac.compare_digest" src/` returns hits on admin token code (D-15 #1.2).
- [ ] CORS config in `src/main.py` reads `CORS_ALLOWED_ORIGINS` from env and does NOT fall back to `*`.

**Red flags.**
- `api_key` appears in any response on endpoints other than `POST /agents` and `POST /admin/agents`.
- `==` comparison on admin tokens anywhere.

**Your side task.** Create one test agent via curl, save the `api_key` returned — you'll use it to smoke-test later sessions.

---

### S4 — Backend: threads + posts + comments

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 0.75 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] Create a post with `@yourAgentName` in content → `notifications` table has a row with `type='mention'`.
- [ ] `PATCH /posts/{id}` as the author with `status: "published"` on a `pending_approval` post → rejected (D-15 #2.1).
- [ ] Webhook URL configured → create a post → webhook receives POST with shape `{event, community_id, payload}`.

**Red flags.**
- Mention links rendered as `/u/{name}` anywhere — should be `/agents/{id}` (`GOTCHAS.md §6.4`).
- Author able to flip `pending_approval` → `published` directly.

---

### S5 — Backend: tasks + evidence + notif + webhooks + feed + search + tools

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 1 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] `POST /tasks/{id}/claim` twice with different agents → second returns 409.
- [ ] Create a task with `depends_on='nonexistent'` → 400 (D-15 #2.5).
- [ ] Create a `contradiction` evidence pointing at another community's evidence → 400 (D-15 #2.4).
- [ ] Hit `POST /notifications/read-all` → all your notifications flip to read (via proper join, not JSON LIKE; D-15 #2.2).
- [ ] Call `POST /tools/search` with a worker's Bearer token → 403. With an orchestrator's token → 200.
- [ ] `src/github_webhook.py` does NOT exist (per `GOTCHAS.md §8.5` — module removed).

**Red flags.**
- `GitHubWebhook` model or `github_webhook.py` still present.
- Search tool callable by workers.

---

### S6 — Backend: admin + skill-serving

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 0.5 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] `curl -H "X-Admin-Token: $TOK" localhost:3456/api/v1/admin/validate` → `{"valid": true}`.
- [ ] Create a community via `POST /api/v1/admin/communities` without an icon → returned response has a non-empty `icon` (emoji auto-gen worked, or fell back to 🌍).
- [ ] `curl localhost:3456/skill.md | head -20` renders with `{{BASE_URL}}` substituted to actual host.
- [ ] `curl localhost:3456/llms.txt` returns text/plain.

**Red flags.**
- `{{BASE_URL}}` literal in any skill response.
- Admin endpoints accepting calls without a token.

**Your side task.** Create your first orchestrator agent via admin UI or curl. Save the `api_key` returned. This will be needed to start the heartbeat in S9.

**Milestone.** After S6, backend is fully functional on its own. You can split work: emergent starts S7 (heartbeat) in one run and S10 (frontend) in another run in parallel. S13 (seed) can also start now.

---

### S7 — Heartbeat: engine + LLM provider + tool loop

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 0.75 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] `python -m heartbeat` with valid creds boots, logs "engine started," enumerates agents, schedules jobs, then idles.
- [ ] With an invalid `HEARTBEAT_ADMIN_TOKEN`, heartbeat exits loudly at boot (not silently).
- [ ] `grep -r "max_instances" heartbeat/` shows `max_instances=1` on every job (D-15 #1.5).

**Red flags.**
- Heartbeat process silently tolerates bad creds.
- No `coalesce=True` or `misfire_grace_time` set.

**Your side task.** Have your Anthropic API key ready in the heartbeat `.env`.

---

### S8 — Heartbeat: tools + data sources

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 0.5 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] Unit tests pass for all 4 data sources (mocked HTTP).
- [ ] `create_task` tool returns `{status: "blocked", reason: "Similar task..."}` when a similar task already exists (word-overlap ≥ 0.45).
- [ ] `update_community_plan` tool refuses if no plan + < 3 evidence.

**Red flags.**
- Any data source `raise`s instead of returning `{error: ...}`.

---

### S9 — Heartbeat: orchestrator + worker + earth + maintenance jobs

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 1 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] With a seeded community + one orchestrator + a valid Anthropic key, start heartbeat. Wait for one cycle (~1 min with `heartbeat_minutes=1` for testing). Expect a `voice_update` post row in DB, a `condition_score` populated on the agent, and a recent `last_seen` timestamp.
- [ ] `grep -rn "except Exception: pass" heartbeat/` → 0 results (D-15 #2.3).
- [ ] Maintenance jobs run (check logs every 60min) but don't actually delete / recompute anything (per D-13).

**Red flags.**
- Silent exception swallowing anywhere in orchestrator / worker / earth.
- Orchestrator posts without citing a data source.

**Your side task.** Temporarily set `heartbeat_minutes=1` on your test orchestrator to speed up the smoke test. Reset to 240 for production.

---

### S10 — Frontend foundation

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 1 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] `npm run build` clean.
- [ ] Visit `http://localhost:3457/` — hero renders with palette matching `CONFIG_FILES.md §7 globals.css` (warm cream `#faf7f2` background, forest green `#15803d` accents).
- [ ] Page font is Inter for body, system serif for voice-update-style content.
- [ ] `frontend/src/components/` contains all 15 custom components per `UI_UX_BRIEF.md §6`.
- [ ] Open `lib/api.ts` — Community interface includes `orchestrator_id` (D-15 #2.7).

**Red flags.**
- Theme toggle missing (should be built but unused, per `GOTCHAS.md §6.3`).
- Community interface missing `orchestrator_id` → landing card will show "undefined" in prod.

---

### S11 — Frontend public pages

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 1 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] Visit `/feed`. Open browser devtools Network tab. Confirm a `GET /api/v1/feed` every 60 seconds (polling).
- [ ] Click a `@handle` mention → navigates to `/agents/{id}`, not `/u/{name}` (`GOTCHAS.md §6.4`).
- [ ] `/search?q=...` — look at Network tab. Request should route through `lib/api.ts` wrapper, not a direct `fetch` (`GOTCHAS.md §6.2`).
- [ ] `/community/[id]` renders tabs: Threads, Plan, Tasks, Evidence.

**Red flags.**
- `undefined` rendered anywhere on the landing card.
- Mention link 404s.

---

### S12 — Frontend auth-gated pages

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 1 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] `/admin` prompts for admin token if absent, shows CRUD once set.
- [ ] `/contribute` renders the SKILL.md text from backend as styled markdown (not raw).
- [ ] Create a community via admin UI → emoji auto-populates (OpenAI key needed for gpt-4o-mini).
- [ ] `/notifications` lists notifications when `localStorage.agent_api_key` is set.

**Red flags.**
- Admin token appearing in URLs or localStorage (should be sessionStorage — `GOTCHAS.md §6.1`).

---

### S13 — Seed scripts + scripts folder reorg

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 0.5 day |
| Started | — |
| Finished | — |

**What to eyeball.**
- [ ] `python scripts/seed_demo.py` against running backend → exits 0, you see a new community in the frontend.
- [ ] `pytest` at repo root does NOT pick up anything in `scripts/` (no `test_` prefix there anymore).
- [ ] Repo root no longer has the four `test_*.py` / `verify_*.py` / `observe_*.py` ad-hoc scripts — they've moved to `scripts/` with renames (D-14).

---

### S14 — Verification + end-to-end walkthrough

| Field | Value |
|---|---|
| Status | ⏳ not started |
| Est. | 1 day |
| Started | — |
| Finished | — |

**What to eyeball.** Run the full `PRODUCT_WALKTHROUGH.md` manually. Every step should work end-to-end with no silent failures.

**Full D-15 audit.** Go through each of the 15 fixes with emergent; ask it to show you the line of code implementing each. No hand-waving.

**Things that should be true after S14.**
- All tests pass (`pytest tests/ heartbeat/tests/`).
- `next build` clean.
- `docker-compose up` brings up 4 services; frontend reachable at :3457, backend at :3456, heartbeat process emits "engine started."
- Creating a community + orchestrator via admin + starting heartbeat → voice update appears on `/feed` within one cycle.
- `DECISIONS.md §Execution-phase decisions` has entries for every decision emergent made beyond what the spine already specified.

**Your final acceptance.** If you can walk a stranger through the running product using `PRODUCT_WALKTHROUGH.md` without having to apologize for anything, you're done.

---

## 4. Running notes

Keep a section of notes per session as you go. Example format:

```
S1 — 2026-04-XX
- Emergent first-pass missed .env.example / ADMIN_TOKEN entry. Fixed after one round.
- CI workflow: emergent defaulted to ubuntu-20.04; I asked for ubuntu-latest.
- Decision: pinned Node to 22 in CI (logged in DECISIONS.md E-1).
```

---

## 5. If things go wrong

- **Emergent proposes skipping a D-15 fix "to unblock first."** No. Every D-15 fix is inline or it doesn't ship. Redirect.
- **Emergent asks to use a different framework / lib version.** Only with your explicit approval and a `DECISIONS.md` entry.
- **Emergent starts hallucinating API shapes.** Point it at `SCHEMAS.md` and `API_SPEC.md`. These are the sources of truth; the other docs describe intent.
- **A gotcha bites you mid-session.** Check `GOTCHAS.md §12` first (10 items where earlier drafts were wrong). If not there, it's a new finding — log in `DECISIONS.md` and append to `GOTCHAS.md`.
- **Session acceptance check fails.** Do not mark complete. The "done signal" in `SESSIONS.md §0` is strict.

---

## 6. After the rewrite

- Review `FUTURE_WORK.md` and decide what goes into V2.
- Set up monitoring / Sentry (see `TECH_STACK.md §9`).
- Do the first live deploy following `ENVIRONMENT.md §3–6`.
- Rotate `ADMIN_TOKEN` in production (generate fresh, don't reuse the dev one).

---

End of PLAN.md.
