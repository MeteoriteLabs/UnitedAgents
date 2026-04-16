/**
 * Text utilities — getPreview and mention parser.
 * GOTCHAS §6.4: mention links target /agents/{id}.
 */

export function getPreview(content: string, maxLen: number = 200): string {
  if (!content) return '';
  const text = content.replace(/[#*`_~\[\]()]/g, '').replace(/\n+/g, ' ').trim();
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).replace(/\s\S*$/, '') + '...';
}

export function parseMentions(text: string): string[] {
  if (!text) return [];
  const matches = text.match(/@([\w-]+)/g);
  if (!matches) return [];
  return [...new Set(matches.map(m => m.slice(1)))];
}

export function formatRelativeTime(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-');
}
