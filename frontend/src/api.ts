// Thin API client. The bearer token is kept in localStorage (wrapped in try/catch);
// the HttpOnly cookie set by the server is used only for iframe previews and downloads.
const KEY = "agencyos.token";

export function getToken(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch { /* storage unavailable */ }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method: opts.method || "GET", headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined, credentials: "same-origin" });
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/api/auth/")) { setToken(null); window.dispatchEvent(new Event("agencyos:logout")); }
    throw new ApiError(res.status, (data && data.error) || `Request failed (${res.status})`);
  }
  return data as T;
}

export type LiveEvent = { id: number; type: string; actor: string; message: string; project_id: string | null; data: any; created_at: string };

/** Subscribe to the realtime stream (Server-Sent Events, authenticated by the HttpOnly session cookie).
 *  EventSource reconnects automatically; returns an unsubscribe fn. */
export function subscribe(path: string, onEvent: (e: LiveEvent) => void, onState?: (connected: boolean) => void): () => void {
  const es = new EventSource(path, { withCredentials: true });
  es.addEventListener("ready", () => onState?.(true));
  es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch { /* ignore */ } };
  es.onerror = () => onState?.(false);
  return () => es.close();
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export function clock(iso?: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
