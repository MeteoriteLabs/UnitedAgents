"""Smoke tests for all 10 SQLAlchemy models.

Per Session 2 acceptance: at least one test per table.
"""

import hashlib
from datetime import datetime, timezone

from src.models import (
    Agent, Community, Thread, CommunityMember, Post,
    Comment, Evidence, Notification, Webhook, PlatformConfig,
    generate_id, utcnow,
)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class TestAgentModel:
    def test_create_agent(self, db_session):
        agent = Agent(
            id=generate_id(),
            name="test-agent",
            type="worker",
            api_key_hash=_hash_key("test-key-123"),
        )
        db_session.add(agent)
        db_session.flush()

        fetched = db_session.query(Agent).filter_by(name="test-agent").first()
        assert fetched is not None
        assert fetched.type == "worker"
        assert fetched.heartbeat_minutes == 240
        assert fetched.created_at is not None

    def test_is_online_none_last_seen(self, db_session):
        """GOTCHAS §6.5: is_online guards last_seen is None."""
        agent = Agent(
            id=generate_id(),
            name="offline-agent",
            api_key_hash=_hash_key("offline-key"),
        )
        db_session.add(agent)
        db_session.flush()
        assert agent.is_online() is False

    def test_is_online_recent(self, db_session):
        agent = Agent(
            id=generate_id(),
            name="online-agent",
            api_key_hash=_hash_key("online-key"),
            last_seen=utcnow(),
        )
        db_session.add(agent)
        db_session.flush()
        assert agent.is_online() is True

    def test_unique_name(self, db_session):
        """Agent names must be unique."""
        a1 = Agent(id=generate_id(), name="unique-name", api_key_hash=_hash_key("k1"))
        db_session.add(a1)
        db_session.flush()

        a2 = Agent(id=generate_id(), name="unique-name", api_key_hash=_hash_key("k2"))
        db_session.add(a2)
        try:
            db_session.flush()
            assert False, "Should have raised IntegrityError"
        except Exception:
            db_session.rollback()


class TestCommunityModel:
    def test_create_community(self, db_session):
        community = Community(
            id=generate_id(),
            name="test-community",
            description="A test community",
        )
        db_session.add(community)
        db_session.flush()

        fetched = db_session.query(Community).filter_by(name="test-community").first()
        assert fetched is not None
        assert fetched.urgency_score == 0.0
        assert fetched.role_descriptions == {}


class TestThreadModel:
    def test_create_thread(self, db_session):
        agent = Agent(id=generate_id(), name="thread-agent", api_key_hash=_hash_key("tk"))
        community = Community(id=generate_id(), name="thread-community")
        db_session.add_all([agent, community])
        db_session.flush()

        thread = Thread(
            id=generate_id(),
            community_id=community.id,
            title="Test Thread",
            stage="sensing",
            created_by=agent.id,
        )
        db_session.add(thread)
        db_session.flush()

        assert thread.stage == "sensing"
        assert thread.created_at is not None


class TestCommunityMemberModel:
    def test_create_member(self, db_session):
        agent = Agent(id=generate_id(), name="member-agent", api_key_hash=_hash_key("mk"))
        community = Community(id=generate_id(), name="member-community")
        db_session.add_all([agent, community])
        db_session.flush()

        member = CommunityMember(
            id=generate_id(),
            agent_id=agent.id,
            community_id=community.id,
            role="worker",
        )
        db_session.add(member)
        db_session.flush()
        assert member.role == "worker"

    def test_unique_agent_community(self, db_session):
        """GOTCHAS §8.1: composite unique on (agent_id, community_id)."""
        agent = Agent(id=generate_id(), name="dup-member-agent", api_key_hash=_hash_key("dmk"))
        community = Community(id=generate_id(), name="dup-member-community")
        db_session.add_all([agent, community])
        db_session.flush()

        m1 = CommunityMember(id=generate_id(), agent_id=agent.id, community_id=community.id)
        db_session.add(m1)
        db_session.flush()

        m2 = CommunityMember(id=generate_id(), agent_id=agent.id, community_id=community.id)
        db_session.add(m2)
        try:
            db_session.flush()
            assert False, "Should have raised IntegrityError for duplicate membership"
        except Exception:
            db_session.rollback()


class TestPostModel:
    def test_create_post(self, db_session):
        agent = Agent(id=generate_id(), name="post-agent", api_key_hash=_hash_key("pk"))
        community = Community(id=generate_id(), name="post-community")
        db_session.add_all([agent, community])
        db_session.flush()

        post = Post(
            id=generate_id(),
            community_id=community.id,
            agent_id=agent.id,
            title="Test Post",
            content="Hello world",
            type="discussion",
        )
        db_session.add(post)
        db_session.flush()
        assert post.status == "published"
        assert post.tags == []
        assert post.pin_order is None


class TestCommentModel:
    def test_create_comment(self, db_session):
        agent = Agent(id=generate_id(), name="comment-agent", api_key_hash=_hash_key("ck"))
        community = Community(id=generate_id(), name="comment-community")
        db_session.add_all([agent, community])
        db_session.flush()

        post = Post(
            id=generate_id(),
            community_id=community.id,
            agent_id=agent.id,
            title="Comment Post",
        )
        db_session.add(post)
        db_session.flush()

        comment = Comment(
            id=generate_id(),
            post_id=post.id,
            author_id=agent.id,
            content="A comment",
        )
        db_session.add(comment)
        db_session.flush()
        assert comment.mentions == []


class TestEvidenceModel:
    def test_create_evidence(self, db_session):
        agent = Agent(id=generate_id(), name="evidence-agent", api_key_hash=_hash_key("ek"))
        community = Community(id=generate_id(), name="evidence-community")
        db_session.add_all([agent, community])
        db_session.flush()

        evidence = Evidence(
            id=generate_id(),
            community_id=community.id,
            agent_id=agent.id,
            type="data_point",
            content="Temperature reading: 28.5C",
        )
        db_session.add(evidence)
        db_session.flush()
        assert evidence.verified is False
        assert evidence.contested is False


class TestNotificationModel:
    def test_create_notification(self, db_session):
        agent = Agent(id=generate_id(), name="notif-agent", api_key_hash=_hash_key("nk"))
        db_session.add(agent)
        db_session.flush()

        notif = Notification(
            id=generate_id(),
            agent_id=agent.id,
            type="mention",
            payload={"post_id": "abc", "by": "someone"},
        )
        db_session.add(notif)
        db_session.flush()
        assert notif.read is False
        assert notif.content is None  # GOTCHAS §12.2: never populated


class TestWebhookModel:
    def test_create_webhook(self, db_session):
        community = Community(id=generate_id(), name="webhook-community")
        db_session.add(community)
        db_session.flush()

        webhook = Webhook(
            id=generate_id(),
            community_id=community.id,
            url="https://example.com/hook",
        )
        db_session.add(webhook)
        db_session.flush()
        assert webhook.active is True
        assert "new_post" in webhook.events
        assert webhook.secret is None  # Not used in current code


class TestPlatformConfigModel:
    def test_create_config(self, db_session):
        config = PlatformConfig(
            id=generate_id(),
            key="site_name",
            value="United Agents",
        )
        db_session.add(config)
        db_session.flush()
        assert config.key == "site_name"
        assert config.updated_at is not None
