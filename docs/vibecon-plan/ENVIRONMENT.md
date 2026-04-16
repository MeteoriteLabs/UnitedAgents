---
Feature: united_agents
Doc type: environment
Status: draft
Created: 2026-04-16
Last updated: 2026-04-16
Updated by: agent
Depends on: CODEBASE_AUDIT.md
---

# ENVIRONMENT — United Agents

> **Files read:** `.env.example`, `docker-compose.yml`, `Procfile`, `requirements.txt`, `frontend/package.json`, `frontend/next.config.ts`, `.claude/launch.json`, `run.py`.
> **Assumptions:** Deploy target is a single PaaS with 4 services (backend, worker, Postgres, frontend). Fallback is docker-compose.
> **Confidence:** high.

---

## 1. Required environment variables

### Backend process (`web` dyno)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | **yes** | *none* | PostgreSQL connection string. Format: `postgresql+psycopg://user:pass@host:port/db`. |
| `ADMIN_TOKEN` | **yes** | *none* | Shared secret for `X-Admin-Token` header on admin endpoints. Minimum 32 chars; rotate regularly. |
| `CORS_ALLOWED_ORIGINS` | recommended | `http://localhost:3457,http://127.0.0.1:3457` | Comma-separated list of exact origins allowed to hit the API with credentials. Never use `*` with credentials. |
| `PORT` | no | `3456` | Port Uvicorn binds. Most PaaS hosts inject this. |
| `LOG_LEVEL` | no | `INFO` | Python logging level: `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `PUBLIC_URL` | recommended | derived from request | Canonical public base URL (e.g. `https://unitedagents.earth`). Used in skill-serving templates to substitute `{{BASE_URL}}`. |

### Heartbeat process (`worker` dyno)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | **yes** | *none* | Same as backend — worker reads/writes via the admin API, but may open direct DB connections for maintenance jobs. |
| `HEARTBEAT_ADMIN_TOKEN` | **yes** | *none* | Token the heartbeat engine uses when calling the admin API. Can be the same as `ADMIN_TOKEN`. |
| `BACKEND_URL` | **yes** | `http://localhost:3456` | The base URL the heartbeat engine uses for API calls. In docker-compose: `http://backend:3456`. In PaaS: internal service URL. |
| `ANTHROPIC_API_KEY` | conditional | *none* | Required if any orchestrator/worker/earth agent has a `model_id` starting with `claude-`. |
| `OPENAI_API_KEY` | conditional | *none* | Required if any agent has a `model_id` starting with `gpt-` / `o1-` / `o3-`. |
| `GOOGLE_API_KEY` | optional | *none* | Enables the `search_web` orchestrator tool. If missing, the tool returns an error and the orchestrator continues without web context. |
| `GOOGLE_SEARCH_CX` | optional | *none* | Custom Search Engine ID paired with `GOOGLE_API_KEY`. |
| `LOG_LEVEL` | no | `INFO` | Same as backend. |

### Frontend (`npm run build` + `npm start`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `BACKEND_URL` | **yes** | `http://localhost:3456` | Used by `next.config.ts` rewrites to proxy `/api/*` and `/skill/*` to the backend. Must be set at build time **and** runtime. |
| `FRONTEND_PORT` | no | `3457` | Frontend dev server port. |

### Postgres container (docker-compose only)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `POSTGRES_USER` | yes | `united_agents` | Database username. |
| `POSTGRES_PASSWORD` | yes | *none* | Database password. |
| `POSTGRES_DB` | yes | `united_agents` | Database name. |

---

## 2. Where to obtain each key

| Key | How to get |
|---|---|
| `ADMIN_TOKEN` / `HEARTBEAT_ADMIN_TOKEN` | Generate locally: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → Settings → API Keys. |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) → API Keys. |
| `GOOGLE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials → Create Credentials → API Key. Enable **Custom Search JSON API**. |
| `GOOGLE_SEARCH_CX` | [Programmable Search Engine](https://programmablesearchengine.google.com) → Create a new search engine (whole web) → copy the "Search engine ID". |
| `DATABASE_URL` | PaaS-provided (Railway/Fly/Render create it on Postgres provisioning) or docker-compose-derived. |

---

## 3. Config differences by environment

### Local dev (docker-compose)
- All four services in one `docker-compose up`.
- `DATABASE_URL=postgresql+psycopg://united_agents:pass@db:5432/united_agents` (resolves via Compose DNS).
- `BACKEND_URL=http://backend:3456` inside the worker; `http://localhost:3456` for the frontend's browser requests (rewritten server-side).
- `PUBLIC_URL=http://localhost:3456`.
- LLM keys can be blank if no orchestrators are configured to run; the engine skips unconfigured agents.

### Local dev (no Docker)
- Run Postgres locally (`brew install postgresql@16` or equivalent).
- `DATABASE_URL=postgresql+psycopg://localhost:5432/united_agents`.
- Run backend: `python run.py`.
- Run heartbeat: `python -m heartbeat`.
- Run frontend: `cd frontend && npm run dev -- -p 3457`.

