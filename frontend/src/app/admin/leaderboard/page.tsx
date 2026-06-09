"use client";

import { useEffect, useState, useCallback } from "react";
import { useRequireAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import styles from "./leaderboard.module.css";

interface Session {
  id: number;
  session_name: string;
  status: string;
}

interface LeaderboardEntry {
  rank: number;
  user_id: number;
  user_name: string;
  prompt_count: number;
  achieved_target: boolean;
  completion_time_seconds: number | null;
  score: number;
}

interface LeaderboardData {
  session_id: number;
  session_name: string;
  entries: LeaderboardEntry[];
}

export default function AdminLeaderboardPage() {
  const { user: admin, loading: authLoading } = useRequireAuth("admin");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<number | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardData | null>(null);
  const [loading, setLoading] = useState(true);

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

  const loadLeaderboard = useCallback(() => {
    if (!selectedSession) return;
    apiFetch<LeaderboardData>(`/admin/leaderboard/${selectedSession}`)
      .then(setLeaderboard)
      .catch(() => setLeaderboard(null));
  }, [selectedSession]);

  useEffect(() => {
    loadLeaderboard();
    const interval = setInterval(loadLeaderboard, 10_000);
    return () => clearInterval(interval);
  }, [loadLeaderboard]);

  if (authLoading || !admin) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
      </div>
    );
  }

  function formatTime(seconds: number | null) {
    if (seconds === null) return "—";
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Leaderboard</h1>
          <p className="page-subtitle">Detailed rankings by session</p>
        </div>
        {sessions.length > 0 && (
          <select
            className="select"
            value={selectedSession || ""}
            onChange={(e) => setSelectedSession(Number(e.target.value))}
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.session_name} ({s.status})
              </option>
            ))}
          </select>
        )}
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}>
          <div className="spinner" />
        </div>
      ) : !leaderboard || leaderboard.entries.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
          {sessions.length === 0
            ? "No sessions created yet."
            : "No participants in this session yet."}
        </p>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Participant</th>
                <th>Prompts Used</th>
                <th>Target Achieved</th>
                <th>Completion Time</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.entries.map((entry) => (
                <tr key={entry.user_id}>
                  <td>
                    <span className={styles.rank}>{entry.rank}</span>
                  </td>
                  <td>
                    <strong>{entry.user_name}</strong>
                    <span className={styles.userId}> #{entry.user_id}</span>
                  </td>
                  <td>{entry.prompt_count}</td>
                  <td>
                    {entry.achieved_target ? (
                      <span className="badge badge-active">Achieved</span>
                    ) : (
                      <span className="badge badge-pending">In Progress</span>
                    )}
                  </td>
                  <td>{formatTime(entry.completion_time_seconds)}</td>
                  <td>
                    <span className={styles.score}>{entry.score}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
