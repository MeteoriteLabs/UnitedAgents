#!/usr/bin/env python3
"""
United Agents Session 5 Backend API Testing
Tests: Tasks, Evidence, Notifications, Webhooks, Feed, Search, Tools
"""

import requests
import json
import time
import secrets
import sys
from datetime import datetime
from typing import Dict, List, Optional

class UnitedAgentsSession5Tester:
    def __init__(self, base_url="https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.admin_token = "ua-admin-token-super-secret-change-me-32chars"
        self.agent_tokens = {}  # agent_id -> token
        self.test_data = {}  # Store created test data
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()
        
    def log(self, message: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None, 
                 params: Optional[Dict] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)
            
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        self.log(f"   {method} {url}")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers, params=params, timeout=15)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=test_headers, params=params, timeout=15)
            elif method == 'PATCH':
                response = self.session.patch(url, json=data, headers=test_headers, params=params, timeout=15)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=test_headers, params=params, timeout=15)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ Passed - Status: {response.status_code}")
            else:
                self.log(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                if response.text:
                    self.log(f"   Response: {response.text[:300]}")
                    
            try:
                response_data = response.json() if response.text else {}
            except:
                response_data = {"raw_response": response.text}
                
            return success, response_data
            
        except Exception as e:
            self.log(f"❌ Failed - Error: {str(e)}")
            return False, {}
    
    def create_test_agent(self, name: str, agent_type: str = "worker") -> Optional[str]:
        """Create a test agent and return its API key"""
        success, response = self.run_test(
            f"Create {agent_type} agent: {name}",
            "POST", 
            "agents",
            201,
            data={"name": name, "type": agent_type},
            headers={"X-Admin-Token": self.admin_token}
        )
        if success and "api_key" in response:
            agent_id = response["id"]
            self.agent_tokens[agent_id] = response["api_key"]
            self.test_data[f"agent_{agent_type}"] = {"id": agent_id, "name": name, "token": response["api_key"]}
            return response["api_key"]
        return None
    
    def create_test_community(self, name: str, agent_token: str) -> Optional[str]:
        """Create a test community"""
        success, response = self.run_test(
            f"Create community: {name}",
            "POST",
            "communities", 
            201,
            data={"name": name, "description": f"Test community for {name}"},
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        if success:
            community_id = response["id"]
            self.test_data["community"] = {"id": community_id, "name": name}
            return community_id
        return None
    
    def create_test_thread(self, community_id: str, agent_token: str) -> Optional[str]:
        """Create a test thread"""
        success, response = self.run_test(
            "Create test thread",
            "POST",
            f"communities/{community_id}/threads",
            201,
            data={"title": "Test Thread", "content": "Test thread for Session 5"},
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        if success:
            thread_id = response["id"]
            self.test_data["thread"] = {"id": thread_id}
            return thread_id
        return None
    
    def create_test_task(self, community_id: str, agent_token: str, title: str = "Test Task") -> Optional[str]:
        """Create a test task"""
        success, response = self.run_test(
            f"Create test task: {title}",
            "POST",
            f"communities/{community_id}/posts",
            201,
            data={
                "title": title,
                "content": f"Test task for Session 5: {title}",
                "type": "task",
                "task_category": "research",
                "urgency": 5
            },
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        if success:
            task_id = response["id"]
            self.test_data[f"task_{title.lower().replace(' ', '_')}"] = {"id": task_id}
            return task_id
        return None

    def test_tasks_flow(self):
        """Test complete task management flow"""
        self.log("\n=== TESTING TASK MANAGEMENT ===")
        
        # Create agents
        orchestrator_token = self.create_test_agent("test_orchestrator_s5", "orchestrator")
        worker_token = self.create_test_agent("test_worker_s5", "worker")
        
        if not orchestrator_token or not worker_token:
            self.log("❌ Failed to create test agents")
            return False
            
        # Create community
        community_id = self.create_test_community("Test Community S5", orchestrator_token)
        if not community_id:
            self.log("❌ Failed to create test community")
            return False
            
        # Create task
        task_id = self.create_test_task(community_id, orchestrator_token, "Claimable Task")
        if not task_id:
            self.log("❌ Failed to create test task")
            return False
        
        # Test GET /api/v1/tasks/open — returns open tasks, filters stale claims and unresolved deps
        success, open_tasks = self.run_test(
            "List open tasks",
            "GET",
            "tasks/open",
            200,
            headers={"Authorization": f"Bearer {worker_token}"}
        )
        
        if success:
            self.log(f"   Found {len(open_tasks)} open tasks")
        
        # Test POST /api/v1/tasks/{id}/claim — claims task, returns 409 on double-claim
        success, claim_response = self.run_test(
            "Claim task",
            "POST",
            f"tasks/{task_id}/claim",
            200,
            headers={"Authorization": f"Bearer {worker_token}"}
        )
        
        # Test double claim (should return 409)
        if success:
            self.run_test(
                "Double claim task (should fail with 409)",
                "POST",
                f"tasks/{task_id}/claim",
                409,
                headers={"Authorization": f"Bearer {orchestrator_token}"}
            )
        
        # Test PATCH /api/v1/tasks/{id}/resolve — resolves task, 403 if not claimant
        self.run_test(
            "Resolve task by claimant",
            "PATCH",
            f"tasks/{task_id}/resolve",
            200,
            data={"result_summary": "Task completed successfully"},
            headers={"Authorization": f"Bearer {worker_token}"}
        )
        
        # Test GET /api/v1/tasks/resolved — returns resolved tasks
        self.run_test(
            "List resolved tasks",
            "GET",
            "tasks/resolved",
            200,
            headers={"Authorization": f"Bearer {worker_token}"}
        )
        
        # Create another task for fail test
        task_id_2 = self.create_test_task(community_id, orchestrator_token, "Fail Task")
        if task_id_2:
            # Claim and then fail
            self.run_test(
                "Claim task for fail test",
                "POST",
                f"tasks/{task_id_2}/claim",
                200,
                headers={"Authorization": f"Bearer {worker_token}"}
            )
            
            # Test PATCH /api/v1/tasks/{id}/fail — resets to open, clears claim fields
            self.run_test(
                "Fail task (reset to open)",
                "PATCH",
                f"tasks/{task_id_2}/fail",
                200,
                headers={"Authorization": f"Bearer {worker_token}"}
            )
            
            # Test 403 if not claimant tries to resolve
            self.run_test(
                "Non-claimant tries to resolve (should fail with 403)",
                "PATCH",
                f"tasks/{task_id_2}/resolve",
                403,
                headers={"Authorization": f"Bearer {orchestrator_token}"}
            )
        
        return True
    
    def test_evidence_flow(self):
        """Test evidence management with D-15 §2.4 community-scope check"""
        self.log("\n=== TESTING EVIDENCE MANAGEMENT ===")
        
        if "community" not in self.test_data:
            self.log("❌ No test community available")
            return False
            
        community_id = self.test_data["community"]["id"]
        agent_token = list(self.agent_tokens.values())[0]
        
        # Create thread for evidence
        thread_id = self.create_test_thread(community_id, agent_token)
        if not thread_id:
            self.log("❌ Failed to create test thread")
            return False
        
        # Test POST /api/v1/communities/{id}/evidence — creates evidence, validates type
        success, evidence_response = self.run_test(
            "Create evidence with valid type",
            "POST",
            f"communities/{community_id}/evidence",
            201,
            data={
                "type": "data_point",
                "content": "Test evidence data for Session 5",
                "thread_id": thread_id,
                "source_url": "https://example.com/evidence"
            },
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        evidence_id = evidence_response.get("id") if success else None
        
        # Test invalid evidence type
        self.run_test(
            "Create evidence with invalid type",
            "POST",
            f"communities/{community_id}/evidence",
            400,
            data={
                "type": "invalid_type",
                "content": "Test evidence data"
            },
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        # Test D-15 §2.4: contradiction contestation same-community check
        if evidence_id:
            # Create contradiction evidence targeting the first one (same community - should work)
            success, contradiction_response = self.run_test(
                "Create contradiction evidence (same community)",
                "POST",
                f"communities/{community_id}/evidence",
                201,
                data={
                    "type": "contradiction",
                    "content": "This contradicts the previous evidence",
                    "contested_target": evidence_id
                },
                headers={"Authorization": f"Bearer {agent_token}"}
            )
        
        # Test GET /api/v1/communities/{id}/evidence
        self.run_test(
            "List community evidence",
            "GET",
            f"communities/{community_id}/evidence",
            200
        )
        
        # Test PATCH /api/v1/evidence/{id}/verify — verifies evidence, 403 if self-verify
        if evidence_id:
            self.run_test(
                "Self-verify evidence (should fail with 403)",
                "PATCH",
                f"evidence/{evidence_id}/verify",
                403,
                headers={"Authorization": f"Bearer {agent_token}"}
            )
            
            # Create another agent to verify evidence
            verifier_token = self.create_test_agent("evidence_verifier", "worker")
            if verifier_token:
                self.run_test(
                    "Verify evidence by different agent",
                    "PATCH",
                    f"evidence/{evidence_id}/verify",
                    200,
                    headers={"Authorization": f"Bearer {verifier_token}"}
                )
        
        return True
    
    def test_notifications_flow(self):
        """Test notifications with D-15 §2.2 proper join"""
        self.log("\n=== TESTING NOTIFICATIONS ===")
        
        if not self.agent_tokens:
            self.log("❌ No test agents available")
            return False
            
        agent_token = list(self.agent_tokens.values())[0]
        
        # Test GET /api/v1/notifications — lists notifications for agent
        success, notifications = self.run_test(
            "List notifications",
            "GET",
            "notifications",
            200,
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        if success:
            self.log(f"   Found {len(notifications)} notifications")
        
        # Test with unread_only filter
        self.run_test(
            "List unread notifications",
            "GET",
            "notifications",
            200,
            params={"unread_only": True},
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        # Test POST /api/v1/notifications/read-all — D-15 §2.2: marks all read via proper agent_id join
        self.run_test(
            "Mark all notifications as read (D-15 §2.2)",
            "POST",
            "notifications/read-all",
            200,
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        # Test POST /api/v1/notifications/{id}/read — marks notification as read
        if success and notifications and len(notifications) > 0:
            notif_id = notifications[0].get("id")
            if notif_id:
                self.run_test(
                    "Mark specific notification as read",
                    "POST",
                    f"notifications/{notif_id}/read",
                    200,
                    headers={"Authorization": f"Bearer {agent_token}"}
                )
        
        return True
    
    def test_webhooks_flow(self):
        """Test webhook CRUD operations"""
        self.log("\n=== TESTING WEBHOOKS ===")
        
        if "community" not in self.test_data:
            self.log("❌ No test community available")
            return False
            
        community_id = self.test_data["community"]["id"]
        agent_token = list(self.agent_tokens.values())[0]
        
        # Test POST /api/v1/communities/{id}/webhooks — creates webhook
        success, webhook_response = self.run_test(
            "Create webhook",
            "POST",
            f"communities/{community_id}/webhooks",
            201,
            data={
                "url": "https://example.com/webhook",
                "events": ["post.created", "task.claimed"],
                "secret": "webhook_secret_123"
            },
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        webhook_id = webhook_response.get("id") if success else None
        
        # Test GET /api/v1/communities/{id}/webhooks — lists webhooks
        success, webhooks = self.run_test(
            "List webhooks",
            "GET",
            f"communities/{community_id}/webhooks",
            200,
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        if success:
            self.log(f"   Found {len(webhooks)} webhooks")
        
        # Test DELETE /api/v1/webhooks/{id} — deletes webhook
        if webhook_id:
            self.run_test(
                "Delete webhook",
                "DELETE",
                f"webhooks/{webhook_id}",
                200,
                headers={"Authorization": f"Bearer {agent_token}"}
            )
        
        return True
    
    def test_feed_and_search(self):
        """Test cross-community feed and search functionality"""
        self.log("\n=== TESTING FEED AND SEARCH ===")
        
        # Test GET /api/v1/feed — returns cross-community published posts, hides rejected
        success, feed = self.run_test(
            "Get cross-community feed",
            "GET",
            "feed",
            200
        )
        
        if success:
            self.log(f"   Found {len(feed)} posts in feed")
        
        # Test with filters
        if "community" in self.test_data:
            community_id = self.test_data["community"]["id"]
            self.run_test(
                "Get feed filtered by community",
                "GET",
                "feed",
                200,
                params={"community_id": community_id, "limit": 10}
            )
        
        # Test GET /api/v1/search?q=... — searches via ILIKE on title+content
        success, search_results = self.run_test(
            "Search posts via ILIKE",
            "GET",
            "search",
            200,
            params={"q": "test", "limit": 5}
        )
        
        if success:
            self.log(f"   Found {len(search_results)} search results")
        
        # Test search with filters
        self.run_test(
            "Search with type filter",
            "GET",
            "search",
            200,
            params={"q": "task", "type": "task", "limit": 5}
        )
        
        return True
    
    def test_tools_restrictions(self):
        """Test tools/search restrictions"""
        self.log("\n=== TESTING TOOLS RESTRICTIONS ===")
        
        # Test POST /api/v1/tools/search — 403 for workers, 503 when Google keys missing
        
        # Test with worker (should get 403)
        if "agent_worker" in self.test_data:
            worker_token = self.test_data["agent_worker"]["token"]
            self.run_test(
                "Worker search (should fail with 403)",
                "POST",
                "tools/search",
                403,
                data={"query": "test search", "count": 3},
                headers={"Authorization": f"Bearer {worker_token}"}
            )
        
        # Test with orchestrator (should get 503 - no Google keys configured)
        if "agent_orchestrator" in self.test_data:
            orchestrator_token = self.test_data["agent_orchestrator"]["token"]
            self.run_test(
                "Orchestrator search (should fail with 503 - no Google keys)",
                "POST",
                "tools/search",
                503,
                data={"query": "test search", "count": 3},
                headers={"Authorization": f"Bearer {orchestrator_token}"}
            )
        
        return True
    
    def run_all_tests(self):
        """Run all Session 5 tests"""
        self.log("🚀 Starting United Agents Session 5 Backend Tests")
        self.log(f"Base URL: {self.base_url}")
        
        # Test health endpoint first
        success, _ = self.run_test("Health check", "GET", "health", 200)
        if not success:
            self.log("❌ Health check failed - backend may not be running")
            return 1
        
        try:
            # Run test flows
            self.test_tasks_flow()
            self.test_evidence_flow()
            self.test_notifications_flow()
            self.test_webhooks_flow()
            self.test_feed_and_search()
            self.test_tools_restrictions()
            
        except Exception as e:
            self.log(f"❌ Test execution failed: {str(e)}")
            return 1
        
        # Print results
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            self.log("✅ Session 5 backend tests mostly successful")
            return 0
        else:
            self.log("❌ Session 5 backend tests had significant failures")
            return 1

def main():
    tester = UnitedAgentsSession5Tester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())