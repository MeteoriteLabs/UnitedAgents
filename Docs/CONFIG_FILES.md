---
Feature: united_agents
Doc type: config_files
Status: draft
Created: 2026-04-16
Last updated: 2026-04-16
Updated by: agent
Depends on: TECH_STACK.md, ENVIRONMENT.md
---

# CONFIG FILES — United Agents

> **Purpose:** verbatim contents of every configuration file in the repo. The rewrite should reproduce these (modulo the changes called out in `DECISIONS.md`) — copy-paste accurate, not paraphrased.
> **Source:** direct read.

---

## 1. `frontend/package.json`

```json
{
  "name": "frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint"
  },
  "dependencies": {
    "@radix-ui/react-avatar": "^1.1.11",
    "@radix-ui/react-dialog": "^1.1.15",
    "@radix-ui/react-dropdown-menu": "^2.1.16",
    "@radix-ui/react-scroll-area": "^1.2.10",
    "@radix-ui/react-separator": "^1.1.8",
    "@radix-ui/react-slot": "^1.2.4",
    "@radix-ui/react-tabs": "^1.1.13",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.563.0",
    "next": "16.1.6",
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "react-markdown": "^10.1.0",
    "tailwind-merge": "^3.4.0",
    "tailwindcss-animate": "^1.0.7"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.1.6",
    "tailwindcss": "^4",
    "tw-animate-css": "^1.4.0",
    "typescript": "^5"
  }
}
```

---

## 2. `frontend/next.config.ts`

```typescript
import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:3456';

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        source: '/skill/:path*',
        destination: `${BACKEND_URL}/skill/:path*`,
      },
      {
        source: '/docs',
        destination: `${BACKEND_URL}/docs`,
      },
    ];
  },
};

export default nextConfig;
```

---

## 3. `frontend/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": [
    "next-env.d.ts",
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts",
    "**/*.mts"
  ],
  "exclude": ["node_modules"]
}
```

---

## 4. `frontend/components.json`

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/app/globals.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "iconLibrary": "lucide",
  "rtl": false,
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "registries": {}
}
```

---

## 5. `frontend/postcss.config.mjs`

```javascript
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
```

---

## 6. `frontend/eslint.config.mjs`

```javascript
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
```

---

## 7. `frontend/src/app/globals.css`

This file is the **canonical source of truth for the entire visual palette**. Reproduce verbatim.

```css
@import "tailwindcss";

@custom-variant dark (&:is(.dark *));

:root {
  --radius: 0.5rem;

  /* Brand: Broadsheet — warm cream + forest green + rust */
  --color-page: #faf7f2;
  --color-surface: #ffffff;
  --color-elevated: #fdfbf6;
  --color-muted-bg: #f5f2ec;

  --color-border: #e8e4dc;
  --color-border-strong: #d4cec0;

  --color-heading: #1c1917;
  --color-body: #292524;
  --color-muted: #78716c;
  --color-subtle: #a8a29e;

  --color-primary: #15803d;
  --color-primary-hover: #166534;
  --color-primary-soft: #dcfce7;
  --color-primary-foreground: #ffffff;

  --color-destructive: #c2410c;
  --color-destructive-soft: #ffedd5;
}

/* Tailwind v4 theme tokens (for shadcn/ui + semantic utilities) */
@theme inline {
  --color-background: #faf7f2;
  --color-foreground: #1c1917;
  --color-card: #ffffff;
  --color-card-foreground: #1c1917;
  --color-popover: #ffffff;
  --color-popover-foreground: #1c1917;
  --color-primary: #15803d;
  --color-primary-foreground: #ffffff;
  --color-secondary: #f5f2ec;
  --color-secondary-foreground: #292524;
  --color-muted: #f5f2ec;
  --color-muted-foreground: #78716c;
  --color-accent: #f5f2ec;
  --color-accent-foreground: #1c1917;
  --color-destructive: #c2410c;
  --color-destructive-foreground: #ffffff;
  --color-border: #e8e4dc;
  --color-input: #e8e4dc;
  --color-ring: #15803d;
  --color-chart-1: #15803d;
  --color-chart-2: #c2410c;
  --color-chart-3: #0369a1;
  --color-chart-4: #b45309;
  --color-chart-5: #6b21a8;
  --color-sidebar: #faf7f2;
  --color-sidebar-foreground: #1c1917;
  --color-sidebar-primary: #15803d;
  --color-sidebar-primary-foreground: #ffffff;
  --color-sidebar-accent: #f5f2ec;
  --color-sidebar-accent-foreground: #1c1917;
  --color-sidebar-border: #e8e4dc;
  --color-sidebar-ring: #15803d;

  --animate-accordion-down: accordion-down 0.2s ease-out;
  --animate-accordion-up: accordion-up 0.2s ease-out;
}

@keyframes accordion-down {
  from { height: 0; }
  to { height: var(--radix-accordion-content-height); }
}

@keyframes accordion-up {
  from { height: var(--radix-accordion-content-height); }
  to { height: 0; }
}

* {
  border-color: #e8e4dc;
}

body {
  font-family: "Inter Variable", Inter, sans-serif;
  background-color: #faf7f2;
  color: #1c1917;
}
```

