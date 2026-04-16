#!/usr/bin/env python3
"""
Backend API Testing for United Agents - Session 12 Auth-gated Pages
Testing admin and agent authentication flows
"""

import requests
import sys
import json
from datetime import datetime

class UnitedAgentsAPITester:
    def __init__(self, base_url="https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_token = "ua-admin-token-super-secret-change-me-32chars"
        self.agent_api_key = None
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        default_headers = {'Content-Type': 'application/json'}
        if headers:
            default_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=default_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=default_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=default_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.text[:200]}")
                except:
                    pass

            return success, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_admin_validate(self):
        """Test admin token validation"""
        return self.run_test(
            "Admin Token Validation",
            "GET",
            "api/v1/admin/validate",
            200,
            headers={"X-Admin-Token": self.admin_token}
        )

    def test_admin_health(self):
        """Test admin health endpoint"""
        return self.run_test(
            "Admin Health Dashboard",
            "GET", 
            "api/v1/admin/health",
            200,
            headers={"X-Admin-Token": self.admin_token}
        )

    def test_admin_list_agents(self):
        """Test admin list agents"""
        return self.run_test(
            "Admin List Agents",
            "GET",
            "api/v1/admin/agents", 
            200,
            headers={"X-Admin-Token": self.admin_token}
        )

    def test_admin_list_communities(self):
        """Test admin list communities"""
        return self.run_test(
            "Admin List Communities",
            "GET",
            "api/v1/admin/communities",
            200,
            headers={"X-Admin-Token": self.admin_token}
        )

    def test_admin_list_pending(self):
        """Test admin list pending posts"""
        return self.run_test(
            "Admin List Pending Posts",
            "GET",
            "api/v1/admin/pending",
            200,
            headers={"X-Admin-Token": self.admin_token}
        )

    def test_create_agent_for_notifications(self):
        """Create a test agent to get API key for notifications testing"""
        test_agent_data = {
            "name": f"test_agent_{datetime.now().strftime('%H%M%S')}",
            "type": "worker",
            "voice_persona": "Test agent for notifications"
        }
        
        success, response = self.run_test(
            "Create Test Agent (for notifications)",
            "POST",
            "api/v1/admin/agents",
            201,
            data=test_agent_data,
            headers={"X-Admin-Token": self.admin_token}
        )
        
        if success and 'api_key' in response:
            self.agent_api_key = response['api_key']
            print(f"   Got API key: {self.agent_api_key[:10]}...")
            return True
        return False

    def test_agent_notifications(self):
        """Test agent notifications endpoint"""
        if not self.agent_api_key:
            print("❌ No agent API key available for notifications test")
            return False
            
        return self.run_test(
            "Agent Notifications",
            "GET",
            "api/v1/notifications",
            200,
            headers={"Authorization": f"Bearer {self.agent_api_key}"}
        )

    def test_admin_create_community(self):
        """Test admin create community"""
        test_community_data = {
            "name": f"Test Community {datetime.now().strftime('%H%M%S')}",
            "description": "Test community for admin CRUD testing",
            "scope": "testing"
        }
        
        return self.run_test(
            "Admin Create Community",
            "POST",
            "api/v1/admin/communities",
            201,
            data=test_community_data,
            headers={"X-Admin-Token": self.admin_token}
        )

def main():
    print("🚀 Starting United Agents Backend API Testing - Session 12")
    print("=" * 60)
    
    tester = UnitedAgentsAPITester()
    
    # Test admin authentication and endpoints
    print("\n📋 Testing Admin Authentication & Endpoints")
    print("-" * 40)
    
    admin_validate_success, _ = tester.test_admin_validate()
    if not admin_validate_success:
        print("❌ Admin token validation failed - stopping admin tests")
        return 1
    
    tester.test_admin_health()
    tester.test_admin_list_agents()
    tester.test_admin_list_communities()
    tester.test_admin_list_pending()
    tester.test_admin_create_community()
    
    # Test agent creation and notifications
    print("\n🤖 Testing Agent Creation & Notifications")
    print("-" * 40)
    
    if tester.test_create_agent_for_notifications():
        tester.test_agent_notifications()
    
    # Print results
    print("\n" + "=" * 60)
    print(f"📊 Backend API Tests Summary")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("✅ Backend APIs are working well - proceeding to frontend testing")
        return 0
    else:
        print("❌ Backend has significant issues - frontend testing may be affected")
        return 1

if __name__ == "__main__":
    sys.exit(main())