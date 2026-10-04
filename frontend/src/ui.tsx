import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import {
  LuBot, LuBrain, LuCheck, LuCode, LuDatabase, LuFileText, LuGauge, LuLayoutTemplate, LuLoader, LuPalette, LuPenTool, LuRocket,
  LuSearch, LuServer, LuShieldCheck, LuTarget, LuUsers, LuAccessibility, LuBookOpen, LuClipboardList, LuTriangleAlert, LuX,
} from "react-icons/lu";
import { api, subscribe, type LiveEvent } from "./api";

// ---------------------------------------------------------------- status badges
const STATUS_TONE: Record<string, string> = {
  DISCOVERY: "b-cyan", REQUIREMENTS: "b-cyan", PLANNING: "b-purple", RESEARCH: "b-blue", DESIGN: "b-orange", ARCHITECTURE: "b-blue",
  DEVELOPMENT: "b-blue", INTEGRATION: "b-blue", QA: "b-purple", SECURITY_REVIEW: "b-purple", USER_ACCEPTANCE: "b-orange",
  READY_TO_DEPLOY: "b-orange", DEPLOYING: "b-blue", DEPLOYED: "b-green", COMPLETED: "b-green", BLOCKED: "b-red", CANCELLED: "b-gray",
  BACKLOG: "b-gray", READY: "b-cyan", IN_PROGRESS: "b-blue", REVIEW: "b-purple", REVISION_REQUIRED: "b-orange", APPROVED: "b-green",
  FAILED: "b-red", PENDING: "b-orange", REJECTED: "b-red", CHANGES_REQUESTED: "b-orange", SUPERSEDED: "b-gray", SUCCEEDED: "b-green",
  RUNNING: "b-blue", WORKING: "b-green", WAITING: "b-gray", THINKING: "b-cyan", IDLE: "b-gray", HEALTHY: "b-green", WARNING: "b-orange",
  BROKEN: "b-red", DISABLED: "b-gray", IN_REVIEW: "b-purple", PASS: "b-green", FAIL: "b-red",
};
const LABEL: Record<string, string> = { USER_ACCEPTANCE: "Review", READY_TO_DEPLOY: "Ready to deploy", SECURITY_REVIEW: "Security",
  IN_PROGRESS: "In progress", REVISION_REQUIRED: "Revision", CHANGES_REQUESTED: "Changes requested", DEVELOPMENT: "Building" };

export function Status({ s }: { s: string }) {
  const label = LABEL[s] || s.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
  return <span className={`badge ${STATUS_TONE[s] || "b-gray"}`}>{s === "IN_PROGRESS" || s === "RUNNING" || s === "DEPLOYING" ? <LuLoader className="spinner" size={11} /> : null}{label}</span>;
}

export function Progress({ value, tone }: { value: number; tone?: "green" | "orange" | "gray" }) {
  return <div className={`progress ${tone || ""}`} role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>;
}

export function toneFor(status: string): "green" | "orange" | "gray" | undefined {
  if (status === "COMPLETED") return "green";
  if (["DESIGN", "USER_ACCEPTANCE", "READY_TO_DEPLOY"].includes(status)) return "orange";
  if (["BLOCKED", "CANCELLED"].includes(status)) return "gray";
}

const ROLE_ICONS: Record<string, any> = {
  project_manager: LuClipboardList, business_analyst: LuTarget, researcher: LuSearch, ux_designer: LuPenTool, ui_designer: LuPalette,
  architect: LuServer, content_writer: LuFileText, seo_specialist: LuGauge, frontend_developer: LuCode, backend_developer: LuServer,
  database_engineer: LuDatabase, qa_engineer: LuCheck, security_engineer: LuShieldCheck, performance_engineer: LuGauge,
  accessibility_specialist: LuAccessibility, technical_writer: LuBookOpen, devops_engineer: LuRocket, requirements_agent: LuBrain,
  reviewer: LuUsers, change_analyst: LuLayoutTemplate,
};
export function RoleIcon({ role }: { role: string }) {
  const I = ROLE_ICONS[role] || LuBot;
  return <span className="role-ic"><I /></span>;
}

export function Empty({ icon: I = LuTriangleAlert, title, children }: { icon?: any; title: string; children?: ReactNode }) {
  return <div className="empty"><I /><div style={{ fontWeight: 600, color: "var(--text)" }}>{title}</div>{children && <div className="small" style={{ marginTop: 6 }}>{children}</div>}</div>;
}

