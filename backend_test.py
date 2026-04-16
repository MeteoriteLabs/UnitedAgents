#!/usr/bin/env python3
"""
United Agents Session 9 Backend Testing
Tests: Orchestrator 5-stage cycle, Worker 3-phase cycle, Earth agent, Maintenance no-ops, all 65 pytest tests
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

class Session9BackendTester:
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

    def test_orchestrator_plan_triggers(self):
        """Test orchestrator plan trigger conditions"""
        from heartbeat.jobs.orchestrator import _check_plan_trigger
        
        # Test 1: no plan + >=3 evidence → trigger
        shared = {
            "plan": None, 
            "evidence": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
            "resolved_tasks": [], 
            "open_tasks": []
        }
        ok, reason = _check_plan_trigger(shared)
        assert ok is True, "Should trigger when no plan and >=3 evidence"
        assert "No plan exists" in reason, f"Reason should mention no plan, got: {reason}"
        
        # Test 2: plan exists + >=3 resolved → trigger
        shared = {
            "plan": {"id": "p1"}, 
            "evidence": [],
            "resolved_tasks": [{"id": "1"}, {"id": "2"}, {"id": "3"}], 
            "open_tasks": []
        }
        ok, reason = _check_plan_trigger(shared)
        assert ok is True, "Should trigger when plan exists and >=3 resolved tasks"
        assert "tasks resolved" in reason, f"Reason should mention resolved tasks, got: {reason}"
        
        # Test 3: contested evidence → trigger
        shared = {
            "plan": {"id": "p1"}, 
            "evidence": [{"contested": True}],
            "resolved_tasks": [], 
            "open_tasks": []
        }
        ok, reason = _check_plan_trigger(shared)
        assert ok is True, "Should trigger when contested evidence exists"
        assert "contested" in reason, f"Reason should mention contested evidence, got: {reason}"
        
        # Test 4: no conditions met → no trigger
        shared = {
            "plan": {"id": "p1"}, 
            "evidence": [{"contested": False}],
            "resolved_tasks": [], 
            "open_tasks": [{"id": "t1"}]
        }
        ok, reason = _check_plan_trigger(shared)
        assert ok is False, "Should not trigger when no conditions are met"
        
        return True

    def test_orchestrator_thread_progression(self):
        """Test orchestrator thread progression logic"""
        from heartbeat.jobs.orchestrator import _find_threads_needing_progression, PROGRESSION_THRESHOLDS
        
        # Test 1: sensing + 3 evidence → advance to investigating
        shared = {"threads": [
            {"id": "t1", "stage": "sensing", "evidence_count": 3, "post_count": 2}
        ]}
        result = _find_threads_needing_progression(shared)
        assert len(result) == 1, "Should find 1 thread needing progression"
        assert result[0]["action"] == "advance_stage", "Should advance stage"
        assert result[0]["target"] == "investigating", "Should advance to investigating"
        assert "3 evidence" in result[0]["reason"], "Reason should mention evidence count"
        
        # Test 2: investigating + 5 evidence → ask_for_proposals
        shared = {"threads": [
            {"id": "t1", "stage": "investigating", "evidence_count": 5, "post_count": 3}
        ]}
        result = _find_threads_needing_progression(shared)
        assert len(result) == 1, "Should find 1 thread needing progression"
        assert result[0]["action"] == "ask_for_proposals", "Should ask for proposals"
        assert "5 evidence" in result[0]["reason"], "Reason should mention evidence count"
        
        # Test 3: below threshold → no action
        shared = {"threads": [
            {"id": "t1", "stage": "sensing", "evidence_count": 1, "post_count": 1}
        ]}
        result = _find_threads_needing_progression(shared)
        assert len(result) == 0, "Should not find any threads needing progression"
        
        return True

    def test_progression_thresholds_exact_values(self):
        """Test progression thresholds match AGENT_SPEC §3.5 values exactly"""
        from heartbeat.jobs.orchestrator import PROGRESSION_THRESHOLDS
        
        # Verify exact values from AGENT_SPEC §3.5
        assert PROGRESSION_THRESHOLDS["evidence_for_investigating"] == 3, "evidence_for_investigating should be 3"
        assert PROGRESSION_THRESHOLDS["evidence_for_brainstorm"] == 5, "evidence_for_brainstorm should be 5"
        assert PROGRESSION_THRESHOLDS["resolved_for_brainstorm"] == 3, "resolved_for_brainstorm should be 3"
        assert PROGRESSION_THRESHOLDS["proposals_for_children"] == 2, "proposals_for_children should be 2"
        assert PROGRESSION_THRESHOLDS["discussion_for_threshold"] == 3, "discussion_for_threshold should be 3"
        assert PROGRESSION_THRESHOLDS["discussion_for_action_ready"] == 5, "discussion_for_action_ready should be 5"
        
        return True

    def test_orchestrator_voice_context(self):
        """Test voice context includes community name, scope, evidence, last voice"""
        from heartbeat.jobs.orchestrator import _build_voice_context
        
        shared = {
            "community": {"name": "Amazon River Basin", "scope": "South America water quality"},
            "evidence": [
                {"type": "data_point", "content": "Dissolved oxygen at 4.2 mg/L"},
                {"type": "measurement", "content": "Temperature 28.5°C"}
            ],
            "last_voice": {"content": "Previous voice update about water conditions"},
            "recent_posts": [
                {"type": "discussion", "title": "New water quality findings"},
                {"type": "research_note", "title": "Mercury levels detected"}
            ],
        }
        
        context = _build_voice_context(shared)
        
        # Verify all required elements are present
        assert "Amazon River Basin" in context, "Context should include community name"
        assert "South America water quality" in context, "Context should include scope"
        assert "Dissolved oxygen" in context, "Context should include evidence"
        assert "Previous voice update" in context, "Context should include last voice"
        assert "ECOSYSTEM:" in context, "Context should have ECOSYSTEM section"
        assert "SCOPE:" in context, "Context should have SCOPE section"
        assert "EVIDENCE:" in context, "Context should have EVIDENCE section"
        assert "LAST VOICE UPDATE:" in context, "Context should have LAST VOICE UPDATE section"
        
        return True

    def test_orchestrator_engage_context(self):
        """Test engage context includes worker contributions, evidence, plan"""
        from heartbeat.jobs.orchestrator import _build_engage_context
        
        shared = {
            "worker_contributions": [
                {
                    "id": "p1", 
                    "author_name": "Scout Alpha", 
                    "type": "research_note",
                    "title": "Water Quality Analysis", 
                    "content": "Found elevated mercury levels in upstream samples"
                },
                {
                    "id": "p2", 
                    "author_name": "Scout Beta", 
                    "type": "field_report",
                    "title": "Temperature Monitoring", 
                    "content": "Recorded temperature anomalies near industrial discharge"
                }
            ],
            "evidence": [
                {"type": "data_point", "content": "Mercury concentration 0.8 mg/L"},
                {"type": "measurement", "content": "Temperature spike to 32°C"}
            ],
            "plan": {"content": "Focus investigation on water quality parameters and industrial impact"},
        }
        
        context = _build_engage_context(shared)
        
        # Verify all required elements are present
        assert "Scout Alpha" in context, "Context should include worker names"
        assert "Scout Beta" in context, "Context should include all workers"
        assert "mercury levels" in context, "Context should include worker contributions"
        assert "Mercury concentration" in context, "Context should include evidence"
        assert "water quality parameters" in context, "Context should include plan"
        assert "WORKER CONTRIBUTIONS" in context, "Context should have worker contributions section"
        assert "EXISTING EVIDENCE" in context, "Context should have evidence section"
        assert "PLAN PRIORITIES" in context, "Context should have plan section"
        
        return True

    def test_orchestrator_work_context(self):
        """Test work context includes threads, open tasks, plan, evidence"""
        from heartbeat.jobs.orchestrator import _build_work_context
        
        shared = {
            "community": {"name": "Coral Reef Ecosystem", "scope": "Pacific Ocean monitoring"},
            "threads": [
                {
                    "title": "Coral Bleaching Investigation", 
                    "stage": "investigating",
                    "evidence_count": 7, 
                    "open_task_count": 2
                },
                {
                    "title": "Temperature Monitoring", 
                    "stage": "sensing",
                    "evidence_count": 3, 
                    "open_task_count": 1
                }
            ],
            "open_tasks": [
                {"title": "Verify sea surface temperature readings"},
                {"title": "Collect coral health samples"}
            ],
            "plan": {"content": "Monitor coral bleaching events and temperature anomalies"},
            "evidence": [
                {"type": "measurement", "content": "SST recorded at 29.5°C"},
                {"type": "observation", "content": "Coral bleaching observed in sector 3"}
            ],
        }
        
        context = _build_work_context(shared)
        
        # Verify all required elements are present
        assert "Coral Reef Ecosystem" in context, "Context should include community name"
        assert "Pacific Ocean monitoring" in context, "Context should include scope"
        assert "Coral Bleaching Investigation" in context, "Context should include threads"
        assert "investigating" in context, "Context should include thread stages"
        assert "Verify sea surface temperature" in context, "Context should include open tasks"
        assert "coral bleaching events" in context, "Context should include plan"
        assert "SST recorded" in context, "Context should include evidence"
        assert "ECOSYSTEM:" in context, "Context should have ecosystem section"
        assert "THREADS:" in context, "Context should have threads section"
        assert "OPEN TASKS" in context, "Context should have open tasks section"
        
        return True

    def test_worker_evidence_json_parsing(self):
        """Test worker evidence JSON block parsing from ```json``` fenced block"""
        from heartbeat.jobs.worker import _parse_evidence_block
        
        # Test JSON block parsing
        text_with_json = """Research findings indicate elevated mercury levels.
