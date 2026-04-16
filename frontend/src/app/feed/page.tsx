"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { api, type Post, type Community } from "@/lib/api";
import { PostItem } from "@/components/post-item";
import { VoiceUpdate } from "@/components/voice-update";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Rss, ArrowUp, Wifi, WifiOff } from "lucide-react";

export default function FeedPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [communities, setCommunities] = useState<Community[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState("");
  const [communityFilter, setCommunityFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [newPosts, setNewPosts] = useState<Post[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
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

  // WebSocket connection
  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || process.env.REACT_APP_BACKEND_URL || '';
    const wsUrl = apiBase.replace(/^http/, 'ws') + '/api/v1/ws/feed';

    function connect() {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
          // Keep alive ping every 30s
          const pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send('ping');
            }
          }, 30000);
          ws.addEventListener('close', () => clearInterval(pingInterval));
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'new_post' && data.post) {
              setNewPosts(prev => [data.post, ...prev]);
            }
          } catch { /* ignore non-JSON */ }
        };

        ws.onclose = () => {
          setWsConnected(false);
          // Reconnect after 5s
          setTimeout(connect, 5000);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        setTimeout(connect, 5000);
      }
    }

    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  function loadNewPosts() {
    setPosts(prev => [...newPosts, ...prev]);
    setNewPosts([]);
  }

  const types = ["", "voice_update", "task", "discussion", "research_note", "signal", "evidence_submission"];

  return (
    <div className="mx-auto max-w-6xl px-4 md:px-6 py-8 animate-fade-in" data-testid="feed-page">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-[var(--color-heading)]">Live Feed</h1>
        <div className="flex items-center gap-2">
          {wsConnected ? (
            <span className="flex items-center gap-1 text-[10px] text-[#15803d] font-medium" data-testid="ws-connected">
              <Wifi className="h-3 w-3" />
              <span className="animate-pulse-dot h-1.5 w-1.5 rounded-full bg-[#15803d] inline-block" />
              Live
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[10px] text-[var(--color-subtle)]" data-testid="ws-disconnected">
              <WifiOff className="h-3 w-3" /> Connecting...
            </span>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-3 mb-6">
        <select value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setOffset(0); }}
          className="h-8 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-xs text-[var(--color-body)] transition-colors focus:ring-1 focus:ring-[var(--color-primary)]" data-testid="filter-type">
          <option value="">All types</option>
          {types.filter(Boolean).map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
        <select value={communityFilter} onChange={e => { setCommunityFilter(e.target.value); setOffset(0); }}
          className="h-8 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-xs text-[var(--color-body)] transition-colors focus:ring-1 focus:ring-[var(--color-primary)]" data-testid="filter-community">
          <option value="">All communities</option>
          {communities.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {/* New posts notification pill */}
      {newPosts.length > 0 && (
        <button
          onClick={loadNewPosts}
          className="ws-new-pill w-full mb-4 flex items-center justify-center gap-2 rounded-lg border border-[var(--color-primary)]/30 bg-[var(--color-primary-soft)] py-2 text-xs font-semibold text-[var(--color-primary)] hover:bg-[var(--color-primary)]/15 transition-colors"
          data-testid="new-posts-pill"
        >
          <ArrowUp className="h-3.5 w-3.5" />
          {newPosts.length} new {newPosts.length === 1 ? 'post' : 'posts'} — Click to load
        </button>
      )}

      {loading ? <LoadingSpinner /> : posts.length === 0 ? (
        <EmptyState icon={Rss} message="No activity yet. Check back soon." />
      ) : (
        <div className="space-y-4 stagger-children">
          {posts.map(p => p.type === "voice_update"
            ? <VoiceUpdate key={p.id} post={p} />
            : <PostItem key={p.id} post={p} />
          )}
        </div>
      )}
      {posts.length >= LIMIT && (
        <div className="flex justify-center gap-4 mt-8">
          {offset > 0 && (
            <button onClick={() => setOffset(o => Math.max(0, o - LIMIT))}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-1.5 text-xs font-medium text-[var(--color-heading)] hover:bg-[var(--color-elevated)] transition-colors" data-testid="feed-prev">
              Previous
            </button>
          )}
          <button onClick={() => setOffset(o => o + LIMIT)}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-1.5 text-xs font-medium text-[var(--color-heading)] hover:bg-[var(--color-elevated)] transition-colors" data-testid="feed-next">
            Next
          </button>
        </div>
      )}
    </div>
  );
}
