"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Thread, type Post, type Evidence } from "@/lib/api";
import { PostItem } from "@/components/post-item";
import { VoiceUpdate } from "@/components/voice-update";
import { EvidenceItem } from "@/components/evidence-item";
import { ReplyGroup } from "@/components/reply-group";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { formatRelativeTime } from "@/lib/text-utils";
import { Users, ArrowLeft, GitBranch } from "lucide-react";
import type { Comment } from "@/lib/api";

const STAGE_COLORS: Record<string, string> = {
  sensing: "bg-[#e0f2fe] text-[#0369a1]",
  investigating: "bg-[#fef3c7] text-[#b45309]",
  building: "bg-[#dcfce7] text-[#15803d]",
  threshold_approaching: "bg-[#ffedd5] text-[#c2410c]",
  action_ready: "bg-[#fee2e2] text-[#991b1b]",
  resolved: "bg-[#f5f2ec] text-[#78716c]",
};

export default function ThreadPage() {
  const params = useParams();
  const communityId = params.id as string;
  const threadId = params.threadId as string;
  const [thread, setThread] = useState<Thread | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [childThreads, setChildThreads] = useState<Thread[]>([]);
  const [comments, setComments] = useState<Record<string, Comment[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!threadId || !communityId) return;
    Promise.all([
      api.getThread(threadId).then(setThread).catch(() => null),
      api.listPosts(communityId, { thread_id: threadId, limit: 50 }).then(setPosts).catch(() => []),
      api.listEvidence(communityId, { thread_id: threadId }).then(setEvidence).catch(() => []),
      api.listThreads(communityId).then(ts => setChildThreads(ts.filter(t => t.parent_thread_id === threadId))).catch(() => []),
    ]).finally(() => setLoading(false));
  }, [threadId, communityId]);

  // Load comments for each post
  useEffect(() => {
    posts.forEach(p => {
      if (p.comment_count > 0) {
        api.listComments(p.id).then(c => setComments(prev => ({ ...prev, [p.id]: c }))).catch(() => {});
      }
    });
  }, [posts]);

  if (loading) return <LoadingSpinner />;
  if (!thread) return <EmptyState message="Thread not found." />;

  const stageColor = STAGE_COLORS[thread.stage] || STAGE_COLORS.sensing;

  // Interleave posts and evidence by created_at
  const timeline = [
    ...posts.map(p => ({ ...p, _kind: "post" as const })),
    ...evidence.map(e => ({ ...e, _kind: "evidence" as const })),
  ].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  return (
    <div className="mx-auto max-w-6xl px-4 md:px-6 py-8" data-testid="thread-page">
      <Link href={`/community/${communityId}`} className="flex items-center gap-1 text-sm text-[var(--color-primary)] hover:underline mb-4">
        <ArrowLeft className="h-4 w-4" /> Back to community
      </Link>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start gap-3 mb-2">
          <h1 className="text-2xl font-bold text-[var(--color-heading)]">{thread.title}</h1>
          <span className={`shrink-0 mt-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${stageColor}`}>
            {thread.stage.replace(/_/g, " ")}
          </span>
        </div>
        {thread.description && <p className="text-sm text-[var(--color-muted)] mb-3">{thread.description}</p>}
        <div className="flex items-center gap-4 text-xs text-[var(--color-subtle)]">
          <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />{thread.participant_count} participants</span>
          <span>{thread.evidence_count} evidence</span>
          <span>{thread.post_count} posts</span>
          <span>Created {formatRelativeTime(thread.created_at)}</span>
        </div>
      </div>

      {/* Child threads */}
      {childThreads.length > 0 && (
        <div className="mb-6 rounded-lg border border-[var(--color-border)] bg-[var(--color-muted-bg)] p-4">
          <h3 className="text-xs font-semibold text-[var(--color-heading)] mb-2 flex items-center gap-1">
            <GitBranch className="h-3.5 w-3.5" /> Sub-investigations ({childThreads.length})
          </h3>
          <div className="space-y-2">
            {childThreads.map(ct => (
              <Link key={ct.id} href={`/community/${communityId}/thread/${ct.id}`}
                className="flex items-center gap-2 text-sm text-[var(--color-primary)] hover:underline">
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${STAGE_COLORS[ct.stage] || ""}`}>{ct.stage}</span>
                {ct.title}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      {timeline.length === 0 ? <EmptyState message="No activity in this thread yet." /> : (
        <div className="space-y-4">
          {timeline.map(item => {
            if (item._kind === "evidence") {
              const ev = item as Evidence & { _kind: "evidence" };
              return <EvidenceItem key={`ev-${ev.id}`} evidence={ev} />;
            }
            const post = item as Post & { _kind: "post" };
            return (
              <div key={`post-${post.id}`}>
                {post.type === "voice_update" ? <VoiceUpdate post={post} /> : <PostItem post={post} />}
                {comments[post.id] && comments[post.id].length > 0 && (
                  <div className="ml-4"><ReplyGroup comments={comments[post.id]} /></div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
