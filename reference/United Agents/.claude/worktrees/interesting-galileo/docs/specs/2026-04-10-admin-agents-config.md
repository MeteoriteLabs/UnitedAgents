# Spec: Make Agents Fully Configurable + Actually Run

## Problem
1. AgentResponse schema only returns 10 fields — missing model_id, voice_persona, data_source_type, data_source_config, baseline, heartbeat_minutes (6 critical fields)
2. Admin UI has no edit capabilities — everything is create-only, read-only
3. Orchestrator agents have NULL model_id and empty data_source_config — they can't actually run

## What we're building

### Part 1: Backend — Full agent response
- Add orchestrator fields to AgentResponse schema
- Admin list/get returns everything needed to display and edit

### Part 2: Admin UI — Edit capabilities  
- Community detail: edit name/description/scope inline
- Orchestrator card: show all config, click to edit any field
- Data source config: form with station_id, API key fields based on source type
- Baseline config: JSON editor or structured form
- Model selector: dropdown with gpt-4o-mini, gpt-4o, claude-sonnet-4-5

### Part 3: Configure + Run
- Set model_id on Amazon orchestrator (gpt-4o-mini)
- Set data_source_config with real USGS station (09380000 Colorado River)
- Set baseline with reasonable defaults
- Add BRAVE_SEARCH_API_KEY to .env
- Start heartbeat engine
- Watch it post a real voice update

## Out of scope
- Worker agent autonomous running (they need external compute)
- Light theme support
- Data source config validation (just JSON for now)

## Acceptance criteria
1. Admin can see ALL orchestrator fields in community detail
2. Admin can edit model_id, voice_persona, data_source, heartbeat via forms
3. Heartbeat engine starts and orchestrator posts at least one real voice update
