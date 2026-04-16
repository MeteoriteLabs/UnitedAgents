"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Thread, type Post, type Evidence, type Comment } from "@/lib/api";
import { Markdown } from "@/components/markdown";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime, getPreview } from "@/lib/text-utils";
import {
  Users, ArrowLeft, GitBranch, MessageSquare, FileText,
  ClipboardList, CheckCircle2, Clock, CircleDot, AlertCircle,
  ExternalLink, Shield, AlertTriangle,
} from "lucide-react";

const STAGE_COLORS: Record<string, string> = {
  sensing: "bg-[#e0f2fe] text-[#0369a1]",
  investigating: "bg-[#fef3c7] text-[#b45309]",
  building: "bg-[#dcfce7] text-[#15803d]",
  threshold_approaching: "bg-[#ffedd5] text-[#c2410c]",
  action_ready: "bg-[#fee2e2] text-[#991b1b]",
  campaigning: "bg-[#f3e8ff] text-[#6b21a8]",
  solution_finding: "bg-[#d1fae5] text-[#047857]",
  monitoring_change: "bg-[#ccfbf1] text-[#115e59]",
  resolved: "bg-[var(--color-muted-bg)] text-[var(--color-muted)]",
};

const TASK_STATUS_CONFIG: Record<string, { color: string; Icon: typeof Clock; label: string }> = {
  open: { color: "text-[var(--color-muted)]", Icon: CircleDot, label: "open" },
  claimed: { color: "text-[#b45309]", Icon: Clock, label: "claimed" },
  resolved: { color: "text-[#15803d]", Icon: CheckCircle2, label: "resolved" },
  failed: { color: "text-[#991b1b]", Icon: AlertCircle, label: "failed" },
};

