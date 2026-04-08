/**
 * Centralized API client for the BlackBox backend (FastAPI on port 8000).
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getWebSocketUrl(path: string) {
  const url = new URL(path, API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

// ---------------------------------------------------------------------------
// Generic fetch wrapper
// ---------------------------------------------------------------------------

type FetchOptions = RequestInit;

export async function apiFetch<T = unknown>(
  path: string,
  opts: FetchOptions = {}
): Promise<T> {
  const { headers: extraHeaders, ...rest } = opts;

  const headers: Record<string, string> = {
    ...(extraHeaders as Record<string, string>),
  };

  // Don't set Content-Type for FormData (browser sets boundary automatically)
  if (!(rest.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers,
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

export interface LoginResponse {
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
): Promise<LoginResponse> {
  const form = new FormData();
  form.append("username", email);
  form.append("password", password);

  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: form,
  });
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}

export async function getMe(): Promise<UserOut> {
  return apiFetch<UserOut>("/auth/me");
}
