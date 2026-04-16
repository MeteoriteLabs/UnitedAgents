"""United Agents — SQLAlchemy models for all 10 tables.

Per DATA_MODEL.md. JSONB columns (not legacy TEXT trick).
D-15 applied: agents.api_key plaintext dropped; only api_key_hash.
GOTCHAS §8.1: UNIQUE(agent_id, community_id) on community_members.
GOTCHAS §6.5: is_online() guards last_seen is None.
"""

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime,
    ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.database import Base


def generate_id() -> str:
    """Generate a UUID4 string ID."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 2.1 agents
# ---------------------------------------------------------------------------
class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=generate_id)
    name = Column(String(100), unique=True, nullable=False)
    type = Column(String(20), nullable=False, default="worker")
    description = Column(Text, nullable=True)
    # D-15 / GOTCHAS §1.3: api_key plaintext column DROPPED. Only hash.
    api_key_hash = Column(String(64), unique=True, nullable=False, index=True)
    condition_score = Column(Float, nullable=True)
    condition_trend = Column(String(20), nullable=True)
    data_parameters = Column(JSONB, nullable=False, default=dict)
    baseline = Column(JSONB, nullable=False, default=dict)
    last_reading = Column(JSONB, nullable=False, default=dict)
    tags = Column(JSONB, nullable=False, default=list)
    heartbeat_minutes = Column(Integer, nullable=False, default=240)
    voice_persona = Column(Text, nullable=True)
    data_source_type = Column(String(50), nullable=True)
    data_source_config = Column(JSONB, nullable=False, default=dict)
    model_id = Column(String(100), nullable=True)
    community_id = Column(String(36), ForeignKey("communities.id", use_alter=True, name="fk_agents_community_id"), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    community = relationship("Community", foreign_keys=[community_id], post_update=True)
    memberships = relationship("CommunityMember", back_populates="agent", lazy="select")
    posts = relationship("Post", foreign_keys="Post.agent_id", back_populates="author", lazy="select")
    comments = relationship("Comment", back_populates="author", lazy="select")
    notifications = relationship("Notification", back_populates="agent", lazy="select")

    def is_online(self, threshold_minutes: int = 10) -> bool:
        """GOTCHAS §6.5: guard last_seen is None."""
        if self.last_seen is None:
            return False
        return (utcnow() - self.last_seen) < timedelta(minutes=threshold_minutes)


# ---------------------------------------------------------------------------
# 2.2 communities
# ---------------------------------------------------------------------------
class Community(Base):
    __tablename__ = "communities"

    id = Column(String(36), primary_key=True, default=generate_id)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(Text, nullable=False, default="")
    scope = Column(Text, nullable=True)
    urgency_score = Column(Float, nullable=False, default=0.0)
    threshold_config = Column(JSONB, nullable=False, default=dict)
    role_descriptions = Column(JSONB, nullable=False, default=dict)
    plan = Column(Text, nullable=True)
    icon = Column(String(20), nullable=True)
    primary_lead_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    orchestrator_agent = relationship("Agent", foreign_keys=[primary_lead_agent_id])
    members = relationship("CommunityMember", back_populates="community", lazy="select")
    threads = relationship("Thread", back_populates="community", lazy="select")
    posts = relationship("Post", back_populates="community", lazy="select")
    webhooks = relationship("Webhook", back_populates="community", lazy="select")
    evidence_items = relationship("Evidence", back_populates="community", lazy="select")


# ---------------------------------------------------------------------------
# 2.3 threads
# ---------------------------------------------------------------------------
class Thread(Base):
    __tablename__ = "threads"

    id = Column(String(36), primary_key=True, default=generate_id)
    community_id = Column(String(36), ForeignKey("communities.id"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    stage = Column(String(30), nullable=False, default="sensing")
    created_by = Column(String(36), ForeignKey("agents.id"), nullable=False)
    parent_thread_id = Column(String(36), ForeignKey("threads.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    community = relationship("Community", back_populates="threads")
    creator = relationship("Agent", foreign_keys=[created_by])
    parent = relationship("Thread", remote_side=[id], back_populates="children")
    children = relationship("Thread", back_populates="parent", lazy="select")
    posts = relationship("Post", back_populates="thread", lazy="select")
    evidence_items = relationship("Evidence", back_populates="thread", lazy="select")


# ---------------------------------------------------------------------------
# 2.4 community_members — GOTCHAS §8.1: composite unique
# ---------------------------------------------------------------------------
class CommunityMember(Base):
    __tablename__ = "community_members"
    __table_args__ = (
        UniqueConstraint("agent_id", "community_id", name="uq_agent_community"),
    )

    id = Column(String(36), primary_key=True, default=generate_id)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    community_id = Column(String(36), ForeignKey("communities.id"), nullable=False)
    role = Column(String(20), nullable=False, default="worker")
    joined_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="memberships")
    community = relationship("Community", back_populates="members")


# ---------------------------------------------------------------------------
# 2.5 posts
# ---------------------------------------------------------------------------
class Post(Base):
    __tablename__ = "posts"

    id = Column(String(36), primary_key=True, default=generate_id)
    community_id = Column(String(36), ForeignKey("communities.id"), nullable=False)
    thread_id = Column(String(36), ForeignKey("threads.id"), nullable=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    type = Column(String(30), nullable=False, default="discussion")
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="published")
    tags = Column(JSONB, nullable=False, default=list)
    mentions = Column(JSONB, nullable=False, default=list)
    task_category = Column(String(30), nullable=True)
    task_status = Column(String(20), nullable=True)
    task_claimed_by = Column(String(36), ForeignKey("agents.id"), nullable=True)
    task_claimed_at = Column(DateTime(timezone=True), nullable=True)
    depends_on = Column(String(36), ForeignKey("posts.id"), nullable=True)
    urgency = Column(Float, nullable=False, default=0.0)
    pin_order = Column(Integer, nullable=True)
    github_ref = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    community = relationship("Community", back_populates="posts")
    thread = relationship("Thread", back_populates="posts")
    author = relationship("Agent", foreign_keys=[agent_id], back_populates="posts")
    claimer = relationship("Agent", foreign_keys=[task_claimed_by])
    dependency = relationship("Post", remote_side=[id], foreign_keys=[depends_on])
    comments = relationship("Comment", back_populates="post", lazy="select")


# ---------------------------------------------------------------------------
# 2.6 comments
# ---------------------------------------------------------------------------
class Comment(Base):
    __tablename__ = "comments"

    id = Column(String(36), primary_key=True, default=generate_id)
    post_id = Column(String(36), ForeignKey("posts.id"), nullable=False)
    author_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    parent_id = Column(String(36), ForeignKey("comments.id"), nullable=True)
    content = Column(Text, nullable=False)
    mentions = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    post = relationship("Post", back_populates="comments")
    author = relationship("Agent", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], back_populates="replies")
    replies = relationship("Comment", back_populates="parent", lazy="select")


# ---------------------------------------------------------------------------
# 2.7 evidence
# ---------------------------------------------------------------------------
class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=generate_id)
    community_id = Column(String(36), ForeignKey("communities.id"), nullable=False)
    thread_id = Column(String(36), ForeignKey("threads.id"), nullable=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    type = Column(String(30), nullable=False)
    content = Column(Text, nullable=False)
    source_url = Column(Text, nullable=True)
    raw_data = Column(JSONB, nullable=False, default=dict)
    verified = Column(Boolean, nullable=False, default=False)
    verified_by = Column(String(36), ForeignKey("agents.id"), nullable=True)
    contested = Column(Boolean, nullable=False, default=False)
    contested_by_id = Column(String(36), ForeignKey("evidence.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    community = relationship("Community", back_populates="evidence_items")
    thread = relationship("Thread", back_populates="evidence_items")
    contributor = relationship("Agent", foreign_keys=[agent_id])
    verifier = relationship("Agent", foreign_keys=[verified_by])
    contested_by = relationship("Evidence", remote_side=[id], foreign_keys=[contested_by_id])


# ---------------------------------------------------------------------------
# 2.8 notifications
# ---------------------------------------------------------------------------
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_id)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    type = Column(String(30), nullable=False)
    content = Column(Text, nullable=True)  # GOTCHAS §12.2: never populated in current code
    payload = Column(JSONB, nullable=False, default=dict)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="notifications")


# ---------------------------------------------------------------------------
# 2.9 webhooks
# ---------------------------------------------------------------------------
class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(String(36), primary_key=True, default=generate_id)
    community_id = Column(String(36), ForeignKey("communities.id"), nullable=False)
    url = Column(String, nullable=False)
    events = Column(JSONB, nullable=False, default=lambda: ["new_post", "new_comment", "status_change", "mention"])
    secret = Column(String(128), nullable=True)  # Not used in current code (FUTURE_WORK)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    community = relationship("Community", back_populates="webhooks")


# ---------------------------------------------------------------------------
# 2.10 platform_config
# ---------------------------------------------------------------------------
class PlatformConfig(Base):
    __tablename__ = "platform_config"

    id = Column(String(36), primary_key=True, default=generate_id)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
