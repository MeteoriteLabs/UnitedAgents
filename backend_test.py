#!/usr/bin/env python3
"""
United Agents Session 8 Backend Testing
Tests: Duplicate task detection, tool definitions, condition scorer, data sources, all 50 pytest tests
"""

import asyncio
import json
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
import os

# Add backend to path
sys.path.insert(0, '/app/backend')

class Session8BackendTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
    def log(self, message: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def run_test(self, name: str, test_func) -> bool:
        """Run a single test function"""
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            result = test_func()
            if result:
                self.tests_passed += 1
                self.log(f"✅ Passed - {name}")
                self.test_results.append({"name": name, "status": "PASSED"})
                return True
            else:
                self.log(f"❌ Failed - {name}")
                self.test_results.append({"name": name, "status": "FAILED"})
                return False
        except Exception as e:
            self.log(f"❌ Failed - {name}: {str(e)}")
            self.test_results.append({"name": name, "status": "ERROR", "error": str(e)})
            return False
    
    async def run_async_test(self, name: str, test_func) -> bool:
        """Run a single async test function"""
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            result = await test_func()
            if result:
                self.tests_passed += 1
                self.log(f"✅ Passed - {name}")
                self.test_results.append({"name": name, "status": "PASSED"})
                return True
            else:
                self.log(f"❌ Failed - {name}")
                self.test_results.append({"name": name, "status": "FAILED"})
                return False
        except Exception as e:
            self.log(f"❌ Failed - {name}: {str(e)}")
            self.test_results.append({"name": name, "status": "ERROR", "error": str(e)})
            return False

    def test_duplicate_task_detection(self):
        """Test duplicate task detection with STOP_WORDS and overlap >0.45"""
        from heartbeat.tools.platform_tools import _find_duplicate_task, STOP_WORDS
        
        # Test exact match blocked
        tasks = [{"title": "Collect water samples from station 5"}]
        dup = _find_duplicate_task("Collect water samples from station 5", tasks)
        assert dup is not None, "Exact match should be blocked"
        
        # Test similar title (overlap >0.45) blocked
        tasks = [{"title": "Research upstream discharge patterns"}]
        dup = _find_duplicate_task("Research upstream discharge trends", tasks)
        # "research", "upstream", "discharge" overlap = 3/4 = 0.75 > 0.45
        assert dup is not None, "Similar title should be blocked"
        
        # Test dissimilar title passes
        tasks = [{"title": "Monitor coral bleaching events"}]
        dup = _find_duplicate_task("Analyze deforestation satellite imagery", tasks)
        assert dup is None, "Dissimilar title should pass"
        
        # Test STOP_WORDS filtered before comparison
        tasks = [{"title": "the water is in the river"}]
        dup = _find_duplicate_task("the river is from the water", tasks)
        # After stop word removal: {"water", "river"} overlap = 2/2 = 1.0 > 0.45
        assert dup is not None, "STOP_WORDS should be filtered"
        
        # Test STOP_WORDS are frozenset
        assert isinstance(STOP_WORDS, frozenset), "STOP_WORDS should be frozenset"
        assert "the" in STOP_WORDS, "STOP_WORDS should contain common words"
        
        return True

    def test_tool_definitions_session8(self):
        """Test tool definitions: orchestrator gets 9 tools, earth gets 11 tools"""
        from heartbeat.tools.platform_tools import (
            ORCHESTRATOR_TOOLS, EARTH_TOOLS, SEARCH_WEB_TOOL, get_tool_definitions
        )
        
        # Test orchestrator has 8 tools
        assert len(ORCHESTRATOR_TOOLS) == 8, f"Expected 8 orchestrator tools, got {len(ORCHESTRATOR_TOOLS)}"
        
        # Test earth has 2 extra tools
        assert len(EARTH_TOOLS) == 2, f"Expected 2 earth tools, got {len(EARTH_TOOLS)}"
        
        # Test orchestrator gets 8+search=9 tools
        orch_tools = get_tool_definitions("orchestrator")
        assert len(orch_tools) == 9, f"Expected 9 total orchestrator tools, got {len(orch_tools)}"
        
        # Test earth gets 8+search+2=11 tools
        earth_tools = get_tool_definitions("earth")
        assert len(earth_tools) == 11, f"Expected 11 total earth tools, got {len(earth_tools)}"
        
        # Verify search_web is included
        orch_names = [t["name"] for t in orch_tools]
        earth_names = [t["name"] for t in earth_tools]
        assert "search_web" in orch_names, "Orchestrator should have search_web"
        assert "search_web" in earth_names, "Earth should have search_web"
        
        # Verify earth-only tools
        assert "post_signal" in earth_names, "Earth should have post_signal"
        assert "create_cross_community_task" in earth_names, "Earth should have create_cross_community_task"
        assert "post_signal" not in orch_names, "Orchestrator should not have post_signal"
        
        return True

    def test_tool_handlers_session8(self):
        """Test tool handlers: post_voice_update, create_task, update_community_plan"""
        from heartbeat.tools.platform_tools import build_tool_handlers
        from unittest.mock import MagicMock, AsyncMock
        
        # Mock API client
        client = MagicMock()
        agent = {"id": "a1", "api_key": "test-key"}
        handlers = build_tool_handlers(client, agent, "c1")
        
        # Verify all expected handlers exist
        expected_handlers = {
            "post_voice_update", "create_thread", "update_thread_stage",
            "create_task", "reply_to_post", "promote_to_evidence",
            "update_community_plan", "post_system_message", "search_web",
            "post_signal", "create_cross_community_task",
        }
        assert set(handlers.keys()) == expected_handlers, "All handlers should be present"
        
        return True

    def test_condition_scorer_session8(self):
        """Test condition scorer: perfect match, directions, critical threshold, trends"""
        from heartbeat.sources.scorer import calculate
        
        # Test perfect match → 100.0, stable
        current = {"temp": 25.0, "do": 8.0}
        baseline = {
            "temp": {"value": 25.0, "weight": 1.0, "direction": "deviation_bad"},
            "do": {"value": 8.0, "weight": 1.0, "direction": "deviation_bad"},
        }
        score, trend = calculate(current, baseline)
        assert score == 100.0, f"Perfect match should score 100.0, got {score}"
        assert trend == "stable", f"Perfect match should be stable, got {trend}"
        
        # Test deviation_bad direction
        current = {"temp": 30.0}
        baseline = {"temp": {"value": 25.0, "weight": 1.0, "direction": "deviation_bad"}}
        score, trend = calculate(current, baseline)
        assert score == 80.0, f"Deviation should score 80.0, got {score}"
        
        # Test high_bad direction
        current = {"temp": 30.0}
        baseline = {"temp": {"value": 25.0, "weight": 1.0, "direction": "high_bad"}}
        score, trend = calculate(current, baseline)
        assert score == 80.0, f"High_bad should score 80.0, got {score}"
        
        # Test low_bad direction
        current = {"do": 4.0}
        baseline = {"do": {"value": 8.0, "weight": 1.0, "direction": "low_bad"}}
        score, trend = calculate(current, baseline)
        assert score == 50.0, f"Low_bad should score 50.0, got {score}"
        
        # Test critical threshold (score ≤10)
        current = {"do": 0.5}
        baseline = {"do": {"value": 8.0, "weight": 1.0, "direction": "low_bad"}}
        score, trend = calculate(current, baseline)
        assert score <= 10, f"Critical score should be ≤10, got {score}"
        assert trend == "critical", f"Low score should be critical, got {trend}"
        
        # Test trend classification with previous_score
        current = {"temp": 25.0}
        baseline = {"temp": {"value": 25.0, "weight": 1.0, "direction": "deviation_bad"}}
        score, trend = calculate(current, baseline, previous_score=90.0)
        assert trend == "improving", f"Score increase should be improving, got {trend}"
        
        # Test weighted composite scoring
        current = {"temp": 25.0, "do": 4.0}
        baseline = {
            "temp": {"value": 25.0, "weight": 0.3, "direction": "deviation_bad"},
            "do": {"value": 8.0, "weight": 0.7, "direction": "low_bad"},
        }
        score, trend = calculate(current, baseline)
        assert score == 65.0, f"Weighted composite should be 65.0, got {score}"
        
        return True

    def test_generic_http_session8(self):
        """Test GenericHTTP: dot-notation path traversal, error handling"""
        from heartbeat.sources.generic_http import _traverse_path
        
        # Test dot-notation path traversal ($.a.b)
        data = {"a": {"b": 42}}
        result = _traverse_path(data, "$.a.b")
        assert result == 42, f"Expected 42, got {result}"
        
        # Test array index
        data = {"items": [{"name": "first"}, {"name": "second"}]}
        result = _traverse_path(data, "$.items.1.name")
        assert result == "second", f"Expected 'second', got {result}"
        
        # Test root path
        data = {"x": 1}
        result = _traverse_path(data, "$")
        assert result == data, f"Root path should return full data"
        
        # Test missing key returns None
        data = {"a": 1}
        result = _traverse_path(data, "$.b.c")
        assert result is None, f"Missing key should return None, got {result}"
        
        return True

    def test_existing_pytest_tests_session8(self):
        """Verify that all 50 existing pytest tests pass"""
        import subprocess
        
        try:
            # Run the existing tests
            result = subprocess.run([
                'python', '-m', 'pytest', 
                '/app/backend/heartbeat/tests/', 
                '-v', '--tb=short'
            ], 
            cwd='/app/backend',
            env={**os.environ, 'DATABASE_URL': 'postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents_test'},
            capture_output=True, 
            text=True, 
            timeout=60
            )
            
            if result.returncode == 0:
                # Count passed tests from output
                output_lines = result.stdout.split('\n')
                passed_count = 0
                for line in output_lines:
                    if 'PASSED' in line:
                        passed_count += 1
                
                self.log(f"   Existing pytest tests: {passed_count} passed")
                return passed_count == 50  # Expect exactly 50 tests
            else:
                self.log(f"   Pytest failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.log(f"   Error running pytest: {str(e)}")
            return False

    async def test_tool_loop_no_tool_calls(self):
        """Test tool loop exits with 'finished' when no tool calls"""
        mock_provider = MagicMock(spec=LLMProvider)
        resp = LLMResponse(text="Task completed!", tool_calls=[], raw_content=None, _provider="openai")
        mock_provider.create_message = AsyncMock(return_value=resp)
        
        with patch.object(LLMProvider, 'detect_provider', return_value="openai"):
            exit_reason, final = await tool_loop(
                provider=mock_provider,
                model="gpt-4o",
                system="Test system",
                messages=[],
                tools=[],
                handlers={},
                max_iterations=3
            )
        
        assert exit_reason == "finished"
        assert final.text == "Task completed!"
        return True

    async def test_tool_loop_unknown_tool(self):
        """Test tool loop handles unknown tools with error feedback"""
        mock_provider = MagicMock(spec=LLMProvider)
        
        # First response has unknown tool call
        resp1 = LLMResponse(
            text="",
            tool_calls=[ToolCall(id="call_1", name="unknown_tool", arguments={})],
            raw_content=MagicMock(),
            _provider="openai"
        )
        # Second response finishes
        resp2 = LLMResponse(text="I understand the error.", tool_calls=[], raw_content=None, _provider="openai")
        
        mock_provider.create_message = AsyncMock(side_effect=[resp1, resp2])
        mock_provider.build_tool_result_messages = MagicMock(return_value=[
            {"role": "assistant", "content": None, "tool_calls": []},
            {"role": "tool", "tool_call_id": "call_1", "content": "Unknown tool: 'unknown_tool'. Available: []"}
        ])
        
        with patch.object(LLMProvider, 'detect_provider', return_value="openai"):
            exit_reason, final = await tool_loop(
                provider=mock_provider,
                model="gpt-4o",
                system="Test system",
                messages=[],
                tools=[],
                handlers={},
                max_iterations=3
            )
        
        assert exit_reason == "finished"
        return True

    async def test_tool_loop_max_iterations(self):
        """Test tool loop returns 'max_iterations' when limit hit"""
        mock_provider = MagicMock(spec=LLMProvider)
        
        # Always return tool calls to hit max iterations
        resp = LLMResponse(
            text="",
            tool_calls=[ToolCall(id="call_1", name="search", arguments={})],
            raw_content=MagicMock(),
            _provider="openai"
        )
        mock_provider.create_message = AsyncMock(return_value=resp)
        mock_provider.build_tool_result_messages = MagicMock(return_value=[
            {"role": "assistant", "content": None, "tool_calls": []},
            {"role": "tool", "tool_call_id": "call_1", "content": "result"}
        ])
        
        async def mock_handler(args):
            return "search result"
        
        with patch.object(LLMProvider, 'detect_provider', return_value="openai"):
            exit_reason, final = await tool_loop(
                provider=mock_provider,
                model="gpt-4o",
                system="Test system",
                messages=[],
                tools=[],
                handlers={"search": mock_handler},
                max_iterations=2
            )
        
        assert exit_reason == "max_iterations"
        return True

    async def test_tool_loop_handler_exception(self):
        """Test tool loop catches handler exceptions and continues"""
        mock_provider = MagicMock(spec=LLMProvider)
        
        # First response has tool call that will fail
        resp1 = LLMResponse(
            text="",
            tool_calls=[ToolCall(id="call_1", name="failing_tool", arguments={})],
            raw_content=MagicMock(),
            _provider="openai"
        )
        # Second response finishes
        resp2 = LLMResponse(text="Handled the error.", tool_calls=[], raw_content=None, _provider="openai")
        
        mock_provider.create_message = AsyncMock(side_effect=[resp1, resp2])
        mock_provider.build_tool_result_messages = MagicMock(return_value=[
            {"role": "assistant", "content": None, "tool_calls": []},
            {"role": "tool", "tool_call_id": "call_1", "content": "Tool 'failing_tool' failed: Test error"}
        ])
        
        async def failing_handler(args):
            raise ValueError("Test error")
        
        with patch.object(LLMProvider, 'detect_provider', return_value="openai"):
            exit_reason, final = await tool_loop(
                provider=mock_provider,
                model="gpt-4o",
                system="Test system",
                messages=[],
                tools=[],
                handlers={"failing_tool": failing_handler},
                max_iterations=3
            )
        
        assert exit_reason == "finished"
        return True

    async def test_api_client_exponential_backoff(self):
        """Test API client exponential backoff on 5xx errors"""
        client = APIClient("http://test.example.com", "test-token")
        
        # Mock httpx client to simulate 5xx errors then success
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_response_500.text = "Internal Server Error"
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"success": True}
        
        with patch.object(client._client, 'request', AsyncMock(side_effect=[
            mock_response_500,  # First attempt fails
            mock_response_500,  # Second attempt fails
            mock_response_200   # Third attempt succeeds
        ])) as mock_request:
            
            start_time = time.time()
            result = await client._request("GET", "/test")
            end_time = time.time()
            
            # Should have made 3 requests
            assert mock_request.call_count == 3
            # Should have taken at least 3 seconds (1s + 2s backoff)
            assert end_time - start_time >= 3.0
            # Should return successful result
            assert result == {"success": True}
        
        await client.close()
        return True

    async def test_api_client_no_retry_4xx(self):
        """Test API client never retries 4xx errors"""
        client = APIClient("http://test.example.com", "test-token")
        
        # Mock httpx client to return 404
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404
        mock_response_404.text = "Not Found"
        
        with patch.object(client._client, 'request', AsyncMock(return_value=mock_response_404)) as mock_request:
            result = await client._request("GET", "/test")
            
            # Should have made only 1 request (no retries)
            assert mock_request.call_count == 1
            # Should return None for 4xx
            assert result is None
        
        await client.close()
        return True

    async def test_engine_admin_token_validation(self):
        """Test engine validates admin token on boot"""
        # Test with invalid token
        with patch.dict(os.environ, {
            'BACKEND_URL': 'http://localhost:8001',
            'ADMIN_TOKEN': 'invalid-token',
            'EMERGENT_LLM_KEY': 'sk-test-key'
        }):
            # Mock APIClient.validate_admin to return False
            with patch('heartbeat.engine.APIClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.validate_admin = AsyncMock(return_value=False)
                mock_client.close = AsyncMock()
                mock_client_class.return_value = mock_client
                
                # Engine should exit early due to invalid token
                await start_engine()
                
                # Verify admin validation was called
                mock_client.validate_admin.assert_called_once()
                mock_client.close.assert_called_once()
        
        return True

    async def test_engine_job_scheduling(self):
        """Test engine schedules jobs with max_instances=1 and coalesce=True"""
        with patch.dict(os.environ, {
            'BACKEND_URL': 'http://localhost:8001',
            'ADMIN_TOKEN': 'ua-admin-token-super-secret-change-me-32chars',
            'EMERGENT_LLM_KEY': 'sk-test-key'
        }):
            # Mock APIClient
            with patch('heartbeat.engine.APIClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.validate_admin = AsyncMock(return_value=True)
                mock_client.get_agents = AsyncMock(return_value=[
                    {"id": "orch1", "name": "Test Orchestrator", "type": "orchestrator"},
                    {"id": "worker1", "name": "Test Worker", "type": "worker", "community_id": "comm1"},
                    {"id": "earth1", "name": "Test Earth", "type": "earth"}
                ])
                mock_client.close = AsyncMock()
                mock_client_class.return_value = mock_client
                
                # Mock LLMProvider
                with patch('heartbeat.engine.LLMProvider') as mock_provider_class:
                    mock_provider = MagicMock()
                    mock_provider_class.return_value = mock_provider
                    
                    # Mock AsyncIOScheduler
                    with patch('heartbeat.engine.AsyncIOScheduler') as mock_scheduler_class:
                        mock_scheduler = MagicMock()
                        mock_scheduler.get_jobs.return_value = [MagicMock() for _ in range(5)]  # 3 agents + 2 maintenance
                        mock_scheduler_class.return_value = mock_scheduler
                        
                        # Mock signal handling and sleep to exit quickly
                        with patch('heartbeat.engine.signal'), \
                             patch('asyncio.sleep', side_effect=KeyboardInterrupt):
                            
                            try:
                                await start_engine()
                            except KeyboardInterrupt:
                                pass
                            
                            # Verify scheduler was configured correctly
                            assert mock_scheduler.add_job.call_count == 5  # 3 agents + 2 maintenance jobs
                            
                            # Check that jobs were added with correct parameters
                            for call in mock_scheduler.add_job.call_args_list:
                                kwargs = call.kwargs
                                assert kwargs.get('max_instances') == 1
                                assert kwargs.get('coalesce') is True
        
        return True

    def test_existing_pytest_tests(self):
        """Verify that all 13 existing pytest tests pass"""
        import subprocess
        
        try:
            # Run the existing tests
            result = subprocess.run([
                'python', '-m', 'pytest', 
                '/app/backend/heartbeat/tests/', 
                '-v', '--tb=short'
            ], 
            cwd='/app/backend',
            env={**os.environ, 'DATABASE_URL': 'postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents_test'},
            capture_output=True, 
            text=True, 
            timeout=30
            )
            
            if result.returncode == 0:
                # Count passed tests from output
                output_lines = result.stdout.split('\n')
                passed_count = 0
                for line in output_lines:
                    if 'PASSED' in line:
                        passed_count += 1
                
                self.log(f"   Existing pytest tests: {passed_count} passed")
                return passed_count >= 13
            else:
                self.log(f"   Pytest failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.log(f"   Error running pytest: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all Session 8 tests"""
        self.log("🚀 Starting United Agents Session 8 Backend Tests")
        
        # Session 8 specific tests
        self.run_test("Duplicate Task Detection", self.test_duplicate_task_detection)
        self.run_test("Tool Definitions (Session 8)", self.test_tool_definitions_session8)
        self.run_test("Tool Handlers (Session 8)", self.test_tool_handlers_session8)
        self.run_test("Condition Scorer (Session 8)", self.test_condition_scorer_session8)
        self.run_test("GenericHTTP Data Source (Session 8)", self.test_generic_http_session8)
        self.run_test("All 50 Pytest Tests Pass", self.test_existing_pytest_tests_session8)
        
        # Print results
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed ({success_rate:.1f}%)")
        
        if success_rate >= 90:
            self.log("✅ Session 8 backend tests successful")
            return 0
        else:
            self.log("❌ Session 8 backend tests had failures")
            return 1

async def main():
    tester = Session8BackendTester()
    return await tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))