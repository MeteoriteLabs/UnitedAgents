"""Tests for data sources and scorer.

Uses mocked HTTP responses — no live API calls.
"""

import pytest
from unittest.mock import patch, AsyncMock

from heartbeat.sources.generic_http import GenericHTTP, _traverse_path
from heartbeat.sources.scorer import calculate


class TestDotNotationTraversal:
    def test_simple_path(self):
        data = {"a": {"b": 42}}
        assert _traverse_path(data, "$.a.b") == 42

    def test_array_index(self):
        data = {"items": [{"name": "first"}, {"name": "second"}]}
        assert _traverse_path(data, "$.items.1.name") == "second"

    def test_root(self):
        data = {"x": 1}
        assert _traverse_path(data, "$") == data

    def test_missing_key(self):
        data = {"a": 1}
        assert _traverse_path(data, "$.b.c") is None

    def test_nested_deep(self):
        data = {"a": {"b": {"c": {"d": "deep"}}}}
        assert _traverse_path(data, "$.a.b.c.d") == "deep"


class TestGenericHTTP:
    @pytest.mark.asyncio
    async def test_no_url_returns_error(self):
        source = GenericHTTP()
        result = await source.fetch_latest({})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_network_error_returns_error(self):
        source = GenericHTTP()
        result = await source.fetch_latest({
            "url": "http://nonexistent.invalid/api",
            "timeout": 1,
        })
        assert "error" in result


class TestConditionScorer:
    """ALGORITHMS.md §2 — deterministic scorer."""

    def test_perfect_match(self):
        current = {"temp": 25.0, "do": 8.0}
        baseline = {
            "temp": {"value": 25.0, "weight": 1.0, "direction": "deviation_bad"},
            "do": {"value": 8.0, "weight": 1.0, "direction": "deviation_bad"},
        }
        score, trend = calculate(current, baseline)
        assert score == 100.0
        assert trend == "stable"

    def test_deviation_bad(self):
        current = {"temp": 30.0}
        baseline = {"temp": {"value": 25.0, "weight": 1.0, "direction": "deviation_bad"}}
        score, trend = calculate(current, baseline)
        # deviation = abs(30-25)/25 = 0.2 → score = 80
        assert score == 80.0
        assert trend == "stable"

    def test_high_bad(self):
        current = {"temp": 30.0}
        baseline = {"temp": {"value": 25.0, "weight": 1.0, "direction": "high_bad"}}
        score, trend = calculate(current, baseline)
        # deviation = max(0, (30-25)/25) = 0.2 → score = 80
        assert score == 80.0

    def test_high_bad_below_baseline(self):
        current = {"temp": 20.0}
        baseline = {"temp": {"value": 25.0, "weight": 1.0, "direction": "high_bad"}}
        score, trend = calculate(current, baseline)
        # deviation = max(0, (20-25)/25) = 0 → score = 100
        assert score == 100.0

    def test_low_bad(self):
        current = {"do": 4.0}
        baseline = {"do": {"value": 8.0, "weight": 1.0, "direction": "low_bad"}}
        score, trend = calculate(current, baseline)
        # deviation = max(0, (8-4)/8) = 0.5 → score = 50
        assert score == 50.0

    def test_critical_score(self):
        current = {"do": 0.5}
        baseline = {"do": {"value": 8.0, "weight": 1.0, "direction": "low_bad"}}
        score, trend = calculate(current, baseline)
        # deviation = (8-0.5)/8 = 0.9375 → score = 6.25
        assert score < 10
        assert trend == "critical"

    def test_trend_improving(self):
        current = {"temp": 25.0}
        baseline = {"temp": {"value": 25.0, "weight": 1.0, "direction": "deviation_bad"}}
        score, trend = calculate(current, baseline, previous_score=90.0)
        # score=100, previous=90 → delta=10 > 5 → improving
        assert trend == "improving"

    def test_trend_declining(self):
        current = {"temp": 35.0}
        baseline = {"temp": {"value": 25.0, "weight": 1.0, "direction": "deviation_bad"}}
        score, trend = calculate(current, baseline, previous_score=90.0)
        # deviation=0.4 → score=60, delta=-30 → declining
        assert trend == "declining"

    def test_trend_stable_with_previous(self):
        current = {"temp": 26.0}
        baseline = {"temp": {"value": 25.0, "weight": 1.0, "direction": "deviation_bad"}}
        score, trend = calculate(current, baseline, previous_score=95.0)
        # deviation=0.04 → score=96, delta=1 → stable
        assert trend == "stable"

    def test_weighted_composite(self):
        current = {"temp": 25.0, "do": 4.0}
        baseline = {
            "temp": {"value": 25.0, "weight": 0.3, "direction": "deviation_bad"},
            "do": {"value": 8.0, "weight": 0.7, "direction": "low_bad"},
        }
        score, trend = calculate(current, baseline)
        # temp_score=100, do_score=50
        # composite = (100*0.3 + 50*0.7) / (0.3+0.7) = (30+35)/1 = 65
        assert score == 65.0

    def test_empty_baseline(self):
        score, trend = calculate({"x": 1}, {})
        assert score == 50.0

    def test_empty_current(self):
        score, trend = calculate({}, {"x": {"value": 1, "weight": 1, "direction": "deviation_bad"}})
        assert score == 50.0
