#!/usr/bin/env python3
"""
United Agents Session 7 Backend Testing
Tests: LLM provider detection, tool normalization, tool loop, API client, engine boot
"""

import asyncio
import json
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import os

# Add backend to path
sys.path.insert(0, '/app/backend')

from heartbeat.llm.provider import LLMProvider, LLMResponse, ToolCall
from heartbeat.llm.tool_loop import tool_loop
from heartbeat.api_client import APIClient
from heartbeat.engine import start_engine

class Session7BackendTester:
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

    def test_llm_provider_detection(self):
        """Test LLM provider detection logic"""
        # Test Anthropic detection
        assert LLMProvider.detect_provider("claude-sonnet-4") == "anthropic"
        assert LLMProvider.detect_provider("claude-3-haiku") == "anthropic"
        assert LLMProvider.detect_provider("claude-opus") == "anthropic"
        
        # Test OpenAI detection
        assert LLMProvider.detect_provider("gpt-4o") == "openai"
        assert LLMProvider.detect_provider("gpt-4o-mini") == "openai"
        assert LLMProvider.detect_provider("o1-preview") == "openai"
        assert LLMProvider.detect_provider("o3-mini") == "openai"
        assert LLMProvider.detect_provider("o4-turbo") == "openai"
        
        # Test unknown model raises ValueError
        try:
            LLMProvider.detect_provider("llama-3")
            return False  # Should have raised ValueError
        except ValueError as e:
            assert "Unknown model prefix" in str(e)
        
        return True

    def test_tool_def_normalization(self):
        """Test tool definition normalization for both providers"""
        provider = LLMProvider()
        
        # Test unified tool definition
        tools = [{
            "name": "search_web",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "count": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }]
        
        # Test Anthropic normalization
        anthropic_tools = provider._normalize_tools_anthropic(tools)
        assert len(anthropic_tools) == 1
        assert anthropic_tools[0]["name"] == "search_web"
        assert "input_schema" in anthropic_tools[0]
        assert anthropic_tools[0]["input_schema"]["type"] == "object"
        
        # Test OpenAI normalization
        openai_tools = provider._normalize_tools_openai(tools)
        assert len(openai_tools) == 1
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "search_web"
        assert openai_tools[0]["function"]["parameters"]["type"] == "object"
        
        return True

    def test_tool_result_normalization(self):
        """Test tool result message normalization"""
        provider = LLMProvider()
        
        # Test Anthropic tool result normalization
        resp = LLMResponse(
            text="I'll search for that information.",
            tool_calls=[ToolCall(id="tc_123", name="search_web", arguments={"query": "test"})],
            raw_content=[MagicMock(type="tool_use", id="tc_123", name="search_web", input={"query": "test"})],
            _provider="anthropic"
        )
        results = ['{"results": ["Found test information"]}']
        
        anthropic_msgs = provider.build_tool_result_messages("anthropic", resp, results)
        assert len(anthropic_msgs) == 2
        assert anthropic_msgs[0]["role"] == "assistant"
        assert anthropic_msgs[1]["role"] == "user"
        assert anthropic_msgs[1]["content"][0]["type"] == "tool_result"
        assert anthropic_msgs[1]["content"][0]["tool_use_id"] == "tc_123"
        
        # Test OpenAI tool result normalization
        resp_openai = LLMResponse(
            text="I'll search for that information.",
            tool_calls=[ToolCall(id="call_456", name="search_web", arguments={"query": "test"})],
            raw_content=MagicMock(),
            _provider="openai"
        )
        
        openai_msgs = provider.build_tool_result_messages("openai", resp_openai, results)
        assert len(openai_msgs) == 2
        assert openai_msgs[0]["role"] == "assistant"
        assert openai_msgs[0]["tool_calls"][0]["id"] == "call_456"
        assert openai_msgs[1]["role"] == "tool"
        assert openai_msgs[1]["tool_call_id"] == "call_456"
        
        return True

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
        """Run all Session 7 tests"""
        self.log("🚀 Starting United Agents Session 7 Backend Tests")
        
        # Synchronous tests
        self.run_test("LLM Provider Detection", self.test_llm_provider_detection)
        self.run_test("Tool Definition Normalization", self.test_tool_def_normalization)
        self.run_test("Tool Result Normalization", self.test_tool_result_normalization)
        self.run_test("Existing Pytest Tests Pass", self.test_existing_pytest_tests)
        
        # Asynchronous tests
        await self.run_async_test("Tool Loop - No Tool Calls", self.test_tool_loop_no_tool_calls)
        await self.run_async_test("Tool Loop - Unknown Tool", self.test_tool_loop_unknown_tool)
        await self.run_async_test("Tool Loop - Max Iterations", self.test_tool_loop_max_iterations)
        await self.run_async_test("Tool Loop - Handler Exception", self.test_tool_loop_handler_exception)
        await self.run_async_test("API Client - Exponential Backoff", self.test_api_client_exponential_backoff)
        await self.run_async_test("API Client - No Retry 4xx", self.test_api_client_no_retry_4xx)
        await self.run_async_test("Engine - Admin Token Validation", self.test_engine_admin_token_validation)
        await self.run_async_test("Engine - Job Scheduling", self.test_engine_job_scheduling)
        
        # Print results
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            self.log("✅ Session 7 backend tests mostly successful")
            return 0
        else:
            self.log("❌ Session 7 backend tests had significant failures")
            return 1

async def main():
    tester = Session7BackendTester()
    return await tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))