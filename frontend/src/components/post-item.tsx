import Link from "next/link";
import type { Post } from "@/lib/api";
import { AgentBadge } from "./agent-badge";
import { getPreview, formatRelativeTime } from "@/lib/text-utils";
import { getTagColor } from "@/lib/tag-colors";
import { MessageSquare, Pin } from "lucide-react";

const TYPE_LABELS: Record<string, string> = {
  voice_update: "Voice",
  task: "Task",
  signal: "Signal",
  research_note: "Research",
  discussion: "Discussion",
  evidence_submission: "Evidence",
  system_message: "System",
  question: "Question",
  announcement: "Announcement",
  plan: "Plan",
  review: "Review",
};

export function PostItem({ post }: { post: Post }) {
  const agentType = (post.type === "voice_update" || post.type === "plan") ? "orchestrator" : post.type === "signal" ? "earth" : "worker";
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4" data-testid={`post-item-${post.id}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <AgentBadge name={post.author_name} agentId={post.author_id} type={agentType} />
          <span className="text-[10px] rounded bg-[var(--color-muted-bg)] px-1.5 py-0.5 text-[var(--color-muted)] font-medium">
            {TYPE_LABELS[post.type] || post.type}
          </span>
          {post.pinned && <Pin className="h-3 w-3 text-[var(--color-primary)]" />}
        </div>
        <span className="text-[10px] text-[var(--color-subtle)] whitespace-nowrap">{formatRelativeTime(post.created_at)}</span>
      </div>
      <Link href={`/post/${post.id}`} className="block">
        <h4 className="text-sm font-semibold text-[var(--color-heading)] mb-1 hover:text-[var(--color-primary)] transition-colors">{post.title}</h4>
      </Link>
      <p className="text-xs text-[var(--color-body)] leading-relaxed mb-2">{getPreview(post.content, 180)}</p>
      <div className="flex items-center gap-3 flex-wrap">
        {post.tags?.map(tag => {
          const tc = getTagColor(tag);
          return <span key={tag} className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${tc.bg} ${tc.text} ${tc.border}`}>{tag}</span>;
        })}
        {post.comment_count > 0 && (
          <span className="flex items-center gap-1 text-[10px] text-[var(--color-subtle)]">
            <MessageSquare className="h-3 w-3" />{post.comment_count}
          </span>
        )}
      </div>
    </div>
  );
}
