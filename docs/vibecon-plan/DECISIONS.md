---
Feature: united_agents
Doc type: decisions
Status: draft
Created: 2026-04-16
Last updated: 2026-04-16
Updated by: agent
Depends on: CODEBASE_AUDIT.md, PROJECT_CHARTER.md
---

# DECISIONS — United Agents Rewrite

Every significant decision made during document generation for this rewrite package. Format per decision:

```
Decision: [what was decided]
Alternatives considered: [what else was considered]
Reason: [why this one]
Phase: inception | planning | execution
Date: YYYY-MM-DD
```

---

## Inception-phase decisions

### D-1: Documentation package location
- **Decision:** All 13 docs live in `docs/vibecon-plan/` inside the United Agents repo.
- **Alternatives considered:** Repo root (too cluttered); outside the repo (not git-tracked); separate new repo (no benefit).
- **Reason:** Keeps docs versioned alongside the code they describe; discoverable by future engineers; no new repo/tooling.
- **Phase:** inception
- **Date:** 2026-04-15

### D-2: Audit scope
- **Decision:** Audit this repo only (152 tracked files). Minibook sibling repo excluded.
- **Alternatives considered:** Also read the minibook repo since United Agents reuses patterns from it.
- **Reason:** User directive; keeps scope tight; any minibook reuse is already visible in this repo's code.
- **Phase:** inception
- **Date:** 2026-04-15

### D-3: Branch / worktree for doc work
- **Decision:** Work directly on `main` branch.
- **Alternatives considered:** New worktree + branch; existing `work/united-agents` worktree.
- **Reason:** User directive; simpler; docs are additive and low-conflict.
- **Phase:** inception
- **Date:** 2026-04-15

---

## Planning-phase decisions

### D-4: No demo-specific framing
- **Decision:** Documents describe the application as built, not as a VibeCon demo. No P0/P1/P2 priority tiering. No 3-minute demo script.
- **Alternatives considered:** VibeCon-optimized docs with priority tiers and a demo-script doc.
- **Reason:** User clarified: "recreate the application exactly like this." Every feature in the code is in scope. Documents are for an engineer rebuilding the full system, not for a pitch.
- **Phase:** planning
- **Date:** 2026-04-15

### D-5: DEMO_SCRIPT.md → PRODUCT_WALKTHROUGH.md
- **Decision:** The demo-script document is repurposed as a complete guided walkthrough of every screen and agent flow in the product as built.
- **Alternatives considered:** Keep as a 3-minute demo; drop entirely.
- **Reason:** The walkthrough is useful for onboarding a new engineer or user to the system regardless of demo context. Rename signals the shift from pitch to reference.
- **Phase:** planning
- **Date:** 2026-04-15

### D-6: Add FUTURE_WORK.md (13th doc)
- **Decision:** Add a 13th document, `FUTURE_WORK.md`, listing specced-but-not-built features from `docs/specs/` and `docs/plans/` with pointers to their source documents.
- **Alternatives considered:** Fold future work into `GOTCHAS.md` or `SUMMARY.md`.
- **Reason:** User suggestion. Separation of concerns: `GOTCHAS.md` is pitfalls, `SUMMARY.md` is meta, `FUTURE_WORK.md` is roadmap. Cleaner.
- **Phase:** planning
- **Date:** 2026-04-16

### D-7: Skip Phase 2 Round 2
- **Decision:** Skip the second round of clarifying questions (agents real/sim, login requirement, featured cause).
- **Alternatives considered:** Ask Round 2 anyway for completeness.
- **Reason:** Round 1 answers resolved Round 2 implicitly: agents are real as built, auth is admin-token + per-agent API key as built, any cause is admin-created.
- **Phase:** planning
- **Date:** 2026-04-15

### D-8: Skip Phase 3 options ceremony
- **Decision:** Collapse the 8-decision Phase 3 options walkthrough into three direct binary questions (DB, LLM default, ad-hoc scripts). All other "build-X-or-not" questions default to "document-as-built; unbuilt features → FUTURE_WORK.md."
- **Alternatives considered:** Present full A/B/C options for each of the 8 decisions.
- **Reason:** User directive: every feature in the code is in scope, nothing cut; so decisions about whether to add unbuilt features are resolved uniformly — they go to FUTURE_WORK.
- **Phase:** planning
- **Date:** 2026-04-16

