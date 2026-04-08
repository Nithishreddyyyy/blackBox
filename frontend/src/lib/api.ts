/**
 * Centralized API client for the BlackBox backend (FastAPI on port 8000).
 *
 * Fixes from UPGRADED_DEEP_REPO_AUDIT:
 *  - Issue 2.1: Removed clearToken() — it was called but never defined, causing crash on logout
 *  - Issue 4.2: credentials:"include" always set (not conditional) so HttpOnly cookies are sent
 *  - Issue 4.1: getToken() removed — tokens are managed server-side via HttpOnly cookies
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Build a WebSocket URL from the base API URL.
 * The backend authenticates via cookie; no token parameter needed.
 */
export function getWebSocketUrl(path: string) {
  const url = new URL(path, API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

// ---------------------------------------------------------------------------
// Generic fetch wrapper
// ---------------------------------------------------------------------------

interface FetchOptions extends RequestInit {
  /** Skip setting credentials (e.g., for truly public endpoints with no cookies). */
  noCredentials?: boolean;
}

export async function apiFetch<T = unknown>(
  path: string,
  opts: FetchOptions = {}
): Promise<T> {
  const { noCredentials, headers: extraHeaders, ...rest } = opts;

  const headers: Record<string, string> = {
    ...(extraHeaders as Record<string, string>),
  };

  // Issue 4.2: Always include credentials so HttpOnly cookies are forwarded
  const credentials = noCredentials ? "omit" : "include";

  // Don't set Content-Type for FormData (browser sets boundary automatically)
  if (!(rest.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    credentials,
    ...rest,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = await res.json();
      detail = err.detail || JSON.stringify(err);
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth APIs
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: number;
  name: string;
}

export interface UserOut {
  id: number;
  name: string;
  email: string;
  role: string;
  created_at: string;
}

/**
 * Login uses OAuth2PasswordRequestForm — must send form-encoded data
 * with `username` (which is the email) and `password`.
 */
export async function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  const form = new FormData();
  form.append("username", email);
  form.append("password", password);

  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: form,
  });
}

/**
 * Logout: tells the backend to delete the HttpOnly cookie.
 * Issue 2.1: clearToken() was removed since tokens are server-managed.
 */
export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}

export async function getMe(): Promise<UserOut> {
  return apiFetch<UserOut>("/auth/me");
}
