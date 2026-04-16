#!/usr/bin/env python3
"""
Backend API Testing for United Agents - Session 14 Final E2E Verification
Comprehensive testing of all endpoints mentioned in requirements
"""

import requests
import sys
import json
from datetime import datetime

class UnitedAgentsSession14Tester:
    def __init__(self, base_url="https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_token = "ua-admin-token-super-secret-change-me-32chars"
        self.tests_run = 0
        self.tests_passed = 0
        self.community_ids = {}

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
                    return success, response.text
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

    def test_health_endpoints(self):
        """Test health check endpoints"""
        # Basic health check
        success1, _ = self.run_test("Health Check", "GET", "health", 200)
        
        # API health check
        success2, response = self.run_test("API Health Check", "GET", "api/v1/health", 200)
        if success2 and isinstance(response, dict):
            if response.get('status') == 'ok':
                print("   ✅ Health status OK")
            else:
                print(f"   ⚠️ Health status: {response.get('status')}")
        
        return success1 and success2

    def test_admin_endpoints(self):
        """Test admin endpoints"""
        admin_headers = {"X-Admin-Token": self.admin_token}
        
        # Admin validation
        success1, _ = self.run_test("Admin Validate", "GET", "api/v1/admin/validate", 200, headers=admin_headers)
        
        # Admin health dashboard
        success2, health_data = self.run_test("Admin Health Dashboard", "GET", "api/v1/admin/health", 200, headers=admin_headers)
        if success2 and isinstance(health_data, dict):
            agents = health_data.get('agents', {})
            communities = health_data.get('communities', 0)
            posts = health_data.get('posts', {})
            print(f"   📊 Agents: {agents.get('online', 0)}/{agents.get('total', 0)} online")
            print(f"   📊 Communities: {communities}")
            print(f"   📊 Posts: {posts.get('total', 0)} total, {posts.get('pending_approval', 0)} pending")
        
        # Admin list agents
        success3, _ = self.run_test("Admin List Agents", "GET", "api/v1/admin/agents", 200, headers=admin_headers)
        
        # Admin list communities
        success4, communities_data = self.run_test("Admin List Communities", "GET", "api/v1/admin/communities", 200, headers=admin_headers)
        if success4 and isinstance(communities_data, list):
            for community in communities_data:
                name = community.get('name', '')
                if 'Amazon River Basin' in name:
                    self.community_ids['amazon'] = community.get('id')
                elif 'Great Barrier Reef' in name:
                    self.community_ids['reef'] = community.get('id')
            print(f"   📍 Found community IDs: {self.community_ids}")
        
        # Admin list pending posts
        success5, _ = self.run_test("Admin List Pending Posts", "GET", "api/v1/admin/pending", 200, headers=admin_headers)
        
        return all([success1, success2, success3, success4, success5])

    def test_communities_api(self):
        """Test communities API endpoints"""
        # List communities
        success1, communities = self.run_test("List Communities", "GET", "api/v1/communities", 200)
        
        amazon_found = False
        reef_found = False
        if success1 and isinstance(communities, list):
            for community in communities:
                name = community.get('name', '')
                score = community.get('orchestrator_condition_score')
                if 'Amazon River Basin' in name:
                    amazon_found = True
                    if score == 38.0:
                        print(f"   ✅ Amazon condition score: {score}")
                    else:
                        print(f"   ⚠️ Amazon condition score: {score} (expected: 38.0)")
                elif 'Great Barrier Reef' in name:
                    reef_found = True
                    if score == 25.0:
                        print(f"   ✅ Reef condition score: {score}")
                    else:
                        print(f"   ⚠️ Reef condition score: {score} (expected: 25.0)")
        
        # Test individual community endpoints if we have IDs
        success2 = True
        success3 = True
        if self.community_ids.get('amazon'):
            success2, _ = self.run_test("Get Amazon Community", "GET", f"api/v1/communities/{self.community_ids['amazon']}", 200)
        
        if self.community_ids.get('reef'):
            success3, _ = self.run_test("Get Reef Community", "GET", f"api/v1/communities/{self.community_ids['reef']}", 200)
        
        return success1 and success2 and success3 and amazon_found and reef_found

    def test_feed_api(self):
        """Test feed API endpoints"""
        # Basic feed
        success1, feed_data = self.run_test("Feed API", "GET", "api/v1/feed", 200)
        
        post_types = {}
        if success1 and isinstance(feed_data, list):
            for post in feed_data:
                post_type = post.get('type', 'unknown')
                post_types[post_type] = post_types.get(post_type, 0) + 1
            print(f"   📝 Post types: {dict(post_types)}")
        
        # Feed with type filter
        success2, _ = self.run_test("Feed with Type Filter", "GET", "api/v1/feed?type=voice_update", 200)
        
        return success1 and success2

    def test_threads_and_posts(self):
        """Test threads and posts endpoints"""
        success_list = []
        
        # Test threads for each community
        for community_name, community_id in self.community_ids.items():
            success, threads_data = self.run_test(f"List Threads ({community_name})", "GET", f"api/v1/communities/{community_id}/threads", 200)
            success_list.append(success)
            
            if success and isinstance(threads_data, list):
                print(f"   📋 {community_name} threads: {len(threads_data)}")
                
                # Test posts for this community
                success_posts, posts_data = self.run_test(f"List Posts ({community_name})", "GET", f"api/v1/communities/{community_id}/posts", 200)
                success_list.append(success_posts)
                
                if success_posts and isinstance(posts_data, list):
                    print(f"   📄 {community_name} posts: {len(posts_data)}")
        
        return all(success_list)

    def test_evidence_and_tasks(self):
        """Test evidence and tasks endpoints"""
        success_list = []
        
        for community_name, community_id in self.community_ids.items():
            # Test evidence
            success_evidence, evidence_data = self.run_test(f"List Evidence ({community_name})", "GET", f"api/v1/communities/{community_id}/evidence", 200)
            success_list.append(success_evidence)
            
            if success_evidence and isinstance(evidence_data, list):
                print(f"   🔍 {community_name} evidence: {len(evidence_data)}")
            
            # Test tasks (posts with type=task)
            success_tasks, tasks_data = self.run_test(f"List Tasks ({community_name})", "GET", f"api/v1/communities/{community_id}/posts?type=task", 200)
            success_list.append(success_tasks)
            
            if success_tasks and isinstance(tasks_data, list):
                open_tasks = [t for t in tasks_data if t.get('task_status') in ['open', 'claimed']]
                print(f"   ✅ {community_name} open tasks: {len(open_tasks)}")
        
        return all(success_list)

    def test_skill_md_endpoint(self):
        """Test skill.md endpoint"""
        success, content = self.run_test("Skill.md Endpoint", "GET", "skill.md", 200)
        
        if success and isinstance(content, str):
            if "{BASE_URL}" in content:
                print("   ❌ Found {BASE_URL} placeholder - not substituted")
                return False
            elif "United Agents" in content:
                print("   ✅ Skill content loaded and substituted")
                return True
            else:
                print("   ⚠️ Skill content loaded but may be incomplete")
                return True
        
        return success

    def test_search_functionality(self):
        """Test search functionality"""
        # Test search for water-related posts
        success, search_results = self.run_test("Search for 'water'", "GET", "api/v1/feed?q=water", 200)
        
        if success and isinstance(search_results, list):
            print(f"   🔍 Search results for 'water': {len(search_results)} posts")
            return True
        
        return success

def main():
    print("🚀 Starting United Agents Backend API Testing - Session 14 Final E2E")
    print("Comprehensive testing of all required endpoints")
    print("=" * 70)
    
    tester = UnitedAgentsSession14Tester()
    
    # Test health endpoints
    print("\n💚 Testing Health Endpoints")
    print("-" * 40)
    health_success = tester.test_health_endpoints()
    
    # Test admin endpoints
    print("\n🔐 Testing Admin Endpoints")
    print("-" * 40)
    admin_success = tester.test_admin_endpoints()
    
    # Test communities API
    print("\n🌍 Testing Communities API")
    print("-" * 40)
    communities_success = tester.test_communities_api()
    
    # Test feed API
    print("\n📡 Testing Feed API")
    print("-" * 40)
    feed_success = tester.test_feed_api()
    
    # Test threads and posts
    print("\n📋 Testing Threads and Posts")
    print("-" * 40)
    threads_success = tester.test_threads_and_posts()
    
    # Test evidence and tasks
    print("\n🔍 Testing Evidence and Tasks")
    print("-" * 40)
    evidence_success = tester.test_evidence_and_tasks()
    
    # Test skill.md endpoint
    print("\n📄 Testing Skill.md Endpoint")
    print("-" * 40)
    skill_success = tester.test_skill_md_endpoint()
    
    # Test search functionality
    print("\n🔍 Testing Search Functionality")
    print("-" * 40)
    search_success = tester.test_search_functionality()
    
    # Print results
    print("\n" + "=" * 70)
    print(f"📊 Backend API Tests Summary - Session 14 Final E2E")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    # Component success summary
    components = {
        "Health Endpoints": health_success,
        "Admin Endpoints": admin_success,
        "Communities API": communities_success,
        "Feed API": feed_success,
        "Threads & Posts": threads_success,
        "Evidence & Tasks": evidence_success,
        "Skill.md": skill_success,
        "Search": search_success
    }
    
    print("\n📋 Component Status:")
    for component, status in components.items():
        status_icon = "✅" if status else "❌"
        print(f"   {status_icon} {component}")
    
    overall_success = all(components.values())
    
    if overall_success and success_rate >= 90:
        print("\n✅ All backend APIs working correctly for Session 14")
        return 0
    else:
        print("\n❌ Backend has issues that need attention")
        return 1

if __name__ == "__main__":
    sys.exit(main())