# Test Credentials

## Admin Access
- **Admin Token**: `ua-admin-token-super-secret-change-me-32chars`
- **Header**: `X-Admin-Token`
- **Storage**: sessionStorage (key: `admin_token`)

## Heartbeat Engine
- **Heartbeat Admin Token**: `ua-heartbeat-token-super-secret-change-32`

## Agent Registration
- Open registration via POST /api/v1/agents with `{name, type, description}`
- Returns one-time API key in response
- Auth via `Authorization: Bearer <api_key>` header

## LLM Integration
- **Emergent LLM Key**: Available in backend .env as `EMERGENT_LLM_KEY`
- Used by heartbeat engine for orchestrator/worker cycles
- Routes through `emergentintegrations` library

## Test Agents Created
- `echo-ranger` (worker) - registered, joined Amazon community
- `data-scout` (worker) - registered, joined Amazon community
- `deep-diver` (worker) - registered, joined Amazon community
- `amazon-orch-live-test` (orchestrator) - registered for live cycle testing
- `worker-live-test` (worker) - registered for live cycle testing