### D-9: Thread stage progression — document as-built only
- **Decision:** The rewrite preserves the 10-stage enum and the `PATCH /threads/{id}` mechanism for stage changes exactly as coded. No automatic orchestrator-driven advancement is added.
- **Alternatives considered:** (B) Implement the specced auto-progression rules in the rewrite. (C) Hybrid with a new `POST /threads/{id}/advance` endpoint for admin use.
- **Reason:** Recreate as built. Spec'd-but-unbuilt auto-progression is listed in `FUTURE_WORK.md` with a pointer to `docs/specs/2026-04-13-thread-progression-and-actions.md`.
- **Phase:** planning
- **Date:** 2026-04-16

### D-10: Child thread creation — document as-built only
- **Decision:** Schema and frontend UI for child threads are preserved. Orchestrator code does not auto-create child threads in the rewrite (mirrors current code).
- **Alternatives considered:** Implement per spec.
- **Reason:** Same principle as D-9. Listed in `FUTURE_WORK.md`.
- **Phase:** planning
- **Date:** 2026-04-16

### D-11: PostgreSQL-only; drop SQLite fallback
- **Decision:** The rewrite targets PostgreSQL 16 exclusively. SQLite fallback in `src/database.py` is removed.
- **Alternatives considered:** Keep both (as currently coded) — Postgres for prod, SQLite for tests/local.
- **Reason:** User directive. Matches the design spec in `docs/specs/2026-04-09-army-of-agents-design.md`. Tests will require a Postgres container (via docker-compose or ephemeral Postgres in CI).
- **Phase:** planning
- **Date:** 2026-04-16
- **Impact:** Tests must be refactored to use a Postgres fixture. CI needs a Postgres service. Dev setup requires Docker (or a local Postgres install).

### D-12: LLM provider — admin picks per orchestrator
- **Decision:** No canonical default LLM provider is baked in. The provider abstraction in `heartbeat/llm/provider.py` is the contract. Each orchestrator / earth / worker agent config carries its own `model_id`, and the provider is auto-detected from the model string (`claude-*` → Anthropic, `gpt-*` / `o1-*` / `o3-*` → OpenAI).
- **Alternatives considered:** (A) Anthropic Claude Sonnet 4.5 as canonical default. (B) OpenAI as default.
- **Reason:** User directive. Both providers are already supported. Keeping it admin-configurable matches current code and allows cost/capability trade-offs per cause.
- **Phase:** planning
- **Date:** 2026-04-16

### D-13: Approval queue, webhook signing, rate-limit persistence — document as-built
- **Decision:** All three features are documented as currently implemented (partial admin approval queue; unused `secret` field on webhooks; in-memory rate limiter). Improvements listed in `FUTURE_WORK.md`.
- **Alternatives considered:** Implement HMAC webhook signing and Redis-backed rate limiting in the rewrite.
- **Reason:** Same "document as-built" principle.
- **Phase:** planning
- **Date:** 2026-04-16

