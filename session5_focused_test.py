#!/usr/bin/env python3
"""
United Agents Session 5 Focused Backend API Tests
Tests specific Session 5 endpoints using existing data
"""

import requests
import json
import sys
from datetime import datetime

class Session5FocusedTester:
    def __init__(self):
        self.base_url = "https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"
        self.admin_token = "ua-admin-token-super-secret-change-me-32chars"
        self.tests_run = 0
        self.tests_passed = 0
        self.issues = []
        
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
                response = requests.get(url, headers=test_headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)
                
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ Status: {response.status_code}")
                try:
                    data = response.json()
                    if isinstance(data, list):
                        self.log(f"   Returned {len(data)} items")
                    elif isinstance(data, dict) and 'results' in data:
                        self.log(f"   Returned {len(data['results'])} results")
                except:
                    pass
            else:
                self.log(f"❌ Expected {expected_status}, got {response.status_code}")
                self.issues.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                if response.text:
                    self.log(f"   Response: {response.text[:200]}")
                    
            return success, response.json() if response.text else {}
            
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            self.issues.append(f"{name}: {str(e)}")
            return False, {}
    
    def test_session_5_endpoints(self):
        """Test all Session 5 specific endpoints"""
        self.log("🚀 Testing United Agents Session 5 Endpoints")
        
        # Test health first
        self.test_endpoint("Health Check", "GET", "health", 200)
        
        # === TASK ENDPOINTS ===
        self.log("\n=== TASK ENDPOINTS ===")
        
        # GET /api/v1/tasks/open — returns open tasks, filters stale claims and unresolved deps
        self.test_endpoint(
            "GET /api/v1/tasks/open", 
            "GET", "tasks/open", 200
        )
        
        # GET /api/v1/tasks/resolved — returns resolved tasks
        self.test_endpoint(
            "GET /api/v1/tasks/resolved", 
            "GET", "tasks/resolved", 200
        )
        
        # Test with filters
        self.test_endpoint(
            "GET /api/v1/tasks/open with filters", 
            "GET", "tasks/open", 200,
            params={"limit": 5, "category": "research"}
        )
        
        # === FEED AND SEARCH ===
        self.log("\n=== FEED AND SEARCH ===")
        
        # GET /api/v1/feed — returns cross-community published posts, hides rejected
        self.test_endpoint(
            "GET /api/v1/feed", 
            "GET", "feed", 200
        )
        
        # GET /api/v1/search?q=... — searches via ILIKE on title+content
        self.test_endpoint(
            "GET /api/v1/search", 
            "GET", "search", 200,
            params={"q": "test", "limit": 5}
        )
        
        # Test search with type filter
        self.test_endpoint(
            "GET /api/v1/search with type filter", 
            "GET", "search", 200,
            params={"q": "task", "type": "task", "limit": 3}
        )
        
        # === TOOLS RESTRICTIONS ===
        self.log("\n=== TOOLS RESTRICTIONS ===")
        
        # POST /api/v1/tools/search — should fail without auth
        self.test_endpoint(
            "POST /api/v1/tools/search (no auth)", 
            "POST", "tools/search", 401,
            data={"query": "test", "count": 3}
        )
        
        # === ADMIN ENDPOINTS ===
        self.log("\n=== ADMIN ENDPOINTS ===")
        
        # Test admin access to agents
        self.test_endpoint(
            "GET /api/v1/agents (admin)", 
            "GET", "agents", 200,
            headers={"X-Admin-Token": self.admin_token}
        )
        
        # Test admin access to communities
        self.test_endpoint(
            "GET /api/v1/communities (admin)", 
            "GET", "communities", 200,
            headers={"X-Admin-Token": self.admin_token}
        )
        
        # === ERROR HANDLING ===
        self.log("\n=== ERROR HANDLING ===")
        
        # Test non-existent task
        self.test_endpoint(
            "GET non-existent task", 
            "GET", "tasks/non-existent-id/claim", 404
        )
        
        # Test invalid search query
        self.test_endpoint(
            "GET search with empty query", 
            "GET", "search", 422,
            params={"q": ""}
        )
        
        # === SPECIFIC SESSION 5 FEATURES ===
        self.log("\n=== SESSION 5 SPECIFIC FEATURES ===")
        
        # Test evidence endpoints (should require auth)
        self.test_endpoint(
            "GET evidence without auth", 
            "GET", "communities/test-id/evidence", 401
        )
        
        # Test notifications without auth
        self.test_endpoint(
            "GET notifications without auth", 
            "GET", "notifications", 401
        )
        
        # Test webhooks without auth
        self.test_endpoint(
            "GET webhooks without auth", 
            "GET", "communities/test-id/webhooks", 401
        )
        
    def run_tests(self):
        """Run all tests and return results"""
        self.test_session_5_endpoints()
        
        # Print results
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed ({success_rate:.1f}%)")
        
        if self.issues:
            self.log("\n❌ Issues found:")
            for issue in self.issues:
                self.log(f"   - {issue}")
        
        if success_rate >= 80:
            self.log("✅ Session 5 backend endpoints mostly working")
            return 0
        else:
            self.log("❌ Session 5 backend has significant issues")
            return 1

def main():
    tester = Session5FocusedTester()
    return tester.run_tests()

if __name__ == "__main__":
    sys.exit(main())