"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  getToken,
  setToken,
  clearToken,
  login as apiLogin,
  logout as apiLogout,
  getMe,
  type TokenResponse,
  type UserOut,
} from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthState {
  user: UserOut | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<TokenResponse>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  token: null,
  loading: true,
  login: async () => {
    throw new Error("AuthProvider not mounted");
  },
  logout: async () => {
    throw new Error("AuthProvider not mounted");
  },
});

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // On mount, try to restore session from localStorage
  useEffect(() => {
    let cancelled = false;
    const stored = getToken();
    if (!stored) {
      queueMicrotask(() => {
        if (!cancelled) setLoading(false);
      });
      return () => {
        cancelled = true;
      };
    }

    Promise.resolve()
      .then(() => getMe())
      .then((u) => {
        if (!cancelled) {
          setTokenState(stored);
          setUser(u);
        }
      })
      .catch(() => {
        clearToken();
        if (!cancelled) setTokenState(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await apiLogin(email, password);
      setToken(res.access_token);
      setTokenState(res.access_token);

      // Fetch full user profile
      const me = await getMe();
      setUser(me);

      return res;
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // ignore
    }
    clearToken();
    setTokenState(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useAuth() {
  return useContext(AuthContext);
}

/**
 * Redirect away if not authenticated or wrong role.
 */
export function useRequireAuth(requiredRole?: "admin" | "user") {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;

    if (!user) {
      router.replace("/login");
      return;
    }

    if (requiredRole && user.role !== requiredRole) {
      // Wrong role — send them to their own area
      router.replace(user.role === "admin" ? "/admin" : "/user");
    }
  }, [user, loading, requiredRole, router, pathname]);

  return { user, loading };
}
