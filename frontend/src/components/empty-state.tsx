import { Inbox } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon?: LucideIcon;
  message: string;
  action?: { label: string; href: string };
}

export function EmptyState({ icon: Icon = Inbox, message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center" data-testid="empty-state">
      <Icon className="h-10 w-10 text-[var(--color-subtle)] mb-3" />
      <p className="text-sm text-[var(--color-muted)]">{message}</p>
      {action && (
        <a href={action.href} className="mt-3 text-sm font-medium text-[var(--color-primary)] hover:underline">
          {action.label}
        </a>
      )}
    </div>
  );
}
