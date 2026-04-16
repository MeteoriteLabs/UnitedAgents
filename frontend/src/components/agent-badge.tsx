import Link from "next/link";

const ROLE_COLORS: Record<string, string> = {
  orchestrator: "bg-[#dcfce7] text-[#15803d] border-[#bbf7d0]",
  guardian: "bg-[#dcfce7] text-[#15803d] border-[#bbf7d0]",
  earth: "bg-[#d1fae5] text-[#047857] border-[#a7f3d0]",
  observer: "bg-[#ccfbf1] text-[#115e59] border-[#99f6e4]",
  scout: "bg-[#f5f2ec] text-[#78716c] border-[#e8e4dc]",
  worker: "bg-[#f5f2ec] text-[#78716c] border-[#e8e4dc]",
  member: "bg-[#f5f2ec] text-[#78716c] border-[#e8e4dc]",
};

interface AgentBadgeProps {
  name: string;
  agentId?: string;
  type?: string;
  showRole?: boolean;
}

export function AgentBadge({ name, agentId, type = "worker", showRole = false }: AgentBadgeProps) {
  const colors = ROLE_COLORS[type] || ROLE_COLORS.worker;
  const badge = (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${colors}`} data-testid={`agent-badge-${name}`}>
      @{name}
      {showRole && <span className="opacity-70">({type})</span>}
    </span>
  );

  if (agentId) {
    return <Link href={`/agents/${agentId}`} className="hover:opacity-80 transition-opacity">{badge}</Link>;
  }
  return badge;
}
