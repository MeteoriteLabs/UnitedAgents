import type { Post } from "@/lib/api";
import { AgentBadge } from "./agent-badge";
import { ConditionBadge } from "./condition-badge";
import { formatRelativeTime } from "@/lib/text-utils";
import Link from "next/link";

/**
 * Specialized post for type='voice_update'.
 * Serif body, condition in header, first-person tone.
 */
export function VoiceUpdate({ post, conditionScore, conditionTrend }: {
  post: Post;
  conditionScore?: number | null;
  conditionTrend?: string | null;
}) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5" data-testid={`voice-update-${post.id}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <AgentBadge name={post.author_name} agentId={post.author_id} type="orchestrator" />
          <span className="text-[10px] rounded bg-[#dcfce7] px-1.5 py-0.5 text-[#15803d] font-medium">Voice Update</span>
          {conditionScore != null && <ConditionBadge score={conditionScore} trend={conditionTrend} />}
        </div>
        <span className="text-[10px] text-[var(--color-subtle)]">{formatRelativeTime(post.created_at)}</span>
      </div>
      <Link href={`/post/${post.id}`}>
        <p className="font-serif text-sm text-[var(--color-body)] leading-relaxed italic">{post.content}</p>
      </Link>
    </div>
  );
}
