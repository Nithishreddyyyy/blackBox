"use client";

import { useEffect, useState, useCallback } from "react";
import { useRequireAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import styles from "./logs.module.css";

interface Session {
  id: number;
  session_name: string;
  status: string;
}

interface MessageLog {
  id: number;
  user_id: number;
  prompt_text: string;
  response_text: string | null;
  prompt_timestamp: string | null;
  response_timestamp: string | null;
  latency_ms: number | null;
  success: boolean;
}

export default function AdminLogsPage() {
  const { user: admin, loading: authLoading } = useRequireAuth("admin");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<number | null>(null);
  const [messages, setMessages] = useState<MessageLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedMsg, setExpandedMsg] = useState<number | null>(null);

  useEffect(() => {
    if (authLoading || !admin) return;
    apiFetch<Session[]>("/admin/sessions")
      .then((data) => {
        setSessions(data);
        if (data.length > 0) setSelectedSession(data[0].id);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [authLoading, admin]);

  const loadMessages = useCallback(() => {
    if (!selectedSession) return;
    apiFetch<MessageLog[]>(`/admin/messages/${selectedSession}`)
      .then(setMessages)
      .catch(() => setMessages([]));
  }, [selectedSession]);

  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  if (authLoading || !admin) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Prompt Logs</h1>
          <p className="page-subtitle">
            {messages.length} message{messages.length !== 1 ? "s" : ""} logged
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {sessions.length > 0 && (
            <select
              className="select"
              value={selectedSession || ""}
              onChange={(e) => setSelectedSession(Number(e.target.value))}
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.session_name}
                </option>
              ))}
            </select>
          )}
          <button className="btn btn-secondary btn-sm" onClick={loadMessages}>
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}>
          <div className="spinner" />
        </div>
      ) : messages.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
          No messages in this session yet.
        </p>
      ) : (
        <div className={styles.logList}>
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`${styles.logItem} ${!msg.success ? styles.logError : ""}`}
              onClick={() =>
                setExpandedMsg(expandedMsg === msg.id ? null : msg.id)
              }
            >
              <div className={styles.logHeader}>
                <span className={styles.logId}>#{msg.id}</span>
                <span className={styles.logUser}>User {msg.user_id}</span>
                <span className={styles.logTime}>
                  {msg.prompt_timestamp
                    ? new Date(msg.prompt_timestamp).toLocaleTimeString()
                    : "—"}
                </span>
                {msg.latency_ms != null && (
                  <span className={styles.logLatency}>{msg.latency_ms}ms</span>
                )}
                {!msg.success && (
                  <span className="badge badge-paused">Failed</span>
                )}
              </div>

              <div className={styles.logPrompt}>
                <span className={styles.logLabel}>Prompt:</span>
                <span>
                  {expandedMsg === msg.id
                    ? msg.prompt_text
                    : msg.prompt_text.length > 120
                      ? msg.prompt_text.slice(0, 120) + "…"
                      : msg.prompt_text}
                </span>
              </div>

              {expandedMsg === msg.id && msg.response_text && (
                <div className={styles.logResponse}>
                  <span className={styles.logLabel}>Response:</span>
                  <span className={styles.logResponseText}>
                    {msg.response_text}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
