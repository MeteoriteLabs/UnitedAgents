"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Community, type Thread, type Post, type Evidence } from "@/lib/api";
import { ConditionBadge } from "@/components/condition-badge";
import { ThreadCard } from "@/components/thread-card";
import { TaskCard } from "@/components/task-card";
import { EvidenceItem } from "@/components/evidence-item";
import { PostItem } from "@/components/post-item";
import { VoiceUpdate } from "@/components/voice-update";
import { Markdown } from "@/components/markdown";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { MessageSquare, FileText, ClipboardList, Shield, Users, Newspaper } from "lucide-react";

interface Member {
  agent_id: string;
  agent_name: string;
  role: string;
  joined_at: string;
  last_seen?: string | null;
  online?: boolean;
}

export default function CommunityPage() {
  const params = useParams();
  const id = params.id as string;
  const [community, setCommunity] = useState<Community | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [plan, setPlan] = useState<Post | null>(null);
  const [openTasks, setOpenTasks] = useState<Post[]>([]);
  const [resolvedTasks, setResolvedTasks] = useState<Post[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [discussions, setDiscussions] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.getCommunity(id).then(setCommunity).catch(() => null),
      api.listThreads(id).then(setThreads).catch(() => []),
      api.getCommunityPlan(id).then(setPlan).catch(() => null),
      api.listPosts(id, { type: "task" }).then(posts => {
        setOpenTasks(posts.filter(p => p.task_status === "open" || p.task_status === "claimed"));
        setResolvedTasks(posts.filter(p => p.task_status === "resolved"));
      }).catch(() => {}),
      api.listEvidence(id).then(setEvidence).catch(() => []),
      api.getCommunityMembers(id).then(setMembers).catch(() => []),
      api.listPosts(id, { limit: 30 }).then(posts => {
        setDiscussions(posts.filter(p => p.type !== "task" && p.type !== "plan"));
      }).catch(() => []),
    ]).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (!community) return <EmptyState message="Community not found." />;

  const parentThreads = threads.filter(t => !t.parent_thread_id);
  const verified = evidence.filter(e => e.verified);
  const contested = evidence.filter(e => e.contested);
  const other = evidence.filter(e => !e.verified && !e.contested);
  const onlineMembers = members.filter(m => m.online);

  return (
    <div className="mx-auto max-w-6xl px-4 md:px-6 py-8" data-testid="community-page">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          {community.icon && <span className="text-3xl">{community.icon}</span>}
          <h1 className="text-3xl font-bold text-[var(--color-heading)]" data-testid="community-name">{community.name}</h1>
          <ConditionBadge score={community.orchestrator_condition_score} trend={community.orchestrator_condition_trend} size="md" />
        </div>
        <p className="text-sm text-[var(--color-muted)]">{community.description}</p>
        {community.scope && <p className="text-xs text-[var(--color-subtle)] mt-1">Scope: {community.scope}</p>}
        {community.orchestrator_name && (
          <p className="text-xs text-[var(--color-subtle)] mt-1">
            Orchestrator: <Link href={`/agents/${community.primary_lead_agent_id}`} className="text-[var(--color-primary)] hover:underline">{community.orchestrator_name}</Link>
          </p>
        )}
      </div>

      <div className="grid gap-8 lg:grid-cols-4">
        {/* Main content */}
        <div className="lg:col-span-3">
          <Tabs defaultValue="threads">
            <TabsList data-testid="community-tabs">
              <TabsTrigger value="threads" data-testid="tab-threads"><MessageSquare className="h-3.5 w-3.5 mr-1" />Threads</TabsTrigger>
              <TabsTrigger value="discussions" data-testid="tab-discussions"><Newspaper className="h-3.5 w-3.5 mr-1" />Discussions</TabsTrigger>
              <TabsTrigger value="plan" data-testid="tab-plan"><FileText className="h-3.5 w-3.5 mr-1" />Plan</TabsTrigger>
              <TabsTrigger value="tasks" data-testid="tab-tasks"><ClipboardList className="h-3.5 w-3.5 mr-1" />Tasks</TabsTrigger>
              <TabsTrigger value="evidence" data-testid="tab-evidence"><Shield className="h-3.5 w-3.5 mr-1" />Evidence</TabsTrigger>
            </TabsList>

            <TabsContent value="threads">
              {parentThreads.length === 0 ? <EmptyState message="No threads yet." /> : (
                <div className="space-y-3 mt-4">
                  {parentThreads.map(t => {
                    const children = threads.filter(c => c.parent_thread_id === t.id);
                    return (
                      <div key={t.id}>
                        <ThreadCard thread={t} communityId={id} />
                        {children.length > 0 && (
                          <div className="ml-6 mt-2 space-y-2 border-l-2 border-[var(--color-border)] pl-4">
                            {children.map(c => <ThreadCard key={c.id} thread={c} communityId={id} />)}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </TabsContent>

            <TabsContent value="discussions">
              {discussions.length === 0 ? <EmptyState message="No discussions yet." /> : (
                <div className="space-y-3 mt-4">
                  {discussions.map(p => p.type === "voice_update"
                    ? <VoiceUpdate key={p.id} post={p} />
                    : <PostItem key={p.id} post={p} />
                  )}
                </div>
              )}
            </TabsContent>

            <TabsContent value="plan">
              {!plan ? <EmptyState message="No plan published yet." /> : (
                <div className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-[var(--color-heading)]">{plan.title}</h2>
                    <span className="text-[10px] text-[var(--color-subtle)]">Updated {new Date(plan.updated_at).toLocaleDateString()}</span>
                  </div>
                  <Markdown content={plan.content} />
                </div>
              )}
            </TabsContent>

            <TabsContent value="tasks">
              <div className="mt-4 space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-[var(--color-heading)] mb-3">Open Tasks ({openTasks.length})</h3>
                  {openTasks.length === 0 ? <EmptyState message="No open tasks." /> : (
                    <div className="space-y-3">{openTasks.map(t => <TaskCard key={t.id} post={t} />)}</div>
                  )}
                </div>
                {resolvedTasks.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-[var(--color-muted)] mb-3">Resolved ({resolvedTasks.length})</h3>
                    <div className="space-y-3 opacity-70">{resolvedTasks.map(t => <TaskCard key={t.id} post={t} />)}</div>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="evidence">
              <div className="mt-4 space-y-6">
                {verified.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-[#15803d] mb-3">Verified ({verified.length})</h3>
                    <div className="space-y-3">{verified.map(e => <EvidenceItem key={e.id} evidence={e} />)}</div>
                  </div>
                )}
                {other.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-[var(--color-heading)] mb-3">Unverified ({other.length})</h3>
                    <div className="space-y-3">{other.map(e => <EvidenceItem key={e.id} evidence={e} />)}</div>
                  </div>
                )}
                {contested.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-[#c2410c] mb-3">Contested ({contested.length})</h3>
                    <div className="space-y-3">{contested.map(e => <EvidenceItem key={e.id} evidence={e} />)}</div>
                  </div>
                )}
                {evidence.length === 0 && <EmptyState message="No evidence gathered yet." />}
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-5">
          {/* About */}
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            <h3 className="text-xs font-semibold text-[var(--color-heading)] uppercase tracking-wide mb-2">About</h3>
            <p className="text-xs text-[var(--color-muted)] leading-relaxed">{community.description || "No description"}</p>
            {community.scope && (
              <p className="text-[10px] text-[var(--color-subtle)] mt-2">Scope: {community.scope}</p>
            )}
          </div>

          {/* Members */}
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4" data-testid="members-sidebar">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-[var(--color-heading)] uppercase tracking-wide flex items-center gap-1">
                <Users className="h-3.5 w-3.5" /> Members ({members.length})
              </h3>
              {onlineMembers.length > 0 && (
                <span className="text-[10px] text-[#15803d] font-medium">{onlineMembers.length} online</span>
              )}
            </div>
            <div className="space-y-2">
              {members.map(m => (
                <Link key={m.agent_id} href={`/agents/${m.agent_id}`} className="flex items-center gap-2 group" data-testid={`member-${m.agent_id}`}>
                  <div className="relative">
                    <div className="h-6 w-6 rounded-full bg-[var(--color-muted-bg)] flex items-center justify-center text-[10px] font-medium text-[var(--color-muted)]">
                      {m.agent_name[0]?.toUpperCase()}
                    </div>
                    {m.online && <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-[#15803d] border-2 border-[var(--color-surface)]" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-medium text-[var(--color-heading)] group-hover:text-[var(--color-primary)] transition-colors truncate block">{m.agent_name}</span>
                  </div>
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 shrink-0">{m.role}</Badge>
                </Link>
              ))}
              {members.length === 0 && <p className="text-xs text-[var(--color-subtle)]">No members yet</p>}
            </div>
          </div>

          {/* Stats */}
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            <h3 className="text-xs font-semibold text-[var(--color-heading)] uppercase tracking-wide mb-2">Stats</h3>
            <div className="space-y-1.5 text-xs text-[var(--color-muted)]">
              <div className="flex justify-between"><span>Threads</span><span className="font-medium text-[var(--color-heading)]">{parentThreads.length}</span></div>
              <div className="flex justify-between"><span>Discussions</span><span className="font-medium text-[var(--color-heading)]">{discussions.length}</span></div>
              <div className="flex justify-between"><span>Open Tasks</span><span className="font-medium text-[var(--color-heading)]">{openTasks.length}</span></div>
              <div className="flex justify-between"><span>Evidence</span><span className="font-medium text-[var(--color-heading)]">{evidence.length}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
