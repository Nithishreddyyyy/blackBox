"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRequireAuth } from "@/lib/auth";
import { apiFetch, getToken, getWebSocketUrl } from "@/lib/api";
import chatStyles from "./chat.module.css";

// ── Types ────────────────────────────────────────────────

interface Session {
  id: number;
  session_name: string;
  start_time: string | null;
  end_time: string | null;
  status: string;
}

interface ChatMessage {
  id: number;
  prompt_text: string;
  response_text: string | null;
  prompt_timestamp: string;
  response_timestamp: string | null;
  latency_ms: number | null;
  success: boolean;
}

interface ChatHistory {
  messages: ChatMessage[];
  remaining_messages: number;
  total_used: number;
}

interface Notification {
  id: number;
  message: string;
  priority: string;
  created_by: number;
  created_at: string;
}

// ── Main Component ───────────────────────────────────────

export default function UserChatPage() {
  const { user, loading: authLoading } = useRequireAuth("user");

  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [remaining, setRemaining] = useState(0);
  const [totalUsed, setTotalUsed] = useState(0);
  const [prompt, setPrompt] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [dismissedNotifs, setDismissedNotifs] = useState<Set<number>>(new Set());
  const [loadingSession, setLoadingSession] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // ── Fetch active sessions ──────────────────────────────

  useEffect(() => {
    if (authLoading || !user) return;

    apiFetch<Session[]>("/sessions/active")
      .then((data) => {
        setSessions(data);
        if (data.length > 0) {
          setActiveSession(data[0]);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingSession(false));
  }, [authLoading, user]);

  // ── Fetch chat history ─────────────────────────────────

  const loadHistory = useCallback(() => {
    if (!activeSession) return;

    apiFetch<ChatHistory>(`/chat/history?session_id=${activeSession.id}`)
      .then((data) => {
        setMessages(data.messages);
        setRemaining(data.remaining_messages);
        setTotalUsed(data.total_used);
        setTimeout(scrollToBottom, 100);
      })
      .catch(() => {});
  }, [activeSession, scrollToBottom]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // ── Poll notifications ─────────────────────────────────

  useEffect(() => {
    if (authLoading || !user) return;

    const fetchNotifs = () => {
      apiFetch<Notification[]>("/notifications/recent")
        .then(setNotifications)
        .catch(() => {});
    };

    fetchNotifs();
    const interval = setInterval(fetchNotifs, 10_000);
    return () => clearInterval(interval);
  }, [authLoading, user]);

  // ── WebSocket ──────────────────────────────────────────

  useEffect(() => {
    if (authLoading || !user) return;

    const token = getToken();
    const wsUrl = getWebSocketUrl("/ws", token);

    let ws: WebSocket;
    let reconnectTimer: NodeJS.Timeout;

    function connect() {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "notification") {
            setNotifications((prev) => {
              const exists = prev.some((n) => n.id === data.id);
              if (exists) return prev;
              return [
                {
                  id: data.id,
                  message: data.message,
                  priority: data.priority,
                  created_by: 0,
                  created_at: data.created_at,
                },
                ...prev,
              ];
            });
          } else if (data.type === "session_update") {
            // Refresh sessions
            apiFetch<Session[]>("/sessions/active").then(setSessions).catch(() => {});
          }
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 5000);
      };
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [authLoading, user]);

  // ── Send prompt ────────────────────────────────────────

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim() || !activeSession || sending) return;

    setError("");
    setSending(true);

    try {
      const newMsg = await apiFetch<ChatMessage>("/chat/send", {
        method: "POST",
        body: JSON.stringify({
          prompt: prompt.trim(),
          session_id: activeSession.id,
        }),
      });

      setMessages((prev) => [...prev, newMsg]);
      setTotalUsed((prev) => prev + 1);
      setRemaining((prev) => Math.max(0, prev - 1));
      setPrompt("");
      setTimeout(scrollToBottom, 100);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send prompt");
    } finally {
      setSending(false);
    }
  }

  // Dismiss notification
  function dismissNotif(id: number) {
    setDismissedNotifs((prev) => new Set(prev).add(id));
  }

  // ── Loading states ─────────────────────────────────────

  if (authLoading || !user) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
      </div>
    );
  }

  const visibleNotifs = notifications.filter((n) => !dismissedNotifs.has(n.id));

  // ── No active sessions ─────────────────────────────────

  if (!loadingSession && sessions.length === 0) {
    return (
      <div className={chatStyles.emptyState}>
        <div className={chatStyles.emptyIcon}>
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="var(--text-muted)" strokeWidth="1.5">
            <circle cx="24" cy="24" r="20" />
            <path d="M16 20h16M16 28h10" strokeLinecap="round" />
          </svg>
        </div>
        <h2 className={chatStyles.emptyTitle}>No Active Sessions</h2>
        <p className={chatStyles.emptyText}>
          Waiting for the admin to start a challenge session. Hang tight!
        </p>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────

  return (
    <div className={chatStyles.wrapper}>
      {/* Notification banners */}
      {visibleNotifs.length > 0 && (
        <div className={chatStyles.notifBar}>
          {visibleNotifs.slice(0, 3).map((n) => (
            <div
              key={n.id}
              className={`${chatStyles.notif} ${
                n.priority === "urgent"
                  ? chatStyles.notifUrgent
                  : n.priority === "high"
                    ? chatStyles.notifHigh
                    : ""
              }`}
            >
              <span className={chatStyles.notifMsg}>{n.message}</span>
              <button
                className={chatStyles.notifDismiss}
                onClick={() => dismissNotif(n.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Session bar */}
      {sessions.length > 1 && (
        <div className={chatStyles.sessionBar}>
          <label className="label" style={{ marginBottom: 0 }}>
            Session:
          </label>
          <select
            className="select"
            value={activeSession?.id || ""}
            onChange={(e) => {
              const s = sessions.find(
                (s) => s.id === Number(e.target.value)
              );
              if (s) setActiveSession(s);
            }}
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.session_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Chat area */}
      <div className={chatStyles.chatArea} ref={chatContainerRef}>
        {messages.length === 0 && (
          <div className={chatStyles.chatWelcome}>
            <h3>Challenge Active: {activeSession?.session_name}</h3>
            <p>
              Send prompts to the AI and try to achieve the target. You have{" "}
              <strong>{remaining}</strong> messages remaining.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={chatStyles.messageGroup}>
            {/* User prompt */}
            <div className={chatStyles.msgRow}>
              <div className={chatStyles.msgLabel}>You</div>
              <div className={`${chatStyles.msgBubble} ${chatStyles.msgUser}`}>
                {msg.prompt_text}
              </div>
            </div>

            {/* AI response */}
            {msg.response_text && (
              <div className={chatStyles.msgRow}>
                <div className={chatStyles.msgLabel}>AI</div>
                <div
                  className={`${chatStyles.msgBubble} ${chatStyles.msgAi} ${
                    !msg.success ? chatStyles.msgError : ""
                  }`}
                >
                  {msg.response_text}
                </div>
                {msg.latency_ms != null && msg.latency_ms > 0 && (
                  <span className={chatStyles.msgMeta}>
                    {msg.latency_ms}ms
                  </span>
                )}
              </div>
            )}
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div className={chatStyles.inputBar}>
        <div className={chatStyles.inputStats}>
          <span>
            {totalUsed} used · {remaining} remaining
          </span>
        </div>

        {error && <div className="alert alert-error" style={{ margin: "0 0 8px" }}>{error}</div>}

        <form onSubmit={handleSend} className={chatStyles.inputForm}>
          <input
            id="chat-input"
            type="text"
            className="input"
            placeholder={
              remaining <= 0
                ? "Message limit reached"
                : "Type your prompt…"
            }
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={sending || remaining <= 0}
            autoFocus
          />
          <button
            id="chat-send"
            type="submit"
            className="btn btn-primary"
            disabled={sending || !prompt.trim() || remaining <= 0}
          >
            {sending ? (
              <span
                className="spinner"
                style={{ width: 14, height: 14 }}
              />
            ) : (
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="2" y1="8" x2="14" y2="8" />
                <polyline points="9,3 14,8 9,13" />
              </svg>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
