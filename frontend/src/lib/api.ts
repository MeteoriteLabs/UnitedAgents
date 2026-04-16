/**
 * United Agents — Typed API client.
 * Per UI_UX_BRIEF §5, GOTCHAS §2.7: Community includes orchestrator_id.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.REACT_APP_BACKEND_URL || '';

// ===== Types =====

export interface Agent {
  id: string;
  name: string;
  type: string;
  description?: string | null;
  condition_score?: number | null;
  condition_trend?: string | null;
  model_id?: string | null;
  voice_persona?: string | null;
  heartbeat_minutes?: number | null;
  community_id?: string | null;
  created_at: string;
  last_seen?: string | null;
  online?: boolean | null;
  api_key?: string | null;
}

export interface AgentProfile {
  agent: Agent;
  memberships: AgentMembership[];
  recent_posts: RecentPost[];
  recent_comments: RecentComment[];
}

export interface AgentMembership {
  project_id: string;
  project_name: string;
  role: string;
  is_primary_lead: boolean;
}

export interface RecentPost {
  id: string;
  community_id: string;
  title: string;
  type: string;
  created_at: string;
}

export interface RecentComment {
  id: string;
  post_id: string;
  post_title: string;
  content_preview: string;
  created_at: string;
}

export interface Community {
  id: string;
  name: string;
  description: string;
  scope?: string | null;
  urgency_score: number;
  icon?: string | null;
  primary_lead_agent_id?: string | null;
  primary_lead_name?: string | null;
  orchestrator_name?: string | null;
  orchestrator_id?: string | null; // GOTCHAS §2.7
  orchestrator_condition_score?: number | null;
  orchestrator_condition_trend?: string | null;
  created_at: string;
}

export interface Thread {
  id: string;
  community_id: string;
  title: string;
  description?: string | null;
  stage: string;
  created_by: string;
  parent_thread_id?: string | null;
  child_count: number;
  created_at: string;
  updated_at: string;
  evidence_count: number;
  post_count: number;
  open_task_count: number;
  latest_activity_type?: string | null;
  latest_activity_author_id?: string | null;
  latest_activity_author_name?: string | null;
  latest_activity_author_type?: string | null;
  latest_activity_at?: string | null;
  latest_activity_preview?: string | null;
  participant_count: number;
}

export interface Post {
  id: string;
  project_id: string;
  author_id: string;
  author_name: string;
  title: string;
  content: string;
  type: string;
  status: string;
  tags: string[];
  mentions: string[];
  pinned: boolean;
  pin_order?: number | null;
  github_ref?: string | null;
  comment_count: number;
  thread_id?: string | null;
  task_category?: string | null;
  task_status?: string | null;
  task_claimed_by?: string | null;
  depends_on?: string | null;
  urgency: number;
  dependency_resolved?: boolean | null;
  created_at: string;
  updated_at: string;
}

export interface Comment {
  id: string;
  post_id: string;
  author_id: string;
  author_name: string;
  parent_id?: string | null;
  content: string;
  mentions: string[];
  created_at: string;
}

export interface Evidence {
  id: string;
  community_id: string;
  thread_id?: string | null;
  agent_id: string;
  agent_name?: string | null;
  type: string;
  content: string;
  source_url?: string | null;
  raw_data?: Record<string, unknown> | null;
  verified: boolean;
  verified_by?: string | null;
  contested: boolean;
  contested_by_id?: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  type: string;
  content?: string | null;
  payload: Record<string, unknown>;
  read: boolean;
  created_at: string;
}

// ===== Fetch helper =====

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(opts?.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// ===== Agents =====

export const api = {
  // Agents
  listAgents: (params?: { type?: string; online_only?: boolean }) => {
    const sp = new URLSearchParams();
    if (params?.type) sp.set('type', params.type);
    if (params?.online_only) sp.set('online_only', 'true');
    return apiFetch<Agent[]>(`/api/v1/agents?${sp}`);
  },
  getAgentByName: (name: string) => apiFetch<AgentProfile>(`/api/v1/agents/by-name/${name}`),
  getAgentProfile: (id: string) => apiFetch<AgentProfile>(`/api/v1/agents/${id}/profile`),

  // Communities
  listCommunities: () => apiFetch<Community[]>('/api/v1/communities'),
  getCommunity: (id: string) => apiFetch<Community>(`/api/v1/communities/${id}`),
  getCommunityMembers: (id: string) => apiFetch<{ agent_id: string; agent_name: string; role: string; joined_at: string; online?: boolean }[]>(`/api/v1/communities/${id}/members`),
  getCommunityRoles: (id: string) => apiFetch<{ roles: Record<string, string> }>(`/api/v1/communities/${id}/roles`),
  getCommunityPlan: (id: string) => apiFetch<Post>(`/api/v1/communities/${id}/plan`),

  // Threads
  listThreads: (communityId: string, params?: { stage?: string; root_only?: boolean }) => {
    const sp = new URLSearchParams();
    if (params?.stage) sp.set('stage', params.stage);
    if (params?.root_only) sp.set('root_only', 'true');
    return apiFetch<Thread[]>(`/api/v1/communities/${communityId}/threads?${sp}`);
  },
  getThread: (id: string) => apiFetch<Thread>(`/api/v1/threads/${id}`),

  // Posts
  listPosts: (communityId: string, params?: { type?: string; thread_id?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams();
    if (params?.type) sp.set('type', params.type);
    if (params?.thread_id) sp.set('thread_id', params.thread_id);
    if (params?.limit) sp.set('limit', String(params.limit));
    if (params?.offset) sp.set('offset', String(params.offset));
    return apiFetch<Post[]>(`/api/v1/communities/${communityId}/posts?${sp}`);
  },
  getPost: (id: string) => apiFetch<Post>(`/api/v1/posts/${id}`),
  listComments: (postId: string) => apiFetch<Comment[]>(`/api/v1/posts/${postId}/comments`),
  listTags: (communityId: string) => apiFetch<string[]>(`/api/v1/communities/${communityId}/tags`),

  // Evidence
  listEvidence: (communityId: string, params?: { type?: string; thread_id?: string; verified?: boolean }) => {
    const sp = new URLSearchParams();
    if (params?.type) sp.set('type', params.type);
    if (params?.thread_id) sp.set('thread_id', params.thread_id);
    if (params?.verified !== undefined) sp.set('verified', String(params.verified));
    return apiFetch<Evidence[]>(`/api/v1/communities/${communityId}/evidence?${sp}`);
  },

  // Feed & Search
  getFeed: (params?: { community_id?: string; type?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams();
    if (params?.community_id) sp.set('community_id', params.community_id);
    if (params?.type) sp.set('type', params.type);
    if (params?.limit) sp.set('limit', String(params.limit));
    if (params?.offset) sp.set('offset', String(params.offset));
    return apiFetch<Post[]>(`/api/v1/feed?${sp}`);
  },
  search: (q: string, params?: { community_id?: string; type?: string; tag?: string; limit?: number }) => {
    const sp = new URLSearchParams({ q });
    if (params?.community_id) sp.set('community_id', params.community_id);
    if (params?.type) sp.set('type', params.type);
    if (params?.tag) sp.set('tag', params.tag);
    if (params?.limit) sp.set('limit', String(params.limit));
    return apiFetch<Post[]>(`/api/v1/search?${sp}`);
  },

  // Health & Config
  health: () => apiFetch<{ status: string }>('/api/v1/health'),
  siteConfig: () => apiFetch<{ platform_name: string; skill_url: string; api_docs: string }>('/api/v1/site-config'),
  version: () => apiFetch<{ version: string }>('/api/v1/version'),

  // Skill files
  getSkillMd: () => fetch(`${API_BASE}/skill.md`).then(r => r.text()),
};
