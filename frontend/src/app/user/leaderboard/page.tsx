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
  user_name: string;
  prompt_count: number;
  achieved_target: boolean;
  score: number;
}

interface LeaderboardData {
  session_id: number;
  entries: LeaderboardEntry[];
}

export default function UserLeaderboardPage() {
  const { user, loading: authLoading } = useRequireAuth("user");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<number | null>(null);
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loadingData, setLoadingData] = useState(true);

  // Fetch active sessions
  useEffect(() => {
    if (authLoading || !user) return;

    apiFetch<Session[]>("/sessions/active")
      .then((data) => {
        setSessions(data);
        if (data.length > 0) setSelectedSession(data[0].id);
      })
      .catch(() => {})
      .finally(() => setLoadingData(false));
  }, [authLoading, user]);

  // Fetch leaderboard
  const loadLeaderboard = useCallback(() => {
    if (!selectedSession) return;

    apiFetch<LeaderboardData>(`/leaderboard/${selectedSession}`)
      .then((data) => setEntries(data.entries))
      .catch(() => setEntries([]));
  }, [selectedSession]);

  useEffect(() => {
    loadLeaderboard();
    const interval = setInterval(loadLeaderboard, 15_000);
    return () => clearInterval(interval);
  }, [loadLeaderboard]);

  if (authLoading || !user) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <h1 className="page-title">Leaderboard</h1>

        {sessions.length > 1 && (
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
      </div>

      {!loadingData && sessions.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
          No active sessions to show a leaderboard for.
        </p>
      ) : entries.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
          No participants yet. Be the first to send a prompt!
        </p>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Participant</th>
                <th>Prompts</th>
                <th>Target</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.rank}>
                  <td>
                    <span className={styles.rank}>{entry.rank}</span>
                  </td>
                  <td>
                    <strong>{entry.user_name}</strong>
                  </td>
                  <td>{entry.prompt_count}</td>
                  <td>
                    {entry.achieved_target ? (
                      <span className="badge badge-active">Achieved</span>
                    ) : (
                      <span className="badge badge-pending">In Progress</span>
                    )}
                  </td>
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
