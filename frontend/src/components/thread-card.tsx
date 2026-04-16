import Link from "next/link";
import type { Thread } from "@/lib/api";
import { formatRelativeTime } from "@/lib/text-utils";
import { MessageSquare, FileText, ClipboardList, Users } from "lucide-react";

const STAGE_COLORS: Record<string, string> = {
  sensing: "bg-[#e0f2fe] text-[#0369a1]",
  investigating: "bg-[#fef3c7] text-[#b45309]",
  building: "bg-[#dcfce7] text-[#15803d]",
  threshold_approaching: "bg-[#ffedd5] text-[#c2410c]",
  action_ready: "bg-[#fee2e2] text-[#991b1b]",
  campaigning: "bg-[#f3e8ff] text-[#6b21a8]",
  solution_finding: "bg-[#d1fae5] text-[#047857]",
  approaching: "bg-[#fef9c3] text-[#854d0e]",
  monitoring_change: "bg-[#ccfbf1] text-[#115e59]",
  resolved: "bg-[#f5f2ec] text-[#78716c]",
};

export function ThreadCard({ thread, communityId }: { thread: Thread; communityId: string }) {
  const stageColor = STAGE_COLORS[thread.stage] || STAGE_COLORS.sensing;

  return (
    <Link href={`/community/${communityId}/thread/${thread.id}`} data-testid={`thread-card-${thread.id}`}>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 hover:bg-[var(--color-elevated)] transition-colors">
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-sm font-semibold text-[var(--color-heading)] line-clamp-2">{thread.title}</h3>
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${stageColor}`}>
            {thread.stage.replace(/_/g, " ")}
          </span>
        </div>
        {thread.latest_activity_preview && (
          <p className="text-xs text-[var(--color-muted)] line-clamp-2 mb-3">
            {thread.latest_activity_author_name && <span className="font-medium">{thread.latest_activity_author_name}: </span>}
            {thread.latest_activity_preview}
          </p>
        )}
        <div className="flex items-center gap-4 text-[10px] text-[var(--color-subtle)]">
          <span className="flex items-center gap-1"><Users className="h-3 w-3" />{thread.participant_count}</span>
          <span className="flex items-center gap-1"><FileText className="h-3 w-3" />{thread.evidence_count}</span>
          <span className="flex items-center gap-1"><MessageSquare className="h-3 w-3" />{thread.post_count}</span>
          {thread.open_task_count > 0 && <span className="flex items-center gap-1"><ClipboardList className="h-3 w-3" />{thread.open_task_count}</span>}
          {thread.updated_at && <span className="ml-auto">{formatRelativeTime(thread.updated_at)}</span>}
        </div>
      </div>
    </Link>
  );
}
