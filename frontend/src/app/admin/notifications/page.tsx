"use client";

import { useEffect, useState, useCallback } from "react";
import { useRequireAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import styles from "./notifications.module.css";

interface Notification {
  id: number;
  message: string;
  priority: string;
  created_by: number;
  created_at: string;
}

export default function AdminNotificationsPage() {
  const { user: admin, loading: authLoading } = useRequireAuth("admin");
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState("normal");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadNotifications = useCallback(() => {
    apiFetch<Notification[]>("/admin/notifications")
      .then(setNotifications)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (authLoading || !admin) return;
    loadNotifications();
  }, [authLoading, admin, loadNotifications]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!message.trim()) return;
    setSending(true);
    setError("");
    setSuccess("");

    try {
      await apiFetch("/admin/notify", {
        method: "POST",
        body: JSON.stringify({ message: message.trim(), priority }),
      });
      setSuccess("Notification broadcasted to all users");
      setMessage("");
      setPriority("normal");
      setTimeout(() => setSuccess(""), 3000);
      loadNotifications();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setSending(false);
    }
  }

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
          <h1 className="page-title">Broadcast Notifications</h1>
          <p className="page-subtitle">Send real-time alerts to all participants</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 32 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>
          Send New Message
        </h3>
        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <form onSubmit={handleSend}>
          <div className="form-group">
            <label className="label">Message content</label>
            <input
              type="text"
              className="input"
              placeholder="e.g. Round 2 begins now! 10 minutes remaining."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
            />
          </div>
          <div className="form-group" style={{ maxWidth: 200 }}>
            <label className="label">Priority Level</label>
            <select
              className="select"
              style={{ width: "100%" }}
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
            >
              <option value="low">Low (Gray)</option>
              <option value="normal">Normal (Blue/Standard)</option>
              <option value="high">High (Yellow/Warning)</option>
              <option value="urgent">Urgent (Red/Alert)</option>
            </select>
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={sending || !message.trim()}
          >
            {sending ? "Broadcasting…" : "Broadcast Now"}
          </button>
        </form>
      </div>

      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>
        History
      </h3>

      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}>
          <div className="spinner" />
        </div>
      ) : notifications.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
          No notifications have been sent yet.
        </p>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Priority</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {notifications.map((n) => (
                <tr key={n.id}>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {new Date(n.created_at).toLocaleString()}
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        n.priority === "urgent"
                          ? "badge-paused" // mapping red to paused here for UI simplicity
                          : n.priority === "high"
                          ? "badge-pending" // mapping yellow
                          : "badge-completed"
                      }`}
                      style={{
                        backgroundColor:
                          n.priority === "urgent"
                            ? "#ffe0e0"
                            : n.priority === "high"
                            ? "#fff3bf"
                            : "#e9ecef",
                        color:
                          n.priority === "urgent"
                            ? "#c92a2a"
                            : n.priority === "high"
                            ? "#e67700"
                            : "#495057",
                      }}
                    >
                      {n.priority}
                    </span>
                  </td>
                  <td style={{ width: "100%" }}>{n.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