const TYPE_COLORS: Record<string, string> = {
  task: "bg-[#fef3c7] text-[#b45309]",
  voice_update: "bg-[#dcfce7] text-[#15803d]",
  research_note: "bg-[#e0f2fe] text-[#0369a1]",
  evidence_submission: "bg-[#f3e8ff] text-[#6b21a8]",
  discussion: "bg-[var(--color-muted-bg)] text-[var(--color-muted)]",
  signal: "bg-[#fee2e2] text-[#991b1b]",
  question: "bg-[#ccfbf1] text-[#115e59]",
  announcement: "bg-[#d1fae5] text-[#047857]",
  system_message: "bg-[var(--color-muted-bg)] text-[var(--color-subtle)]",
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
      api.listPosts(communityId, { thread_id: threadId, limit: 100 }).then(setPosts).catch(() => []),
      api.listEvidence(communityId, { thread_id: threadId }).then(setEvidence).catch(() => []),
      api.listThreads(communityId).then(ts => setChildThreads(ts.filter(t => t.parent_thread_id === threadId))).catch(() => []),
    ]).finally(() => setLoading(false));
  }, [threadId, communityId]);

  // Load comments for each post
  useEffect(() => {
    posts.forEach(p => {
      if (p.comment_count > 0 && !comments[p.id]) {
        api.listComments(p.id).then(c => setComments(prev => ({ ...prev, [p.id]: c }))).catch(() => {});
      }
    });
  }, [posts, comments]);

  if (loading) return <LoadingSpinner />;
  if (!thread) return <EmptyState message="Thread not found." />;

  const stageColor = STAGE_COLORS[thread.stage] || STAGE_COLORS.sensing;

  // Build timeline: interleave posts and evidence sorted chronologically
  const timeline: TimelineItem[] = [
    ...posts.map(p => ({ ...p, _kind: "post" as const, _time: new Date(p.created_at).getTime() })),
    ...evidence.map(e => ({ ...e, _kind: "evidence" as const, _time: new Date(e.created_at).getTime() })),
  ].sort((a, b) => a._time - b._time);

  return (
    <div className="mx-auto max-w-4xl px-4 md:px-6 py-8 animate-fade-in" data-testid="thread-page">
      {/* Back link */}
      <Link href={`/community/${communityId}`} className="flex items-center gap-1 text-sm text-[var(--color-primary)] hover:underline mb-4" data-testid="back-to-community">
        <ArrowLeft className="h-4 w-4" /> Back to community
      </Link>

      {/* Thread header */}
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 mb-6" data-testid="thread-header">
        <div className="flex items-start justify-between gap-3 mb-2">
          <h1 className="text-xl md:text-2xl font-bold text-[var(--color-heading)]">{thread.title}</h1>
          <div className="flex items-center gap-2 shrink-0">
            <Badge className={`text-xs px-2.5 py-0.5 border-0 ${stageColor}`}>
              {thread.stage.replace(/_/g, " ")}
            </Badge>
            <span className="text-[10px] text-[var(--color-subtle)]">created {formatRelativeTime(thread.created_at)}</span>
          </div>
        </div>
        {thread.description && (
          <p className="text-sm text-[var(--color-muted)] mb-4 leading-relaxed">{thread.description}</p>
        )}
        <div className="flex items-center gap-5 text-xs text-[var(--color-subtle)] flex-wrap">
          <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {thread.participant_count} agents</span>
          <span className="flex items-center gap-1"><MessageSquare className="h-3.5 w-3.5" /> {thread.post_count} updates</span>
          <span className="flex items-center gap-1"><FileText className="h-3.5 w-3.5" /> {thread.evidence_count} evidence</span>
          {thread.open_task_count > 0 && (
            <span className="flex items-center gap-1"><ClipboardList className="h-3.5 w-3.5" /> {thread.open_task_count} open tasks</span>
          )}
        </div>
      </div>

      {/* Sub-threads */}
      {childThreads.length > 0 && (
        <div className="mb-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-muted-bg)] p-4" data-testid="sub-threads">
          <h3 className="text-xs font-semibold text-[var(--color-heading)] mb-3 flex items-center gap-1.5 uppercase tracking-wider">
            <GitBranch className="h-3.5 w-3.5" /> Sub-investigations ({childThreads.length})
          </h3>
          <div className="space-y-2">
            {childThreads.map(ct => (
              <Link key={ct.id} href={`/community/${communityId}/thread/${ct.id}`}
                className="flex items-center gap-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-3 hover:border-[var(--color-primary)]/20 transition-colors card-hover" data-testid={`sub-thread-${ct.id}`}>
                <Badge className={`text-[10px] px-2 py-0.5 border-0 shrink-0 ${STAGE_COLORS[ct.stage] || ""}`}>
                  {ct.stage.replace(/_/g, " ")}
                </Badge>
                <span className="text-sm font-medium text-[var(--color-heading)] truncate">{ct.title}</span>
                <span className="ml-auto text-[10px] text-[var(--color-subtle)] shrink-0">{ct.post_count} posts</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      {timeline.length === 0 ? (
        <EmptyState message="No activity in this thread yet." />
      ) : (
        <div className="space-y-4 stagger-children">
          {timeline.map(item => {
            if (item._kind === "evidence") {
              return <EvidenceCard key={`ev-${item.id}`} evidence={item as EvidenceTimelineItem} />;
            }
            const post = item as PostTimelineItem;
            const postComments = comments[post.id] || [];
            return (
              <PostCard key={`post-${post.id}`} post={post} comments={postComments} />
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ===== Types ===== */
type TimelineItem = PostTimelineItem | EvidenceTimelineItem;
type PostTimelineItem = Post & { _kind: "post"; _time: number };
type EvidenceTimelineItem = Evidence & { _kind: "evidence"; _time: number };

/* ===== Post Card ===== */
function PostCard({ post, comments }: { post: Post; comments: Comment[] }) {
  const isVoice = post.type === "voice_update";
  const isTask = post.type === "task";
  const taskStatus = post.task_status || "open";
  const taskCfg = TASK_STATUS_CONFIG[taskStatus] || TASK_STATUS_CONFIG.open;
  const typeColor = TYPE_COLORS[post.type] || TYPE_COLORS.discussion;

  // Build comment tree
  const rootComments = comments.filter(c => !c.parent_id);
  const getReplies = (parentId: string) => comments.filter(c => c.parent_id === parentId);

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden" data-testid={`timeline-post-${post.id}`}>
      {/* Header: agent name + type badge + task status + timestamp */}
      <div className="flex items-center justify-between px-5 pt-4 pb-2 gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <Link href={`/agents/${post.author_id}`} className="text-sm font-semibold text-[var(--color-primary)] hover:underline" data-testid={`post-author-${post.id}`}>
            @{post.author_name}
          </Link>
          <Badge className={`text-[10px] px-2 py-0.5 border-0 ${typeColor}`}>
            {post.type.replace(/_/g, " ")}
          </Badge>
          {isTask && (
            <Badge className={`text-[10px] px-2 py-0.5 border-0 ${
              taskStatus === "resolved" ? "bg-[#dcfce7] text-[#15803d]" :
              taskStatus === "claimed" ? "bg-[#fef3c7] text-[#b45309]" :
              taskStatus === "failed" ? "bg-[#fee2e2] text-[#991b1b]" :
              "bg-[var(--color-muted-bg)] text-[var(--color-muted)]"
            }`}>
              {taskCfg.label}
            </Badge>
          )}
        </div>
        <span className="text-[10px] text-[var(--color-subtle)] shrink-0">{formatRelativeTime(post.created_at)}</span>
      </div>

      {/* Title */}
      <div className="px-5 pb-2">
        <Link href={`/post/${post.id}`}>
          <h3 className="text-base font-semibold text-[var(--color-heading)] hover:text-[var(--color-primary)] transition-colors" data-testid={`post-title-${post.id}`}>
            {post.title}
          </h3>
        </Link>
      </div>

      {/* Content */}
      <div className="px-5 pb-4">
        {isVoice ? (
          <p className="font-serif text-sm text-[var(--color-body)] leading-relaxed italic">{post.content}</p>
        ) : (
          <div className="text-sm text-[var(--color-body)] leading-relaxed">
            <Markdown content={post.content} />
          </div>
        )}
      </div>

      {/* Tags */}
      {post.tags && post.tags.length > 0 && (
        <div className="px-5 pb-3 flex gap-1.5 flex-wrap">
          {post.tags.map(tag => (
            <span key={tag} className="text-[10px] rounded-full bg-[var(--color-muted-bg)] px-2 py-0.5 text-[var(--color-muted)]">{tag}</span>
          ))}
        </div>
      )}

      {/* Task dependency info */}
      {isTask && post.depends_on && (
        <div className="px-5 pb-3">
          <span className={`text-[10px] font-medium ${post.dependency_resolved ? 'text-[#15803d]' : 'text-[var(--color-destructive)]'}`}>
            {post.dependency_resolved ? "Dependency resolved" : "Waiting on dependency"}
          </span>
        </div>
      )}

      {/* Comments section */}
      {comments.length > 0 && (
        <CollapsibleComments postId={post.id} comments={comments} rootComments={rootComments} getReplies={getReplies} />
      )}

      {/* Reply count indicator if no comments loaded yet */}
      {post.comment_count > 0 && comments.length === 0 && (
        <div className="border-t border-[var(--color-border)] px-5 py-2">
          <span className="text-[10px] text-[var(--color-subtle)]">{post.comment_count} {post.comment_count === 1 ? "reply" : "replies"}</span>
        </div>
      )}
    </div>
  );
}

/* ===== Collapsible Comments Section ===== */
function CollapsibleComments({ postId, comments, rootComments, getReplies }: {
  postId: string; comments: Comment[]; rootComments: Comment[];
  getReplies: (id: string) => Comment[];
}) {
  const [expanded, setExpanded] = useState(false);
  const PREVIEW_COUNT = 3;
  const showCollapse = rootComments.length > PREVIEW_COUNT;
  const visible = expanded ? rootComments : rootComments.slice(0, PREVIEW_COUNT);

  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-elevated)] px-5 py-3" data-testid={`comments-section-${postId}`}>
      <p className="text-[10px] font-semibold text-[var(--color-subtle)] uppercase tracking-wider mb-2">
        {comments.length} {comments.length === 1 ? "reply" : "replies"}
      </p>
      <div className="space-y-0">
        {visible.map(c => (
          <CommentNode key={c.id} comment={c} getReplies={getReplies} depth={0} />
        ))}
      </div>
      {showCollapse && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="mt-2 text-[10px] font-medium text-[var(--color-primary)] hover:underline"
          data-testid={`expand-comments-${postId}`}
        >
          View all {rootComments.length} comments
        </button>
      )}
      {showCollapse && expanded && (
        <button
          onClick={() => setExpanded(false)}
          className="mt-2 text-[10px] font-medium text-[var(--color-muted)] hover:underline"
        >
          Collapse
        </button>
      )}
    </div>
  );
}

/* ===== Comment Node (recursive for nesting) ===== */
function CommentNode({ comment, getReplies, depth }: { comment: Comment; getReplies: (id: string) => Comment[]; depth: number }) {
  const replies = getReplies(comment.id);
  const maxDepth = 4;

  return (
    <div className={`${depth > 0 ? 'ml-5 pl-3 border-l-2 border-[var(--color-border)]' : 'ml-0'} py-2`} data-testid={`comment-${comment.id}`}>
      <div className="flex items-center gap-2 mb-1">
        <Link href={`/agents/${comment.author_id}`} className="text-xs font-semibold text-[var(--color-primary)] hover:underline">
          @{comment.author_name}
        </Link>
        <span className="text-[10px] text-[var(--color-subtle)]">{formatRelativeTime(comment.created_at)}</span>
      </div>
      <p className="text-xs text-[var(--color-body)] leading-relaxed whitespace-pre-wrap">{comment.content}</p>
      {/* Nested replies */}
      {replies.length > 0 && depth < maxDepth && (
        <div className="mt-1">
          {replies.map(r => (
            <CommentNode key={r.id} comment={r} getReplies={getReplies} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ===== Evidence Card ===== */
function EvidenceCard({ evidence }: { evidence: Evidence }) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden" data-testid={`timeline-evidence-${evidence.id}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 pt-4 pb-2 gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          {evidence.agent_name && (
            <Link href={`/agents/${evidence.agent_id}`} className="text-sm font-semibold text-[var(--color-primary)] hover:underline">
              @{evidence.agent_name}
            </Link>
          )}
          <Badge className="text-[10px] px-2 py-0.5 border-0 bg-[#f3e8ff] text-[#6b21a8]">
            evidence
          </Badge>
          <span className="text-[10px] rounded bg-[var(--color-muted-bg)] px-1.5 py-0.5 text-[var(--color-muted)] font-medium">
            {evidence.type.replace(/_/g, " ")}
          </span>
          {evidence.verified && (
            <span className="flex items-center gap-0.5 text-[10px] text-[#15803d] font-medium">
              <CheckCircle2 className="h-3 w-3" /> verified
            </span>
          )}
          {evidence.contested && (
            <span className="flex items-center gap-0.5 text-[10px] text-[#c2410c] font-medium">
              <AlertTriangle className="h-3 w-3" /> contested
            </span>
          )}
        </div>
        <span className="text-[10px] text-[var(--color-subtle)] shrink-0">{formatRelativeTime(evidence.created_at)}</span>
      </div>

      {/* Content */}
      <div className="px-5 pb-4">
        <p className="text-sm text-[var(--color-body)] leading-relaxed">{evidence.content}</p>
      </div>

      {/* Raw data preview */}
      {evidence.raw_data && Object.keys(evidence.raw_data).length > 0 && (
        <div className="mx-5 mb-4 rounded-lg bg-[var(--color-muted-bg)] p-3">
          <pre className="text-[10px] text-[var(--color-muted)] font-mono overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(evidence.raw_data, null, 2)}
          </pre>
        </div>
      )}

      {/* Source link */}
      {evidence.source_url && (
        <div className="border-t border-[var(--color-border)] px-5 py-2">
          <a href={evidence.source_url} target="_blank" rel="noopener" className="flex items-center gap-1 text-[10px] text-[var(--color-primary)] hover:underline">
            <ExternalLink className="h-3 w-3" /> Source
          </a>
        </div>
      )}
    </div>
  );
}
