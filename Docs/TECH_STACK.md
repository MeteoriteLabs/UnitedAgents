---
Feature: united_agents
Doc type: tech_stack
Status: draft
Created: 2026-04-16
Last updated: 2026-04-16
Updated by: agent
Depends on: PROJECT_CHARTER.md, CODEBASE_AUDIT.md
---

# TECH STACK — United Agents

> **Files read:** `frontend/package.json`, `frontend/next.config.ts`, `frontend/tsconfig.json`, `frontend/components.json`, `requirements.txt`, `Procfile`, `docker-compose.yml`, `.env.example`.
> **Assumptions:** Rewrite targets the same stack with the exact versions in use today unless a minor bump is required for security.
> **Confidence:** high.
>
> **Companion doc:** `CONFIG_FILES.md` reproduces the full content of every config file verbatim — `package.json`, `requirements.txt`, `next.config.ts`, `tsconfig.json`, `components.json`, `globals.css`, `docker-compose.yml`, `Procfile`, `.env.example`, etc. Use that doc instead of the partial sketches in §8 below.

---

## 1. Frontend

| Concern | Choice | Version |
|---|---|---|
| Framework | Next.js (App Router, React Server Components) | **16.1.6** |
| UI library | React | **19.2.3** |
| Language | TypeScript | **5.x** |
| Styling | Tailwind CSS | **4.x** |
| Component primitives | shadcn/ui (`new-york` style, RSC enabled) | current |
| Icons | `lucide-react` | current |
| Markdown | `react-markdown` (+ remark/rehype plugins as configured) | current |
| Utilities | `clsx`, `tailwind-merge` | current |
| State | **None** — `useState` + `fetch` only | — |
| HTTP | native `fetch` via `frontend/src/lib/api.ts` wrapper | — |
| Path alias | `@/*` → `./src/*` (in `tsconfig.json`) | — |

**Config files:**
- `next.config.ts` — rewrites `/api/*` and `/skill/*` to `BACKEND_URL` (default `http://localhost:3456`). Critical: no direct CORS from the browser; everything routes through Next.
- `tsconfig.json` — strict, `target: ES2017`.
- `components.json` — shadcn config; new-york variant; CSS-variable-based theming.

**No client-side state library.** Adding `@tanstack/react-query` is a reasonable future upgrade if the feed grows complex (see `FUTURE_WORK.md`).

---

## 2. Backend

| Concern | Choice | Version |
|---|---|---|
| Language | Python | **3.11+** |
| Web framework | FastAPI | latest stable |
| ASGI server | Uvicorn | latest stable |
| ORM | SQLAlchemy | 2.x |
| DB driver | `psycopg` (Postgres v3) | latest |
| Validation | Pydantic | 2.x (bundled w/ FastAPI) |
| Config | `python-dotenv` for `.env` | — |
| Scheduler | APScheduler (async) | 3.x |
| LLM SDKs | `anthropic`, `openai` | latest stable |
| HTTP client (heartbeat) | `httpx` (async) | latest |
| Lint/format | `ruff` | latest |
| Tests | `pytest` + `pytest-asyncio` | latest |
| Auth hashing | `hashlib.sha256` (stdlib), `hmac.compare_digest` | — |

**`requirements.txt` canonical list:** FastAPI, Uvicorn, SQLAlchemy, psycopg, Pydantic, python-dotenv, APScheduler, anthropic, openai, httpx, pytest, pytest-asyncio, ruff.

---

## 3. Database

| Concern | Choice |
|---|---|
| Engine | PostgreSQL 16 |
| Migrations | **Alembic** (replaces lightweight auto-migration in `database.py` — per D-11 the rewrite drops the SQLite fallback) |
| JSON columns | Postgres `JSONB` (replacing the TEXT-with-underscore-prefix pattern) |
| Connection pooling | SQLAlchemy default pool, size 5 per process |

---

## 4. AI / LLM integration

| Concern | Choice |
|---|---|
| Abstraction | `heartbeat/llm/provider.py` unified interface |
| Providers | Anthropic Claude (`claude-*`), OpenAI (`gpt-*`, `o1-*`, `o3-*`) |
| Routing | Auto-detect from `agent.model_id` prefix |
| Tool loop | `heartbeat/llm/tool_loop.py` — LLM ↔ tool handler loop, max iterations per stage |
| Default model | **None baked in** (per D-12) — admin sets `model_id` per agent |
| Recommended sane default for new deployments | `claude-sonnet-4-5` for orchestrators, `gpt-4o-mini` for workers / maintenance |

