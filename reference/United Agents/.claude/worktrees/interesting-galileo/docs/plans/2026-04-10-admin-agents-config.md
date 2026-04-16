# Plan: Make Agents Fully Configurable + Run

## Task 1: Fix AgentResponse schema [15min]

**File: `src/schemas.py`**
- Add to AgentResponse: model_id, voice_persona, data_source_type, data_source_config, baseline, heartbeat_minutes
- All Optional fields (only orchestrators have them)

**File: `src/routes/admin.py`**
- Update admin_list_agents and admin_create_agent to populate the new fields from model

**Test:** `curl /admin/agents` returns model_id, data_source_type, voice_persona for orchestrators

## Task 2: Add admin API methods to api.ts [5min]

**File: `frontend/src/lib/api.ts`**
- Update Agent interface to include: model_id, voice_persona, data_source_type, data_source_config, baseline, heartbeat_minutes

## Task 3: Rewrite admin community detail with edit forms [45min]

**File: `frontend/src/app/admin/page.tsx`**

Community detail view changes:
- **Community header**: editable name/description/scope (click to edit, save button)
- **Orchestrator card**: show ALL fields in a structured layout:
  - Name, Model (dropdown), Data Source Type (dropdown), Heartbeat (input)
  - Voice Persona (textarea, collapsible)
  - Data Source Config (structured form based on type):
    - USGS: station_id input
    - NOAA: station_id input  
    - GFW: api_key + geostore_id inputs
    - Generic: url, method, headers inputs
  - Baseline (JSON textarea for now)
  - [Save Changes] button → calls PATCH /admin/agents/{id}
- **Edit mode**: toggle between view and edit with pencil icon

## Task 4: Configure Amazon orchestrator + run [15min]

Via admin UI (or curl if UI isn't ready):
- Set model_id: "gpt-4o-mini"
- Set data_source_config: {"station_id": "09380000"} (Colorado River at Lees Ferry)
- Set baseline: {"discharge": {"value": 12000, "weight": 2, "direction": "deviation_bad"}, "temperature": {"value": 10, "weight": 1, "direction": "high_bad"}}
- Start heartbeat engine: python -m heartbeat.engine
- Verify: voice update appears in feed

## Verification
1. Backend tests pass (67)
2. Frontend builds clean
3. Admin shows all orchestrator fields
4. Can edit orchestrator config from admin
5. Heartbeat engine starts and posts
