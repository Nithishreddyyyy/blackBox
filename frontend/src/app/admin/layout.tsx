"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRequireAuth, useAuth } from "@/lib/auth";
import styles from "./admin.module.css";

const NAV_ITEMS = [
  { href: "/admin", label: "Dashboard", icon: "grid" },
  { href: "/admin/users", label: "Users", icon: "users" },
  { href: "/admin/sessions", label: "Sessions", icon: "play" },
  { href: "/admin/leaderboard", label: "Leaderboard", icon: "trophy" },
  { href: "/admin/logs", label: "Logs", icon: "file" },
  { href: "/admin/notifications", label: "Notifications", icon: "bell" },
];

function NavIcon({ icon }: { icon: string }) {
  switch (icon) {
    case "grid":
      return (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <rect x="1" y="1" width="6" height="6" rx="1" />
          <rect x="9" y="1" width="6" height="6" rx="1" opacity="0.5" />
          <rect x="1" y="9" width="6" height="6" rx="1" opacity="0.5" />
          <rect x="9" y="9" width="6" height="6" rx="1" opacity="0.3" />
        </svg>
      );
    case "users":
      return (
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="6" cy="5" r="2.5" />
          <path d="M1.5 14c0-2.5 2-4 4.5-4s4.5 1.5 4.5 4" />
          <circle cx="11.5" cy="5.5" r="2" />
          <path d="M12 10c1.5 0 3 1 3 3.5" />
        </svg>
      );
    case "play":
      return (
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect x="2" y="2" width="12" height="12" rx="2" />
          <polygon points="6,5 12,8 6,11" fill="currentColor" />
        </svg>
      );
    case "trophy":
      return (
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4 2h8v5a4 4 0 01-8 0V2z" />
          <path d="M8 11v2" />
          <path d="M5 14h6" />
          <path d="M4 4H2a1 1 0 00-1 1v1a2 2 0 002 2h1" />
          <path d="M12 4h2a1 1 0 011 1v1a2 2 0 01-2 2h-1" />
        </svg>
      );
    case "file":
      return (
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M9 1H4a1 1 0 00-1 1v12a1 1 0 001 1h8a1 1 0 001-1V5L9 1z" />
          <polyline points="9,1 9,5 13,5" />
          <line x1="5" y1="8" x2="11" y2="8" />
          <line x1="5" y1="11" x2="9" y2="11" />
        </svg>
      );
    case "bell":
      return (
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 5.5a4 4 0 00-8 0c0 4-2 5.5-2 5.5h12s-2-1.5-2-5.5" />
          <path d="M6.5 13a1.5 1.5 0 003 0" />
        </svg>
      );
    default:
      return null;
  }
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useRequireAuth("admin");
  const { logout } = useAuth();
  const pathname = usePathname();

  if (loading || !user) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className={styles.shell}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
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
          <div>
            <div className={styles.brandName}>BlackBox</div>
            <div className={styles.brandSub}>Admin Panel</div>
          </div>
        </div>

        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.navItem} ${isActive ? styles.navItemActive : ""}`}
              >
                <NavIcon icon={item.icon} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className={styles.sidebarFooter}>
          <div className={styles.adminInfo}>
            <span className={styles.adminName}>{user.name}</span>
            <span className={styles.adminRole}>Administrator</span>
          </div>
          <button
            id="admin-logout"
            className="btn btn-ghost btn-sm"
            onClick={logout}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className={styles.main}>{children}</main>
    </div>
  );
}
