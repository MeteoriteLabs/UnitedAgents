"""Tests for platform tools — duplicate detection + tool definitions.

No live API calls — uses mocked APIClient.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from heartbeat.tools.platform_tools import (
    _find_duplicate_task, STOP_WORDS, ORCHESTRATOR_TOOLS,
    EARTH_TOOLS, SEARCH_WEB_TOOL, get_tool_definitions, build_tool_handlers,
)


class TestDuplicateTaskDetection:
    """ALGORITHMS.md §1: word-overlap >0.45 with STOP_WORDS filtered."""

    def test_exact_duplicate(self):
        tasks = [{"title": "Collect water samples from station 5"}]
        dup = _find_duplicate_task("Collect water samples from station 5", tasks)
        assert dup is not None

    def test_similar_title(self):
        tasks = [{"title": "Research upstream discharge patterns"}]
        dup = _find_duplicate_task("Research upstream discharge trends", tasks)
        # "research", "upstream", "discharge" overlap = 3/4 = 0.75 > 0.45
        assert dup is not None

    def test_no_duplicate(self):
        tasks = [{"title": "Monitor coral bleaching events"}]
        dup = _find_duplicate_task("Analyze deforestation satellite imagery", tasks)
        assert dup is None

    def test_stop_words_filtered(self):
        tasks = [{"title": "the water is in the river"}]
        # After stop word removal: {"water", "river"}
        dup = _find_duplicate_task("the river is from the water", tasks)
        # After stop word removal: {"river", "water"} — overlap 2/2 = 1.0 > 0.45
        assert dup is not None

    def test_empty_tasks(self):
        assert _find_duplicate_task("New task", []) is None

    def test_stop_words_only_title(self):
        tasks = [{"title": "the is a an to"}]
        dup = _find_duplicate_task("for by at of in", tasks)
        assert dup is None

    def test_checks_both_open_and_resolved(self):
        tasks = [
            {"title": "Verify water quality readings"},
            {"title": "Check dissolved oxygen levels"},
        ]
        dup = _find_duplicate_task("Verify water quality measurements", tasks)
        # "verify", "water", "quality" overlap vs "verify", "water", "quality", "readings"
        # = 3/4 = 0.75 > 0.45
        assert dup is not None


class TestStopWords:
    def test_stop_words_are_frozenset(self):
        assert isinstance(STOP_WORDS, frozenset)

    def test_contains_expected_words(self):
        for word in ["the", "a", "an", "is", "to", "for", "of", "in"]:
            assert word in STOP_WORDS


class TestToolDefinitions:
    def test_orchestrator_has_8_tools(self):
        assert len(ORCHESTRATOR_TOOLS) == 8

    def test_earth_has_2_extra_tools(self):
        assert len(EARTH_TOOLS) == 2

    def test_get_tool_definitions_orchestrator(self):
        tools = get_tool_definitions("orchestrator")
        names = [t["name"] for t in tools]
        assert "post_voice_update" in names
        assert "create_task" in names
        assert "search_web" in names
        assert "post_signal" not in names  # earth-only

    def test_get_tool_definitions_earth(self):
        tools = get_tool_definitions("earth")
        names = [t["name"] for t in tools]
        assert "post_signal" in names
        assert "create_cross_community_task" in names
        assert "search_web" in names

    def test_all_tools_have_required_fields(self):
        all_tools = ORCHESTRATOR_TOOLS + EARTH_TOOLS + [SEARCH_WEB_TOOL]
        for t in all_tools:
            assert "name" in t
            assert "description" in t
            assert "parameters" in t
            assert t["parameters"]["type"] == "object"


class TestToolHandlers:
    def test_build_handlers_returns_all(self):
        client = MagicMock()
        agent = {"id": "a1", "api_key": "key"}
        handlers = build_tool_handlers(client, agent, "c1")
        expected = {
            "post_voice_update", "create_thread", "update_thread_stage",
            "create_task", "reply_to_post", "promote_to_evidence",
            "update_community_plan", "post_system_message", "search_web",
            "post_signal", "create_cross_community_task",
        }
        assert set(handlers.keys()) == expected

    @pytest.mark.asyncio
    async def test_post_voice_update_handler(self):
        client = MagicMock()
        client.create_post = AsyncMock(return_value={"id": "p1"})
        agent = {"id": "a1", "api_key": "key"}
        handlers = build_tool_handlers(client, agent, "c1")

        result = await handlers["post_voice_update"]({
            "content": "Water levels are declining. We need immediate attention.",
        })
        assert result["status"] == "posted"
        assert result["post_id"] == "p1"

    @pytest.mark.asyncio
    async def test_create_task_duplicate_blocked(self):
        client = MagicMock()
        client.get_open_tasks = AsyncMock(return_value=[
            {"title": "Collect dissolved oxygen readings"}
        ])
        client.get_resolved_tasks = AsyncMock(return_value=[])
        agent = {"id": "a1", "api_key": "key"}
        handlers = build_tool_handlers(client, agent, "c1")

        result = await handlers["create_task"]({
            "title": "Collect dissolved oxygen measurements",
            "content": "Need readings", "category": "data_collection",
        })
        assert result["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_update_plan_guard_no_plan_few_evidence(self):
        client = MagicMock()
        client.get_plan = AsyncMock(return_value=None)
        client.get_evidence = AsyncMock(return_value=[{"id": "e1"}, {"id": "e2"}])
        agent = {"id": "a1", "api_key": "key"}
        handlers = build_tool_handlers(client, agent, "c1")

        result = await handlers["update_community_plan"]({
            "content": "New plan", "reason": "First plan",
        })
        assert result["status"] == "blocked"
