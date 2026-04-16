"use client";
import { useEffect, useState, useCallback } from "react";
import { api, type Post, type Community } from "@/lib/api";
import { PostItem } from "@/components/post-item";
import { VoiceUpdate } from "@/components/voice-update";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Rss } from "lucide-react";

export default function FeedPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [communities, setCommunities] = useState<Community[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState("");
  const [communityFilter, setCommunityFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  const fetchFeed = useCallback(async () => {
    try {
      const data = await api.getFeed({
        type: typeFilter || undefined,
        community_id: communityFilter || undefined,
        limit: LIMIT,
        offset,
      });
      setPosts(data);
    } catch { /* silent */ }
    setLoading(false);
  }, [typeFilter, communityFilter, offset]);

  useEffect(() => {
    api.listCommunities().then(setCommunities).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchFeed();
    const interval = setInterval(fetchFeed, 60000);
    return () => clearInterval(interval);
  }, [fetchFeed]);

  const types = ["", "voice_update", "task", "discussion", "research_note", "signal", "evidence_submission"];

  return (
    <div className="mx-auto max-w-6xl px-4 md:px-6 py-8" data-testid="feed-page">
      <h1 className="text-3xl font-bold text-[var(--color-heading)] mb-6">Live Feed</h1>
      <div className="flex flex-wrap gap-3 mb-6">
        <select value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setOffset(0); }}
          className="h-8 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs" data-testid="filter-type">
          <option value="">All types</option>
          {types.filter(Boolean).map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
        <select value={communityFilter} onChange={e => { setCommunityFilter(e.target.value); setOffset(0); }}
          className="h-8 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs" data-testid="filter-community">
          <option value="">All communities</option>
          {communities.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      {loading ? <LoadingSpinner /> : posts.length === 0 ? (
        <EmptyState icon={Rss} message="No activity yet. Check back soon." />
      ) : (
        <div className="space-y-4">
          {posts.map(p => p.type === "voice_update"
            ? <VoiceUpdate key={p.id} post={p} />
            : <PostItem key={p.id} post={p} />
          )}
        </div>
      )}
      {posts.length >= LIMIT && (
        <div className="flex justify-center gap-3 mt-6">
          {offset > 0 && <button onClick={() => setOffset(o => Math.max(0, o - LIMIT))} className="text-sm text-[var(--color-primary)] hover:underline">Previous</button>}
          <button onClick={() => setOffset(o => o + LIMIT)} className="text-sm text-[var(--color-primary)] hover:underline">Next</button>
        </div>
      )}
    </div>
  );
}
