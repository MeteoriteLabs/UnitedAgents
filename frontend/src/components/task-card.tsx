import type { Post } from "@/lib/api";
import { AgentBadge } from "./agent-badge";
import { formatRelativeTime } from "@/lib/text-utils";
import Link from "next/link";
import { CheckCircle2, Clock, AlertCircle, CircleDot } from "lucide-react";

const STATUS_CONFIG: Record<string, { color: string; icon: typeof Clock; label: string }> = {
  open: { color: "text-[var(--color-muted)]", icon: CircleDot, label: "Open" },
  claimed: { color: "text-[#b45309]", icon: Clock, label: "Claimed" },
  resolved: { color: "text-[#15803d]", icon: CheckCircle2, label: "Resolved" },
  failed: { color: "text-[#991b1b]", icon: AlertCircle, label: "Failed" },
};

export function TaskCard({ post }: { post: Post }) {
  const status = post.task_status || "open";
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.open;
  const Icon = cfg.icon;

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4" data-testid={`task-card-${post.id}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${cfg.color}`} />
          <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
          {post.task_category && (
            <span className="text-[10px] rounded bg-[var(--color-muted-bg)] px-1.5 py-0.5 text-[var(--color-muted)]">{post.task_category}</span>
          )}
        </div>
        {post.urgency > 0 && (
          <span className="text-[10px] font-medium text-[var(--color-destructive)]">urgency {Math.round(post.urgency)}</span>
        )}
      </div>
      <Link href={`/post/${post.id}`}>
        <h4 className="text-sm font-semibold text-[var(--color-heading)] mb-1 hover:text-[var(--color-primary)]">{post.title}</h4>
      </Link>
      <p className="text-xs text-[var(--color-body)] line-clamp-2 mb-2">{post.content}</p>
      <div className="flex items-center justify-between text-[10px] text-[var(--color-subtle)]">
        <AgentBadge name={post.author_name} agentId={post.author_id} />
        {post.depends_on && (
          <span className="text-[var(--color-destructive)]">
            {post.dependency_resolved ? "dep resolved" : "waiting on dependency"}
          </span>
        )}
        <span>{formatRelativeTime(post.created_at)}</span>
      </div>
    </div>
  );
}
