import type { Evidence } from "@/lib/api";
import { formatRelativeTime } from "@/lib/text-utils";
import { CheckCircle2, AlertTriangle, ExternalLink } from "lucide-react";

const TYPE_LABELS: Record<string, string> = {
  data_point: "Data",
  verification: "Verification",
  research: "Research",
  connection: "Connection",
  contradiction: "Contradiction",
  observation: "Observation",
  measurement: "Measurement",
};

export function EvidenceItem({ evidence }: { evidence: Evidence }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4" data-testid={`evidence-${evidence.id}`}>
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-[10px] rounded bg-[var(--color-muted-bg)] px-1.5 py-0.5 text-[var(--color-muted)] font-medium">
          {TYPE_LABELS[evidence.type] || evidence.type}
        </span>
        {evidence.verified && (
          <span className="flex items-center gap-0.5 text-[10px] text-[#15803d]">
            <CheckCircle2 className="h-3 w-3" /> Verified
          </span>
        )}
        {evidence.contested && (
          <span className="flex items-center gap-0.5 text-[10px] text-[#c2410c]">
            <AlertTriangle className="h-3 w-3" /> Contested
          </span>
        )}
        <span className="ml-auto text-[10px] text-[var(--color-subtle)]">{formatRelativeTime(evidence.created_at)}</span>
      </div>
      <p className="text-xs text-[var(--color-body)] leading-relaxed mb-2">{evidence.content}</p>
      <div className="flex items-center justify-between">
        {evidence.agent_name && <span className="text-[10px] text-[var(--color-muted)]">by {evidence.agent_name}</span>}
        {evidence.source_url && (
          <a href={evidence.source_url} target="_blank" rel="noopener" className="flex items-center gap-0.5 text-[10px] text-[var(--color-primary)] hover:underline">
            Source <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
    </div>
  );
}
