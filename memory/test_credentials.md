# Test Credentials — United Agents

## Admin Token
- **Header**: `X-Admin-Token`
- **Value**: `ua-admin-token-super-secret-change-me-32chars`
- **Source**: `/app/backend/.env` → `ADMIN_TOKEN`

## Database
- **URL**: `postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents`
- **Test DB**: `postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents_test`
- **User**: `united_agents`
- **Password**: `changeme`

## Agent Authentication
- Agents authenticate via `Authorization: Bearer <api_key>` header
- API keys are generated at registration time and shown once
- Keys are stored as SHA-256 hashes only (no plaintext per D-15)
- To create a test agent: `POST /api/v1/agents` with `{"name":"test","type":"worker"}`

## Notes
- No human user accounts — only agents and admins
- Admin token is a static secret, not per-user
- Agent keys are generated via `secrets.token_urlsafe(32)`
