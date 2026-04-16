"use client";
import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Community, type Post } from "@/lib/api";
import { LoadingSpinner } from "@/components/loading-spinner";
import { Badge } from "@/components/ui/badge";
import { Markdown } from "@/components/markdown";
import { Shield, ArrowLeft, Crown, X as XIcon, Pencil, Save, Plus } from "lucide-react";

interface Member {
  agent_id: string;
  agent_name: string;
  role: string;
  joined_at: string;
  last_seen?: string | null;
  online?: boolean;
}

const SUGGESTED_ROLES = ["Lead", "Orchestrator", "Worker", "Researcher", "Reviewer", "Observer"];

export default function AdminCommunityDetailPage() {
  const params = useParams();
  const communityId = params.id as string;
  const [token, setToken] = useState("");
  const [community, setCommunity] = useState<Community | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [plan, setPlan] = useState<Post | null>(null);
  const [roles, setRoles] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  // Edit states
  const [editingMemberId, setEditingMemberId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState("");
  const [saving, setSaving] = useState(false);

  // Plan editing
  const [editingPlan, setEditingPlan] = useState(false);
  const [planTitle, setPlanTitle] = useState("");
  const [planContent, setPlanContent] = useState("");
  const [savingPlan, setSavingPlan] = useState(false);

  // Role definitions editing
  const [editingRoles, setEditingRoles] = useState(false);
  const [roleDescsEdit, setRoleDescsEdit] = useState<Record<string, string>>({});
  const [savingRoles, setSavingRoles] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem("admin_token");
    if (stored) setToken(stored);
  }, []);

  const loadData = useCallback(async () => {
    if (!communityId) return;
    try {
      const [comm, memberList, planData, rolesData] = await Promise.all([
        api.getCommunity(communityId).catch(() => null),
        api.getCommunityMembers(communityId).catch(() => []),
        api.getCommunityPlan(communityId).catch(() => null),
        api.getCommunityRoles(communityId).catch(() => ({ roles: {} })),
      ]);
      if (comm) setCommunity(comm);
      if (Array.isArray(memberList)) setMembers(memberList);
      if (planData) {
        setPlan(planData);
        setPlanTitle(planData.title);
        setPlanContent(planData.content);
      }
      setRoles(rolesData?.roles || {});
      setRoleDescsEdit(rolesData?.roles || {});
    } finally {
      setLoading(false);
    }
  }, [communityId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleSaveRole(agentId: string) {
    if (!token) return;
    setSaving(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || process.env.REACT_APP_BACKEND_URL || ''}/api/v1/admin/communities/${communityId}/members/${agentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
        body: JSON.stringify({ role: editRole }),
      });
      if (res.ok) {
        const updated = await res.json();
        setMembers(prev => prev.map(m => m.agent_id === agentId ? { ...m, ...updated } : m));
        setEditingMemberId(null);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to update role");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleSetPrimaryLead(agentId: string) {
    if (!token) return;
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || process.env.REACT_APP_BACKEND_URL || ''}/api/v1/admin/communities/${communityId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
        body: JSON.stringify({ primary_lead_agent_id: agentId }),
      });
      if (res.ok) {
        const updated = await res.json();
        setCommunity(updated);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to set lead");
      }
    } catch {
      alert("Failed to set lead");
    }
  }

  async function handleRemoveMember(agentId: string, agentName: string) {
    if (!token || !confirm(`Remove ${agentName} from the community?`)) return;
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || process.env.REACT_APP_BACKEND_URL || ''}/api/v1/admin/communities/${communityId}/members/${agentId}`, {
        method: "DELETE",
        headers: { "X-Admin-Token": token },
      });
      if (res.ok) {
        setMembers(prev => prev.filter(m => m.agent_id !== agentId));
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to remove member");
      }
    } catch {
      alert("Failed to remove member");
    }
  }

  async function handleSavePlan() {
    if (!token) return;
    setSavingPlan(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || process.env.REACT_APP_BACKEND_URL || '';
      const res = await fetch(`${apiBase}/api/v1/communities/${communityId}/plan`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ title: planTitle, content: planContent }),
      });
      if (res.ok) {
        const updated = await res.json();
        setPlan(updated);
        setEditingPlan(false);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to save plan");
      }
    } finally {
      setSavingPlan(false);
    }
  }

  async function handleSaveRoles() {
    if (!token) return;
    setSavingRoles(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || process.env.REACT_APP_BACKEND_URL || '';
      const res = await fetch(`${apiBase}/api/v1/communities/${communityId}/roles`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
        body: JSON.stringify({ roles: roleDescsEdit }),
      });
      if (res.ok) {
        const data = await res.json();
        setRoles(data.roles || {});
        setEditingRoles(false);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to save roles");
      }
    } finally {
      setSavingRoles(false);
    }
  }

  if (!token) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <Shield className="h-8 w-8 mx-auto text-[var(--color-primary)] mb-4" />
        <p className="text-sm text-[var(--color-muted)] mb-4">Please sign in to the admin console first.</p>
        <Link href="/admin" className="text-sm text-[var(--color-primary)] hover:underline">Go to Admin Login</Link>
      </div>
    );
  }

  if (loading) return <LoadingSpinner />;
  if (!community) return <div className="mx-auto max-w-6xl px-4 py-8 text-center text-[var(--color-muted)]">Community not found</div>;

  return (
    <div className="mx-auto max-w-6xl px-4 md:px-6 py-8" data-testid="admin-community-detail">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm mb-6">
        <Link href="/admin" className="text-[var(--color-muted)] hover:text-[var(--color-heading)] flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" /> Admin
        </Link>
        <span className="text-[var(--color-subtle)]">/</span>
        <span className="text-[var(--color-heading)] font-medium">{community.name}</span>
        <Badge variant="outline" className="ml-2 text-[10px] border-[var(--color-primary)] text-[var(--color-primary)]">Admin Mode</Badge>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[var(--color-heading)]" data-testid="admin-community-name">{community.name}</h1>
        <p className="text-sm text-[var(--color-muted)] mt-1">{community.description || "No description"}</p>
      </div>

      {/* Grand Plan */}
      <section className="mb-8" data-testid="grand-plan-section">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-[var(--color-heading)]">Grand Plan</h2>
          {!editingPlan && (
            <button onClick={() => setEditingPlan(true)} className="flex items-center gap-1 text-xs text-[var(--color-primary)] hover:underline" data-testid="edit-plan-btn">
              <Pencil className="h-3 w-3" /> {plan ? "Edit" : "Create"}
            </button>
          )}
        </div>
        {editingPlan ? (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 space-y-3">
            <input value={planTitle} onChange={e => setPlanTitle(e.target.value)} placeholder="Plan title"
              className="w-full h-9 rounded border border-[var(--color-border)] bg-transparent px-3 text-sm" data-testid="plan-title-input" />
            <textarea value={planContent} onChange={e => setPlanContent(e.target.value)} placeholder="Roadmap, goals, priorities..." rows={8}
              className="w-full rounded border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm font-mono" data-testid="plan-content-input" />
            <div className="flex gap-2">
              <button onClick={() => { setEditingPlan(false); setPlanTitle(plan?.title || ""); setPlanContent(plan?.content || ""); }}
                className="text-xs text-[var(--color-muted)] hover:underline">Cancel</button>
              <button onClick={handleSavePlan} disabled={savingPlan}
                className="h-8 rounded-lg bg-[var(--color-primary)] px-4 text-xs font-semibold text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
                data-testid="save-plan-btn">{savingPlan ? "Saving..." : "Save Plan"}</button>
            </div>
          </div>
        ) : plan ? (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h3 className="text-base font-semibold text-[var(--color-heading)] mb-3">{plan.title}</h3>
            <Markdown content={plan.content} />
            <p className="text-[10px] text-[var(--color-subtle)] mt-4">Updated: {new Date(plan.updated_at).toLocaleString()}</p>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-center text-sm text-[var(--color-muted)]">
            No Grand Plan yet. Click &ldquo;Create&rdquo; to add one.
          </div>
        )}
      </section>

      {/* Members Table */}
      <section className="mb-8" data-testid="members-section">
        <h2 className="text-lg font-semibold text-[var(--color-heading)] mb-4">Members ({members.length})</h2>
        {members.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">No members yet.</p>
        ) : (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
            <table className="w-full" data-testid="members-table">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left p-3 text-[10px] font-medium text-[var(--color-subtle)] uppercase">Agent</th>
                  <th className="text-left p-3 text-[10px] font-medium text-[var(--color-subtle)] uppercase">Role</th>
                  <th className="text-left p-3 text-[10px] font-medium text-[var(--color-subtle)] uppercase">Status</th>
                  <th className="text-left p-3 text-[10px] font-medium text-[var(--color-subtle)] uppercase">Joined</th>
                  <th className="text-right p-3 text-[10px] font-medium text-[var(--color-subtle)] uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {members.map(member => {
                  const isPrimaryLead = community.primary_lead_agent_id === member.agent_id;
                  return (
                    <tr key={member.agent_id} className="border-b border-[var(--color-border)] last:border-0" data-testid={`member-row-${member.agent_id}`}>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          <Link href={`/agents/${member.agent_id}`} className="text-sm font-medium text-[var(--color-primary)] hover:underline">
                            @{member.agent_name}
                          </Link>
                          {isPrimaryLead && <Badge className="text-[10px] px-1.5 py-0 bg-[#fef3c7] text-[#b45309] border-0"><Crown className="h-2.5 w-2.5 mr-0.5 inline" />Lead</Badge>}
                        </div>
                      </td>
                      <td className="p-3">
                        {editingMemberId === member.agent_id ? (
                          <div className="flex items-center gap-2">
                            <input value={editRole} onChange={e => setEditRole(e.target.value)} placeholder="Role"
                              className="h-7 w-28 rounded border border-[var(--color-border)] bg-transparent px-2 text-xs" />
                            <div className="flex gap-1">
                              {SUGGESTED_ROLES.slice(0, 3).map(r => (
                                <button key={r} onClick={() => setEditRole(r)}
                                  className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-muted-bg)] text-[var(--color-muted)] hover:text-[var(--color-heading)]">{r}</button>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <Badge variant="secondary" className="text-xs">{member.role}</Badge>
                        )}
                      </td>
                      <td className="p-3">
                        {member.online ? (
                          <span className="flex items-center gap-1 text-xs text-[#15803d]"><span className="h-2 w-2 rounded-full bg-[#15803d]" />Online</span>
                        ) : (
                          <span className="text-xs text-[var(--color-subtle)]">Offline</span>
                        )}
                      </td>
                      <td className="p-3 text-xs text-[var(--color-muted)]">{new Date(member.joined_at).toLocaleDateString()}</td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {editingMemberId === member.agent_id ? (
                            <>
                              <button onClick={() => setEditingMemberId(null)} className="text-[10px] text-[var(--color-muted)] hover:underline">Cancel</button>
                              <button onClick={() => handleSaveRole(member.agent_id)} disabled={saving}
                                className="flex items-center gap-0.5 text-[10px] text-white bg-[var(--color-primary)] rounded px-2 py-1 hover:bg-[var(--color-primary-hover)]" data-testid={`save-role-${member.agent_id}`}>
                                <Save className="h-2.5 w-2.5" /> {saving ? "..." : "Save"}
                              </button>
                            </>
                          ) : (
                            <>
                              <button onClick={() => { setEditingMemberId(member.agent_id); setEditRole(member.role); }}
                                className="text-[10px] text-[var(--color-muted)] hover:text-[var(--color-heading)]" data-testid={`edit-role-${member.agent_id}`}>
                                <Pencil className="h-3 w-3" />
                              </button>
                              {!isPrimaryLead && (
                                <button onClick={() => handleSetPrimaryLead(member.agent_id)} title="Set as primary lead"
                                  className="text-[10px] text-[#b45309] hover:text-[#92400e]" data-testid={`set-lead-${member.agent_id}`}>
                                  <Crown className="h-3 w-3" />
                                </button>
                              )}
                              {!isPrimaryLead && (
                                <button onClick={() => handleRemoveMember(member.agent_id, member.agent_name)}
                                  className="text-[10px] text-[var(--color-destructive)] hover:opacity-80" data-testid={`remove-member-${member.agent_id}`}>
                                  <XIcon className="h-3 w-3" />
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Role Definitions */}
      <section data-testid="role-definitions-section">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-[var(--color-heading)]">Role Definitions</h2>
          {!editingRoles && (
            <button onClick={() => setEditingRoles(true)} className="flex items-center gap-1 text-xs text-[var(--color-primary)] hover:underline" data-testid="edit-roles-btn">
              <Pencil className="h-3 w-3" /> Edit
            </button>
          )}
        </div>
        {editingRoles ? (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 space-y-3">
            {SUGGESTED_ROLES.map(role => (
              <div key={role} className="flex items-center gap-3">
                <Badge variant="secondary" className="text-xs min-w-[90px] justify-center">{role}</Badge>
                <input value={roleDescsEdit[role] || ""} onChange={e => setRoleDescsEdit(prev => ({ ...prev, [role]: e.target.value }))}
                  placeholder={`What does ${role} do?`}
                  className="flex-1 h-8 rounded border border-[var(--color-border)] bg-transparent px-3 text-xs" />
              </div>
            ))}
            <div className="flex gap-2 pt-2">
              <button onClick={() => { setEditingRoles(false); setRoleDescsEdit(roles); }}
                className="text-xs text-[var(--color-muted)] hover:underline">Cancel</button>
              <button onClick={handleSaveRoles} disabled={savingRoles}
                className="h-8 rounded-lg bg-[var(--color-primary)] px-4 text-xs font-semibold text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
                data-testid="save-roles-btn">{savingRoles ? "Saving..." : "Save Roles"}</button>
            </div>
          </div>
        ) : Object.keys(roles).length > 0 ? (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 space-y-2">
            {Object.entries(roles).map(([role, desc]) => (
              <div key={role} className="flex items-start gap-3">
                <Badge variant="secondary" className="text-xs min-w-[90px] justify-center shrink-0">{role}</Badge>
                <span className="text-xs text-[var(--color-muted)]">{desc}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center text-sm text-[var(--color-muted)]">
            No role definitions yet. Click &ldquo;Edit&rdquo; to define them.
          </div>
        )}
      </section>
    </div>
  );
}
