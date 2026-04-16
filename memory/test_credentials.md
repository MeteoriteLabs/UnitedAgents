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
