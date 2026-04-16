/**
 * Condition badge — score (0-100) + trend icon.
 * Verbatim from ALGORITHMS.md §12.
 */

interface ConditionBadgeProps {
  score?: number | null;
  trend?: string | null;
  size?: "sm" | "md";
}

function getScoreColor(score: number): string {
  if (score >= 80) return "bg-[#dcfce7] text-[#15803d] border-[#bbf7d0]";
  if (score >= 50) return "bg-[#fef9c3] text-[#854d0e] border-[#fde68a]";
  if (score >= 25) return "bg-[#ffedd5] text-[#c2410c] border-[#fed7aa]";
  return "bg-[#fee2e2] text-[#991b1b] border-[#fecaca]";
}

function getTrendIcon(trend: string | null | undefined): string {
  switch (trend) {
    case "improving": return "\u2191";
    case "declining": return "\u2193";
    case "critical":  return "\u26A0";
    case "stable":    return "\u2192";
    default:          return "";
  }
}

export function ConditionBadge({ score, trend, size = "sm" }: ConditionBadgeProps) {
  if (score == null) return null;
  const colors = getScoreColor(score);
  const icon = getTrendIcon(trend);
  const textSize = size === "sm" ? "text-xs" : "text-sm";

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium ${colors} ${textSize}`} data-testid="condition-badge">
      {Math.round(score)}
      {icon && <span>{icon}</span>}
    </span>
  );
}
