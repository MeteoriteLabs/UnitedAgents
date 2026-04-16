/**
 * Tag colors — 16-color hash-based assignment.
 * Verbatim from ALGORITHMS.md §11.
 */

const TAG_COLORS = [
  { bg: "bg-[#fee2e2]", text: "text-[#991b1b]", border: "border-[#fecaca]" },
  { bg: "bg-[#ffedd5]", text: "text-[#c2410c]", border: "border-[#fed7aa]" },
  { bg: "bg-[#fef3c7]", text: "text-[#b45309]", border: "border-[#fde68a]" },
  { bg: "bg-[#fef9c3]", text: "text-[#854d0e]", border: "border-[#fde68a]" },
  { bg: "bg-[#ecfccb]", text: "text-[#3f6212]", border: "border-[#d9f99d]" },
  { bg: "bg-[#dcfce7]", text: "text-[#15803d]", border: "border-[#bbf7d0]" },
  { bg: "bg-[#d1fae5]", text: "text-[#047857]", border: "border-[#a7f3d0]" },
  { bg: "bg-[#ccfbf1]", text: "text-[#115e59]", border: "border-[#99f6e4]" },
  { bg: "bg-[#cffafe]", text: "text-[#155e75]", border: "border-[#a5f3fc]" },
  { bg: "bg-[#e0f2fe]", text: "text-[#0369a1]", border: "border-[#bae6fd]" },
  { bg: "bg-[#dbeafe]", text: "text-[#1e40af]", border: "border-[#bfdbfe]" },
  { bg: "bg-[#e0e7ff]", text: "text-[#3730a3]", border: "border-[#c7d2fe]" },
  { bg: "bg-[#ede9fe]", text: "text-[#5b21b6]", border: "border-[#ddd6fe]" },
  { bg: "bg-[#f3e8ff]", text: "text-[#6b21a8]", border: "border-[#e9d5ff]" },
  { bg: "bg-[#fae8ff]", text: "text-[#86198f]", border: "border-[#f5d0fe]" },
  { bg: "bg-[#fce7f3]", text: "text-[#9d174d]", border: "border-[#fbcfe8]" },
];

function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash);
}

export function getTagColor(tag: string) {
  const index = hashString(tag.toLowerCase()) % TAG_COLORS.length;
  return TAG_COLORS[index];
}

export { TAG_COLORS };
