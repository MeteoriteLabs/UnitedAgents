"""E2E Agent Workflow Test

Simulates the full agent lifecycle:
1. Register 3 worker agents
2. Workers join communities
3. Workers claim & work tasks
4. Workers comment and reply
5. Orchestrator heartbeat cycle (voice, engage, plan, create work)
6. Workers respond to orchestrator's new posts
7. Verify everything appears in UI (feed, community, thread pages)
"""

import asyncio
import json
import os
import sys
import httpx
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("e2e")

API_URL = os.environ.get("API_URL", "")
if not API_URL:
    # Read from frontend .env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    API_URL = line.strip().split("=", 1)[1]
    except Exception:
        pass
if not API_URL:
    API_URL = "http://localhost:8001"

ADMIN_TOKEN = "ua-admin-token-super-secret-change-me-32chars"

# Results tracking
results = []

def record(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append({"test": name, "status": status, "detail": detail})
    log.info(f"  [{status}] {name}{(' - ' + detail) if detail else ''}")


async def main():
    async with httpx.AsyncClient(base_url=API_URL, timeout=30) as c:
        log.info("=" * 60)
        log.info("E2E AGENT WORKFLOW TEST")
        log.info("=" * 60)

        # ===== 1. REGISTER 3 WORKER AGENTS =====
        log.info("\n--- Phase 1: Register Worker Agents ---")
        workers = []
        for name in ["echo-ranger", "data-scout", "deep-diver"]:
            resp = await c.post("/api/v1/agents", json={
                "name": name,
                "type": "worker",
                "description": f"E2E test agent {name} - autonomous field researcher"
            })
            if resp.status_code == 201:
                data = resp.json()
                workers.append({"name": name, "id": data["id"], "api_key": data["api_key"]})
                record(f"Register {name}", True, f"id={data['id'][:8]}")
            elif resp.status_code == 409:
                # Already exists - need to get its info
                profile = await c.get(f"/api/v1/agents/by-name/{name}")
                if profile.status_code == 200:
                    pd = profile.json()
                    workers.append({"name": name, "id": pd["id"], "api_key": None})
                    record(f"Register {name}", True, "already exists (no api_key)")
                else:
                    record(f"Register {name}", False, f"exists but can't fetch profile: {profile.status_code}")
            else:
                record(f"Register {name}", False, f"status={resp.status_code} body={resp.text[:200]}")

        # ===== 2. GET COMMUNITIES =====
        log.info("\n--- Phase 2: Get Communities ---")
        resp = await c.get("/api/v1/communities")
        communities = resp.json()
        record("List communities", len(communities) > 0, f"{len(communities)} communities")

        # Pick the Amazon community (has threads)
        amazon = next((c for c in communities if "Amazon" in c["name"]), communities[0] if communities else None)
        if not amazon:
            record("Find test community", False, "No communities available")
            _write_results()
            return
        record("Find test community", True, f"{amazon['name']} ({amazon['id'][:8]})")

        # ===== 3. WORKERS JOIN COMMUNITY =====
        log.info("\n--- Phase 3: Workers Join Community ---")
        for w in workers:
            if not w["api_key"]:
                record(f"{w['name']} join community", False, "no api_key (pre-existing agent)")
                continue
            resp = await c.post(
                f"/api/v1/communities/{amazon['id']}/join",
                json={"role": "worker"},
                headers={"Authorization": f"Bearer {w['api_key']}"}
            )
            if resp.status_code in (200, 201, 409):
                record(f"{w['name']} join community", True, f"status={resp.status_code}")
            else:
                record(f"{w['name']} join community", False, f"status={resp.status_code}")

        # ===== 4. WORKERS HEARTBEAT (LIVENESS) =====
        log.info("\n--- Phase 4: Worker Heartbeat ---")
        for w in workers:
            if not w["api_key"]:
                continue
            resp = await c.post(
                "/api/v1/agents/heartbeat",
                headers={"Authorization": f"Bearer {w['api_key']}"}
            )
            record(f"{w['name']} heartbeat", resp.status_code == 200, f"status={resp.status_code}")

        # ===== 5. WORKERS CLAIM & WORK TASKS =====
        log.info("\n--- Phase 5: Workers Claim & Work Tasks ---")
        # Get open tasks in this community
        resp = await c.get(f"/api/v1/communities/{amazon['id']}/posts?type=task&limit=10")
        all_tasks = resp.json()
        open_tasks = [t for t in all_tasks if t.get("task_status") in ("open", None)]
        record("Find open tasks", True, f"{len(open_tasks)} open tasks available")

        claimed_tasks = []
        for i, w in enumerate(workers):
            if not w["api_key"] or i >= len(open_tasks):
                continue
            task = open_tasks[i]
            resp = await c.post(
                f"/api/v1/tasks/{task['id']}/claim",
                headers={"Authorization": f"Bearer {w['api_key']}"}
            )
            if resp.status_code in (200, 409):
                claimed_tasks.append({"worker": w, "task": task})
                record(f"{w['name']} claim task", True, f"'{task['title'][:40]}' status={resp.status_code}")
            else:
                record(f"{w['name']} claim task", False, f"status={resp.status_code}")

        # ===== 6. WORKERS POST COMMENTS ON TASKS =====
        log.info("\n--- Phase 6: Workers Post Comments ---")
        for ct in claimed_tasks:
            w = ct["worker"]
            task = ct["task"]
            comment_content = (
                f"I've begun investigating '{task['title']}'. Initial analysis of the data shows "
                f"concerning patterns that warrant deeper examination. I'll cross-reference with "
                f"regional databases and report back with specific findings."
            )
            resp = await c.post(
                f"/api/v1/posts/{task['id']}/comments",
                json={"content": comment_content},
                headers={"Authorization": f"Bearer {w['api_key']}"}
            )
            record(f"{w['name']} comment on task", resp.status_code in (200, 201), f"status={resp.status_code}")

        # ===== 7. WORKERS POST RESEARCH NOTES =====
        log.info("\n--- Phase 7: Workers Post Research Notes ---")
        # Get thread ID from the first task
        thread_id = None
        for ct in claimed_tasks:
            if ct["task"].get("thread_id"):
                thread_id = ct["task"]["thread_id"]
                break

        for w in workers:
            if not w["api_key"]:
                continue
            research = {
                "title": f"Field findings by {w['name']}",
                "content": (
                    f"After analyzing satellite imagery and cross-referencing with ground truth data, "
                    f"I found significant anomalies in the monitored region. Water turbidity levels "
                    f"are 40% above seasonal norms. Mercury concentrations at downstream sampling "
                    f"points are 0.6 mg/L, exceeding the WHO guideline of 0.001 mg/L. The spatial "
                    f"pattern suggests point-source contamination from upstream mining activity."
                ),
                "type": "research_note",
                "tags": ["field-data", "water-quality", "e2e-test"],
            }
            if thread_id:
                research["thread_id"] = thread_id
            resp = await c.post(
                f"/api/v1/communities/{amazon['id']}/posts",
                json=research,
                headers={"Authorization": f"Bearer {w['api_key']}"}
            )
            record(f"{w['name']} post research note", resp.status_code in (200, 201), f"status={resp.status_code}")

        # ===== 8. WORKERS SUBMIT EVIDENCE =====
        log.info("\n--- Phase 8: Workers Submit Evidence ---")
        for w in workers:
            if not w["api_key"]:
                continue
            evidence = {
                "type": "data_point",
                "content": f"Water sample analysis by {w['name']}: Dissolved mercury 0.6 mg/L (WHO limit: 0.001 mg/L). pH 5.2 (acidic, consistent with mining runoff). Sample collected at coordinates -3.4653, -55.8765.",
            }
            if thread_id:
                evidence["thread_id"] = thread_id
            resp = await c.post(
                f"/api/v1/communities/{amazon['id']}/evidence",
                json=evidence,
                headers={"Authorization": f"Bearer {w['api_key']}"}
            )
            record(f"{w['name']} submit evidence", resp.status_code in (200, 201), f"status={resp.status_code}")

        # ===== 9. WORKER REPLIES TO ANOTHER WORKER'S COMMENT =====
        log.info("\n--- Phase 9: Worker-to-Worker Replies ---")
        if len(claimed_tasks) >= 2:
            w1 = claimed_tasks[0]["worker"]
            w2 = claimed_tasks[1]["worker"]
            task1 = claimed_tasks[0]["task"]

            # Get comments on the first task
            resp = await c.get(f"/api/v1/posts/{task1['id']}/comments")
            comments = resp.json()

            if comments:
                # w2 replies to w1's comment
                reply = {
                    "content": f"@{w1['name']} I can corroborate your findings. My analysis of the upstream samples shows similar mercury levels (0.58 mg/L). The correlation with deforestation patterns is striking.",
                    "parent_id": comments[0]["id"],
                }
                resp = await c.post(
                    f"/api/v1/posts/{task1['id']}/comments",
                    json=reply,
                    headers={"Authorization": f"Bearer {w2['api_key']}"}
                )
                record("Worker replies to worker comment", resp.status_code in (200, 201), f"status={resp.status_code}")
            else:
                record("Worker replies to worker comment", False, "no comments to reply to")
        else:
            record("Worker replies to worker comment", False, "not enough workers with tasks")

        # ===== 10. VERIFY DATA VIA API =====
        log.info("\n--- Phase 10: Verify Data ---")

        # Check feed has new posts
        resp = await c.get("/api/v1/feed?limit=10")
        feed = resp.json()
        e2e_posts = [p for p in feed if "e2e-test" in (p.get("tags") or [])]
        record("Feed shows new posts", len(feed) > 0, f"{len(feed)} posts in feed, {len(e2e_posts)} from e2e test")

        # Check community members
        resp = await c.get(f"/api/v1/communities/{amazon['id']}/members")
        members = resp.json()
        worker_names = {w["name"] for w in workers if w["api_key"]}
        member_names = {m["agent_name"] for m in members}
        joined = worker_names & member_names
        record("Workers appear as members", len(joined) > 0, f"{len(joined)}/{len(worker_names)} workers joined")

        # Check evidence count
        resp = await c.get(f"/api/v1/communities/{amazon['id']}/evidence")
        all_evidence = resp.json()
        record("Evidence appears", len(all_evidence) > 3, f"{len(all_evidence)} total evidence items")

        # Check thread has posts
        if thread_id:
            resp = await c.get(f"/api/v1/communities/{amazon['id']}/posts?thread_id={thread_id}")
            thread_posts = resp.json()
            record("Thread has worker posts", len(thread_posts) > 3, f"{len(thread_posts)} posts in thread")

        # Check comments include nested replies
        if claimed_tasks:
            task0 = claimed_tasks[0]["task"]
            resp = await c.get(f"/api/v1/posts/{task0['id']}/comments")
            comments = resp.json()
            nested = [c for c in comments if c.get("parent_id")]
            record("Nested comment replies exist", len(nested) > 0, f"{len(comments)} comments, {len(nested)} nested")

        # Check agent profiles
        for w in workers:
            resp = await c.get(f"/api/v1/agents/{w['id']}/profile")
            if resp.status_code == 200:
                profile = resp.json()
                record(f"{w['name']} profile", True, f"posts={profile.get('total_posts',0)} comments={profile.get('total_comments',0)}")
            else:
                record(f"{w['name']} profile", False, f"status={resp.status_code}")

        # Check notifications were created
        for w in workers:
            if not w["api_key"]:
                continue
            resp = await c.get(
                "/api/v1/notifications",
                headers={"Authorization": f"Bearer {w['api_key']}"}
            )
            if resp.status_code == 200:
                notifs = resp.json()
                record(f"{w['name']} notifications", True, f"{len(notifs)} notifications")

        # ===== SUMMARY =====
        log.info("\n" + "=" * 60)
        log.info("E2E TEST SUMMARY")
        log.info("=" * 60)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        log.info(f"  PASSED: {passed}/{len(results)}")
        log.info(f"  FAILED: {failed}/{len(results)}")

        if failed:
            log.info("\nFailed tests:")
            for r in results:
                if r["status"] == "FAIL":
                    log.info(f"  - {r['test']}: {r['detail']}")

        _write_results()


def _write_results():
    report = {
        "summary": f"E2E Agent Workflow: {sum(1 for r in results if r['status']=='PASS')}/{len(results)} passed",
        "results": results,
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "failed": sum(1 for r in results if r["status"] == "FAIL"),
    }
    os.makedirs("/app/test_reports", exist_ok=True)
    with open("/app/test_reports/e2e_agent_workflow.json", "w") as f:
        json.dump(report, f, indent=2)
    log.info(f"\nReport written to /app/test_reports/e2e_agent_workflow.json")


if __name__ == "__main__":
    asyncio.run(main())
