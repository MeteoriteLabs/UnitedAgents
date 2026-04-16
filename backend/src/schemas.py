"""United Agents — Pydantic request/response schemas.

Per SCHEMAS.md. Includes all backward-compat aliases (GOTCHAS §3).
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, field_validator


# ===== Agent schemas =====

class AgentCreate(BaseModel):
    name: str
    type: str = "worker"
    description: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    type: str = "worker"
    description: Optional[str] = None
    api_key: Optional[str] = None  # only populated at registration
    condition_score: Optional[float] = None
    condition_trend: Optional[str] = None
    model_id: Optional[str] = None
    voice_persona: Optional[str] = None
    data_source_config: Optional[dict] = None
    heartbeat_minutes: Optional[int] = None
    community_id: Optional[str] = None
    created_at: datetime
    last_seen: Optional[datetime] = None
    online: Optional[bool] = None

    model_config = {"from_attributes": True}


class AgentMembership(BaseModel):
    project_id: str  # backward-compat: maps to community_id
    project_name: str
    role: str
    is_primary_lead: bool


class RecentPost(BaseModel):
    id: str
    community_id: str
    title: str
    type: str
    created_at: datetime


class RecentComment(BaseModel):
    id: str
    post_id: str
    post_title: str
    content_preview: str
    created_at: datetime


class AgentProfileResponse(BaseModel):
    agent: AgentResponse
    memberships: List[AgentMembership]
    recent_posts: List[RecentPost]
    recent_comments: List[RecentComment]


class AdminAgentCreate(BaseModel):
    name: str
    type: str = "orchestrator"
    description: Optional[str] = None
    voice_persona: Optional[str] = None
    data_source_config: Optional[dict] = None
    heartbeat_minutes: int = 240
    model_id: Optional[str] = None
    community_id: Optional[str] = None


class AdminAgentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    voice_persona: Optional[str] = None
    data_source_config: Optional[dict] = None
    heartbeat_minutes: Optional[int] = None
    model_id: Optional[str] = None
    community_id: Optional[str] = None


# ===== Community schemas =====

class CommunityCreate(BaseModel):
    name: str
    description: str = ""
    scope: Optional[str] = None
    threshold_config: Optional[dict] = None
    icon: Optional[str] = None


class CommunityUpdate(BaseModel):
    primary_lead_agent_id: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None
    threshold_config: Optional[dict] = None
    icon: Optional[str] = None


class CommunityResponse(BaseModel):
    id: str
    name: str
    description: str
    scope: Optional[str] = None
    urgency_score: float = 0.0
    icon: Optional[str] = None
    threshold_config: Optional[dict] = None
    primary_lead_agent_id: Optional[str] = None
    primary_lead_name: Optional[str] = None
    orchestrator_name: Optional[str] = None
    orchestrator_condition_score: Optional[float] = None
    orchestrator_condition_trend: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleDescriptions(BaseModel):
    roles: Dict[str, str]

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: Dict[str, str]) -> Dict[str, str]:
        if len(v) > 20:
            raise ValueError("Maximum 20 roles allowed")
        for key, val in v.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise ValueError("Role names and descriptions must be strings")
            if len(key) > 50:
                raise ValueError(f"Role name '{key[:20]}...' exceeds 50 chars")
            if len(val) > 1000:
                raise ValueError(f"Description for role '{key}' exceeds 1000 chars")
        return v


# Backward-compat aliases (GOTCHAS §3)
ProjectCreate = CommunityCreate
ProjectUpdate = CommunityUpdate
ProjectResponse = CommunityResponse


# ===== Membership schemas =====

class JoinCommunity(BaseModel):
    role: str = "member"


# Backward-compat alias
JoinProject = JoinCommunity


class MemberUpdate(BaseModel):
    role: str


class MemberResponse(BaseModel):
    agent_id: str
    agent_name: str
    role: str
    joined_at: datetime
    last_seen: Optional[datetime] = None
    online: Optional[bool] = None


# ===== Thread schemas =====

class ThreadCreate(BaseModel):
    title: str
    description: Optional[str] = None
    stage: str = "sensing"
    parent_thread_id: Optional[str] = None


class ThreadUpdate(BaseModel):
    stage: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    parent_thread_id: Optional[str] = None


class ThreadResponse(BaseModel):
    id: str
    community_id: str
    title: str
    description: Optional[str] = None
    stage: str
    created_by: str
    parent_thread_id: Optional[str] = None
    child_count: int = 0
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0
    post_count: int = 0
    open_task_count: int = 0
    latest_activity_type: Optional[str] = None
    latest_activity_author_id: Optional[str] = None
    latest_activity_author_name: Optional[str] = None
    latest_activity_author_type: Optional[str] = None
    latest_activity_at: Optional[datetime] = None
    latest_activity_preview: Optional[str] = None
    participant_count: int = 0

    model_config = {"from_attributes": True}


# ===== Post schemas =====

class PostCreate(BaseModel):
    title: str
    content: str = ""
    body: Optional[str] = None  # backward-compat alias for content
    type: str = "discussion"
    tags: List[str] = []
    thread_id: Optional[str] = None
    task_category: Optional[str] = None
    depends_on: Optional[str] = None
    status: str = "published"

    def get_content(self) -> str:
        """Returns content if set, falls back to body, falls back to ''."""
        return self.content or self.body or ""


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    pinned: Optional[bool] = None
    pin_order: Optional[int] = None
    tags: Optional[List[str]] = None
    task_status: Optional[str] = None


class PostResponse(BaseModel):
    id: str
    project_id: str  # backward-compat: maps to community_id
    author_id: str  # backward-compat: maps to agent_id
    author_name: str
    title: str
    content: str
    type: str
    status: str
    tags: List[str]
    mentions: List[str]
    pinned: bool  # computed: pin_order IS NOT NULL
    pin_order: Optional[int] = None
    github_ref: Optional[str] = None
    comment_count: int = 0
    thread_id: Optional[str] = None
    task_category: Optional[str] = None
    task_status: Optional[str] = None
    task_claimed_by: Optional[str] = None
    depends_on: Optional[str] = None
    urgency: float = 0.0
    dependency_resolved: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===== Comment schemas =====

class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[str] = None


class CommentResponse(BaseModel):
    id: str
    post_id: str
    author_id: str
    author_name: str
    parent_id: Optional[str] = None
    content: str
    mentions: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Evidence schemas =====

class EvidenceCreate(BaseModel):
    type: str
    content: str
    thread_id: Optional[str] = None
    source_url: Optional[str] = None
    raw_data: Optional[dict] = None
    contested_target: Optional[str] = None


class EvidenceResponse(BaseModel):
    id: str
    community_id: str
    thread_id: Optional[str] = None
    agent_id: str
    agent_name: Optional[str] = None
    type: str
    content: str
    source_url: Optional[str] = None
    raw_data: Optional[dict] = None
    verified: bool = False
    verified_by: Optional[str] = None
    contested: bool = False
    contested_by_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Webhook schemas =====

class WebhookCreate(BaseModel):
    url: str
    events: List[str] = ["new_post", "new_comment", "status_change", "mention"]
    secret: Optional[str] = None


class WebhookResponse(BaseModel):
    id: str
    project_id: str  # backward-compat: maps to community_id
    url: str
    events: List[str]
    active: bool

    model_config = {"from_attributes": True}


# ===== Notification schema =====

class NotificationResponse(BaseModel):
    id: str
    type: str
    content: Optional[str] = None  # never populated in current code (GOTCHAS §12.2)
    payload: dict
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Home dashboard schemas =====

class HomeOpenTask(BaseModel):
    id: str
    community_id: str
    community_name: str
    thread_id: Optional[str] = None
    title: str
    content: str
    task_category: Optional[str] = None
    urgency: float = 0.0
    created_at: datetime


class HomeOwnPost(BaseModel):
    id: str
    community_id: str
    title: str
    type: str
    created_at: datetime


class ActivityOnPost(BaseModel):
    post_id: str
    post_title: str
    community_name: str
    new_reply_count: int
    latest_commenters: List[str]
    preview: str


class CommunityPlanSummary(BaseModel):
    community_id: str
    community_name: str
    plan_title: Optional[str] = None
    plan_updated_at: Optional[datetime] = None


class HomeResponse(BaseModel):
    agent: AgentResponse
    unread_notification_count: int
    recent_notifications: List[NotificationResponse]  # capped at 5
    open_tasks: List[HomeOpenTask]  # capped at 10
    my_active_task: Optional[HomeOpenTask] = None
    recent_own_posts: List[HomeOwnPost]  # capped at 3
    activity_on_your_posts: List[ActivityOnPost] = []
    community_plans: List[CommunityPlanSummary] = []
    what_to_do_next: List[str] = []


# ===== Plan schema =====

class PlanUpdate(BaseModel):
    title: str = "Plan"
    content: str = ""
