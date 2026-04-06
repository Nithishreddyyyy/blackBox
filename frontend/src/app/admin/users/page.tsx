"use client";

import { useEffect, useState, useCallback } from "react";
import { useRequireAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import styles from "./users.module.css";

interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  created_at: string;
}

export default function AdminUsersPage() {
  const { user: admin, loading: authLoading } = useRequireAuth("admin");
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadUsers = useCallback(() => {
    apiFetch<User[]>("/admin/users")
      .then(setUsers)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (authLoading || !admin) return;
    loadUsers();
  }, [authLoading, admin, loadUsers]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setCreating(true);
    try {
      await apiFetch("/admin/users", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm({ name: "", email: "", password: "" });
      setShowForm(false);
      setSuccess("User created successfully");
      setTimeout(() => setSuccess(""), 3000);
      loadUsers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(userId: number, userName: string) {
    if (!confirm(`Delete user "${userName}"? This cannot be undone.`)) return;
    try {
      await apiFetch(`/admin/users/${userId}`, { method: "DELETE" });
      setSuccess("User deleted");
      setTimeout(() => setSuccess(""), 3000);
      loadUsers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  if (authLoading || !admin) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
      </div>
    );
  }

  const participants = users.filter((u) => u.role === "user");
  const admins = users.filter((u) => u.role === "admin");

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Users</h1>
          <p className="page-subtitle">
            {participants.length} participant{participants.length !== 1 ? "s" : ""},{" "}
            {admins.length} admin{admins.length !== 1 ? "s" : ""}
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? "Cancel" : "+ Add User"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Create user form */}
      {showForm && (
        <div className={`card ${styles.createForm}`}>
          <h3 className={styles.formTitle}>Create New User</h3>
          <form onSubmit={handleCreate}>
            <div className={styles.formGrid}>
              <div className="form-group">
                <label className="label">Name</label>
                <input
                  type="text"
                  className="input"
                  placeholder="John Doe"
                  value={form.name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, name: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label className="label">Email</label>
                <input
                  type="email"
                  className="input"
                  placeholder="john@example.com"
                  value={form.email}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, email: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label className="label">Password</label>
                <input
                  type="text"
                  className="input"
                  placeholder="temp-password"
                  value={form.password}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, password: e.target.value }))
                  }
                  required
                />
              </div>
            </div>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={creating}
            >
              {creating ? "Creating…" : "Create User"}
            </button>
          </form>
        </div>
      )}

      {/* Users table */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}>
          <div className="spinner" />
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <span className={styles.userId}>{u.id}</span>
                  </td>
                  <td>
                    <strong>{u.name}</strong>
                  </td>
                  <td>{u.email}</td>
                  <td>
                    <span
                      className={`badge ${u.role === "admin" ? "badge-active" : "badge-pending"}`}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className={styles.dateCell}>
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    {u.role !== "admin" && (
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(u.id, u.name)}
                      >
                        Delete
                      </button>
                    )}
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
