#!/usr/bin/env python3
"""
United Agents Backend Testing - Session 2 Database & Schema Tests
Tests Session 2 deliverables: database models, schemas, migrations.
"""

import requests
import sys
import os
from datetime import datetime
import psycopg2
from urllib.parse import urlparse

class UnitedAgentsSession2Tester:
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

    def test_database_tables_exist(self):
        """Test that all 10 database tables exist in PostgreSQL"""
        expected_tables = [
            "agents", "communities", "threads", "community_members", "posts",
            "comments", "evidence", "notifications", "webhooks", "platform_config"
        ]
        
        try:
            # Database connection
            db_url = "postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents"
            parsed = urlparse(db_url.replace("postgresql+psycopg2://", "postgresql://"))
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password
            )
            
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            
            existing_tables = [row[0] for row in cursor.fetchall()]
            missing_tables = [t for t in expected_tables if t not in existing_tables]
            
            cursor.close()
            conn.close()
            
            if not missing_tables:
                self.log_test("All 10 database tables exist", True)
                return True
            else:
                self.log_test("All 10 database tables exist", False, f"Missing: {missing_tables}")
                return False
                
        except Exception as e:
            self.log_test("All 10 database tables exist", False, f"Database error: {str(e)}")
            return False

    def test_agents_table_security_fix(self):
        """Test agents table has NO api_key column (D-15 fix), only api_key_hash"""
        try:
            db_url = "postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents"
            parsed = urlparse(db_url.replace("postgresql+psycopg2://", "postgresql://"))
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password
            )
            
            cursor = conn.cursor()
            
            # Get column names for agents table
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'agents' AND table_schema = 'public'
            """)
            
            columns = [row[0] for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            has_api_key = "api_key" in columns
            has_api_key_hash = "api_key_hash" in columns
            
            if not has_api_key and has_api_key_hash:
                self.log_test("Agents table security fix (D-15)", True)
                return True
            else:
                details = f"api_key present: {has_api_key}, api_key_hash present: {has_api_key_hash}"
                self.log_test("Agents table security fix (D-15)", False, details)
                return False
                
        except Exception as e:
            self.log_test("Agents table security fix (D-15)", False, f"Database error: {str(e)}")
            return False

    def test_community_members_unique_constraint(self):
        """Test community_members table has UNIQUE constraint on (agent_id, community_id) - GOTCHAS §8.1"""
        try:
            db_url = "postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents"
            parsed = urlparse(db_url.replace("postgresql+psycopg2://", "postgresql://"))
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password
            )
            
            cursor = conn.cursor()
            
            # Check for unique constraint
            cursor.execute("""
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints 
                WHERE table_name = 'community_members' 
                AND table_schema = 'public'
                AND constraint_type = 'UNIQUE'
            """)
            
            constraints = cursor.fetchall()
            
            # Check constraint columns
            for constraint_name, _ in constraints:
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.constraint_column_usage
                    WHERE constraint_name = %s
                    ORDER BY column_name
                """, (constraint_name,))
                
                columns = [row[0] for row in cursor.fetchall()]
                if set(columns) == {"agent_id", "community_id"}:
                    cursor.close()
                    conn.close()
                    self.log_test("Community members unique constraint (GOTCHAS §8.1)", True)
                    return True
            
            cursor.close()
            conn.close()
            self.log_test("Community members unique constraint (GOTCHAS §8.1)", False, 
                         f"Found constraints: {constraints}")
            return False
            
        except Exception as e:
            self.log_test("Community members unique constraint (GOTCHAS §8.1)", False, 
                         f"Database error: {str(e)}")
            return False

    def test_pydantic_schemas(self):
        """Test Pydantic schema aliases and validation"""
        try:
            # Change to backend directory to import schemas
            sys.path.insert(0, '/app/backend')
            from src.schemas import (
                ProjectCreate, CommunityCreate,
                JoinProject, JoinCommunity,
                PostCreate, PostResponse,
                RoleDescriptions
            )
            
            # Test 1: ProjectCreate is alias of CommunityCreate
            test1_passed = ProjectCreate is CommunityCreate
            self.log_test("ProjectCreate is alias of CommunityCreate", test1_passed)
            
            # Test 2: JoinProject is alias of JoinCommunity  
            test2_passed = JoinProject is JoinCommunity
            self.log_test("JoinProject is alias of JoinCommunity", test2_passed)
            
            # Test 3: PostCreate.get_content() resolves body -> content fallback
            post_create = PostCreate(title="Test", body="Body content")
            content = post_create.get_content()
            test3_passed = content == "Body content"
            self.log_test("PostCreate.get_content() body fallback", test3_passed)
            
            # Test 4: PostResponse has backward-compat fields
            post_response_fields = PostResponse.model_fields
            has_project_id = "project_id" in post_response_fields
            has_author_id = "author_id" in post_response_fields
            test4_passed = has_project_id and has_author_id
            self.log_test("PostResponse backward-compat fields", test4_passed)
            
            # Test 5: RoleDescriptions validation
            try:
                # Test max 20 roles
                roles_dict = {f"role_{i}": f"desc_{i}" for i in range(21)}
                RoleDescriptions(roles=roles_dict)
                test5a_passed = False  # Should have raised error
            except ValueError:
                test5a_passed = True
            
            try:
                # Test role name length
                RoleDescriptions(roles={"a" * 51: "description"})
                test5b_passed = False  # Should have raised error
            except ValueError:
                test5b_passed = True
                
            try:
                # Test description length
                RoleDescriptions(roles={"role": "a" * 1001})
                test5c_passed = False  # Should have raised error
            except ValueError:
                test5c_passed = True
            
            test5_passed = test5a_passed and test5b_passed and test5c_passed
            self.log_test("RoleDescriptions validation", test5_passed)
            
            return test1_passed and test2_passed and test3_passed and test4_passed and test5_passed
            
        except Exception as e:
            self.log_test("Pydantic schemas test", False, f"Error: {str(e)}")
            return False

    def test_alembic_migration_status(self):
        """Test that Alembic migration was applied successfully"""
        try:
            db_url = "postgresql+psycopg2://united_agents:changeme@localhost:5432/united_agents"
            parsed = urlparse(db_url.replace("postgresql+psycopg2://", "postgresql://"))
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password
            )
            
            cursor = conn.cursor()
            
            # Check if alembic_version table exists and has current migration
            cursor.execute("""
                SELECT version_num FROM alembic_version 
                ORDER BY version_num DESC LIMIT 1
            """)
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                version = result[0]
                self.log_test("Alembic migration applied", True, f"Current version: {version}")
                return True
            else:
                self.log_test("Alembic migration applied", False, "No version found in alembic_version")
                return False
                
        except Exception as e:
            self.log_test("Alembic migration applied", False, f"Database error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all Session 2 tests"""
        print("🚀 Starting United Agents Session 2 Backend Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Session 1 tests (infrastructure)
        self.test_health_endpoint()
        self.test_api_v1_health_endpoint()
        self.test_database_connectivity()
        self.test_backend_port_accessibility()
        
        # Session 2 tests (database & schemas)
        self.test_database_tables_exist()
        self.test_agents_table_security_fix()
        self.test_community_members_unique_constraint()
        self.test_pydantic_schemas()
        self.test_alembic_migration_status()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All Session 2 tests passed!")
            return True
        else:
            print("⚠️  Some Session 2 tests failed")
            return False

def main():
    """Main test runner"""
    tester = UnitedAgentsSession2Tester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())