export function Loading() {
  return <div className="empty"><LuLoader className="spinner" /><div>Loading…</div></div>;
}

// ---------------------------------------------------------------- safe markdown (escape first, then format)
function esc(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function inline(s: string) {
  return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>").replace(/`(.+?)`/g, "<code>$1</code>");
}
export function Markdown({ text }: { text: string }) {
  const lines = (text || "").split("\n");
  const out: string[] = [];
  let list = false;
  for (const raw of lines) {
    const l = raw.trimEnd();
    if (/^\s*[-*] /.test(l)) { if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${inline(l.replace(/^\s*[-*] /, ""))}</li>`); continue; }
    if (list) { out.push("</ul>"); list = false; }
    if (!l.trim()) continue;
    if (l.startsWith("> ")) out.push(`<blockquote>${inline(l.slice(2))}</blockquote>`);
    else if (/^#{1,3} /.test(l)) out.push(`<p><b>${inline(l.replace(/^#+ /, ""))}</b></p>`);
    else out.push(`<p>${inline(l)}</p>`);
  }
  if (list) out.push("</ul>");
  return <div className="md" dangerouslySetInnerHTML={{ __html: out.join("") }} />;
}

// ---------------------------------------------------------------- toasts
type Toast = { id: number; text: string; err?: boolean };
const ToastCtx = createContext<(text: string, err?: boolean) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, err?: boolean) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, err }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4500);
  }, []);
  return <ToastCtx.Provider value={push}>{children}
    <div aria-live="polite">{items.map((t, i) => <div key={t.id} className={`toast ${t.err ? "err" : ""}`} style={{ bottom: 20 + i * 64 }}>{t.text}</div>)}</div>
  </ToastCtx.Provider>;
}

// ---------------------------------------------------------------- data hooks
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const load = useCallback(async () => {
    if (!path) return;
    const n = ++seq.current;
    try {
      const d = await api<T>(path);
      if (n === seq.current) { setData(d); setError(null); }
    } catch (e: any) { if (n === seq.current) setError(e.message); }
    finally { if (n === seq.current) setLoading(false); }
  }, [path]);
  useEffect(() => { setLoading(true); load(); }, [load, ...deps]);
  return { data, error, loading, reload: load, setData };
}

/** Re-fetch when live events arrive (debounced). */
export function useLive(path: string, onEvent: (e: LiveEvent) => void) {
  const cb = useRef(onEvent);
  cb.current = onEvent;
  const [connected, setConnected] = useState(false);
  useEffect(() => subscribe(path, (e) => cb.current(e), setConnected), [path]);
  return connected;
}

export function useDebounced(fn: () => void, ms = 250) {
  const t = useRef<number | undefined>(undefined);
  const f = useRef(fn);
  f.current = fn;
  return useCallback(() => { window.clearTimeout(t.current); t.current = window.setTimeout(() => f.current(), ms); }, [ms]);
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => { const k = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [onClose]);
  return <div className="modal-bg" onClick={onClose}><div className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
    <div className="row between" style={{ marginBottom: 14 }}><h3>{title}</h3><button className="icon-btn" onClick={onClose} aria-label="Close"><LuX /></button></div>
    {children}</div></div>;
}

export function Drawer({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  useEffect(() => { const k = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [onClose]);
  return <div className="drawer-bg" onClick={onClose}><div className="drawer" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
    <div style={{ display: "flex", justifyContent: "flex-end" }}><button className="icon-btn" onClick={onClose} aria-label="Close"><LuX /></button></div>{children}</div></div>;
}

export function eventTone(t: string): "ok" | "err" | "warn" | "" {
  if (/COMPLETED|PASSED|APPROVED|SUCCEEDED/.test(t)) return "ok";
  if (/FAILED|BLOCKED|ESCALATION/.test(t)) return "err";
  if (/BUG|REVISION|APPROVAL_REQUIRED|CHANGE/.test(t)) return "warn";
  return "";
}

export const fmtUsd = (n: number) => `$${(n || 0).toFixed(n && n < 0.1 ? 4 : 2)}`;

const PHASES: Record<string, string> = { requirements: "Requirements", research: "Research", ux: "UX design", ui: "UI design", architecture: "Architecture",
  content: "Content", development: "Development", testing: "Testing", security: "Security", documentation: "Documentation", uat: "Acceptance", deployment: "Deployment", planning: "Planning" };
export const phaseLabel = (p: string) => PHASES[p] || p;