The data shows concerning trends in water quality.

```json
{"ev_type": "data_point", "ev_summary": "Mercury concentration at 0.8 mg/L exceeds safe limits"}
```"""
        
        ev_type, ev_summary = _parse_evidence_block(text_with_json)
        assert ev_type == "data_point", f"Expected 'data_point', got '{ev_type}'"
        assert "Mercury concentration" in ev_summary, f"Summary should contain mercury data, got: {ev_summary}"
        assert "0.8 mg/L" in ev_summary, f"Summary should contain specific measurement, got: {ev_summary}"
        
        return True

    def test_worker_evidence_fallback_parsing(self):
        """Test worker evidence fallback when no JSON block (type=research, first sentence)"""
        from heartbeat.jobs.worker import _parse_evidence_block
        
        # Test fallback parsing without JSON block
        text_without_json = "The temperature measurements show a significant increase. This could indicate thermal pollution from industrial sources. Further investigation is needed."
        
        ev_type, ev_summary = _parse_evidence_block(text_without_json)
        assert ev_type == "research", f"Expected 'research' fallback type, got '{ev_type}'"
        assert "temperature measurements" in ev_summary, f"Summary should contain first sentence content, got: {ev_summary}"
        assert ev_summary.endswith("."), f"Summary should end with period, got: {ev_summary}"
        
        return True

    async def test_maintenance_no_ops(self):
        """Test maintenance functions run without error (no-op)"""
        from heartbeat.jobs.maintenance import task_timeout_check, compute_urgency_scores
        
        # Test task_timeout_check runs without error
        try:
            await task_timeout_check()
            timeout_success = True
        except Exception as e:
            self.log(f"task_timeout_check failed: {e}")
            timeout_success = False
        
        # Test compute_urgency_scores runs without error
        try:
            await compute_urgency_scores()
            urgency_success = True
        except Exception as e:
            self.log(f"compute_urgency_scores failed: {e}")
            urgency_success = False
        
        assert timeout_success, "task_timeout_check should run without error"
        assert urgency_success, "compute_urgency_scores should run without error"
        
        return True

    def test_all_65_pytest_tests_pass(self):
        """Verify that all 65 pytest tests pass in heartbeat/tests/"""
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
                return passed_count == 65  # Expect exactly 65 tests
            else:
                self.log(f"   Pytest failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.log(f"   Error running pytest: {str(e)}")
            return False

    def test_thread_progression_disabled_by_default(self):
        """Test that thread progression is disabled by default (D-9)"""
        from heartbeat.jobs.orchestrator import THREAD_PROGRESSION_ENABLED
        
        assert THREAD_PROGRESSION_ENABLED is False, "Thread progression should be disabled by default per D-9"
        
        return True

    def test_orchestrator_5_stage_cycle_structure(self):
        """Test that orchestrator has proper 5-stage cycle structure"""
        from heartbeat.jobs.orchestrator import orchestrator_heartbeat
        import inspect
        
        # Get the source code to verify stage structure
        source = inspect.getsource(orchestrator_heartbeat)
        
        # Verify all 5 stages are present
        assert "Stage 1: VOICE" in source, "Should have Stage 1: VOICE"
        assert "Stage 2: ENGAGE" in source, "Should have Stage 2: ENGAGE"
        assert "Stage 3: PLAN" in source, "Should have Stage 3: PLAN"
        assert "Stage 3.5: THREAD MGMT" in source, "Should have Stage 3.5: THREAD MGMT"
        assert "Stage 4: CREATE WORK" in source, "Should have Stage 4: CREATE WORK"
        
        # Verify conditional execution
        assert "conditional" in source, "Stages should have conditional execution"
        assert "THREAD_PROGRESSION_ENABLED" in source, "Thread management should check enabled flag"
        
        return True

    def test_worker_3_phase_cycle_structure(self):
        """Test that worker has proper 3-phase cycle structure"""
        from heartbeat.jobs.worker import worker_heartbeat
        import inspect
        
        # Get the source code to verify phase structure
        source = inspect.getsource(worker_heartbeat)
        
        # Verify all 3 phases are present
        assert "Phase 1: NOTIFICATIONS" in source, "Should have Phase 1: NOTIFICATIONS"
        assert "Phase 2: TASK WORK" in source, "Should have Phase 2: TASK WORK"
        assert "Phase 3: DEBRIEF" in source, "Should have Phase 3: DEBRIEF"
        
        return True

    def test_earth_agent_10_iteration_cap(self):
        """Test that earth agent has 10-iteration cap"""
        from heartbeat.jobs.earth_agent import earth_heartbeat
        import inspect
        
        # Get the source code to verify iteration cap
        source = inspect.getsource(earth_heartbeat)
        
        # Verify 10-iteration cap is set
        assert "max_iterations=10" in source, "Earth agent should have 10-iteration cap"
        
        return True

    async def run_all_tests(self):
        """Run all Session 9 tests"""
        self.log("🚀 Starting United Agents Session 9 Backend Tests")
        
        # Session 9 specific tests - Orchestrator
        self.run_test("Orchestrator Plan Triggers", self.test_orchestrator_plan_triggers)
        self.run_test("Orchestrator Thread Progression", self.test_orchestrator_thread_progression)
        self.run_test("Progression Thresholds Exact Values", self.test_progression_thresholds_exact_values)
        self.run_test("Orchestrator Voice Context", self.test_orchestrator_voice_context)
        self.run_test("Orchestrator Engage Context", self.test_orchestrator_engage_context)
        self.run_test("Orchestrator Work Context", self.test_orchestrator_work_context)
        self.run_test("Orchestrator 5-Stage Cycle Structure", self.test_orchestrator_5_stage_cycle_structure)
        
        # Session 9 specific tests - Worker
        self.run_test("Worker Evidence JSON Parsing", self.test_worker_evidence_json_parsing)
        self.run_test("Worker Evidence Fallback Parsing", self.test_worker_evidence_fallback_parsing)
        self.run_test("Worker 3-Phase Cycle Structure", self.test_worker_3_phase_cycle_structure)
        
        # Session 9 specific tests - Earth Agent
        self.run_test("Earth Agent 10-Iteration Cap", self.test_earth_agent_10_iteration_cap)
        
        # Session 9 specific tests - Maintenance
        await self.run_async_test("Maintenance No-Ops", self.test_maintenance_no_ops)
        
        # Session 9 specific tests - Configuration
        self.run_test("Thread Progression Disabled by Default", self.test_thread_progression_disabled_by_default)
        
        # All pytest tests
        self.run_test("All 65 Pytest Tests Pass", self.test_all_65_pytest_tests_pass)
        
        # Print results
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed ({success_rate:.1f}%)")
        
        if success_rate >= 90:
            self.log("✅ Session 9 backend tests successful")
            return 0
        else:
            self.log("❌ Session 9 backend tests had failures")
            return 1

async def main():
    tester = Session9BackendTester()
    return await tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))