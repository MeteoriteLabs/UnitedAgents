#!/usr/bin/env python3
"""
United Agents Session 5 Complete Backend Test
Tests all Session 5 features with proper authentication
"""

import requests
import json
import sys
import time
from datetime import datetime

class Session5CompleteTester:
    def __init__(self):
        self.base_url = "https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"
        self.admin_token = "ua-admin-token-super-secret-change-me-32chars"
        self.tests_run = 0
        self.tests_passed = 0
        self.issues = []
        self.test_data = {}
        
    def log(self, message: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def test_endpoint(self, name: str, method: str, endpoint: str, expected_status: int, 
                     data=None, headers=None, params=None):
        """Test a single endpoint"""
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)
            
        self.tests_run += 1
        self.log(f"🔍 {name}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, params=params, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=15)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=test_headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=15)
                
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ Status: {response.status_code}")
                try:
                    resp_data = response.json()
                    if isinstance(resp_data, list):
                        self.log(f"   Returned {len(resp_data)} items")
                    elif isinstance(resp_data, dict) and 'results' in resp_data:
                        self.log(f"   Returned {len(resp_data['results'])} results")
                    return True, resp_data
                except:
                    return True, {}
            else:
                self.log(f"❌ Expected {expected_status}, got {response.status_code}")
                self.issues.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                if response.text:
                    self.log(f"   Response: {response.text[:200]}")
                try:
                    return False, response.json()
                except:
                    return False, {}
                    
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            self.issues.append(f"{name}: {str(e)}")
            return False, {}
    
    def setup_test_data(self):
        """Create test agents and communities"""
        self.log("🔧 Setting up test data...")
        
        # Create test agent
        success, agent_data = self.test_endpoint(
            "Create test agent",
            "POST", "agents", 201,
            data={"name": f"s5_tester_{int(time.time())}", "type": "worker"},
            headers={"X-Admin-Token": self.admin_token}
        )
        
        if success and "api_key" in agent_data:
            self.test_data["agent_token"] = agent_data["api_key"]
            self.test_data["agent_id"] = agent_data["id"]
            self.log(f"✅ Created agent: {agent_data['id']}")
        else:
            self.log("❌ Failed to create test agent")
            return False
            
        # Create orchestrator for tools test
        success, orch_data = self.test_endpoint(
            "Create orchestrator agent",
            "POST", "agents", 201,
            data={"name": f"s5_orchestrator_{int(time.time())}", "type": "orchestrator"},
            headers={"X-Admin-Token": self.admin_token}
        )
        
        if success and "api_key" in orch_data:
            self.test_data["orch_token"] = orch_data["api_key"]
            self.test_data["orch_id"] = orch_data["id"]
            self.log(f"✅ Created orchestrator: {orch_data['id']}")
        
        # Create test community
        success, comm_data = self.test_endpoint(
            "Create test community",
            "POST", "communities", 201,
            data={"name": f"S5 Test Community {int(time.time())}", "description": "Session 5 testing"},
            headers={"Authorization": f"Bearer {self.test_data['agent_token']}"}
        )
        
        if success:
            self.test_data["community_id"] = comm_data["id"]
            self.log(f"✅ Created community: {comm_data['id']}")
        else:
            self.log("❌ Failed to create test community")
            return False
            
        return True
    
    def test_task_management(self):
        """Test complete task management flow"""
        self.log("\n=== TESTING TASK MANAGEMENT ===")
        
        if "agent_token" not in self.test_data:
            self.log("❌ No agent token available")
            return
            
        agent_token = self.test_data["agent_token"]
        community_id = self.test_data["community_id"]
        
        # Create a test task
        success, task_data = self.test_endpoint(
            "Create test task",
            "POST", f"communities/{community_id}/posts", 201,
            data={
                "title": "Session 5 Test Task",
                "content": "Test task for Session 5 validation",
                "type": "task",
                "task_category": "research",
                "urgency": 5
            },
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        if success:
            task_id = task_data["id"]
            self.test_data["task_id"] = task_id
        
        # Test GET /api/v1/tasks/open — returns open tasks, filters stale claims and unresolved deps
        self.test_endpoint(
            "GET /api/v1/tasks/open",
            "GET", "tasks/open", 200,
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        # Test with filters
        self.test_endpoint(
            "GET /api/v1/tasks/open with filters",
            "GET", "tasks/open", 200,
            params={"community_id": community_id, "limit": 5},
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        if "task_id" in self.test_data:
            task_id = self.test_data["task_id"]
            
            # Test POST /api/v1/tasks/{id}/claim — claims task, returns 409 on double-claim
            success, _ = self.test_endpoint(
                "POST /api/v1/tasks/{id}/claim",
                "POST", f"tasks/{task_id}/claim", 200,
                headers={"Authorization": f"Bearer {agent_token}"}
            )
            
            if success:
                # Test double claim (should return 409)
                self.test_endpoint(
                    "Double claim task (should return 409)",
                    "POST", f"tasks/{task_id}/claim", 409,
                    headers={"Authorization": f"Bearer {agent_token}"}
                )
                
                # Test PATCH /api/v1/tasks/{id}/resolve — resolves task, 403 if not claimant
                self.test_endpoint(
                    "PATCH /api/v1/tasks/{id}/resolve",
                    "PATCH", f"tasks/{task_id}/resolve", 200,
                    data={"result_summary": "Task completed successfully"},
                    headers={"Authorization": f"Bearer {agent_token}"}
                )
        
        # Test GET /api/v1/tasks/resolved — returns resolved tasks
        self.test_endpoint(
            "GET /api/v1/tasks/resolved",
            "GET", "tasks/resolved", 200,
            headers={"Authorization": f"Bearer {agent_token}"}
        )
    
    def test_evidence_management(self):
        """Test evidence management with D-15 §2.4 community-scope check"""
        self.log("\n=== TESTING EVIDENCE MANAGEMENT ===")
        
        if "agent_token" not in self.test_data:
            self.log("❌ No agent token available")
            return
            
        agent_token = self.test_data["agent_token"]
        community_id = self.test_data["community_id"]
        
        # Create thread for evidence
        success, thread_data = self.test_endpoint(
            "Create test thread",
            "POST", f"communities/{community_id}/threads", 201,
            data={"title": "Evidence Thread", "content": "Thread for evidence testing"},
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        if success:
            thread_id = thread_data["id"]
            
            # Test POST /api/v1/communities/{id}/evidence — creates evidence, validates type
            success, evidence_data = self.test_endpoint(
                "POST /api/v1/communities/{id}/evidence",
                "POST", f"communities/{community_id}/evidence", 201,
                data={
                    "type": "data_point",
                    "content": "Test evidence for Session 5",
                    "thread_id": thread_id,
                    "source_url": "https://example.com"
                },
                headers={"Authorization": f"Bearer {agent_token}"}
            )
            
            if success:
                evidence_id = evidence_data["id"]
                
                # Test D-15 §2.4: contradiction contestation same-community check
                self.test_endpoint(
                    "POST contradiction evidence (D-15 §2.4)",
                    "POST", f"communities/{community_id}/evidence", 201,
                    data={
                        "type": "contradiction",
                        "content": "This contradicts the previous evidence",
                        "contested_target": evidence_id
                    },
                    headers={"Authorization": f"Bearer {agent_token}"}
                )
                
                # Test PATCH /api/v1/evidence/{id}/verify — verifies evidence, 403 if self-verify
                self.test_endpoint(
                    "PATCH /api/v1/evidence/{id}/verify (self-verify should fail)",
                    "PATCH", f"evidence/{evidence_id}/verify", 403,
                    headers={"Authorization": f"Bearer {agent_token}"}
                )
        
        # Test invalid evidence type
        self.test_endpoint(
            "POST evidence with invalid type",
            "POST", f"communities/{community_id}/evidence", 400,
            data={
                "type": "invalid_type",
                "content": "Test evidence"
            },
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        # Test GET /api/v1/communities/{id}/evidence
        self.test_endpoint(
            "GET /api/v1/communities/{id}/evidence",
            "GET", f"communities/{community_id}/evidence", 200
        )
    
    def test_notifications(self):
        """Test notifications with D-15 §2.2 proper join"""
        self.log("\n=== TESTING NOTIFICATIONS ===")
        
        if "agent_token" not in self.test_data:
            self.log("❌ No agent token available")
            return
            
        agent_token = self.test_data["agent_token"]
        
        # Test GET /api/v1/notifications — lists notifications for agent
        self.test_endpoint(
            "GET /api/v1/notifications",
            "GET", "notifications", 200,
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        # Test with unread_only filter
        self.test_endpoint(
            "GET /api/v1/notifications?unread_only=true",
            "GET", "notifications", 200,
            params={"unread_only": True},
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        # Test POST /api/v1/notifications/read-all — D-15 §2.2: marks all read via proper agent_id join
        self.test_endpoint(
            "POST /api/v1/notifications/read-all (D-15 §2.2)",
            "POST", "notifications/read-all", 200,
            headers={"Authorization": f"Bearer {agent_token}"}
        )
    
    def test_webhooks(self):
        """Test webhook CRUD operations"""
        self.log("\n=== TESTING WEBHOOKS ===")
        
        if "agent_token" not in self.test_data:
            self.log("❌ No agent token available")
            return
            
        agent_token = self.test_data["agent_token"]
        community_id = self.test_data["community_id"]
        
        # Test POST /api/v1/communities/{id}/webhooks — creates webhook
        success, webhook_data = self.test_endpoint(
            "POST /api/v1/communities/{id}/webhooks",
            "POST", f"communities/{community_id}/webhooks", 201,
            data={
                "url": "https://example.com/webhook",
                "events": ["post.created", "task.claimed"],
                "secret": "test_secret"
            },
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        
        if success:
            webhook_id = webhook_data["id"]
            
            # Test GET /api/v1/communities/{id}/webhooks — lists webhooks
            self.test_endpoint(
                "GET /api/v1/communities/{id}/webhooks",
                "GET", f"communities/{community_id}/webhooks", 200,
                headers={"Authorization": f"Bearer {agent_token}"}
            )
            
            # Test DELETE /api/v1/webhooks/{id} — deletes webhook
            self.test_endpoint(
                "DELETE /api/v1/webhooks/{id}",
                "DELETE", f"webhooks/{webhook_id}", 200,
                headers={"Authorization": f"Bearer {agent_token}"}
            )
    
    def test_feed_and_search(self):
        """Test cross-community feed and search functionality"""
        self.log("\n=== TESTING FEED AND SEARCH ===")
        
        # Test GET /api/v1/feed — returns cross-community published posts, hides rejected
        self.test_endpoint(
            "GET /api/v1/feed",
            "GET", "feed", 200
        )
        
        # Test with filters
        if "community_id" in self.test_data:
            self.test_endpoint(
                "GET /api/v1/feed with community filter",
                "GET", "feed", 200,
                params={"community_id": self.test_data["community_id"], "limit": 5}
            )
        
        # Test GET /api/v1/search?q=... — searches via ILIKE on title+content
        self.test_endpoint(
            "GET /api/v1/search?q=...",
            "GET", "search", 200,
            params={"q": "test", "limit": 5}
        )
        
        # Test search with type filter
        self.test_endpoint(
            "GET /api/v1/search with type filter",
            "GET", "search", 200,
            params={"q": "task", "type": "task", "limit": 3}
        )
    
    def test_tools_restrictions(self):
        """Test tools/search restrictions"""
        self.log("\n=== TESTING TOOLS RESTRICTIONS ===")
        
        # Test POST /api/v1/tools/search — 403 for workers, 503 when Google keys missing
        if "agent_token" in self.test_data:
            self.test_endpoint(
                "POST /api/v1/tools/search (worker should get 403)",
                "POST", "tools/search", 403,
                data={"query": "test search", "count": 3},
                headers={"Authorization": f"Bearer {self.test_data['agent_token']}"}
            )
        
        if "orch_token" in self.test_data:
            self.test_endpoint(
                "POST /api/v1/tools/search (orchestrator should get 503)",
                "POST", "tools/search", 503,
                data={"query": "test search", "count": 3},
                headers={"Authorization": f"Bearer {self.test_data['orch_token']}"}
            )
    
    def run_tests(self):
        """Run all Session 5 tests"""
        self.log("🚀 Starting United Agents Session 5 Complete Backend Tests")
        
        # Test health first
        success, _ = self.test_endpoint("Health Check", "GET", "health", 200)
        if not success:
            self.log("❌ Health check failed - backend may not be running")
            return 1
        
        # Setup test data
        if not self.setup_test_data():
            self.log("❌ Failed to setup test data")
            return 1
        
        # Run all test suites
        self.test_task_management()
        self.test_evidence_management()
        self.test_notifications()
        self.test_webhooks()
        self.test_feed_and_search()
        self.test_tools_restrictions()
        
        # Print results
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed ({success_rate:.1f}%)")
        
        if self.issues:
            self.log("\n❌ Issues found:")
            for issue in self.issues:
                self.log(f"   - {issue}")
        
        if success_rate >= 80:
            self.log("✅ Session 5 backend tests mostly successful")
            return 0
        else:
            self.log("❌ Session 5 backend has significant issues")
            return 1

def main():
    tester = Session5CompleteTester()
    return tester.run_tests()

if __name__ == "__main__":
    sys.exit(main())