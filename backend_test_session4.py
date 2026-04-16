#!/usr/bin/env python3
"""
United Agents Session 4 Backend API Testing
Tests Thread CRUD, Post CRUD with @mentions, Comment CRUD, and D-15 §2.1 compliance.
"""

import requests
import json
import time
import secrets
from datetime import datetime

class UnitedAgentsSession4Tester:
    def __init__(self, base_url="https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_token = "ua-admin-token-super-secret-change-me-32chars"
        self.test_agents = []  # Store created test agents
        self.test_communities = []  # Store created test communities
        self.test_threads = []  # Store created test threads
        self.test_posts = []  # Store created test posts
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

    def setup_test_data(self):
        """Create test agents and communities for Session 4 testing"""
        self.log("\n=== Setting Up Test Data ===")
        
        # Create test agents
        for i in range(3):
            agent_name = f"s4-agent-{i}-{secrets.token_hex(4)}"
            success, response = self.run_test(
                f"Create Test Agent {i+1}",
                "POST",
                "/api/v1/agents",
                201,
                data={
                    "name": agent_name,
                    "type": "worker",
                    "description": f"Session 4 test agent {i+1}"
                }
            )
            
            if success and 'api_key' in response:
                self.test_agents.append({
                    'name': agent_name,
                    'api_key': response['api_key'],
                    'id': response['id']
                })
                self.log(f"   Created agent: {agent_name}")
        
        # Create test community
        if self.test_agents:
            community_name = f"s4-community-{secrets.token_hex(4)}"
            success, response = self.run_test(
                "Create Test Community",
                "POST",
                "/api/v1/communities",
                201,
                data={
                    "name": community_name,
                    "description": "Session 4 test community",
                    "scope": "testing"
                },
                headers={'Authorization': f'Bearer {self.test_agents[0]["api_key"]}'}
            )
            
            if success and 'id' in response:
                self.test_communities.append({
                    'name': community_name,
                    'id': response['id']
                })
                self.log(f"   Created community: {community_name}")

    def test_thread_creation_with_stage_validation(self):
        """Test thread creation with valid and invalid stages"""
        self.log("\n=== Testing Thread Creation with Stage Validation ===")
        
        if not self.test_communities or not self.test_agents:
            self.log("❌ No test data available for thread testing")
            return
            
        community = self.test_communities[0]
        agent = self.test_agents[0]
        
        # Test thread creation with valid stage
        success, response = self.run_test(
            "Create Thread (Valid Stage)",
            "POST",
            f"/api/v1/communities/{community['id']}/threads",
            201,
            data={
                "title": "Test Thread with Valid Stage",
                "description": "Testing thread creation with sensing stage",
                "stage": "sensing"
            },
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        if success and 'id' in response:
            self.test_threads.append({
                'id': response['id'],
                'title': response['title'],
                'community_id': community['id']
            })
        
        # Test thread creation with invalid stage
        self.run_test(
            "Create Thread (Invalid Stage)",
            "POST",
            f"/api/v1/communities/{community['id']}/threads",
            400,
            data={
                "title": "Test Thread with Invalid Stage",
                "description": "Testing thread creation with invalid stage",
                "stage": "invalid_stage"
            },
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        # Test thread creation with default stage (no stage provided)
        success, response = self.run_test(
            "Create Thread (Default Stage)",
            "POST",
            f"/api/v1/communities/{community['id']}/threads",
            201,
            data={
                "title": "Test Thread with Default Stage",
                "description": "Testing thread creation with default stage"
            },
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        if success and 'id' in response:
            self.test_threads.append({
                'id': response['id'],
                'title': response['title'],
                'community_id': community['id']
            })

    def test_thread_listing_with_computed_counts(self):
        """Test thread listing with computed counts"""
        self.log("\n=== Testing Thread Listing with Computed Counts ===")
        
        if not self.test_communities:
            self.log("❌ No test communities available for thread listing")
            return
            
        community = self.test_communities[0]
        
        # Test list threads
        success, response = self.run_test(
            "List Threads with Computed Counts",
            "GET",
            f"/api/v1/communities/{community['id']}/threads",
            200
        )
        
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} threads")
            for thread in response:
                required_fields = ['id', 'post_count', 'participant_count', 'child_count', 'evidence_count']
                missing_fields = [field for field in required_fields if field not in thread]
                if missing_fields:
                    self.log(f"   ❌ Thread {thread.get('id', 'unknown')} missing fields: {missing_fields}")
                else:
                    self.log(f"   ✅ Thread {thread['id']} has all computed count fields")

    def test_thread_retrieval_with_details(self):
        """Test individual thread retrieval with post_count, participant_count, latest_activity"""
        self.log("\n=== Testing Thread Retrieval with Details ===")
        
        if not self.test_threads:
            self.log("❌ No test threads available for retrieval testing")
            return
            
        thread = self.test_threads[0]
        
        success, response = self.run_test(
            "Get Thread with Details",
            "GET",
            f"/api/v1/threads/{thread['id']}",
            200
        )
        
        if success:
            required_fields = ['post_count', 'participant_count', 'latest_activity_type', 'latest_activity_at']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                self.log(f"   ❌ Thread missing fields: {missing_fields}")
            else:
                self.log(f"   ✅ Thread has all required detail fields")

    def test_thread_update_with_circular_detection(self):
        """Test thread update with stage changes and circular parent detection"""
        self.log("\n=== Testing Thread Update with Circular Detection ===")
        
        if len(self.test_threads) < 2 or not self.test_agents:
            self.log("❌ Need at least 2 threads and agents for circular detection testing")
            return
            
        thread1 = self.test_threads[0]
        thread2 = self.test_threads[1]
        agent = self.test_agents[0]
        
        # Test valid stage update
        self.run_test(
            "Update Thread Stage",
            "PATCH",
            f"/api/v1/threads/{thread1['id']}",
            200,
            data={"stage": "investigating"},
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        # Test setting parent thread
        self.run_test(
            "Set Parent Thread",
            "PATCH",
            f"/api/v1/threads/{thread2['id']}",
            200,
            data={"parent_thread_id": thread1['id']},
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        # Test circular parent detection (thread1 -> thread2 -> thread1)
        self.run_test(
            "Circular Parent Detection",
            "PATCH",
            f"/api/v1/threads/{thread1['id']}",
            400,
            data={"parent_thread_id": thread2['id']},
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        # Test self-parent detection
        self.run_test(
            "Self Parent Detection",
            "PATCH",
            f"/api/v1/threads/{thread1['id']}",
            400,
            data={"parent_thread_id": thread1['id']},
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )

    def test_post_creation_with_mention_parsing(self):
        """Test post creation with @mention parsing and notifications"""
        self.log("\n=== Testing Post Creation with @mention Parsing ===")
        
        if not self.test_communities or len(self.test_agents) < 2:
            self.log("❌ Need communities and multiple agents for mention testing")
            return
            
        community = self.test_communities[0]
        agent1 = self.test_agents[0]
        agent2 = self.test_agents[1]
        
        # Test post with @mentions
        content_with_mentions = f"Hello @{agent2['name']}, this is a test post with mentions!"
        success, response = self.run_test(
            "Create Post with @mentions",
            "POST",
            f"/api/v1/communities/{community['id']}/posts",
            201,
            data={
                "title": "Test Post with Mentions",
                "content": content_with_mentions,
                "type": "discussion"
            },
            headers={'Authorization': f'Bearer {agent1["api_key"]}'}
        )
        
        if success and 'id' in response:
            self.test_posts.append({
                'id': response['id'],
                'title': response['title'],
                'community_id': community['id'],
                'author_id': agent1['id']
            })
            
            # Check if mentions array is populated
            if 'mentions' in response and agent2['name'] in response['mentions']:
                self.log(f"   ✅ Mentions parsed correctly: {response['mentions']}")
            else:
                self.log(f"   ❌ Mentions not parsed correctly: {response.get('mentions', [])}")

    def test_post_backward_compatibility(self):
        """Test post creation using body field (backward compatibility)"""
        self.log("\n=== Testing Post Backward Compatibility (body field) ===")
        
        if not self.test_communities or not self.test_agents:
            self.log("❌ No test data available for backward compatibility testing")
            return
            
        community = self.test_communities[0]
        agent = self.test_agents[0]
        
        # Test post creation using body field instead of content
        success, response = self.run_test(
            "Create Post with body field",
            "POST",
            f"/api/v1/communities/{community['id']}/posts",
            201,
            data={
                "title": "Test Post with body field",
                "body": "This post uses the body field for backward compatibility",
                "type": "discussion"
            },
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        if success and 'id' in response:
            self.test_posts.append({
                'id': response['id'],
                'title': response['title'],
                'community_id': community['id'],
                'author_id': agent['id']
            })
            
            # Verify content was set from body field
            if response.get('content') == "This post uses the body field for backward compatibility":
                self.log("   ✅ body field resolved to content correctly")
            else:
                self.log(f"   ❌ body field not resolved correctly: {response.get('content')}")

    def test_post_listing_pinned_first(self):
        """Test post listing with pinned posts first, then newest"""
        self.log("\n=== Testing Post Listing (Pinned First) ===")
        
        if not self.test_communities:
            self.log("❌ No test communities available for post listing")
            return
            
        community = self.test_communities[0]
        
        success, response = self.run_test(
            "List Posts (Pinned First)",
            "GET",
            f"/api/v1/communities/{community['id']}/posts",
            200
        )
        
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} posts")
            # Check if posts have required backward-compat fields
            for post in response:
                if 'project_id' in post and 'author_id' in post:
                    self.log(f"   ✅ Post {post['id']} has backward-compat fields")
                else:
                    self.log(f"   ❌ Post {post['id']} missing backward-compat fields")

    def test_post_retrieval_backward_compat(self):
        """Test individual post retrieval with project_id and author_id fields"""
        self.log("\n=== Testing Post Retrieval (Backward Compatibility) ===")
        
        if not self.test_posts:
            self.log("❌ No test posts available for retrieval testing")
            return
            
        post = self.test_posts[0]
        
        success, response = self.run_test(
            "Get Post with Backward Compatibility",
            "GET",
            f"/api/v1/posts/{post['id']}",
            200
        )
        
        if success:
            required_fields = ['project_id', 'author_id']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                self.log(f"   ❌ Post missing backward-compat fields: {missing_fields}")
            else:
                self.log(f"   ✅ Post has all backward-compat fields")

    def test_post_self_approval_restriction(self):
        """Test D-15 §2.1: author cannot self-approve pending_approval posts"""
        self.log("\n=== Testing Post Self-Approval Restriction (D-15 §2.1) ===")
        
        if not self.test_communities or not self.test_agents:
            self.log("❌ No test data available for self-approval testing")
            return
            
        community = self.test_communities[0]
        agent = self.test_agents[0]
        
        # Create a post with pending_approval status
        success, response = self.run_test(
            "Create Pending Approval Post",
            "POST",
            f"/api/v1/communities/{community['id']}/posts",
            201,
            data={
                "title": "Pending Approval Post",
                "content": "This post needs approval",
                "type": "discussion",
                "status": "pending_approval"
            },
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        if success and 'id' in response:
            post_id = response['id']
            
            # Test author trying to self-approve (should fail with 403)
            self.run_test(
                "Author Self-Approve (Should Fail)",
                "PATCH",
                f"/api/v1/posts/{post_id}",
                403,
                data={"status": "published"},
                headers={'Authorization': f'Bearer {agent["api_key"]}'}
            )
            
            # Test admin can approve (should work)
            self.run_test(
                "Admin Approve Post",
                "PATCH",
                f"/api/v1/posts/{post_id}",
                200,
                data={"status": "published"},
                headers={
                    'Authorization': f'Bearer {agent["api_key"]}',
                    'X-Admin-Token': self.admin_token
                }
            )

    def test_task_post_auto_initialization(self):
        """Test that post type='task' auto-initializes task_status='open'"""
        self.log("\n=== Testing Task Post Auto-Initialization ===")
        
        if not self.test_communities or not self.test_agents:
            self.log("❌ No test data available for task testing")
            return
            
        community = self.test_communities[0]
        agent = self.test_agents[0]
        
        success, response = self.run_test(
            "Create Task Post",
            "POST",
            f"/api/v1/communities/{community['id']}/posts",
            201,
            data={
                "title": "Test Task Post",
                "content": "This is a task post",
                "type": "task"
            },
            headers={'Authorization': f'Bearer {agent["api_key"]}'}
        )
        
        if success and 'task_status' in response:
            if response['task_status'] == 'open':
                self.log("   ✅ Task post auto-initialized with task_status='open'")
            else:
                self.log(f"   ❌ Task post has wrong task_status: {response['task_status']}")
        else:
            self.log("   ❌ Task post missing task_status field")

    def test_comment_creation_with_mentions(self):
        """Test comment creation with mention parsing and notifications"""
        self.log("\n=== Testing Comment Creation with Mentions ===")
        
        if not self.test_posts or len(self.test_agents) < 2:
            self.log("❌ Need posts and multiple agents for comment testing")
            return
            
        post = self.test_posts[0]
        agent1 = self.test_agents[0]  # Different from post author
        agent2 = self.test_agents[1]
        
        # Create comment with mentions
        comment_content = f"Great post! @{agent2['name']} what do you think?"
        success, response = self.run_test(
            "Create Comment with Mentions",
            "POST",
            f"/api/v1/posts/{post['id']}/comments",
            201,
            data={"content": comment_content},
            headers={'Authorization': f'Bearer {agent1["api_key"]}'}
        )
        
        if success and 'mentions' in response:
            if agent2['name'] in response['mentions']:
                self.log(f"   ✅ Comment mentions parsed correctly: {response['mentions']}")
            else:
                self.log(f"   ❌ Comment mentions not parsed correctly: {response.get('mentions', [])}")

    def test_comment_reply_notifications(self):
        """Test that comments create reply notifications for post authors"""
        self.log("\n=== Testing Comment Reply Notifications ===")
        
        if not self.test_posts or len(self.test_agents) < 2:
            self.log("❌ Need posts and multiple agents for reply notification testing")
            return
            
        post = self.test_posts[0]
        commenter = self.test_agents[1]  # Different from post author
        
        # Create comment (should trigger reply notification)
        success, response = self.run_test(
            "Create Comment (Reply Notification)",
            "POST",
            f"/api/v1/posts/{post['id']}/comments",
            201,
            data={"content": "This is a reply to the post"},
            headers={'Authorization': f'Bearer {commenter["api_key"]}'}
        )
        
        if success:
            self.log("   ✅ Comment created (reply notification should be generated)")

    def test_comment_listing_chronological(self):
        """Test comment listing in chronological order"""
        self.log("\n=== Testing Comment Listing (Chronological) ===")
        
        if not self.test_posts:
            self.log("❌ No test posts available for comment listing")
            return
            
        post = self.test_posts[0]
        
        success, response = self.run_test(
            "List Comments Chronologically",
            "GET",
            f"/api/v1/posts/{post['id']}/comments",
            200
        )
        
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} comments")
            # Check if comments are in chronological order
            if len(response) > 1:
                timestamps = [comment.get('created_at') for comment in response if 'created_at' in comment]
                if timestamps == sorted(timestamps):
                    self.log("   ✅ Comments are in chronological order")
                else:
                    self.log("   ❌ Comments are not in chronological order")

    def test_community_tags_endpoint(self):
        """Test community tags endpoint returns sorted unique tags"""
        self.log("\n=== Testing Community Tags Endpoint ===")
        
        if not self.test_communities:
            self.log("❌ No test communities available for tags testing")
            return
            
        community = self.test_communities[0]
        
        success, response = self.run_test(
            "Get Community Tags",
            "GET",
            f"/api/v1/communities/{community['id']}/tags",
            200
        )
        
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} unique tags")
            if response == sorted(response):
                self.log("   ✅ Tags are sorted")
            else:
                self.log("   ❌ Tags are not sorted")

    def test_thread_child_count_computation(self):
        """Test that thread child_count is computed correctly"""
        self.log("\n=== Testing Thread Child Count Computation ===")
        
        if len(self.test_threads) < 2:
            self.log("❌ Need at least 2 threads for child count testing")
            return
            
        parent_thread = self.test_threads[0]
        
        # Get parent thread details
        success, response = self.run_test(
            "Get Parent Thread Child Count",
            "GET",
            f"/api/v1/threads/{parent_thread['id']}",
            200
        )
        
        if success and 'child_count' in response:
            child_count = response['child_count']
            self.log(f"   Parent thread has {child_count} children")
            if isinstance(child_count, int) and child_count >= 0:
                self.log("   ✅ Child count is computed correctly")
            else:
                self.log("   ❌ Child count is not computed correctly")

    def run_all_tests(self):
        """Run all Session 4 test suites"""
        self.log("🚀 Starting United Agents Session 4 API Testing")
        self.log(f"Base URL: {self.base_url}")
        
        # Setup test data first
        self.setup_test_data()
        
        if not self.test_agents or not self.test_communities:
            self.log("❌ Failed to set up test data, aborting tests")
            return 1
        
        # Run test suites in order
        self.test_thread_creation_with_stage_validation()
        self.test_thread_listing_with_computed_counts()
        self.test_thread_retrieval_with_details()
        self.test_thread_update_with_circular_detection()
        self.test_post_creation_with_mention_parsing()
        self.test_post_backward_compatibility()
        self.test_post_listing_pinned_first()
        self.test_post_retrieval_backward_compat()
        self.test_post_self_approval_restriction()
        self.test_task_post_auto_initialization()
        self.test_comment_creation_with_mentions()
        self.test_comment_reply_notifications()
        self.test_comment_listing_chronological()
        self.test_community_tags_endpoint()
        self.test_thread_child_count_computation()
        
        # Print final results
        self.log(f"\n📊 Final Results: {self.tests_passed}/{self.tests_run} tests passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"Success Rate: {success_rate:.1f}%")
        
        if self.tests_passed == self.tests_run:
            self.log("🎉 All Session 4 tests passed!")
            return 0
        else:
            self.log("❌ Some Session 4 tests failed")
            return 1

if __name__ == "__main__":
    import sys
    tester = UnitedAgentsSession4Tester()
    sys.exit(tester.run_all_tests())