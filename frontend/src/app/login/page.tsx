"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import styles from "./login.module.css";

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // If already logged in, redirect
  if (!loading && user) {
    router.replace(user.role === "admin" ? "/admin" : "/user");
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const res = await login(email, password);
      router.replace(res.role === "admin" ? "/admin" : "/user");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.card}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.logo}>
            <svg
              width="32"
              height="32"
              viewBox="0 0 32 32"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <rect width="32" height="32" rx="8" fill="#111111" />
              <rect x="8" y="8" width="7" height="7" rx="1.5" fill="#ffffff" />
              <rect
                x="17"
                y="8"
                width="7"
                height="7"
                rx="1.5"
                fill="#ffffff"
                opacity="0.6"
              />
              <rect
                x="8"
                y="17"
                width="7"
                height="7"
                rx="1.5"
                fill="#ffffff"
                opacity="0.6"
              />
              <rect
                x="17"
                y="17"
                width="7"
                height="7"
                rx="1.5"
                fill="#ffffff"
                opacity="0.3"
              />
            </svg>
          </div>
          <h1 className={styles.title}>BlackBox</h1>
          <p className={styles.subtitle}>AI Red-Team Challenge Platform</p>
        </div>

        {/* Error */}
        {error && <div className="alert alert-error">{error}</div>}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="login-email" className="label">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              className="input"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="login-password" className="label">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              className="input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button
            id="login-submit"
            type="submit"
            className={`btn btn-primary ${styles.submitBtn}`}
            disabled={submitting}
          >
            {submitting ? (
              <>
                <span className="spinner" style={{ width: 16, height: 16 }} />
                Signing in…
              </>
            ) : (
              "Sign in"
            )}
          </button>
        </form>

        <p className={styles.footer}>
          Authorized participants only. Contact the event organizer for access.
        </p>
      </div>
    </div>
  );
}
