"use client";

import { useEffect, useState, useCallback } from "react";
import { useRequireAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import styles from "./dashboard.module.css";

interface Stats {
  total_users: number;
  active_sessions: number;
  total_messages: number;
  active_users: number;
  messages_last_minute: number;
}

interface AdminSettings {
  id: number;
  max_messages_per_user: number;
  max_messages_per_minute: number;
  challenge_duration: number;
  llm_provider: string;
  llm_model: string;
}

export default function AdminDashboard() {
  const { user, loading: authLoading } = useRequireAuth("admin");
  const [stats, setStats] = useState<Stats | null>(null);
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [editingSettings, setEditingSettings] = useState(false);
  const [settingsForm, setSettingsForm] = useState({
    max_messages_per_user: 50,
    max_messages_per_minute: 5,
    challenge_duration: 3600,
    llm_provider: "ollama",
    llm_model: "llama3",
  });
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState("");

  // Fetch stats
  const loadStats = useCallback(() => {
    apiFetch<Stats>("/admin/stats")
      .then(setStats)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    loadStats();
    const interval = setInterval(loadStats, 5_000);
    return () => clearInterval(interval);
  }, [authLoading, user, loadStats]);

  // Fetch settings
  useEffect(() => {
    if (authLoading || !user) return;
    apiFetch<AdminSettings>("/admin/settings")
      .then((s) => {
        setSettings(s);
        setSettingsForm({
          max_messages_per_user: s.max_messages_per_user,
          max_messages_per_minute: s.max_messages_per_minute,
          challenge_duration: s.challenge_duration,
          llm_provider: s.llm_provider,
          llm_model: s.llm_model,
        });
      })
      .catch(() => {});
  }, [authLoading, user]);

  async function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault();
    setSavingSettings(true);
    setSettingsMsg("");
    try {
      const updated = await apiFetch<AdminSettings>("/admin/settings", {
        method: "POST",
        body: JSON.stringify(settingsForm),
      });
      setSettings(updated);
      setEditingSettings(false);
      setSettingsMsg("Settings updated");
      setTimeout(() => setSettingsMsg(""), 3000);
    } catch (err: unknown) {
      setSettingsMsg(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSavingSettings(false);
    }
  }

  if (authLoading || !user) {
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
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Real-time platform overview</p>
        </div>
      </div>

      {/* Stats cards */}
      <div className={styles.statsGrid}>
        <div className={`card ${styles.statCard}`}>
          <div className={styles.statLabel}>Total Users</div>
          <div className={styles.statValue}>{stats?.total_users ?? "—"}</div>
        </div>
        <div className={`card ${styles.statCard}`}>
          <div className={styles.statLabel}>Active Sessions</div>
          <div className={styles.statValue}>
            {stats?.active_sessions ?? "—"}
          </div>
        </div>
        <div className={`card ${styles.statCard}`}>
          <div className={styles.statLabel}>Total Messages</div>
          <div className={styles.statValue}>
            {stats?.total_messages ?? "—"}
          </div>
        </div>
        <div className={`card ${styles.statCard}`}>
          <div className={styles.statLabel}>Active Users</div>
          <div className={styles.statValue}>{stats?.active_users ?? "—"}</div>
          <div className={styles.statSub}>last 5 min</div>
        </div>
        <div className={`card ${styles.statCard}`}>
          <div className={styles.statLabel}>Msgs / Min</div>
          <div className={styles.statValue}>
            {stats?.messages_last_minute ?? "—"}
          </div>
          <div className={styles.statSub}>last minute</div>
        </div>
      </div>

      {/* Settings */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Competition Settings</h2>
          {!editingSettings && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setEditingSettings(true)}
            >
              Edit
            </button>
          )}
        </div>

        {settingsMsg && (
          <div
            className={`alert ${settingsMsg.includes("updated") ? "alert-success" : "alert-error"}`}
          >
            {settingsMsg}
          </div>
        )}

        {editingSettings ? (
          <form onSubmit={handleSaveSettings} className={styles.settingsForm}>
            <div className={styles.settingsGrid}>
              <div className="form-group">
                <label className="label">Max Messages Per User</label>
                <input
                  type="number"
                  className="input"
                  value={settingsForm.max_messages_per_user}
                  onChange={(e) =>
                    setSettingsForm((f) => ({
                      ...f,
                      max_messages_per_user: Number(e.target.value),
                    }))
                  }
                />
              </div>
              <div className="form-group">
                <label className="label">Max Messages Per Minute</label>
                <input
                  type="number"
                  className="input"
                  value={settingsForm.max_messages_per_minute}
                  onChange={(e) =>
                    setSettingsForm((f) => ({
                      ...f,
                      max_messages_per_minute: Number(e.target.value),
                    }))
                  }
                />
              </div>
              <div className="form-group">
                <label className="label">Challenge Duration (seconds)</label>
                <input
                  type="number"
                  className="input"
                  value={settingsForm.challenge_duration}
                  onChange={(e) =>
                    setSettingsForm((f) => ({
                      ...f,
                      challenge_duration: Number(e.target.value),
                    }))
                  }
                />
              </div>
              <div className="form-group">
                <label className="label">LLM Provider</label>
                <select
                  className="select"
                  style={{ width: "100%" }}
                  value={settingsForm.llm_provider}
                  onChange={(e) =>
                    setSettingsForm((f) => ({
                      ...f,
                      llm_provider: e.target.value,
                    }))
                  }
                >
                  <option value="ollama">Ollama</option>
                  <option value="openai">OpenAI</option>
                  <option value="openrouter">OpenRouter</option>
                </select>
              </div>
              <div className="form-group">
                <label className="label">LLM Model</label>
                <input
                  type="text"
                  className="input"
                  value={settingsForm.llm_model}
                  onChange={(e) =>
                    setSettingsForm((f) => ({
                      ...f,
                      llm_model: e.target.value,
                    }))
                  }
                />
              </div>
            </div>
            <div className={styles.settingsActions}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={savingSettings}
              >
                {savingSettings ? "Saving…" : "Save Settings"}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setEditingSettings(false);
                  if (settings) {
                    setSettingsForm({
                      max_messages_per_user: settings.max_messages_per_user,
                      max_messages_per_minute: settings.max_messages_per_minute,
                      challenge_duration: settings.challenge_duration,
                      llm_provider: settings.llm_provider,
                      llm_model: settings.llm_model,
                    });
                  }
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        ) : settings ? (
          <div className={styles.settingsDisplay}>
            <div className={styles.settingsItem}>
              <span className={styles.settingsLabel}>Max Messages/User</span>
              <span className={styles.settingsValue}>
                {settings.max_messages_per_user}
              </span>
            </div>
            <div className={styles.settingsItem}>
              <span className={styles.settingsLabel}>Max Messages/Min</span>
              <span className={styles.settingsValue}>
                {settings.max_messages_per_minute}
              </span>
            </div>
            <div className={styles.settingsItem}>
              <span className={styles.settingsLabel}>Duration</span>
              <span className={styles.settingsValue}>
                {settings.challenge_duration}s
              </span>
            </div>
            <div className={styles.settingsItem}>
              <span className={styles.settingsLabel}>Provider</span>
              <span className={styles.settingsValue}>
                {settings.llm_provider}
              </span>
            </div>
            <div className={styles.settingsItem}>
              <span className={styles.settingsLabel}>Model</span>
              <span className={styles.settingsValue}>
                {settings.llm_model}
              </span>
            </div>
          </div>
        ) : (
          <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
            Loading settings…
          </p>
        )}
      </div>
    </div>
  );
}
