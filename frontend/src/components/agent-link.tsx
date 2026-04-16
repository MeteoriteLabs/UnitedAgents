import Link from "next/link";

interface AgentLinkProps {
  agentId: string;
  name: string;
  className?: string;
}

/** Plain text link to /agents/{id} per GOTCHAS §6.4. */
export function AgentLink({ agentId, name, className = "" }: AgentLinkProps) {
  return (
    <Link
      href={`/agents/${agentId}`}
      className={`text-[var(--color-primary)] hover:underline ${className}`}
      data-testid={`agent-link-${name}`}
    >
      {name}
    </Link>
  );
}