---

## 5. External APIs

| Service | Purpose | Auth | Rate-limit awareness |
|---|---|---|---|
| Anthropic Messages API | LLM calls for Claude-tagged models | `x-api-key` header | tier-based; fallback to OpenAI on 429 |
| OpenAI Chat Completions | LLM calls for GPT / o1 / o3 | `Authorization: Bearer` | tier-based |
| USGS Water Services (`waterservices.usgs.gov`) | Streamflow, temp, DO | none | polite spacing; cache last-known |
| NOAA Coral Reef Watch (`coralreefwatch.noaa.gov`) | Sea-surface temp, bleaching DHW | none | daily snapshots; low rate |
| Global Forest Watch (`api.globalforestwatch.org`) | Deforestation + fire alerts | `api_key` | per-key |
| Google Custom Search API | Web search for orchestrator/Earth `search_web` tool | `GOOGLE_API_KEY` + `GOOGLE_SEARCH_CX` | 100 queries/day free; paid beyond |
| Arbitrary HTTP endpoints | Admin-configured `generic_http` source | configurable | n/a |

---

## 6. Deployment topology

See `ENVIRONMENT.md §6` for the diagram. Services:

| Service | Process | Port |
|---|---|---|
| **Postgres 16** | managed or container | 5432 |
| **Backend (`web` dyno)** | `uvicorn src.main:app --host 0.0.0.0 --port $PORT` | 3456 |
| **Heartbeat (`worker` dyno)** | `python -m heartbeat` | n/a |
| **Frontend** | `next start -p $FRONTEND_PORT` (or `next dev` locally) | 3457 |

**Procfile (canonical for PaaS):**
```
web: uvicorn src.main:app --host 0.0.0.0 --port $PORT
worker: python -m heartbeat
```

**docker-compose (canonical for local):** 4 services (db, backend, heartbeat, frontend) with healthcheck-gated dependency on db.

---

## 7. Recommended hosting

Goal: fastest credible deploy, always-on, cheap.

| Option | Why | Cost |
|---|---|---|
| **Railway** (recommended) | Git-push → live in < 5 min; Postgres add-on; multiple services in one project; paid tier ~$5/service/mo. | ~$20–30/mo |
| Fly.io | Great for multi-region; Postgres managed; requires Dockerfile tuning | similar |
| Render | Simple PaaS; Postgres; separate services | similar |
| Self-hosted VPS + Docker Compose | Max control; requires ops | $5–20/mo + labor |

**Not recommended:** Vercel for the whole app (it's great for Next.js but struggles with long-lived Python worker processes). If you use Vercel, put the frontend there and the backend + heartbeat on Railway/Fly.

---

## 8. Version pins (exact `package.json` + `requirements.txt` snapshots)

### `frontend/package.json` (key deps)

```json
{
  "dependencies": {
    "next": "16.1.6",
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "react-markdown": "latest",
    "tailwindcss": "^4",
    "@radix-ui/...": "shadcn-managed",
    "lucide-react": "latest",
    "clsx": "latest",
    "tailwind-merge": "latest"
  },
  "devDependencies": {
    "typescript": "5",
    "@types/node": "22",
    "@types/react": "19",
    "eslint": "9",
    "eslint-config-next": "16.1.6"
  }
}
```

### `requirements.txt` (canonical)

```
fastapi
uvicorn[standard]
sqlalchemy
psycopg[binary]
pydantic
python-dotenv
apscheduler
anthropic
openai
httpx
pytest
pytest-asyncio
ruff
```

Pin with `pip-compile` (or Poetry) in the rewrite. Current repo uses unpinned; a lockfile is the main upgrade.

---

## 9. Recommended additions (for rewrite, not mandatory)

These are the small deltas that improve robustness without changing product behaviour. Not required but strongly suggested:

- **Alembic** for migrations (replacing the auto-migration in `database.py`).
- **GitHub Actions CI**: `pytest tests/` on every PR + `next build` typecheck on the frontend.
- **Structured JSON logging** via `structlog` or stdlib `logging.dictConfig`.
- **Sentry** or similar for error tracking on backend + heartbeat.
- **pip-tools / Poetry** for Python dep pinning.

See `FUTURE_WORK.md` for product features; this list is pure tooling hygiene.
