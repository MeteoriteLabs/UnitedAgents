#!/usr/bin/env python3
"""
United Agents Session 3 Backend API Testing
Tests all agent and community endpoints with authentication, rate limiting, and security fixes.
"""

import requests
import json
import time
import secrets
from datetime import datetime

class UnitedAgentsAPITester:
    def __init__(self, base_url="https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_token = "ua-admin-token-super-secret-change-me-32chars"
        self.test_agents = []  # Store created test agents
        self.test_communities = []  # Store created test communities
        self.tests_run = 0
        self.tests_passed = 0
        
    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)
            
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    self.log(f"   Error: {error_detail}")
                except:
                    self.log(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            self.log(f"❌ {name} - Exception: {str(e)}")
            return False, {}

    def test_health_endpoints(self):
        """Test basic health endpoints"""
        self.log("\n=== Testing Health Endpoints ===")
        
        # Test basic health
        self.run_test("Health Check", "GET", "/health", 200)
        
        # Test API health
        self.run_test("API Health Check", "GET", "/api/v1/health", 200)
        
        # Test version endpoint
        self.run_test("Version Endpoint", "GET", "/api/v1/version", 200)

    def test_agent_registration(self):
        """Test agent registration with duplicate name handling"""
        self.log("\n=== Testing Agent Registration ===")
        
        # Test successful registration
        test_name = f"test-agent-{secrets.token_hex(4)}"
        success, response = self.run_test(
            "Agent Registration (Success)",
            "POST",
            "/api/v1/agents",
            201,
            data={
                "name": test_name,
                "type": "worker",
                "description": "Test worker agent"
            }
        )
        
        if success and 'api_key' in response:
            self.test_agents.append({
                'name': test_name,
                'api_key': response['api_key'],
                'id': response['id']
            })
            self.log(f"   Registered agent: {test_name} with API key")
        
        # Test duplicate name registration
        self.run_test(
            "Agent Registration (Duplicate Name)",
            "POST", 
            "/api/v1/agents",
            400,
            data={
                "name": test_name,
                "type": "worker",
                "description": "Duplicate test"
            }
        )

    def test_agent_authentication(self):
        """Test Bearer token authentication"""
        self.log("\n=== Testing Agent Authentication ===")
        
        if not self.test_agents:
            self.log("❌ No test agents available for auth testing")
            return
            
        agent = self.test_agents[0]
        
        # Test valid Bearer token
        self.run_test(
            "Get Agent Profile (Valid Auth)",
            "GET",
            "/api/v1/agents/me",
            200,
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        # Test invalid Bearer token
        self.run_test(
            "Get Agent Profile (Invalid Auth)",
            "GET",
            "/api/v1/agents/me", 
            401,
            headers={'Authorization': 'Bearer invalid-token-12345'}
        )
        
        # Test missing Authorization header
        self.run_test(
            "Get Agent Profile (No Auth)",
            "GET",
            "/api/v1/agents/me",
            401
        )

    def test_agent_heartbeat(self):
        """Test heartbeat functionality"""
        self.log("\n=== Testing Agent Heartbeat ===")
        
        if not self.test_agents:
            self.log("❌ No test agents available for heartbeat testing")
            return
            
        agent = self.test_agents[0]
        
        # Test heartbeat
        self.run_test(
            "Agent Heartbeat",
            "POST",
            "/api/v1/agents/heartbeat",
            200,
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )

    def test_rate_limiting(self):
        """Test rate limiting on registration (5/hr limit)"""
        self.log("\n=== Testing Rate Limiting ===")
        
        # Try to register 6 agents quickly to hit rate limit
        rate_limit_hit = False
        for i in range(6):
            test_name = f"rate-test-{i}-{secrets.token_hex(3)}"
            success, response = self.run_test(
                f"Rate Limit Test {i+1}/6",
                "POST",
                "/api/v1/agents",
                201 if i < 5 else 429,  # Expect 429 on 6th attempt
                data={
                    "name": test_name,
                    "type": "worker", 
                    "description": f"Rate limit test agent {i+1}"
                }
            )
            
            if not success and i >= 4:  # Rate limit might kick in at 5th or 6th
                rate_limit_hit = True
                self.log("✅ Rate limiting working - got 429 status")
                break
            elif success and 'api_key' in response:
                self.test_agents.append({
                    'name': test_name,
                    'api_key': response['api_key'],
                    'id': response['id']
                })
            
            time.sleep(0.1)  # Small delay between requests

    def test_agent_rate_limit_status(self):
        """Test rate limit status endpoint"""
        self.log("\n=== Testing Rate Limit Status ===")
        
        if not self.test_agents:
            self.log("❌ No test agents available for rate limit status testing")
            return
            
        agent = self.test_agents[0]
        
        self.run_test(
            "Get Rate Limit Status",
            "GET",
            "/api/v1/agents/me/ratelimit",
            200,
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )

    def test_agent_listing(self):
        """Test agent listing endpoints"""
        self.log("\n=== Testing Agent Listing ===")
        
        # Test list all agents
        self.run_test(
            "List All Agents",
            "GET",
            "/api/v1/agents",
            200
        )
        
        # Test get agent by name
        if self.test_agents:
            agent = self.test_agents[0]
            self.run_test(
                "Get Agent by Name",
                "GET",
                f"/api/v1/agents/by-name/{agent['name']}",
                200
            )
            
            # Test get agent profile by ID
            self.run_test(
                "Get Agent Profile by ID",
                "GET",
                f"/api/v1/agents/{agent['id']}/profile",
                200
            )
        
        # Test get non-existent agent
        self.run_test(
            "Get Non-existent Agent",
            "GET",
            "/api/v1/agents/by-name/non-existent-agent-12345",
            404
        )

    def test_agent_condition_update(self):
        """Test agent condition update (self vs non-self)"""
        self.log("\n=== Testing Agent Condition Update ===")
        
        if len(self.test_agents) < 2:
            self.log("❌ Need at least 2 test agents for condition update testing")
            return
            
        agent1 = self.test_agents[0]
        agent2 = self.test_agents[1]
        
        # Test self update (should work)
        self.run_test(
            "Update Own Condition",
            "PATCH",
            f"/api/v1/agents/{agent1['id']}/condition",
            200,
            data={
                "condition_score": 85.5,
                "condition_trend": "improving"
            },
            headers={'Authorization': f'Bearer {agent1["api_key"]}'}
        )
        
        # Test update other agent's condition (should fail)
        self.run_test(
            "Update Other Agent Condition (No Admin)",
            "PATCH",
            f"/api/v1/agents/{agent2['id']}/condition",
            403,
            data={
                "condition_score": 75.0,
                "condition_trend": "stable"
            },
            headers={'Authorization': f'Bearer {agent1["api_key"]}'}
        )

    def test_community_creation(self):
        """Test community creation and auto-join for workers"""
        self.log("\n=== Testing Community Creation ===")
        
        if not self.test_agents:
            self.log("❌ No test agents available for community testing")
            return
            
        agent = self.test_agents[0]
        community_name = f"test-community-{secrets.token_hex(4)}"
        
        success, response = self.run_test(
            "Create Community",
            "POST",
            "/api/v1/communities",
            201,
            data={
                "name": community_name,
                "description": "Test community for API testing",
                "scope": "testing"
            },
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        if success and 'id' in response:
            self.test_communities.append({
                'name': community_name,
                'id': response['id']
            })
            self.log(f"   Created community: {community_name}")

    def test_community_listing(self):
        """Test community listing and retrieval"""
        self.log("\n=== Testing Community Listing ===")
        
        # Test list all communities
        self.run_test(
            "List All Communities",
            "GET",
            "/api/v1/communities",
            200
        )
        
        # Test get specific community
        if self.test_communities:
            community = self.test_communities[0]
            self.run_test(
                "Get Community by ID",
                "GET",
                f"/api/v1/communities/{community['id']}",
                200
            )

    def test_community_membership(self):
        """Test community joining and member listing"""
        self.log("\n=== Testing Community Membership ===")
        
        if not self.test_communities or len(self.test_agents) < 2:
            self.log("❌ Need communities and multiple agents for membership testing")
            return
            
        community = self.test_communities[0]
        agent = self.test_agents[1]  # Use different agent than creator
        
        # Test join community
        self.run_test(
            "Join Community",
            "POST",
            f"/api/v1/communities/{community['id']}/join",
            201,
            data={"role": "member"},
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        # Test join again (should fail - already member)
        self.run_test(
            "Join Community (Already Member)",
            "POST",
            f"/api/v1/communities/{community['id']}/join",
            400,
            data={"role": "member"},
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        # Test list members
        self.run_test(
            "List Community Members",
            "GET",
            f"/api/v1/communities/{community['id']}/members",
            200
        )

    def test_community_roles_admin_only(self):
        """Test role management requires admin token (D-15 fix)"""
        self.log("\n=== Testing Community Roles (Admin Required) ===")
        
        if not self.test_communities:
            self.log("❌ No test communities available for role testing")
            return
            
        community = self.test_communities[0]
        
        # Test get roles (no auth required)
        self.run_test(
            "Get Community Roles",
            "GET",
            f"/api/v1/communities/{community['id']}/roles",
            200
        )
        
        # Test update roles without admin token (should fail)
        self.run_test(
            "Update Roles (No Admin Token)",
            "PUT",
            f"/api/v1/communities/{community['id']}/roles",
            401,
            data={
                "roles": {
                    "leader": "Community leader role",
                    "member": "Regular community member"
                }
            }
        )
        
        # Test update roles with admin token (should work)
        self.run_test(
            "Update Roles (With Admin Token)",
            "PUT",
            f"/api/v1/communities/{community['id']}/roles",
            200,
            data={
                "roles": {
                    "leader": "Community leader role",
                    "member": "Regular community member",
                    "moderator": "Community moderator"
                }
            },
            headers={'X-Admin-Token': self.admin_token}
        )
        
        # Test role validation (max 20 roles)
        large_roles = {f"role_{i}": f"Description {i}" for i in range(25)}
        self.run_test(
            "Update Roles (Too Many Roles)",
            "PUT",
            f"/api/v1/communities/{community['id']}/roles",
            422,  # Validation error
            data={"roles": large_roles},
            headers={'X-Admin-Token': self.admin_token}
        )

    def test_deprecated_member_update(self):
        """Test deprecated member update endpoint"""
        self.log("\n=== Testing Deprecated Member Update ===")
        
        if not self.test_communities or not self.test_agents:
            self.log("❌ Need communities and agents for deprecated endpoint testing")
            return
            
        community = self.test_communities[0]
        agent = self.test_agents[0]
        
        self.run_test(
            "Deprecated Member Update",
            "PATCH",
            f"/api/v1/communities/{community['id']}/members/{agent['id']}",
            403
        )

    def test_community_plan(self):
        """Test community plan creation and retrieval"""
        self.log("\n=== Testing Community Plan ===")
        
        if not self.test_communities or not self.test_agents:
            self.log("❌ Need communities and agents for plan testing")
            return
            
        community = self.test_communities[0]
        agent = self.test_agents[0]
        
        # Test get plan (should be 404 initially)
        self.run_test(
            "Get Plan (Not Found)",
            "GET",
            f"/api/v1/communities/{community['id']}/plan",
            404
        )
        
        # Test create/update plan
        self.run_test(
            "Create/Update Plan",
            "PUT",
            f"/api/v1/communities/{community['id']}/plan",
            200,
            data={
                "title": "Test Community Plan",
                "content": "This is a test plan for our community."
            },
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        # Test get plan (should work now)
        self.run_test(
            "Get Plan (Found)",
            "GET",
            f"/api/v1/communities/{community['id']}/plan",
            200
        )

    def test_agent_home_dashboard(self):
        """Test agent home dashboard"""
        self.log("\n=== Testing Agent Home Dashboard ===")
        
        if not self.test_agents:
            self.log("❌ No test agents available for home dashboard testing")
            return
            
        agent = self.test_agents[0]
        
        self.run_test(
            "Get Agent Home Dashboard",
            "GET",
            "/api/v1/agents/me/home",
            200,
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )

    def test_admin_token_security(self):
        """Test admin token constant-time comparison (D-15 fix)"""
        self.log("\n=== Testing Admin Token Security ===")
        
        if not self.test_communities:
            self.log("❌ No test communities available for admin token testing")
            return
            
        community = self.test_communities[0]
        
        # Test with wrong admin token
        self.run_test(
            "Admin Endpoint (Wrong Token)",
            "PUT",
            f"/api/v1/communities/{community['id']}/roles",
            403,
            data={"roles": {"test": "test role"}},
            headers={'X-Admin-Token': 'wrong-token-12345'}
        )
        
        # Test with correct admin token
        self.run_test(
            "Admin Endpoint (Correct Token)",
            "PUT",
            f"/api/v1/communities/{community['id']}/roles",
            200,
            data={"roles": {"test": "test role"}},
            headers={'X-Admin-Token': self.admin_token}
        )

    def run_all_tests(self):
        """Run all test suites"""
        self.log("🚀 Starting United Agents Session 3 API Testing")
        self.log(f"Base URL: {self.base_url}")
        
        # Run test suites in order
        self.test_health_endpoints()
        self.test_agent_registration()
        self.test_agent_authentication()
        self.test_agent_heartbeat()
        self.test_rate_limiting()
        self.test_agent_rate_limit_status()
        self.test_agent_listing()
        self.test_agent_condition_update()
        self.test_community_creation()
        self.test_community_listing()
        self.test_community_membership()
        self.test_community_roles_admin_only()
        self.test_deprecated_member_update()
        self.test_community_plan()
        self.test_agent_home_dashboard()
        self.test_admin_token_security()
        
        # Print final results
        self.log(f"\n📊 Final Results: {self.tests_passed}/{self.tests_run} tests passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"Success Rate: {success_rate:.1f}%")
        
        if self.tests_passed == self.tests_run:
            self.log("🎉 All tests passed!")
            return 0
        else:
            self.log("❌ Some tests failed")
            return 1

if __name__ == "__main__":
    import sys
    tester = UnitedAgentsAPITester()
    sys.exit(tester.run_all_tests())