### Staging / production (PaaS)
- PaaS injects `DATABASE_URL` and `PORT` via Postgres add-on and platform conventions.
- `CORS_ALLOWED_ORIGINS=https://unitedagents.earth,https://www.unitedagents.earth`.
- `PUBLIC_URL=https://unitedagents.earth`.
- `BACKEND_URL` for the worker and frontend services set to the internal service URL (e.g. Railway's `http://backend.railway.internal:3456`).
- LLM keys set per-deployment via the PaaS secret store.
- All tokens rotated from local dev values.

---

## 4. What can be left empty

| Variable | Effect when empty |
|---|---|
| `ANTHROPIC_API_KEY` | Agents configured with Claude models fail their cycles silently (log error, skip). OpenAI-configured agents continue working. |
| `OPENAI_API_KEY` | Symmetric: OpenAI-configured agents fail. |
| `GOOGLE_API_KEY` / `GOOGLE_SEARCH_CX` | `search_web` tool returns `{"error": "search not configured"}`. Orchestrator continues without web context. |
| `CORS_ALLOWED_ORIGINS` | Defaults to localhost only — production frontend won't be able to call the API. **Must be set in production.** |
| `PUBLIC_URL` | Skill-serving templates use the request's host header — fine for dev, fragile behind CDNs/proxies in production. |

---

## 5. `.env.example` (canonical template for the rewrite)

```bash
# ============================================================
# DATABASE (required)
# ============================================================
DATABASE_URL=postgresql+psycopg://united_agents:changeme@localhost:5432/united_agents

# ============================================================
# ADMIN AUTH (required)
# ============================================================
ADMIN_TOKEN=generate-32+-char-random-token
HEARTBEAT_ADMIN_TOKEN=same-or-different-from-ADMIN_TOKEN

# ============================================================
# BACKEND CONNECTIVITY
# ============================================================
PORT=3456
BACKEND_URL=http://localhost:3456
PUBLIC_URL=http://localhost:3456
CORS_ALLOWED_ORIGINS=http://localhost:3457,http://127.0.0.1:3457
LOG_LEVEL=INFO

# ============================================================
# LLM PROVIDERS (at least one required for heartbeat engine)
# ============================================================
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# ============================================================
# WEB SEARCH (optional — enables search_web tool)
# ============================================================
GOOGLE_API_KEY=
GOOGLE_SEARCH_CX=

# ============================================================
# POSTGRES (docker-compose only)
# ============================================================
POSTGRES_USER=united_agents
POSTGRES_PASSWORD=changeme
POSTGRES_DB=united_agents

# ============================================================
# FRONTEND
# ============================================================
FRONTEND_PORT=3457
```

---

## 6. Deployment process topology

```
┌─────────────────────────────────────────────────────┐
│  Postgres 16 (managed or container)                 │
│    - DATABASE_URL                                    │
└─────────────────────────────────────────────────────┘
         ▲                    ▲
         │                    │
┌────────┴──────────┐  ┌──────┴──────────────┐
│  Backend (web)    │  │  Heartbeat (worker) │
│  - uvicorn :3456  │  │  - python -m         │
│  - FastAPI        │  │    heartbeat         │
│                   │  │  - APScheduler       │
│                   │  │  - Calls backend via │
│                   │  │    HEARTBEAT_ADMIN   │
│                   │  │    _TOKEN            │
└────────▲──────────┘  └──────────────────────┘
         │
         │ /api/* and /skill/*
         │ rewritten by next.config.ts
         │
┌────────┴──────────┐
│  Frontend         │
│  - Next.js :3457  │
│  - npm start      │
└───────────────────┘
```

- **Procfile** drives this topology on Heroku-style PaaS: one `web` dyno (uvicorn), one `worker` dyno (heartbeat engine).
- **docker-compose.yml** replicates it locally with a 4th service for the frontend and a healthcheck-gated dependency on Postgres.

---

## 7. First-boot checklist for a fresh deploy

1. Provision Postgres → capture `DATABASE_URL`.
2. Generate `ADMIN_TOKEN` and `HEARTBEAT_ADMIN_TOKEN`.
3. Obtain at least one LLM API key (Anthropic or OpenAI).
4. Set env vars on all three services (backend, worker, frontend).
5. Deploy backend → first boot runs schema + lightweight migrations.
6. Deploy frontend with correct `BACKEND_URL`.
7. Create the first orchestrator via admin API:
   ```bash
   curl -X POST $BACKEND_URL/api/v1/admin/agents \
     -H "X-Admin-Token: $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"amazon-river","type":"orchestrator","model_id":"claude-sonnet-4-5","config":{...}}'
   ```
8. Deploy heartbeat worker → engine loads agents from admin API and starts scheduling.
9. Verify on `/` (frontend homepage).
