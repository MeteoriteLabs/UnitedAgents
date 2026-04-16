"""Tests for orchestrator, worker, earth, and maintenance jobs.

Uses mocked LLM provider and API client — no live calls.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from heartbeat.llm.provider import LLMResponse, ToolCall
from heartbeat.jobs.orchestrator import (
    _check_plan_trigger, _find_threads_needing_progression,
    _build_voice_context, _build_engage_context,
    _build_work_context, PROGRESSION_THRESHOLDS,
)
from heartbeat.jobs.worker import _parse_evidence_block
from heartbeat.jobs.maintenance import task_timeout_check, compute_urgency_scores


class TestPlanTrigger:
    def test_no_plan_enough_evidence(self):
        shared = {"plan": None, "evidence": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
                  "resolved_tasks": [], "open_tasks": []}
        ok, reason = _check_plan_trigger(shared)
        assert ok is True
        assert "No plan exists" in reason

    def test_plan_exists_tasks_resolved(self):
        shared = {"plan": {"id": "p1"}, "evidence": [],
                  "resolved_tasks": [{"id": "1"}, {"id": "2"}, {"id": "3"}], "open_tasks": []}
        ok, reason = _check_plan_trigger(shared)
        assert ok is True
        assert "tasks resolved" in reason

    def test_contested_evidence(self):
        shared = {"plan": {"id": "p1"}, "evidence": [{"contested": True}],
                  "resolved_tasks": [], "open_tasks": []}
        ok, reason = _check_plan_trigger(shared)
        assert ok is True
        assert "contested" in reason

    def test_no_trigger(self):
        shared = {"plan": {"id": "p1"}, "evidence": [{"contested": False}],
                  "resolved_tasks": [], "open_tasks": [{"id": "t1"}]}
        ok, reason = _check_plan_trigger(shared)
        assert ok is False


class TestThreadProgression:
    def test_sensing_to_investigating(self):
        shared = {"threads": [
            {"id": "t1", "stage": "sensing", "evidence_count": 5, "post_count": 2}
        ]}
        result = _find_threads_needing_progression(shared)
        assert len(result) == 1
        assert result[0]["action"] == "advance_stage"
        assert result[0]["target"] == "investigating"

    def test_investigating_to_brainstorm(self):
        shared = {"threads": [
            {"id": "t1", "stage": "investigating", "evidence_count": 6, "post_count": 3}
        ]}
        result = _find_threads_needing_progression(shared)
        assert len(result) == 1
        assert result[0]["action"] == "ask_for_proposals"

    def test_no_progression_needed(self):
        shared = {"threads": [
            {"id": "t1", "stage": "sensing", "evidence_count": 1, "post_count": 1}
        ]}
        result = _find_threads_needing_progression(shared)
        assert len(result) == 0


class TestContextBuilders:
    def test_voice_context(self):
        shared = {
            "community": {"name": "Amazon River", "scope": "South America"},
            "evidence": [{"type": "data_point", "content": "DO at 4.2 mg/L"}],
            "last_voice": {"content": "Previous update text"},
            "recent_posts": [{"type": "discussion", "title": "New findings"}],
        }
        ctx = _build_voice_context(shared)
        assert "Amazon River" in ctx
        assert "DO at 4.2" in ctx
        assert "Previous update" in ctx

    def test_engage_context(self):
        shared = {
            "worker_contributions": [
                {"id": "p1", "author_name": "Scout Alpha", "type": "research_note",
                 "title": "Water Quality", "content": "Found high mercury levels"},
            ],
            "evidence": [{"type": "data_point", "content": "Mercury 0.8 mg/L"}],
            "plan": {"content": "Focus on water quality"},
        }
        ctx = _build_engage_context(shared)
        assert "Scout Alpha" in ctx
        assert "Mercury" in ctx

    def test_work_context(self):
        shared = {
            "community": {"name": "Coral Reef", "scope": "Pacific"},
            "threads": [{"title": "Bleaching Event", "stage": "investigating",
                        "evidence_count": 5, "open_task_count": 1}],
            "open_tasks": [{"title": "Verify SST readings"}],
            "plan": {"content": "Monitor coral bleaching"},
            "evidence": [{"type": "measurement", "content": "SST 29.5C"}],
        }
        ctx = _build_work_context(shared)
        assert "Coral Reef" in ctx
        assert "Bleaching Event" in ctx
        assert "Verify SST" in ctx


class TestEvidenceParsing:
    def test_parse_json_block(self):
        text = """Findings here. Some data.
```json
{"ev_type": "data_point", "ev_summary": "Temperature at 28.5C"}
```"""
        ev_type, ev_summary = _parse_evidence_block(text)
        assert ev_type == "data_point"
        assert "28.5C" in ev_summary

    def test_fallback_no_json(self):
        text = "The temperature was 28.5C at the monitoring station."
        ev_type, ev_summary = _parse_evidence_block(text)
        assert ev_type == "research"
        assert "temperature" in ev_summary.lower()


class TestMaintenanceNoOps:
    @pytest.mark.asyncio
    async def test_task_timeout_runs(self):
        await task_timeout_check()  # Should not raise

    @pytest.mark.asyncio
    async def test_urgency_scores_runs(self):
        await compute_urgency_scores()  # Should not raise


class TestProgressionThresholds:
    """Verify thresholds match AGENT_SPEC.md §3.5."""
    def test_thresholds_values(self):
        assert PROGRESSION_THRESHOLDS["evidence_for_investigating"] == 3
        assert PROGRESSION_THRESHOLDS["evidence_for_brainstorm"] == 5
        assert PROGRESSION_THRESHOLDS["resolved_for_brainstorm"] == 3
        assert PROGRESSION_THRESHOLDS["proposals_for_children"] == 2
        assert PROGRESSION_THRESHOLDS["discussion_for_threshold"] == 3
        assert PROGRESSION_THRESHOLDS["discussion_for_action_ready"] == 5
