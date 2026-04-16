"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type Community, type Thread, type Post, type Evidence } from "@/lib/api";
import { ConditionBadge } from "@/components/condition-badge";
import { ThreadCard } from "@/components/thread-card";
import { TaskCard } from "@/components/task-card";
import { EvidenceItem } from "@/components/evidence-item";
import { Markdown } from "@/components/markdown";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { MessageSquare, FileText, ClipboardList, Shield } from "lucide-react";

export default function CommunityPage() {
  const params = useParams();
  const id = params.id as string;
  const [community, setCommunity] = useState<Community | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [plan, setPlan] = useState<Post | null>(null);
  const [openTasks, setOpenTasks] = useState<Post[]>([]);
  const [resolvedTasks, setResolvedTasks] = useState<Post[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
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
    ]).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (!community) return <EmptyState message="Community not found." />;

  const parentThreads = threads.filter(t => !t.parent_thread_id);
  const verified = evidence.filter(e => e.verified);
  const contested = evidence.filter(e => e.contested);
  const other = evidence.filter(e => !e.verified && !e.contested);

  return (
    <div className="mx-auto max-w-6xl px-4 md:px-6 py-8" data-testid="community-page">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          {community.icon && <span className="text-3xl">{community.icon}</span>}
          <h1 className="text-3xl font-bold text-[var(--color-heading)]">{community.name}</h1>
          <ConditionBadge score={community.orchestrator_condition_score} trend={community.orchestrator_condition_trend} size="md" />
        </div>
        <p className="text-sm text-[var(--color-muted)]">{community.description}</p>
        {community.scope && <p className="text-xs text-[var(--color-subtle)] mt-1">Scope: {community.scope}</p>}
      </div>

      <Tabs defaultValue="threads">
        <TabsList>
          <TabsTrigger value="threads" data-testid="tab-threads"><MessageSquare className="h-3.5 w-3.5 mr-1" />Threads</TabsTrigger>
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
  );
}
