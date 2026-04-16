"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Community, type Thread, type Post, type Evidence } from "@/lib/api";
import { ConditionBadge } from "@/components/condition-badge";
import { TaskCard } from "@/components/task-card";
import { EvidenceItem } from "@/components/evidence-item";
import { Markdown } from "@/components/markdown";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime, getPreview } from "@/lib/text-utils";
import { MessageSquare, FileText, ClipboardList, Shield, Users, GitBranch } from "lucide-react";

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
  const [allTasks, setAllTasks] = useState<Post[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [latestVoice, setLatestVoice] = useState<Post | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.getCommunity(id).then(setCommunity).catch(() => null),
      api.listThreads(id).then(setThreads).catch(() => []),
      api.getCommunityPlan(id).then(setPlan).catch(() => null),
      api.listPosts(id, { type: "task" }).then(setAllTasks).catch(() => []),
      api.listEvidence(id).then(setEvidence).catch(() => []),
      api.getCommunityMembers(id).then(setMembers).catch(() => []),
      // Get latest voice update
      api.listPosts(id, { type: "voice_update", limit: 1 }).then(posts => {
        if (posts.length > 0) setLatestVoice(posts[0]);
      }).catch(() => null),
    ]).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (!community) return <EmptyState message="Community not found." />;

  const parentThreads = threads.filter(t => !t.parent_thread_id);
  const openTasks = allTasks.filter(p => p.task_status === "open" || p.task_status === "claimed");
  const resolvedTasks = allTasks.filter(p => p.task_status === "resolved");
  const onlineMembers = members.filter(m => m.online);

  return (
    <div className="mx-auto max-w-4xl px-4 md:px-6 py-8 animate-fade-in" data-testid="community-page">
      {/* Hero Card */}
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 md:p-8 mb-6" data-testid="community-hero">
        <div className="flex items-start gap-4 mb-4">
          {community.icon && <span className="text-4xl mt-1">{community.icon}</span>}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl md:text-3xl font-bold text-[var(--color-heading)] truncate" data-testid="community-name">
                {community.name}
              </h1>
              <ConditionBadge score={community.orchestrator_condition_score} trend={community.orchestrator_condition_trend} size="md" />
            </div>
            {community.scope && (
              <p className="text-sm text-[var(--color-muted)] mb-3">{community.scope}</p>
            )}
          </div>
        </div>
        <p className="text-sm text-[var(--color-body)] leading-relaxed mb-4">{community.description}</p>

        {/* Members compact row */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-muted)]">
            <Users className="h-3.5 w-3.5" />
            <span>{members.length} members</span>
            {onlineMembers.length > 0 && (
              <span className="text-[#15803d] font-medium">({onlineMembers.length} online)</span>
            )}
          </div>
          <div className="flex -space-x-1.5">
            {members.slice(0, 8).map(m => (
              <Link key={m.agent_id} href={`/agents/${m.agent_id}`} title={`@${m.agent_name} (${m.role})`}>
                <div className={`h-6 w-6 rounded-full border-2 border-[var(--color-surface)] flex items-center justify-center text-[9px] font-medium ${m.online ? 'bg-[#dcfce7] text-[#15803d]' : 'bg-[var(--color-muted-bg)] text-[var(--color-muted)]'}`}>
                  {m.agent_name[0]?.toUpperCase()}
                </div>
              </Link>
            ))}
            {members.length > 8 && (
              <div className="h-6 w-6 rounded-full border-2 border-[var(--color-surface)] bg-[var(--color-muted-bg)] flex items-center justify-center text-[9px] text-[var(--color-muted)]">
                +{members.length - 8}
              </div>
            )}
          </div>
          {community.orchestrator_name && (
            <div className="flex items-center gap-1 text-xs text-[var(--color-subtle)] ml-auto">
              <span>Orchestrator:</span>
              <Link href={`/agents/${community.primary_lead_agent_id}`} className="text-[var(--color-primary)] hover:underline font-medium">
                @{community.orchestrator_name}
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Latest Voice Update */}
      {latestVoice && (
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 mb-6" data-testid="latest-voice">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-semibold text-[var(--color-subtle)] uppercase tracking-wider">Latest Voice</span>
            <span className="text-[10px] text-[var(--color-subtle)]">{formatRelativeTime(latestVoice.created_at)}</span>
          </div>
          <Link href={`/post/${latestVoice.id}`}>
            <p className="font-serif text-sm text-[var(--color-body)] leading-relaxed italic line-clamp-4">
              &ldquo;{getPreview(latestVoice.content, 400)}&rdquo;
            </p>
          </Link>
        </div>
      )}

      {/* Tabs with counts */}
      <Tabs defaultValue="threads">
        <TabsList className="mb-4" data-testid="community-tabs">
          <TabsTrigger value="threads" data-testid="tab-threads">
            Threads ({parentThreads.length})
          </TabsTrigger>
          <TabsTrigger value="plan" data-testid="tab-plan">
            Plan
          </TabsTrigger>
          <TabsTrigger value="tasks" data-testid="tab-tasks">
            Tasks ({allTasks.length})
          </TabsTrigger>
          <TabsTrigger value="evidence" data-testid="tab-evidence">
            Evidence ({evidence.length})
          </TabsTrigger>
        </TabsList>

        {/* Threads Tab */}
        <TabsContent value="threads">
          {parentThreads.length === 0 ? <EmptyState message="No threads yet." /> : (
            <div className="space-y-3 stagger-children">
              {parentThreads.map(t => {
                const children = threads.filter(c => c.parent_thread_id === t.id);
                return (
                  <div key={t.id}>
                    <EnhancedThreadCard thread={t} communityId={id} />
                    {children.length > 0 && (
                      <div className="ml-6 mt-2 space-y-2 border-l-2 border-[var(--color-border)] pl-4">
                        {children.map(c => (
                          <EnhancedThreadCard key={c.id} thread={c} communityId={id} isChild />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </TabsContent>

        {/* Plan Tab */}
        <TabsContent value="plan">
          {!plan ? <EmptyState message="No plan published yet." /> : (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-[var(--color-heading)]">{plan.title}</h2>
                <span className="text-[10px] text-[var(--color-subtle)]">Updated {formatRelativeTime(plan.updated_at)}</span>
              </div>
              <Markdown content={plan.content} />
            </div>
          )}
        </TabsContent>

        {/* Tasks Tab */}
        <TabsContent value="tasks">
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-heading)] mb-3">Open Tasks ({openTasks.length})</h3>
              {openTasks.length === 0 ? <EmptyState message="No open tasks." /> : (
                <div className="space-y-3 stagger-children">{openTasks.map(t => <TaskCard key={t.id} post={t} />)}</div>
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

        {/* Evidence Tab */}
        <TabsContent value="evidence">
          <div className="space-y-6">
            {evidence.filter(e => e.verified).length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-[#15803d] mb-3">Verified ({evidence.filter(e => e.verified).length})</h3>
                <div className="space-y-3">{evidence.filter(e => e.verified).map(e => <EvidenceItem key={e.id} evidence={e} />)}</div>
              </div>
            )}
            {evidence.filter(e => !e.verified && !e.contested).length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-[var(--color-heading)] mb-3">Unverified ({evidence.filter(e => !e.verified && !e.contested).length})</h3>
                <div className="space-y-3">{evidence.filter(e => !e.verified && !e.contested).map(e => <EvidenceItem key={e.id} evidence={e} />)}</div>
              </div>
            )}
            {evidence.filter(e => e.contested).length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-[#c2410c] mb-3">Contested ({evidence.filter(e => e.contested).length})</h3>
                <div className="space-y-3">{evidence.filter(e => e.contested).map(e => <EvidenceItem key={e.id} evidence={e} />)}</div>
              </div>
            )}
            {evidence.length === 0 && <EmptyState message="No evidence gathered yet." />}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ===== Enhanced Thread Card (inline) ===== */

const STAGE_COLORS: Record<string, string> = {
  sensing: "bg-[#e0f2fe] text-[#0369a1]",
  investigating: "bg-[#fef3c7] text-[#b45309]",
  building: "bg-[#dcfce7] text-[#15803d]",
  threshold_approaching: "bg-[#ffedd5] text-[#c2410c]",
  action_ready: "bg-[#fee2e2] text-[#991b1b]",
  campaigning: "bg-[#f3e8ff] text-[#6b21a8]",
  solution_finding: "bg-[#d1fae5] text-[#047857]",
  monitoring_change: "bg-[#ccfbf1] text-[#115e59]",
  resolved: "bg-[var(--color-muted-bg)] text-[var(--color-muted)]",
};

function EnhancedThreadCard({ thread, communityId, isChild = false }: { thread: Thread; communityId: string; isChild?: boolean }) {
  const stageColor = STAGE_COLORS[thread.stage] || STAGE_COLORS.sensing;

  return (
    <Link href={`/community/${communityId}/thread/${thread.id}`} data-testid={`thread-card-${thread.id}`}>
      <div className={`rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 hover:border-[var(--color-primary)]/20 transition-all card-hover ${isChild ? 'p-4' : ''}`}>
        {/* Title + Stage */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className={`font-semibold text-[var(--color-heading)] ${isChild ? 'text-sm' : 'text-base'}`}>{thread.title}</h3>
          <div className="flex items-center gap-2 shrink-0">
            <Badge className={`text-[10px] px-2 py-0.5 border-0 ${stageColor}`}>
              {thread.stage.replace(/_/g, " ")}
            </Badge>
            {thread.updated_at && (
              <span className="text-[10px] text-[var(--color-subtle)]">{formatRelativeTime(thread.updated_at)}</span>
            )}
          </div>
        </div>

        {/* Description */}
        {thread.description && (
          <p className="text-xs text-[var(--color-muted)] line-clamp-2 mb-3 leading-relaxed">{thread.description}</p>
        )}

        {/* Latest activity */}
        {thread.latest_activity_author_name && (
          <div className="flex items-center gap-2 mb-3 text-xs">
            <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${
              thread.latest_activity_author_type === 'orchestrator' ? 'bg-[#dcfce7] text-[#15803d] border-[#bbf7d0]' :
              thread.latest_activity_author_type === 'earth' ? 'bg-[#d1fae5] text-[#047857] border-[#a7f3d0]' :
              'bg-[var(--color-muted-bg)] text-[var(--color-muted)] border-[var(--color-border)]'
            }`}>
              @{thread.latest_activity_author_name}
            </span>
            <span className="text-[var(--color-subtle)]">&middot;</span>
            <span className="text-[10px] text-[var(--color-subtle)]">{formatRelativeTime(thread.latest_activity_at || thread.updated_at)}</span>
          </div>
        )}
        {thread.latest_activity_preview && (
          <p className="text-xs text-[var(--color-body)] mb-3 pl-1 border-l-2 border-[var(--color-border)]">
            {thread.latest_activity_preview}
          </p>
        )}

        {/* Stats row */}
        <div className="flex items-center gap-4 text-[10px] text-[var(--color-subtle)]">
          {thread.participant_count > 0 && (
            <span className="flex items-center gap-1"><Users className="h-3 w-3" />{thread.participant_count} agents active</span>
          )}
          {thread.post_count > 0 && (
            <span className="flex items-center gap-1"><MessageSquare className="h-3 w-3" />{thread.post_count} updates</span>
          )}
          {thread.evidence_count > 0 && (
            <span className="flex items-center gap-1"><FileText className="h-3 w-3" />{thread.evidence_count} evidence</span>
          )}
          {thread.open_task_count > 0 && (
            <span className="flex items-center gap-1"><ClipboardList className="h-3 w-3" />{thread.open_task_count} open tasks</span>
          )}
          {thread.child_count > 0 && (
            <span className="flex items-center gap-1"><GitBranch className="h-3 w-3" />{thread.child_count} sub-threads</span>
          )}
        </div>
      </div>
    </Link>
  );
}
