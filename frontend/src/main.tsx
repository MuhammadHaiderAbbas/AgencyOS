import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  LuActivity, LuBell, LuBot, LuCreditCard, LuFolderKanban, LuLayoutDashboard, LuLayoutTemplate, LuListChecks, LuLogOut,
  LuMenu, LuSearch, LuSettings, LuShapes, LuShieldCheck, LuStore,
} from "react-icons/lu";
import { api, getToken, setToken, timeAgo } from "./api";
import { ToastProvider, useApi, useDebounced, useLive } from "./ui";
import { AuthPage } from "./pages/Auth";
import { Dashboard } from "./pages/Dashboard";
import { ProjectPage } from "./pages/Project";
import { ProjectsPage } from "./pages/Projects";
import { AgentsPage } from "./pages/Agents";
import { ActivityPage, ApprovalsPage, ArtifactsPage, SearchPage, TasksPage, TemplatesPage } from "./pages/Lists";
import { BillingPage, SettingsPage } from "./pages/Settings";

export type Me = { user: { id: string; name: string; email: string; is_admin: boolean; org_role: string; org_id: string }; organization: any; unread_notifications: number; llm: { provider: string; is_mock: boolean; models: any } };
const MeCtx = createContext<{ me: Me; refreshMe: () => void } | null>(null);
export const useMe = () => useContext(MeCtx)!;

// ---------------------------------------------------------------- hash router
export function useRoute(): string[] {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => { const f = () => setHash(location.hash); window.addEventListener("hashchange", f); return () => window.removeEventListener("hashchange", f); }, []);
  return (hash.replace(/^#\/?/, "").split("?")[0] || "dashboard").split("/").map(decodeURIComponent);
}
export function go(path: string) { location.hash = "#/" + path.replace(/^\//, ""); }
export function query(): URLSearchParams { return new URLSearchParams(location.hash.split("?")[1] || ""); }

function Logo() {
  return <svg className="brand-mark" viewBox="0 0 40 40" aria-hidden="true"><defs><linearGradient id="lg" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stopColor="#8b7cff" /><stop offset="1" stopColor="#3b82f6" /></linearGradient></defs>
    <path d="M20 4 4 36h8.5L20 20l7.5 16H36z" fill="url(#lg)" /><path d="M13 30h14" stroke="#22d3ee" strokeWidth="3" strokeLinecap="round" /></svg>;
}

const NAV = [
  [["dashboard", "Dashboard", LuLayoutDashboard], ["projects", "Projects", LuFolderKanban], ["agents", "Agents", LuBot], ["marketplace", "Marketplace", LuStore], ["templates", "Templates", LuLayoutTemplate]],
  [["tasks", "Tasks", LuListChecks], ["artifacts", "Artifacts", LuShapes], ["approvals", "Approvals", LuShieldCheck], ["activity", "Activity", LuActivity]],
  [["settings", "Settings", LuSettings], ["billing", "Billing", LuCreditCard]],
] as const;

function Shell() {
  const { me, refreshMe } = useMe();
  const route = useRoute();
  const [open, setOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const pending = useApi<any[]>("/api/approvals");
  const reloadPending = useDebounced(() => { pending.reload(); refreshMe(); }, 400);
  const live = useLive("/api/stream/org", (e) => { if (/APPROVAL|NOTIFICATION/.test(e.type)) reloadPending(); });
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); searchRef.current?.focus(); } };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, []);
  useEffect(() => setOpen(false), [route.join("/")]);
  const page = route[0];
  const initials = me.user.name.split(/\s+/).map((x) => x[0]).slice(0, 2).join("").toUpperCase();

  let view;
  switch (page) {
    case "projects": view = route[1] ? <ProjectPage id={route[1]} tab={route[2] || "chat"} /> : <ProjectsPage />; break;
    case "agents": view = <AgentsPage mode="registry" />; break;
    case "marketplace": view = <AgentsPage mode="marketplace" />; break;
    case "templates": view = <TemplatesPage />; break;
    case "tasks": view = <TasksPage />; break;
    case "artifacts": view = <ArtifactsPage />; break;
    case "approvals": view = <ApprovalsPage />; break;
    case "activity": view = <ActivityPage />; break;
    case "settings": view = <SettingsPage />; break;
    case "billing": view = <BillingPage />; break;
    case "search": view = <SearchPage />; break;
    default: view = <Dashboard />;
  }
  return <div className="shell">
    <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
      <div className="brand"><Logo /><div><b>AgencyOS</b><small>Turn an idea into a finished product.</small></div></div>
      {NAV.map((group, gi) => <div key={gi}>
        {gi > 0 && <div className="nav-sep" />}
        <nav className="nav">{group.map(([id, label, I]) => <a key={id} href={`#/${id}`} className={page === id || (page === "" && id === "dashboard") ? "active" : ""}>
          <I />{label}{id === "approvals" && (pending.data?.length || 0) > 0 && <span className="count">{pending.data!.length}</span>}</a>)}</nav>
      </div>)}
      <div className="user-card"><div className="avatar">{initials}</div><div className="who"><b>{me.user.name}</b><small>{me.user.email}</small></div>
        <button className="icon-btn" title="Sign out" aria-label="Sign out" onClick={async () => { await api("/api/auth/logout", { method: "POST" }).catch(() => {}); setToken(null); location.reload(); }}><LuLogOut size={16} /></button></div>
    </aside>
    <div className="main">
      <header className="topbar">
        <button className="icon-btn menu-toggle" aria-label="Open menu" onClick={() => setOpen(!open)}><LuMenu /></button>
        <form className="search" role="search" onSubmit={(e) => { e.preventDefault(); const q = searchRef.current?.value.trim(); if (q) go(`search?q=${encodeURIComponent(q)}`); }}>
          <LuSearch size={17} /><input ref={searchRef} placeholder="Search projects, agents, or anything…" aria-label="Search" /><span className="kbd">⌘ K</span>
        </form>
        <div className="spacer" />
        <span className="pill" title={me.llm.is_mock ? "No LLM key configured: agents use deterministic local implementations" : `Models: ${me.llm.models.fast} / ${me.llm.models.strong}`}>
          <span className={`dot ${!live ? "off" : me.llm.is_mock ? "warn" : ""}`} /><span className="lbl">{!live ? "Reconnecting…" : me.llm.is_mock ? "AI Agents Online · local mode" : `AI Agents Online · ${me.llm.provider}`}</span>
        </span>
        <div style={{ position: "relative" }}>
          <button className="icon-btn" aria-label="Notifications" onClick={() => setNotifOpen(!notifOpen)}><LuBell size={18} />{me.unread_notifications > 0 && <span className="badge-n">{me.unread_notifications}</span>}</button>
          {notifOpen && <Notifications onClose={() => { setNotifOpen(false); refreshMe(); }} />}
        </div>
      </header>
      <main className="content" id="main">{view}</main>
    </div>
  </div>;
}