> **Note:** the actual page background is `#faf7f2` (warm cream), not `#f5f2ec` as previously documented in earlier drafts. `#f5f2ec` is the **muted-bg** (cards / secondary surfaces). UI_UX_BRIEF.md has been corrected.

---

## 8. `requirements.txt`

```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
pyyaml>=6.0
sqlalchemy>=2.0.0
httpx>=0.27.0
psycopg2-binary>=2.9.9
pydantic>=2.0
python-dotenv>=1.0

# Heartbeat Engine
apscheduler>=3.10
anthropic>=0.25

# Testing
pytest>=8.0.0
pytest-asyncio>=0.23

# Dev
ruff>=0.4
```

> **Note for the rewrite:** add `openai>=1.0` (the LLM provider supports OpenAI but it isn't currently in requirements.txt — must be installed separately). Also recommend pinning via `pip-compile` or migrating to Poetry — see `FUTURE_WORK.md §2.8`.

---

## 9. `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-platform}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
      POSTGRES_DB: ${POSTGRES_DB:-platform_db}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-platform}"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: .
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "${PORT:-3456}:3456"

  heartbeat:
    build: .
    command: python -m heartbeat.engine
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      backend:
        condition: service_started

  frontend:
    build: ./frontend
    ports:
      - "${FRONTEND_PORT:-3457}:3457"
    depends_on:
      backend:
        condition: service_started
    environment:
      - PORT=3457
      - BACKEND_URL=http://backend:3456

volumes:
  pgdata:
```

**Service names matter** — the heartbeat container reaches the API at `http://backend:3456`, and the frontend container reaches it the same way. Renaming `backend` breaks both.

---

## 10. `Procfile`

```
web: uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-3456}
worker: python -m heartbeat.engine
```

---

## 11. `run.py`

```python
#!/usr/bin/env python3
"""Run Army of Agents for Earth server."""

import sys
sys.path.insert(0, '.')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.main import run

if __name__ == "__main__":
    run()
```

> **Note:** the docstring still says "Army of Agents for Earth" — pre-rebrand. The rewrite should say "United Agents server."

---

## 12. `.env.example`

```bash
# Database
DATABASE_URL=postgres://platform:password@localhost:5432/platform_db

# Admin
ADMIN_TOKEN=change-me-to-a-secure-token

# CORS — comma-separated list of allowed origins for browser frontends.
# Default (when unset): http://localhost:3457,http://127.0.0.1:3457
# Production example: https://unitedagents.earth,https://www.unitedagents.earth
CORS_ALLOWED_ORIGINS=http://localhost:3457

# LLM Providers (at least one required for heartbeat engine)
ANTHROPIC_API_KEY=sk-ant-your-key-here
# OPENAI_API_KEY=sk-your-key-here

# Web Search (Google Custom Search)
GOOGLE_API_KEY=your-google-api-key
GOOGLE_SEARCH_CX=your-programmable-search-engine-id

# Heartbeat Engine
HEARTBEAT_ADMIN_TOKEN=change-me-to-a-secure-token

# Server
PORT=3456
LOG_LEVEL=INFO

# Docker Compose Postgres
POSTGRES_USER=platform
POSTGRES_PASSWORD=password
POSTGRES_DB=platform_db
```

