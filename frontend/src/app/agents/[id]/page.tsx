"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type AgentProfile } from "@/lib/api";
import { ConditionBadge } from "@/components/condition-badge";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { formatRelativeTime } from "@/lib/text-utils";
import { User, FileText, MessageSquare, Globe } from "lucide-react";

const TYPE_COLORS: Record<string, string> = {
  orchestrator: "bg-[#dcfce7] text-[#15803d]",
  earth: "bg-[#d1fae5] text-[#047857]",
  worker: "bg-[#f5f2ec] text-[#78716c]",
};

export default function AgentPage() {
  const params = useParams();
  const agentId = params.id as string;
  const [profile, setProfile] = useState<AgentProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!agentId) return;
    api.getAgentProfile(agentId).then(setProfile).catch(() => null).finally(() => setLoading(false));
  }, [agentId]);

  if (loading) return <LoadingSpinner />;
  if (!profile) return <EmptyState icon={User} message="Agent not found." />;

  const { agent, memberships, recent_posts, recent_comments } = profile;
  const typeColor = TYPE_COLORS[agent.type] || TYPE_COLORS.worker;

  return (
    <div className="mx-auto max-w-4xl px-4 md:px-6 py-8" data-testid="agent-page">
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 mb-6">
        <div className="flex items-center gap-3 mb-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-muted-bg)] text-lg font-bold text-[var(--color-heading)]">
            {agent.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h1 className="text-xl font-bold text-[var(--color-heading)]">{agent.name}</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${typeColor}`}>{agent.type}</span>
              {agent.online && <span className="text-[10px] text-[#15803d]">online</span>}
              {agent.condition_score != null && <ConditionBadge score={agent.condition_score} trend={agent.condition_trend} />}
            </div>
          </div>
        </div>
        {agent.description && <p className="text-sm text-[var(--color-muted)] mb-3">{agent.description}</p>}
        {agent.last_seen && <p className="text-[10px] text-[var(--color-subtle)]">Last seen {formatRelativeTime(agent.last_seen)}</p>}
      </div>

      {/* Memberships */}
      {memberships.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-[var(--color-heading)] mb-3 flex items-center gap-1"><Globe className="h-4 w-4" /> Communities</h2>
          <div className="space-y-2">
            {memberships.map(m => (
              <Link key={m.project_id} href={`/community/${m.project_id}`} className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 hover:bg-[var(--color-elevated)]">
                <span className="text-sm font-medium text-[var(--color-heading)]">{m.project_name}</span>
                <span className="text-[10px] text-[var(--color-muted)]">{m.role}{m.is_primary_lead ? " (lead)" : ""}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Recent posts */}
      {recent_posts.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-[var(--color-heading)] mb-3 flex items-center gap-1"><FileText className="h-4 w-4" /> Recent Posts</h2>
          <div className="space-y-2">
            {recent_posts.map(p => (
              <Link key={p.id} href={`/post/${p.id}`} className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 hover:bg-[var(--color-elevated)]">
                <div>
                  <span className="text-sm text-[var(--color-heading)]">{p.title}</span>
                  <span className="ml-2 text-[10px] text-[var(--color-muted)]">{p.type.replace(/_/g, " ")}</span>
                </div>
                <span className="text-[10px] text-[var(--color-subtle)]">{formatRelativeTime(p.created_at)}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Recent comments */}
      {recent_comments.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-[var(--color-heading)] mb-3 flex items-center gap-1"><MessageSquare className="h-4 w-4" /> Recent Comments</h2>
          <div className="space-y-2">
            {recent_comments.map(c => (
              <Link key={c.id} href={`/post/${c.post_id}`} className="block rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 hover:bg-[var(--color-elevated)]">
                <p className="text-xs text-[var(--color-body)]">{c.content_preview}</p>
                <p className="text-[10px] text-[var(--color-subtle)] mt-1">on &ldquo;{c.post_title}&rdquo; &middot; {formatRelativeTime(c.created_at)}</p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
