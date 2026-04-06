"use client";

import { useRequireAuth, useAuth } from "@/lib/auth";
import styles from "./user.module.css";

export default function UserLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useRequireAuth("user");
  const { logout } = useAuth();

  if (loading || !user) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <div className={styles.topbarLeft}>
          <svg
            width="24"
            height="24"
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
          <span className={styles.brand}>BlackBox</span>
        </div>

        <div className={styles.topbarRight}>
          <span className={styles.userName}>{user.name}</span>
          <button
            id="user-logout"
            className="btn btn-ghost btn-sm"
            onClick={logout}
          >
            Sign out
          </button>
        </div>
      </header>

      <main className={styles.main}>{children}</main>
    </div>
  );
}
