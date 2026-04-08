/**
 * Centralized API client for the BlackBox backend (FastAPI on port 8000).
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getWebSocketUrl(path: string, token?: string | null) {
  const url = new URL(path, API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

// No localStorage token helpers anymore, using HttpOnly cookies.

// ---------------------------------------------------------------------------
// Generic fetch wrapper
// ---------------------------------------------------------------------------

interface FetchOptions extends RequestInit {
  /** Skip adding the Authorization header */
  noAuth?: boolean;
}

export async function apiFetch<T = unknown>(
  path: string,
  opts: FetchOptions = {}
): Promise<T> {
  const { noAuth, headers: extraHeaders, ...rest } = opts;

  const headers: Record<string, string> = {
    ...(extraHeaders as Record<string, string>),
  };

  if (!noAuth) {
    opts.credentials = "include";
  }

  // Don't set Content-Type for FormData (browser sets boundary automatically)
  if (!(rest.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { headers, ...rest });

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
    noAuth: true,
  });
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
  clearToken();
}

export async function getMe(): Promise<UserOut> {
  return apiFetch<UserOut>("/auth/me");
}
