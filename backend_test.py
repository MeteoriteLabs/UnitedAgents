#!/usr/bin/env python3
"""
United Agents Backend Testing - Session 1 Infrastructure Tests
Tests scaffold and infrastructure components only.
"""

import requests
import sys
import os
from datetime import datetime
import psycopg2
from urllib.parse import urlparse

class UnitedAgentsInfraTester:
    def __init__(self):
        # Use the external URL for testing as specified in the requirements
        self.base_url = "https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def test_health_endpoint(self):
        """Test /health endpoint returns 200 with JSON {status: ok}"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    self.log_test("Health endpoint /health", True)
                    return True
                else:
                    self.log_test("Health endpoint /health", False, f"Status not 'ok': {data}")
                    return False
            else:
                self.log_test("Health endpoint /health", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Health endpoint /health", False, f"Exception: {str(e)}")
            return False

    def test_api_v1_health_endpoint(self):
        """Test /api/v1/health endpoint returns 200 with JSON {status: ok}"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    self.log_test("API health endpoint /api/v1/health", True)
                    return True
                else:
                    self.log_test("API health endpoint /api/v1/health", False, f"Status not 'ok': {data}")
                    return False
            else:
                self.log_test("API health endpoint /api/v1/health", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("API health endpoint /api/v1/health", False, f"Exception: {str(e)}")
            return False

    def test_database_connectivity(self):
        """Test PostgreSQL database connectivity"""
        try:
            # Database connection string from backend/.env
            db_url = "postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents"
            
            # Parse the URL for psycopg2
            parsed = urlparse(db_url.replace("postgresql+psycopg2://", "postgresql://"))
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path[1:],  # Remove leading slash
                user=parsed.username,
                password=parsed.password
            )
            
            # Test basic query
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if result and result[0] == 1:
                self.log_test("PostgreSQL database connectivity", True)
                return True
            else:
                self.log_test("PostgreSQL database connectivity", False, "Query returned unexpected result")
                return False
                
        except Exception as e:
            self.log_test("PostgreSQL database connectivity", False, f"Exception: {str(e)}")
            return False

    def test_backend_port_accessibility(self):
        """Test that backend is accessible on expected port (via external URL)"""
        try:
            # Test that we can reach the backend through the external URL
            response = requests.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                self.log_test("Backend accessibility via external URL", True)
                return True
            else:
                self.log_test("Backend accessibility via external URL", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Backend accessibility via external URL", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all infrastructure tests"""
        print("🚀 Starting United Agents Infrastructure Tests (Session 1)")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test health endpoints
        self.test_health_endpoint()
        self.test_api_v1_health_endpoint()
        
        # Test database connectivity
        self.test_database_connectivity()
        
        # Test backend accessibility
        self.test_backend_port_accessibility()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All infrastructure tests passed!")
            return True
        else:
            print("⚠️  Some infrastructure tests failed")
            return False

def main():
    """Main test runner"""
    tester = UnitedAgentsInfraTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())