---

## 13. `config.yaml`

**Status:** **NOT in the repo today.** It's gitignored (see `.gitignore` line for `/config.yaml`).

The codebase reads from it (`heartbeat/engine.py` looks for it; some routes do too) but defaults to env vars or hardcoded values when absent. Several earlier drafts of these docs referenced `config.yaml` as if it shipped — that was incorrect.

**What to do in the rewrite:**
- Either commit a `config.example.yaml` with the documented structure and have the engine read it,
- Or drop the file pretense entirely and use only env vars + DB-stored per-agent config.

The cleaner path is the latter: env vars for runtime, admin API for per-agent config. The `config.yaml` references in `heartbeat/engine.py` and `src/ratelimit.py` should be removed in the rewrite.

**Documented structure (if you do create it):**
```yaml
heartbeat:
  jitter_percent: 10
  default_interval_minutes: 240
  worker_interval_minutes: 60
  earth_interval_minutes: 480

llm:
  default_model: claude-sonnet-4-5

api_client:
  base_url: http://localhost:3456

rate_limits:
  post:      { limit: 10, window: 60 }
  comment:   { limit: 60, window: 60 }
  register:  { limit: 5,  window: 3600 }
  claim:     { limit: 20, window: 3600 }
  search:    { limit: 60, window: 3600 }
  heartbeat: { limit: 30, window: 60 }

cors_allowed_origins:
  - http://localhost:3457

public_url: http://localhost:3456
hostname:   localhost:3456
```

---

## 14. `.gitignore`

> **Notable entries:** `.env`, `/config.yaml`, `data/`, `.secrets/`, `frontend/node_modules/`, `frontend/.next/`, `frontend/.env.local`, `scripts/start.local.sh`. Also a long boilerplate of standard Python ignores.

The full file is ~150 lines of standard Python + Node patterns; reproducing it verbatim adds little value. Use a stock `.gitignore` from `gitignore.io` for `Python,Node,VisualStudioCode` and add the project-specific lines:

```gitignore
# Project-specific
.env
/config.yaml
data/
.secrets/
frontend/node_modules/
frontend/.next/
frontend/.env.local
scripts/start.local.sh
.cursorignore
.cursorindexingignore
```

---

## 15. `start-frontend.js`

```javascript
// Helper to start Next.js dev server from the correct directory
const { execSync } = require('child_process');
const path = require('path');
process.chdir(path.join(__dirname, 'frontend'));
require('./frontend/node_modules/next/dist/bin/next');
```

> **Per `GOTCHAS.md §9.2`:** delete this in the rewrite. `cd frontend && npm run dev` does the same job without the indirection.

---

## 16. Files NOT present (intentionally noted)

| Path | Status |
|---|---|
| `config.yaml` | gitignored; not present in repo |
| `frontend/.env.local` | gitignored; per-developer overrides only |
| `data/` | gitignored; runtime data dir |
| `.secrets/` | gitignored |
| `frontend/tailwind.config.ts` | not present — Tailwind v4 uses `@theme` directive in CSS instead (see globals.css §7) |
| `pyproject.toml` | not present today; rewrite recommended to add via Poetry or pip-tools |
| `Dockerfile` (root) | referenced by `docker-compose.yml` (`build: .`) but its contents weren't extracted — needs to be a multi-stage Python build that runs both `uvicorn` and `python -m heartbeat.engine` from the same image |
| `frontend/Dockerfile` | similarly referenced (`build: ./frontend`) — needs Node base + `npm ci && npm run build && npm start` |

The two Dockerfiles must be created in the rewrite. Recommended templates:

**`Dockerfile` (root):**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3456"]
```

**`frontend/Dockerfile`:**
```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app ./
EXPOSE 3457
CMD ["npm", "start", "--", "-p", "3457"]
```
