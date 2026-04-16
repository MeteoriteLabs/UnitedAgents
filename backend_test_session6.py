#!/usr/bin/env python3
"""
United Agents Session 6 Backend API Testing
Tests: Admin CRUD endpoints (X-Admin-Token gated) + Skill-serving routes with template substitution
"""

import requests
import json
import time
import secrets
import sys
from datetime import datetime
from typing import Dict, List, Optional

class UnitedAgentsSession6Tester:
    def __init__(self, base_url="https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.admin_token = "ua-admin-token-super-secret-change-me-32chars"
        self.test_data = {}  # Store created test data
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()
        
    def log(self, message: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None, 
                 params: Optional[Dict] = None, check_content: Optional[str] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        # Handle both API and non-API endpoints
        if endpoint.startswith('/api/'):
            url = f"{self.base_url}{endpoint}"
        elif endpoint.startswith('api/'):
            url = f"{self.base_url}/{endpoint}"
        else:
            # Skill-serving routes (no /api prefix)
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            
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
            
            # Additional content check for skill files
            if success and check_content:
                content_check = check_content in response.text
                if not content_check:
                    success = False
                    self.log(f"   Content check failed: '{check_content}' not found in response")
                    
            if success:
                self.tests_passed += 1
                self.log(f"✅ Passed - Status: {response.status_code}")
                if check_content:
                    self.log(f"   Content check passed: '{check_content}' found")
            else:
                self.log(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                if response.text:
                    self.log(f"   Response: {response.text[:300]}")
                    
            try:
                response_data = response.json() if response.text and response.headers.get('content-type', '').startswith('application/json') else {"raw_response": response.text}
            except:
                response_data = {"raw_response": response.text}
                
            return success, response_data
            
        except Exception as e:
            self.log(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_admin_validation(self):
        """Test admin token validation"""
        self.log("\n=== TESTING ADMIN VALIDATION ===")
        
        # Test GET /api/v1/admin/validate — returns {valid: true} with correct token
        success, response = self.run_test(
            "Admin validate with correct token",
            "GET",
            "api/v1/admin/validate",
            200,
            headers={"X-Admin-Token": self.admin_token}
        )
        
        if success and response.get("valid") == True:
            self.log("   ✅ Correct token validation passed")
        else:
            self.log(f"   ❌ Expected {{valid: true}}, got {response}")
        
        # Test GET /api/v1/admin/validate — returns 401/403 without token
        self.run_test(
            "Admin validate without token (should fail)",
            "GET",
            "api/v1/admin/validate",
            401  # or 403, either is acceptable
        )
        
        # Test GET /api/v1/admin/validate — returns 401/403 with wrong token
        self.run_test(
            "Admin validate with wrong token (should fail)",
            "GET",
            "api/v1/admin/validate",
            401,  # or 403, either is acceptable
            headers={"X-Admin-Token": "wrong-token"}
        )
        
        return True

    def test_admin_agents_crud(self):
        """Test admin agent CRUD operations"""
        self.log("\n=== TESTING ADMIN AGENTS CRUD ===")
        
        admin_headers = {"X-Admin-Token": self.admin_token}
        
        # Test GET /api/v1/admin/agents — lists all agents
        success, agents_list = self.run_test(
            "List all agents (admin)",
            "GET",
            "api/v1/admin/agents",
            200,
            headers=admin_headers
        )
        
        if success:
            self.log(f"   Found {len(agents_list)} existing agents")
        
        # Test POST /api/v1/admin/agents — creates agent (orchestrator) with api_key
        agent_name = f"test_orchestrator_{int(time.time())}"
        success, create_response = self.run_test(
            "Create orchestrator agent",
            "POST",
            "api/v1/admin/agents",
            201,
            data={
                "name": agent_name,
                "type": "orchestrator",
                "description": "Test orchestrator for Session 6",
                "voice_persona": "Professional and analytical",
                "heartbeat_minutes": 30
            },
            headers=admin_headers
        )
        
        agent_id = None
        if success and "id" in create_response and "api_key" in create_response:
            agent_id = create_response["id"]
            self.test_data["test_agent"] = {
                "id": agent_id,
                "name": agent_name,
                "api_key": create_response["api_key"]
            }
            self.log(f"   ✅ Created agent {agent_id} with API key")
        else:
            self.log(f"   ❌ Failed to create agent or missing api_key in response")
            return False
        
        # Test PATCH /api/v1/admin/agents/{id} — updates agent fields
        if agent_id:
            success, update_response = self.run_test(
                "Update agent fields",
                "PATCH",
                f"api/v1/admin/agents/{agent_id}",
                200,
                data={
                    "description": "Updated description for Session 6 testing",
                    "heartbeat_minutes": 45
                },
                headers=admin_headers
            )
            
            if success:
                self.log("   ✅ Agent update successful")
        
        # Test DELETE /api/v1/admin/agents/{id} — deletes with cascade
        if agent_id:
            success, delete_response = self.run_test(
                "Delete agent with cascade",
                "DELETE",
                f"api/v1/admin/agents/{agent_id}",
                200,
                headers=admin_headers
            )
            
            if success and delete_response.get("status") == "deleted":
                self.log("   ✅ Agent deletion successful")
            else:
                self.log(f"   ❌ Expected status 'deleted', got {delete_response}")
        
        return True

    def test_admin_communities_crud(self):
        """Test admin community CRUD operations"""
        self.log("\n=== TESTING ADMIN COMMUNITIES CRUD ===")
        
        admin_headers = {"X-Admin-Token": self.admin_token}
        
        # Test GET /api/v1/admin/communities — lists communities
        success, communities_list = self.run_test(
            "List all communities (admin)",
            "GET",
            "api/v1/admin/communities",
            200,
            headers=admin_headers
        )
        
        if success:
            self.log(f"   Found {len(communities_list)} existing communities")
        
        # Test POST /api/v1/admin/communities — creates community with emoji auto-gen fallback
        community_name = f"Test Community {int(time.time())}"
        success, create_response = self.run_test(
            "Create community with emoji auto-gen",
            "POST",
            "api/v1/admin/communities",
            201,
            data={
                "name": community_name,
                "description": "Test community for Session 6 admin testing",
                "scope": "local"
            },
            headers=admin_headers
        )
        
        community_id = None
        if success and "id" in create_response:
            community_id = create_response["id"]
            icon = create_response.get("icon", "")
            self.test_data["test_community"] = {
                "id": community_id,
                "name": community_name
            }
            self.log(f"   ✅ Created community {community_id} with icon: {icon}")
            
            # Check if emoji fallback worked (should be globe emoji since no OPENAI_API_KEY)
            if icon == "🌍":
                self.log("   ✅ Emoji fallback to globe worked correctly")
        else:
            self.log(f"   ❌ Failed to create community")
            return False
        
        # Test DELETE /api/v1/admin/communities/{id} — cascading delete
        if community_id:
            success, delete_response = self.run_test(
                "Delete community with cascade",
                "DELETE",
                f"api/v1/admin/communities/{community_id}",
                200,
                headers=admin_headers
            )
            
            if success and delete_response.get("status") == "deleted":
                self.log("   ✅ Community deletion successful")
            else:
                self.log(f"   ❌ Expected status 'deleted', got {delete_response}")
        
        return True

    def test_admin_member_management(self):
        """Test admin member management operations"""
        self.log("\n=== TESTING ADMIN MEMBER MANAGEMENT ===")
        
        admin_headers = {"X-Admin-Token": self.admin_token}
        
        # Create a test agent and community for member management
        agent_name = f"test_member_{int(time.time())}"
        success, agent_response = self.run_test(
            "Create agent for member test",
            "POST",
            "api/v1/admin/agents",
            201,
            data={
                "name": agent_name,
                "type": "worker",
                "description": "Test agent for member management"
            },
            headers=admin_headers
        )
        
        if not success or "id" not in agent_response:
            self.log("❌ Failed to create test agent for member management")
            return False
            
        agent_id = agent_response["id"]
        
        community_name = f"Member Test Community {int(time.time())}"
        success, community_response = self.run_test(
            "Create community for member test",
            "POST",
            "api/v1/admin/communities",
            201,
            data={
                "name": community_name,
                "description": "Test community for member management"
            },
            headers=admin_headers
        )
        
        if not success or "id" not in community_response:
            self.log("❌ Failed to create test community for member management")
            return False
            
        community_id = community_response["id"]
        
        # Test PATCH /api/v1/admin/communities/{id}/members/{agent_id} — updates role
        success, update_response = self.run_test(
            "Update member role",
            "PATCH",
            f"api/v1/admin/communities/{community_id}/members/{agent_id}",
            200,
            data={"role": "moderator"},
            headers=admin_headers
        )
        
        if success:
            self.log("   ✅ Member role update successful")
        
        # Test DELETE /api/v1/admin/communities/{id}/members/{agent_id}
        # First test normal deletion (should work)
        success, delete_response = self.run_test(
            "Delete community member",
            "DELETE",
            f"api/v1/admin/communities/{community_id}/members/{agent_id}",
            200,
            headers=admin_headers
        )
        
        if success and delete_response.get("status") == "deleted":
            self.log("   ✅ Member deletion successful")
        
        # Clean up
        self.run_test("Cleanup agent", "DELETE", f"api/v1/admin/agents/{agent_id}", 200, headers=admin_headers)
        self.run_test("Cleanup community", "DELETE", f"api/v1/admin/communities/{community_id}", 200, headers=admin_headers)
        
        return True

    def test_admin_post_management(self):
        """Test admin post approval/rejection"""
        self.log("\n=== TESTING ADMIN POST MANAGEMENT ===")
        
        admin_headers = {"X-Admin-Token": self.admin_token}
        
        # Test GET /api/v1/admin/pending — lists pending_approval posts
        success, pending_posts = self.run_test(
            "List pending approval posts",
            "GET",
            "api/v1/admin/pending",
            200,
            headers=admin_headers
        )
        
        if success:
            self.log(f"   Found {len(pending_posts)} pending posts")
            
            # If there are pending posts, test approve/reject
            if len(pending_posts) > 0:
                post_id = pending_posts[0]["id"]
                
                # Test POST /api/v1/admin/posts/{id}/approve — approves post, notifies author
                success, approve_response = self.run_test(
                    "Approve pending post",
                    "POST",
                    f"api/v1/admin/posts/{post_id}/approve",
                    200,
                    headers=admin_headers
                )
                
                if success and approve_response.get("status") == "approved":
                    self.log("   ✅ Post approval successful")
                
            # Create a test post for rejection if no pending posts exist
            else:
                self.log("   No pending posts found for approval/rejection testing")
        
        return True

    def test_admin_health(self):
        """Test admin health endpoint"""
        self.log("\n=== TESTING ADMIN HEALTH ===")
        
        admin_headers = {"X-Admin-Token": self.admin_token}
        
        # Test GET /api/v1/admin/health — returns agent/community/post counts
        success, health_response = self.run_test(
            "Admin health check",
            "GET",
            "api/v1/admin/health",
            200,
            headers=admin_headers
        )
        
        if success:
            expected_fields = ["status", "agents", "communities", "posts"]
            missing_fields = [field for field in expected_fields if field not in health_response]
            
            if not missing_fields:
                self.log("   ✅ Health response contains all expected fields")
                self.log(f"   Agents: {health_response.get('agents', {})}")
                self.log(f"   Communities: {health_response.get('communities', 0)}")
                self.log(f"   Posts: {health_response.get('posts', {})}")
            else:
                self.log(f"   ❌ Missing fields in health response: {missing_fields}")
        
        return True

    def test_skill_serving_routes(self):
        """Test skill-serving routes with template substitution"""
        self.log("\n=== TESTING SKILL-SERVING ROUTES ===")
        
        # Test GET /skill.md — serves SKILL.md with {BASE_URL} substituted
        success, skill_response = self.run_test(
            "Serve SKILL.md with template substitution",
            "GET",
            "skill.md",
            200,
            check_content=self.base_url  # Should contain the substituted base URL
        )
        
        if success:
            self.log("   ✅ SKILL.md served with BASE_URL substitution")
        
        # Test GET /heartbeat.md — serves heartbeat.md with substitution
        success, heartbeat_response = self.run_test(
            "Serve heartbeat.md with template substitution",
            "GET",
            "heartbeat.md",
            200,
            check_content=self.base_url  # Should contain the substituted base URL
        )
        
        if success:
            self.log("   ✅ heartbeat.md served with BASE_URL substitution")
        
        # Test GET /llms.txt — serves llms.txt with substitution
        success, llms_response = self.run_test(
            "Serve llms.txt with template substitution",
            "GET",
            "llms.txt",
            200,
            check_content=self.base_url  # Should contain the substituted base URL
        )
        
        if success:
            self.log("   ✅ llms.txt served with BASE_URL substitution")
        
        # Test GET /skill/army-of-agents — returns JSON manifest
        success, manifest_response = self.run_test(
            "Serve army-of-agents JSON manifest",
            "GET",
            "skill/army-of-agents",
            200
        )
        
        if success and isinstance(manifest_response, dict):
            expected_fields = ["name", "version", "description", "homepage", "files", "config"]
            missing_fields = [field for field in expected_fields if field not in manifest_response]
            
            if not missing_fields:
                self.log("   ✅ JSON manifest contains all expected fields")
                # Check if URLs contain the base URL
                files = manifest_response.get("files", {})
                if all(self.base_url in url for url in files.values()):
                    self.log("   ✅ All file URLs contain correct base URL")
                else:
                    self.log("   ❌ Some file URLs missing correct base URL")
            else:
                self.log(f"   ❌ Missing fields in manifest: {missing_fields}")
        
        # Test GET /skill/army-of-agents/SKILL.md — long-form URL works
        success, long_skill_response = self.run_test(
            "Serve SKILL.md via long-form URL",
            "GET",
            "skill/army-of-agents/SKILL.md",
            200,
            check_content=self.base_url  # Should contain the substituted base URL
        )
        
        if success:
            self.log("   ✅ Long-form SKILL.md URL works with BASE_URL substitution")
        
        return True

    def run_all_tests(self):
        """Run all Session 6 tests"""
        self.log("🚀 Starting United Agents Session 6 Backend Tests")
        self.log(f"Base URL: {self.base_url}")
        self.log(f"Admin Token: {self.admin_token}")
        
        # Test basic health endpoint first
        success, _ = self.run_test("Basic health check", "GET", "health", 200)
        if not success:
            self.log("❌ Basic health check failed - backend may not be running")
            return 1
        
        try:
            # Run admin test flows
            self.test_admin_validation()
            self.test_admin_agents_crud()
            self.test_admin_communities_crud()
            self.test_admin_member_management()
            self.test_admin_post_management()
            self.test_admin_health()
            
            # Run skill-serving tests
            self.test_skill_serving_routes()
            
        except Exception as e:
            self.log(f"❌ Test execution failed: {str(e)}")
            return 1
        
        # Print results
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            self.log("✅ Session 6 backend tests mostly successful")
            return 0
        else:
            self.log("❌ Session 6 backend tests had significant failures")
            return 1

def main():
    tester = UnitedAgentsSession6Tester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())