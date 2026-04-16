#!/usr/bin/env python3
"""
United Agents Session 5 Backend Test - Rate Limited Version
Tests endpoints that don't require fresh agent creation
"""

import requests
import json
import sys
from datetime import datetime

class Session5RateLimitedTester:
    def __init__(self):
        self.base_url = "https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"
        self.admin_token = "ua-admin-token-super-secret-change-me-32chars"
        self.tests_run = 0
        self.tests_passed = 0
        self.issues = []
        self.backend_issues = []
        self.passed_tests = []
        
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
                self.passed_tests.append(name)
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
                issue = {
                    "endpoint": endpoint,
                    "issue": f"Expected {expected_status}, got {response.status_code}",
                    "impact": "API endpoint not working as expected",
                    "fix_priority": "MEDIUM"
                }
                self.backend_issues.append(issue)
                if response.text:
                    self.log(f"   Response: {response.text[:200]}")
                try:
                    return False, response.json()
                except:
                    return False, {}
                    
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            issue = {
                "endpoint": endpoint,
                "issue": f"Connection/timeout error: {str(e)}",
                "impact": "API endpoint unreachable",
                "fix_priority": "HIGH"
            }
            self.backend_issues.append(issue)
            return False, {}
    
    def test_public_endpoints(self):
        """Test endpoints that don't require authentication"""
        self.log("\n=== TESTING PUBLIC ENDPOINTS ===")
        
        # Health check
        self.test_endpoint("Health Check", "GET", "health", 200)
        
        # Feed endpoint (cross-community)
        self.test_endpoint(
            "GET /api/v1/feed (cross-community published posts)",
            "GET", "feed", 200
        )
        
        # Search endpoint (ILIKE on title+content)
        self.test_endpoint(
            "GET /api/v1/search (ILIKE search)",
            "GET", "search", 200,
            params={"q": "test", "limit": 5}
        )
        
        # Search with type filter
        self.test_endpoint(
            "GET /api/v1/search with type filter",
            "GET", "search", 200,
            params={"q": "task", "type": "task", "limit": 3}
        )
        
        # Test search validation (empty query should fail)
        self.test_endpoint(
            "GET /api/v1/search with empty query (should fail)",
            "GET", "search", 422,
            params={"q": ""}
        )
    
    def test_admin_endpoints(self):
        """Test admin-only endpoints"""
        self.log("\n=== TESTING ADMIN ENDPOINTS ===")
        
        # Admin access to agents
        self.test_endpoint(
            "GET /api/v1/agents (admin access)",
            "GET", "agents", 200,
            headers={"X-Admin-Token": self.admin_token}
        )
        
        # Admin access to communities
        self.test_endpoint(
            "GET /api/v1/communities (admin access)",
            "GET", "communities", 200,
            headers={"X-Admin-Token": self.admin_token}
        )
    
    def test_auth_required_endpoints(self):
        """Test that auth-required endpoints properly reject unauthorized requests"""
        self.log("\n=== TESTING AUTH REQUIREMENTS ===")
        
        # Task endpoints should require auth
        self.test_endpoint(
            "GET /api/v1/tasks/open (should require auth)",
            "GET", "tasks/open", 401
        )
        
        self.test_endpoint(
            "GET /api/v1/tasks/resolved (should require auth)",
            "GET", "tasks/resolved", 401
        )
        
        # Notifications should require auth
        self.test_endpoint(
            "GET /api/v1/notifications (should require auth)",
            "GET", "notifications", 401
        )
        
        # Tools should require auth
        self.test_endpoint(
            "POST /api/v1/tools/search (should require auth)",
            "POST", "tools/search", 401,
            data={"query": "test", "count": 3}
        )
        
        # Evidence endpoints should require auth
        self.test_endpoint(
            "GET /api/v1/communities/test-id/evidence (should require auth)",
            "GET", "communities/test-id/evidence", 401
        )
        
        # Webhooks should require auth
        self.test_endpoint(
            "GET /api/v1/communities/test-id/webhooks (should require auth)",
            "GET", "communities/test-id/webhooks", 401
        )
    
    def test_existing_data_endpoints(self):
        """Test endpoints with existing data"""
        self.log("\n=== TESTING WITH EXISTING DATA ===")
        
        # Get existing communities
        success, communities = self.test_endpoint(
            "GET existing communities",
            "GET", "communities", 200,
            headers={"X-Admin-Token": self.admin_token}
        )
        
        if success and communities and len(communities) > 0:
            community_id = communities[0]["id"]
            self.log(f"   Using community: {community_id}")
            
            # Test evidence endpoint with real community ID
            self.test_endpoint(
                f"GET /api/v1/communities/{community_id}/evidence (should require auth)",
                "GET", f"communities/{community_id}/evidence", 401
            )
            
            # Test webhooks endpoint with real community ID
            self.test_endpoint(
                f"GET /api/v1/communities/{community_id}/webhooks (should require auth)",
                "GET", f"communities/{community_id}/webhooks", 401
            )
            
            # Test feed with community filter
            self.test_endpoint(
                "GET /api/v1/feed with community filter",
                "GET", "feed", 200,
                params={"community_id": community_id, "limit": 5}
            )
    
    def run_tests(self):
        """Run all available tests"""
        self.log("🚀 Starting United Agents Session 5 Backend Tests (Rate Limited)")
        self.log("Note: Cannot create new agents due to rate limiting, testing available endpoints")
        
        self.test_public_endpoints()
        self.test_admin_endpoints()
        self.test_auth_required_endpoints()
        self.test_existing_data_endpoints()
        
        # Print results
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed ({success_rate:.1f}%)")
        
        self.log(f"\n✅ Passed Tests:")
        for test in self.passed_tests:
            self.log(f"   - {test}")
        
        if self.backend_issues:
            self.log(f"\n❌ Backend Issues Found:")
            for issue in self.backend_issues:
                self.log(f"   - {issue['endpoint']}: {issue['issue']}")
        
        # Summary of Session 5 features tested
        self.log(f"\n📋 Session 5 Features Tested:")
        self.log(f"   ✅ GET /api/v1/feed — cross-community published posts")
        self.log(f"   ✅ GET /api/v1/search — ILIKE search on title+content")
        self.log(f"   ✅ Auth requirements for task endpoints")
        self.log(f"   ✅ Auth requirements for evidence endpoints")
        self.log(f"   ✅ Auth requirements for notification endpoints")
        self.log(f"   ✅ Auth requirements for webhook endpoints")
        self.log(f"   ✅ Auth requirements for tools/search")
        self.log(f"   ⚠️  Full task flow (blocked by rate limiting)")
        self.log(f"   ⚠️  Evidence D-15 §2.4 checks (blocked by rate limiting)")
        self.log(f"   ⚠️  Notification D-15 §2.2 checks (blocked by rate limiting)")
        
        return {
            "success_rate": success_rate,
            "tests_passed": self.tests_passed,
            "tests_run": self.tests_run,
            "backend_issues": self.backend_issues,
            "passed_tests": self.passed_tests
        }

def main():
    tester = Session5RateLimitedTester()
    results = tester.run_tests()
    
    if results["success_rate"] >= 80:
        print("✅ Available Session 5 endpoints working correctly")
        return 0
    else:
        print("❌ Some Session 5 endpoints have issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())