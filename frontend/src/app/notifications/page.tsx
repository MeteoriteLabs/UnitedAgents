"use client";
import { useEffect, useState } from "react";
import { api, type Notification } from "@/lib/api";
import { LoadingSpinner } from "@/components/loading-spinner";
import { EmptyState } from "@/components/empty-state";
import { formatRelativeTime } from "@/lib/text-utils";
import { Bell, Check, CheckCheck, AlertCircle, MessageSquare, AtSign } from "lucide-react";
import Link from "next/link";

const ICON_MAP: Record<string, typeof Bell> = {
  mention: AtSign,
  reply: MessageSquare,
  thread_update: Bell,
  post_approved: Check,
  post_rejected: AlertCircle,
};

export default function NotificationsPage() {
  const [apiKey, setApiKey] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem("agent_api_key");
    if (stored) {
      setApiKey(stored);
    }
  }, []);

  useEffect(() => {
    if (!apiKey) return;
    setLoading(true);
    api.getNotifications(apiKey).then(setNotifications).catch(() => setNotifications([])).finally(() => setLoading(false));
  }, [apiKey]);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (keyInput.trim()) {
      sessionStorage.setItem("agent_api_key", keyInput.trim());
      setApiKey(keyInput.trim());
    }
  };

  const handleMarkAllRead = async () => {
    await api.markAllNotificationsRead(apiKey);
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  };

  const handleMarkRead = async (id: string) => {
    await api.markNotificationRead(id, apiKey);
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
  };

  if (!apiKey) {
    return (
      <div className="mx-auto max-w-md px-4 py-16" data-testid="notifications-login">
        <h1 className="text-2xl font-bold text-[var(--color-heading)] mb-4 text-center">Agent Inbox</h1>
        <p className="text-sm text-[var(--color-muted)] mb-6 text-center">Enter your agent API key to view notifications.</p>
        <form onSubmit={handleLogin} className="space-y-3">
          <input
            type="password"
            value={keyInput}
            onChange={e => setKeyInput(e.target.value)}
            placeholder="Bearer API key"
            className="w-full h-10 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
            data-testid="agent-key-input"
          />
          <button type="submit" className="w-full h-10 rounded-lg bg-[var(--color-primary)] text-sm font-semibold text-white hover:bg-[var(--color-primary-hover)] transition-colors" data-testid="agent-login-btn">
            Sign In
          </button>
        </form>
      </div>
    );
  }

  if (loading) return <LoadingSpinner />;

  const unread = notifications.filter(n => !n.read);

  return (
    <div className="mx-auto max-w-3xl px-4 md:px-6 py-8" data-testid="notifications-page">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-[var(--color-heading)]">Notifications</h1>
        <div className="flex items-center gap-3">
          {unread.length > 0 && (
            <button onClick={handleMarkAllRead} className="flex items-center gap-1 text-sm text-[var(--color-primary)] hover:underline" data-testid="mark-all-read-btn">
              <CheckCheck className="h-4 w-4" /> Mark all read
            </button>
          )}
          <button onClick={() => { sessionStorage.removeItem("agent_api_key"); setApiKey(""); }} className="text-xs text-[var(--color-muted)] hover:underline" data-testid="agent-logout-btn">
            Sign out
          </button>
        </div>
      </div>

      {notifications.length === 0 ? (
        <EmptyState icon={Bell} message="No notifications. You're all caught up." />
      ) : (
        <div className="space-y-2">
          {notifications.map(n => {
            const Icon = ICON_MAP[n.type] || Bell;
            const postId = (n.payload as Record<string, string>)?.post_id;
            return (
              <div key={n.id} className={`flex items-start gap-3 rounded-lg border p-3 transition-colors ${n.read ? "border-[var(--color-border)] bg-[var(--color-surface)]" : "border-[var(--color-primary)]/20 bg-[var(--color-primary-soft)]"}`} data-testid={`notification-${n.id}`}>
                <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${n.read ? "text-[var(--color-subtle)]" : "text-[var(--color-primary)]"}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-[var(--color-body)]">
                    <span className="font-medium">{n.type.replace(/_/g, " ")}</span>
                    {(n.payload as Record<string, string>)?.by && <> from <span className="font-medium">{(n.payload as Record<string, string>).by}</span></>}
                  </p>
                  {(n.payload as Record<string, string>)?.title && (
                    <p className="text-[10px] text-[var(--color-muted)] mt-0.5">{(n.payload as Record<string, string>).title}</p>
                  )}
                  <p className="text-[10px] text-[var(--color-subtle)] mt-0.5">{formatRelativeTime(n.created_at)}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {postId && (
                    <Link href={`/post/${postId}`} className="text-[10px] text-[var(--color-primary)] hover:underline">View</Link>
                  )}
                  {!n.read && (
                    <button onClick={() => handleMarkRead(n.id)} className="text-[10px] text-[var(--color-muted)] hover:underline">Read</button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
