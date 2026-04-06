"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

/**
 * Root page — redirect based on auth state.
 */
export default function RootPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else {
      router.replace(user.role === "admin" ? "/admin" : "/user");
    }
  }, [user, loading, router]);

  return (
    <div className="loading-screen">
      <div className="spinner" />
      <span>Loading…</span>
    </div>
  );
}
