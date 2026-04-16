"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Community } from "@/lib/api";
import { ConditionBadge } from "@/components/condition-badge";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Globe } from "lucide-react";

export default function DashboardPage() {
  const [communities, setCommunities] = useState<Community[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listCommunities().then(setCommunities).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="mx-auto max-w-6xl px-4 md:px-6 py-8 animate-fade-in" data-testid="dashboard-page">
      <h1 className="text-3xl font-bold text-[var(--color-heading)] mb-6">Communities</h1>
      {communities.length === 0 ? (
        <EmptyState icon={Globe} message="No communities yet." />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
          {communities.map(c => (
            <Link key={c.id} href={`/community/${c.id}`} data-testid={`community-card-${c.id}`}>
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5 hover:bg-[var(--color-elevated)] hover:border-[var(--color-primary)]/20 transition-all duration-200 card-hover">
                <div className="flex items-center gap-2 mb-2">
                  {c.icon && <span className="text-xl">{c.icon}</span>}
                  <h3 className="text-base font-semibold text-[var(--color-heading)]">{c.name}</h3>
                </div>
                <p className="text-xs text-[var(--color-muted)] line-clamp-2 mb-3">{c.description}</p>
                <div className="flex items-center gap-3">
                  <ConditionBadge score={c.orchestrator_condition_score} trend={c.orchestrator_condition_trend} />
                  {c.orchestrator_name && <span className="text-[10px] text-[var(--color-subtle)]">by {c.orchestrator_name}</span>}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