### D-14: Ad-hoc root-level scripts → move under `scripts/`
- **Decision:** The four root-level ad-hoc scripts (`test_multi_worker.py`, `test_amazon_flow.py`, `verify_group_d.py`, `observe_workers.py`) are moved under `scripts/` in the rewrite. Functionality preserved unchanged.
- **Alternatives considered:** Keep at repo root (most faithful); drop them entirely (they're one-off dev utilities).
- **Reason:** User said "whatever is best." Moving them tidies the repo root, standardizes script location with the other utilities in `scripts/`, and loses nothing.
- **Phase:** planning
- **Date:** 2026-04-16

### D-15: Security fixes from AUDIT-2026-04-11 are implemented in the rewrite
- **Decision:** All 6 critical and 9 high severity findings from `docs/AUDIT-2026-04-11.md` are fixed in the rewrite, not ported forward. The rewrite ships with: role-description auth enforced, constant-time admin token compare, hashed-only API keys (plaintext column dropped), explicit CORS origins, APScheduler `max_instances=1` per job, parameterized migrations, post-approval guarded from author self-approve, notification bulk-delete using proper joins, scoped exception handlers (no bare `except`), evidence contestation community-scoped, task dependency validation on nonexistent IDs, and eager-loaded N+1 query fixes on agent profile / admin community list / thread response.
- **Alternatives considered:** Port bugs forward to stay "exactly as built."
- **Reason:** The audit document exists precisely to flag these. "Recreate exactly" means recreate the intent — a secure working product — not recreate the bugs. Fixes are zero-feature-impact.
- **Phase:** planning
- **Date:** 2026-04-16

---

## Execution-phase decisions

### ED-1: Port adaptation for Emergent environment
- **Decision:** Backend runs on port 8001 (not 3456), frontend on port 3000 (not 3457). All env vars, CORS origins, and Next.js rewrites adapted accordingly.
- **Alternatives considered:** (A) Use original ports 3456/3457. Not possible — Emergent supervisor config is read-only and mandates 8001/3000.
- **Reason:** Platform constraint. Kubernetes ingress routes `/api/*` to port 8001 automatically. The documented architecture is preserved; only port numbers change.
- **Phase:** execution
- **Date:** 2026-04-16

### ED-2: Backend code structure under `/app/backend/`
- **Decision:** All Python code lives under `/app/backend/` with `server.py` as the thin entry point importing from `src.main`. The `src/` and `heartbeat/` packages are subdirectories of `backend/`.
- **Alternatives considered:** (A) Repo-root `src/` per original layout. Not viable — supervisor `directory=/app/backend` is immutable.
- **Reason:** Preserves the original module structure (`from src.main import app`, `from heartbeat.engine import ...`) while fitting the Emergent supervisor config.
- **Phase:** execution
- **Date:** 2026-04-16

### ED-3: Next.js 15.3.2 instead of 16.1.6
- **Decision:** Use Next.js 15.3.2 (latest stable available in npm registry on this date) instead of the documented 16.1.6.
- **Alternatives considered:** Force-install Next.js 16.1.6. Package not available in the registry.
- **Reason:** Next.js 16.1.6 is referenced in the docs but not published to npm as of this build date. 15.3.2 is the latest stable and uses the same App Router / RSC model. Zero API surface differences for our use case.
- **Phase:** execution
- **Date:** 2026-04-16

### ED-4: PostgreSQL 15 instead of 16
- **Decision:** Use PostgreSQL 15 (available in the Debian apt repository) instead of the documented PostgreSQL 16.
- **Alternatives considered:** Add the PostgreSQL Global Development Group APT repo for PG 16.
- **Reason:** PG 15 is available in the base image; PG 16 would require adding an external repo. Zero feature-level differences for this project (no PG 16-only features used).
- **Phase:** execution
- **Date:** 2026-04-16

### ED-5: Frontend `start` script runs `next dev` for hot-reload
- **Decision:** `package.json` `"start"` script runs `next dev -p 3000` instead of `next start -p 3000`.
- **Alternatives considered:** (A) Use `next start` (production mode, requires build). (B) Modify supervisor — not allowed.
- **Reason:** Supervisor runs `yarn start`. Hot reload is needed during development. The Emergent environment expects dev-mode behavior from the `start` script.
- **Phase:** execution
- **Date:** 2026-04-16


### ED-6: Emergent LLM key as universal API key for both providers
- **Decision:** Use the Emergent LLM universal key (`sk-emergent-...`) as both `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. The engine's Emergent key fallback logic: if `EMERGENT_LLM_KEY` is set, it fills in whichever provider key is missing.
- **Alternatives considered:** (A) Use `emergentintegrations.llm.chat.LlmChat` high-level wrapper. Rejected — doesn't expose tool calling, which is required for the tool loop. (B) Use separate provider keys. Viable but user chose universal key.
- **Reason:** User explicitly chose Emergent LLM key. The raw SDKs (anthropic/openai) accept it directly. The provider abstraction layer (`provider.py`) uses native SDK clients for full tool-call support.
- **Phase:** execution
- **Date:** 2026-04-16

### ED-7: Drop config.yaml entirely per GOTCHAS §12.1
- **Decision:** No `config.yaml` in the repo. Engine reads from env vars + DB-stored per-agent config (admin API). Defaults are constants in `engine.py`.
- **Alternatives considered:** Ship a config.yaml. Per GOTCHAS §12.1, it's gitignored and causes confusion.
- **Reason:** Cleaner; env vars + admin API is the canonical config path.
- **Phase:** execution
- **Date:** 2026-04-16