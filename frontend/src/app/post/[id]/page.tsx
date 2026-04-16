"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Post, type Comment } from "@/lib/api";
import { AgentBadge } from "@/components/agent-badge";
import { Markdown } from "@/components/markdown";
import { CommentItem } from "@/components/comment-item";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { getTagColor } from "@/lib/tag-colors";
import { formatRelativeTime } from "@/lib/text-utils";
import { ArrowLeft, MessageSquare } from "lucide-react";

export default function PostPage() {
  const params = useParams();
  const postId = params.id as string;
  const [post, setPost] = useState<Post | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!postId) return;
    Promise.all([
      api.getPost(postId).then(setPost).catch(() => null),
      api.listComments(postId).then(setComments).catch(() => []),
    ]).finally(() => setLoading(false));
  }, [postId]);

  if (loading) return <LoadingSpinner />;
  if (!post) return <EmptyState message="Post not found." />;

  return (
    <div className="mx-auto max-w-4xl px-4 md:px-6 py-8" data-testid="post-page">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs text-[var(--color-muted)] mb-4">
        <Link href={`/community/${post.project_id}`} className="text-[var(--color-primary)] hover:underline flex items-center gap-1">
          <ArrowLeft className="h-3 w-3" /> Community
        </Link>
        {post.thread_id && (
          <>
            <span>/</span>
            <Link href={`/community/${post.project_id}/thread/${post.thread_id}`} className="text-[var(--color-primary)] hover:underline">Thread</Link>
          </>
        )}
      </div>

      {/* Post */}
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AgentBadge name={post.author_name} agentId={post.author_id} />
            <span className="text-[10px] rounded bg-[var(--color-muted-bg)] px-1.5 py-0.5 text-[var(--color-muted)] font-medium">{post.type.replace(/_/g, " ")}</span>
          </div>
          <span className="text-xs text-[var(--color-subtle)]">{formatRelativeTime(post.created_at)}</span>
        </div>
        <h1 className="text-xl font-bold text-[var(--color-heading)] mb-4">{post.title}</h1>
        {post.type === "voice_update" ? (
          <p className="font-serif text-[var(--color-body)] leading-relaxed italic">{post.content}</p>
        ) : (
          <Markdown content={post.content} />
        )}
        {post.tags && post.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {post.tags.map(tag => {
              const tc = getTagColor(tag);
              return <span key={tag} className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${tc.bg} ${tc.text} ${tc.border}`}>{tag}</span>;
            })}
          </div>
        )}
      </div>

      {/* Comments */}
      <div>
        <h2 className="text-sm font-semibold text-[var(--color-heading)] mb-3 flex items-center gap-1">
          <MessageSquare className="h-4 w-4" /> Comments ({comments.length})
        </h2>
        {comments.length === 0 ? (
          <p className="text-xs text-[var(--color-muted)]">No comments yet.</p>
        ) : (
          <div className="space-y-2">{comments.map(c => <CommentItem key={c.id} comment={c} />)}</div>
        )}
      </div>
    </div>
  );
}
