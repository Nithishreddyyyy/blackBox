"use client";

import { useEffect, useState, useCallback } from "react";
import { useRequireAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import styles from "./sessions.module.css";

interface Session {
  id: number;
  session_name: string;
  llm_system_prompts: string | null;
  start_time: string | null;
  end_time: string | null;
  status: string;
}

interface Participant {
  id: number;
  user_id: number;
  session_id: number;
  joined_at: string;
  completed_at: string | null;
  score: number;
  achieved_target: boolean;
  prompt_count: number;
  user_name: string | null;
  user_email: string | null;
}

export default function AdminSessionsPage() {
  const { user: admin, loading: authLoading } = useRequireAuth("admin");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [sessionName, setSessionName] = useState("");
  const [newSessionPrompt, setNewSessionPrompt] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [promptEdits, setPromptEdits] = useState<Record<number, string>>({});
  const [savingPromptId, setSavingPromptId] = useState<number | null>(null);
  const [expandedSession, setExpandedSession] = useState<number | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [loadingParticipants, setLoadingParticipants] = useState(false);

  const loadSessions = useCallback(() => {
    apiFetch<Session[]>("/admin/sessions")
      .then((data) => {
        setSessions(data);
        setPromptEdits((prev) => {
          const next = { ...prev };
          data.forEach((session) => {
            next[session.id] = session.llm_system_prompts ?? "";
          });
          return next;
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (authLoading || !admin) return;
    loadSessions();
  }, [authLoading, admin, loadSessions]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!sessionName.trim()) return;
    setCreating(true);
    setError("");
    try {
      await apiFetch("/admin/sessions", {
        method: "POST",
        body: JSON.stringify({
          session_name: sessionName.trim(),
          llm_system_prompts: newSessionPrompt,
        }),
      });
      setSessionName("");
      setNewSessionPrompt("");
      setShowCreate(false);
      setSuccess("Session created");
      setTimeout(() => setSuccess(""), 3000);
      loadSessions();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setCreating(false);
    }
  }

  async function handleAction(sessionId: number, action: string) {
    setError("");
    try {
      await apiFetch(`/admin/sessions/${sessionId}/action`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      loadSessions();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  }

  async function handleSavePrompt(session: Session) {
    const nextPrompt = promptEdits[session.id] ?? "";

    setSavingPromptId(session.id);
    setError("");

    try {
      const updated = await apiFetch<Session>(`/admin/sessions/${session.id}`, {
        method: "PUT",
        body: JSON.stringify({ llm_system_prompts: nextPrompt }),
      });

      setSessions((prev) =>
        prev.map((existing) =>
          existing.id === session.id ? updated : existing
        )
      );
      setPromptEdits((prev) => ({
        ...prev,
        [session.id]: updated.llm_system_prompts ?? "",
      }));

      setSuccess("Session prompt saved");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save prompt");
    } finally {
      setSavingPromptId(null);
    }
  }

  async function toggleParticipants(sessionId: number) {
    if (expandedSession === sessionId) {
      setExpandedSession(null);
      setParticipants([]);
      return;
    }
    setExpandedSession(sessionId);
    setLoadingParticipants(true);
    try {
      const data = await apiFetch<Participant[]>(
        `/admin/sessions/${sessionId}/participants`
      );
      setParticipants(data);
    } catch {
      setParticipants([]);
    } finally {
      setLoadingParticipants(false);
    }
  }

  async function handleResetUser(sessionId: number, userId: number) {
    if (!confirm("Reset this user's session? All their messages will be deleted."))
      return;
    try {
      await apiFetch(`/admin/sessions/${sessionId}/reset/${userId}`, {
        method: "POST",
      });
      setSuccess("User session reset");
      setTimeout(() => setSuccess(""), 3000);
      toggleParticipants(sessionId); // Refresh
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  }

  function getStatusBadge(status: string) {
    const map: Record<string, string> = {
      active: "badge-active",
      pending: "badge-pending",
      completed: "badge-completed",
      paused: "badge-paused",
    };
    return map[status] || "badge-pending";
  }

  function getActions(session: Session) {
    const actions: { label: string; action: string; variant: string }[] = [];
    switch (session.status) {
      case "pending":
        actions.push({ label: "Start", action: "start", variant: "btn-primary" });
        actions.push({ label: "End", action: "end", variant: "btn-secondary" });
        break;
      case "active":
        actions.push({ label: "Pause", action: "pause", variant: "btn-secondary" });
        actions.push({ label: "End", action: "end", variant: "btn-danger" });
        break;
      case "paused":
        actions.push({ label: "Resume", action: "resume", variant: "btn-primary" });
        actions.push({ label: "End", action: "end", variant: "btn-danger" });
        break;
    }
    return actions;
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
          <h1 className="page-title">Sessions</h1>
          <p className="page-subtitle">
            {sessions.length} session{sessions.length !== 1 ? "s" : ""}
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowCreate(!showCreate)}
        >
          {showCreate ? "Cancel" : "+ New Session"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showCreate && (
        <div className={`card ${styles.createForm}`}>
          <form onSubmit={handleCreate} className={styles.createFormBody}>
            <div className={styles.createRow}>
              <input
                type="text"
                className="input"
                placeholder="Session name (e.g. Round 1)"
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                required
                style={{ flex: 1 }}
              />
              <button
                type="submit"
                className="btn btn-primary"
                disabled={creating}
              >
                {creating ? "Creating…" : "Create"}
              </button>
            </div>
            <label htmlFor="new-session-prompt" className={styles.fieldLabel}>
              LLM System Prompt (optional)
            </label>
            <textarea
              id="new-session-prompt"
              className={`input ${styles.promptInput}`}
              rows={4}
              placeholder="Set a custom system prompt for this session"
              value={newSessionPrompt}
              onChange={(e) => setNewSessionPrompt(e.target.value)}
            />
          </form>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}>
          <div className="spinner" />
        </div>
      ) : sessions.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
          No sessions yet. Create one to get started.
        </p>
      ) : (
        <div className={styles.sessionList}>
          {sessions.map((s) => {
            const currentPrompt = promptEdits[s.id] ?? "";
            const storedPrompt = s.llm_system_prompts ?? "";
            const isPromptDirty = currentPrompt !== storedPrompt;
            const isSavingPrompt = savingPromptId === s.id;

            return (
              <div key={s.id} className={`card ${styles.sessionCard}`}>
                <div className={styles.sessionRow}>
                  <div className={styles.sessionInfo}>
                    <div className={styles.sessionName}>{s.session_name}</div>
                    <div className={styles.sessionMeta}>
                      ID: {s.id}
                      {s.start_time &&
                        ` · Started: ${new Date(s.start_time).toLocaleTimeString()}`}
                      {s.end_time &&
                        ` · Ended: ${new Date(s.end_time).toLocaleTimeString()}`}
                    </div>
                  </div>

                  <div className={styles.sessionActions}>
                    <span className={`badge ${getStatusBadge(s.status)}`}>
                      {s.status}
                    </span>
                    {getActions(s).map((a) => (
                      <button
                        key={a.action}
                        className={`btn ${a.variant} btn-sm`}
                        onClick={() => handleAction(s.id, a.action)}
                      >
                        {a.label}
                      </button>
                    ))}
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => toggleParticipants(s.id)}
                    >
                      {expandedSession === s.id ? "Hide" : "Participants"}
                    </button>
                  </div>
                </div>

                <div className={styles.promptPanel}>
                  <label className={styles.fieldLabel} htmlFor={`prompt-${s.id}`}>
                    LLM System Prompt
                  </label>
                  <textarea
                    id={`prompt-${s.id}`}
                    className={`input ${styles.promptInput}`}
                    rows={4}
                    placeholder="Set a custom system prompt for this session"
                    value={currentPrompt}
                    onChange={(e) =>
                      setPromptEdits((prev) => ({
                        ...prev,
                        [s.id]: e.target.value,
                      }))
                    }
                  />
                  <div className={styles.promptActions}>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() =>
                        setPromptEdits((prev) => ({
                          ...prev,
                          [s.id]: storedPrompt,
                        }))
                      }
                      disabled={!isPromptDirty || isSavingPrompt}
                    >
                      Reset
                    </button>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => handleSavePrompt(s)}
                      disabled={!isPromptDirty || isSavingPrompt}
                    >
                      {isSavingPrompt ? "Saving…" : "Save Prompt"}
                    </button>
                  </div>
                </div>

                {/* Expanded participants */}
                {expandedSession === s.id && (
                  <div className={styles.participantsPanel}>
                    {loadingParticipants ? (
                      <div style={{ textAlign: "center", padding: 16 }}>
                        <div className="spinner" />
                      </div>
                    ) : participants.length === 0 ? (
                      <p
                        style={{
                          color: "var(--text-muted)",
                          fontSize: 13,
                          padding: "8px 0",
                        }}
                      >
                        No participants yet
                      </p>
                    ) : (
                      <table className="table">
                        <thead>
                          <tr>
                            <th>User</th>
                            <th>Prompts</th>
                            <th>Target</th>
                            <th>Score</th>
                            <th>Joined</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {participants.map((p) => (
                            <tr key={p.id}>
                              <td>
                                <strong>{p.user_name}</strong>
                                <br />
                                <span
                                  style={{
                                    fontSize: 12,
                                    color: "var(--text-muted)",
                                  }}
                                >
                                  {p.user_email}
                                </span>
                              </td>
                              <td>{p.prompt_count}</td>
                              <td>
                                {p.achieved_target ? (
                                  <span className="badge badge-active">Yes</span>
                                ) : (
                                  <span className="badge badge-pending">No</span>
                                )}
                              </td>
                              <td style={{ fontFamily: "var(--font-mono)" }}>
                                {p.score}
                              </td>
                              <td style={{ fontSize: 13 }}>
                                {new Date(p.joined_at).toLocaleTimeString()}
                              </td>
                              <td>
                                <button
                                  className="btn btn-danger btn-sm"
                                  onClick={() =>
                                    handleResetUser(s.id, p.user_id)
                                  }
                                >
                                  Reset
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
