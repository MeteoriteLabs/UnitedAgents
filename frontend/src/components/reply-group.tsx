"use client";
import { useState } from "react";
import type { Comment } from "@/lib/api";
import { CommentItem } from "./comment-item";

export function ReplyGroup({ comments }: { comments: Comment[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!comments.length) return null;

  const visible = expanded ? comments : comments.slice(-2);
  const hidden = comments.length - 2;

  return (
    <div className="mt-2 space-y-1" data-testid="reply-group">
      {!expanded && hidden > 0 && (
        <button onClick={() => setExpanded(true)} className="text-[10px] text-[var(--color-primary)] hover:underline mb-1" data-testid="show-more-replies">
          Show {hidden} more {hidden === 1 ? "reply" : "replies"}
        </button>
      )}
      {visible.map(c => <CommentItem key={c.id} comment={c} />)}
    </div>
  );
}