function Notifications({ onClose }: { onClose: () => void }) {
  const { data } = useApi<any[]>("/api/notifications");
  useEffect(() => { api("/api/notifications/read", { method: "POST" }).catch(() => {}); }, []);
  return <div className="card" style={{ position: "absolute", right: 0, top: 46, width: 340, maxHeight: 420, overflowY: "auto", padding: 8, boxShadow: "var(--shadow)" }} onMouseLeave={onClose}>
    {!data?.length ? <div className="empty small">No notifications yet</div> : data.map((n) => <a key={n.id} href={n.project_id ? `#/projects/${n.project_id}` : "#/"} className="list-item" style={{ display: "block", color: "var(--text)" }} onClick={onClose}>
      <div className="row between"><b style={{ fontSize: 13 }}>{n.title}</b>{!n.read && <span className="dot" />}</div>
      {n.body && <div className="small muted">{n.body}</div>}<div className="tiny dim">{timeAgo(n.created_at)}</div></a>)}
  </div>;
}

function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const refreshMe = useCallback(() => {
    if (!getToken()) { setMe(null); setChecked(true); return; }
    api<Me>("/api/auth/me").then(setMe).catch(() => setMe(null)).finally(() => setChecked(true));
  }, []);
  useEffect(() => { refreshMe(); const f = () => setMe(null); window.addEventListener("agencyos:logout", f); return () => window.removeEventListener("agencyos:logout", f); }, [refreshMe]);
  if (!checked) return null;
  if (!me) return <AuthPage onAuthed={refreshMe} />;
  return <MeCtx.Provider value={{ me, refreshMe }}><Shell /></MeCtx.Provider>;
}

createRoot(document.getElementById("root")!).render(<ToastProvider><App /></ToastProvider>);
