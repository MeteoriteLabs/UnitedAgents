import type { Comment } from "@/lib/api";
import { AgentBadge } from "./agent-badge";
import { formatRelativeTime } from "@/lib/text-utils";

export function CommentItem({ comment }: { comment: Comment }) {
  return (
    <div className="border-l-2 border-[var(--color-border)] pl-3 py-2" data-testid={`comment-${comment.id}`}>
      <div className="flex items-center gap-2 mb-1">
        <AgentBadge name={comment.author_name} agentId={comment.author_id} />
        <span className="text-[10px] text-[var(--color-subtle)]">{formatRelativeTime(comment.created_at)}</span>
      </div>
      <p className="text-xs text-[var(--color-body)] leading-relaxed">{comment.content}</p>
    </div>
  );
}
