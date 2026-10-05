import { useState } from "react";
import { LuArrowRight, LuCircle, LuCircleCheck, LuEye, LuFolderOpen, LuGithub, LuLoader, LuMessageSquare, LuRocket, LuSparkles, LuUsers, LuListChecks } from "react-icons/lu";
import { api, timeAgo } from "../api";
import { go, useMe } from "../main";
import { Empty, Loading, Progress, RoleIcon, Status, eventTone, fmtUsd, toneFor, useApi, useDebounced, useLive, useToast, phaseLabel } from "../ui";

const CHIPS: [string, string][] = [["Website", "I want a website for my business"], ["Mobile App", "I want a mobile app"], ["Ecommerce", "I want an online store"],
  ["SaaS", "I want a SaaS web app"], ["Dashboard", "I want a data dashboard"], ["Custom", ""]];

export function useCreateProject() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const create = async (idea: string, template?: string) => {
    setBusy(true);
    try {
      const p = await api<any>("/api/projects", { method: "POST", body: { idea, template } });
      go(`projects/${p.id}/chat`);
    } catch (e: any) { toast(e.message, true); } finally { setBusy(false); }
  };
  return { create, busy };
}

export function ProjectCard({ p }: { p: any }) {
  return <article className="card pcard" onClick={() => go(`projects/${p.id}`)} onKeyDown={(e) => e.key === "Enter" && go(`projects/${p.id}`)} tabIndex={0} aria-label={p.name}>
    <div className="row between"><Status s={p.status} />{p.is_demo && <span className="demo-flag">DEMO</span>}</div>
    <div className="thumb">{p.has_preview ? <iframe src={`/api/projects/${p.id}/preview/index.html`} title={`${p.name} preview`} loading="lazy" tabIndex={-1} sandbox="allow-same-origin" /> :
      <div className="ph">{p.status === "DISCOVERY" || p.status === "REQUIREMENTS" ? "Gathering requirements…" : "Preview appears after the first build"}</div>}</div>
    <div><h4>{p.name}</h4><div className="small muted">{(p.project_type || "").replace("_", " ")} · {(p.industry || "").replace("_", " ")}</div></div>
    <div className="row" style={{ gap: 8 }}><div style={{ flex: 1 }}><Progress value={p.progress} tone={toneFor(p.status)} /></div><span className="small muted">{Math.round(p.progress)}%</span></div>
    <div className="meta"><span><LuUsers size={12} /> {p.team_size} agents</span><span><LuListChecks size={12} /> {p.tasks_done}/{p.tasks_total} tasks</span></div>
    <div className="tiny dim">Last activity: {timeAgo(p.last_activity)}</div>
  </article>;
}

export function Dashboard() {
  const { me } = useMe();
  const { data, loading, reload } = useApi<any>("/api/dashboard");
  const [idea, setIdea] = useState("");
  const { create, busy } = useCreateProject();
  const refresh = useDebounced(reload, 500);
  useLive("/api/stream/org", (e) => { if (!/PING/.test(e.type)) refresh(); });
  if (loading && !data) return <Loading />;
  const projects: any[] = data?.projects || [];
  const focus = projects.find((p) => !["COMPLETED", "CANCELLED"].includes(p.status) && p.tasks_total > 0) || projects[0];
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const s = data?.stats || {};
  return <div className="dash">
    <div>
      <section className="card hero" aria-label="Start a project">
        <div>
          <div className="eyebrow"><LuSparkles /> AI SOFTWARE AGENCY · {greet}, {me.user.name.split(" ")[0]}</div>
          <h1>Describe your idea.<br />Our AI team <em>builds it.</em></h1>
          <p className="lead">From websites to mobile apps, AI-powered teams turn your ideas into real products that <b>earn</b> — Stripe checkout, newsletter, SEO & deploy included. No tech skills needed.</p>
          <form className="idea-box" onSubmit={(e) => { e.preventDefault(); if (idea.trim()) create(idea.trim()); }}>
            <LuSparkles color="#a5b4fc" /><input value={idea} onChange={(e) => setIdea(e.target.value)} placeholder="I want a modern website for my hotel that takes bookings…" aria-label="What do you want to build?" />
            <button className="go" disabled={busy || !idea.trim()} aria-label="Start project">{busy ? <LuLoader className="spinner" /> : <LuArrowRight />}</button>
          </form>
          <div className="chips">{CHIPS.map(([l, v]) => <button key={l} className="chip" type="button" onClick={() => v ? setIdea(v) : (document.querySelector<HTMLInputElement>(".idea-box input")!.focus())}>{l}</button>)}</div>
          <div className="small muted" style={{ marginTop:10 }}>Try: <i>“A luxury hotel site with Stripe deposits”</i> · <i>“An ecommerce store with real checkout”</i></div>
        </div>
        <Pipeline project={focus} />
      </section>

      <div className="card pad small" style={{ display:"flex", gap:10, alignItems:"center", flexWrap:"wrap", background:"linear-gradient(135deg, rgba(109,94,252,.12), rgba(34,211,238,.08))", borderColor:"#6d5efc33", margin:"16px 0 8px" }}>
        <span className="badge b-purple">Earning</span><span className="small"><b>Build → Deploy → Earn:</b> each hotel/ecommerce site ships with Stripe Checkout (demo works, Stripe live when you set keys) + newsletter + SEO.</span><a className="btn sm primary" href="#/billing">Billing & referrals →</a>
      </div>

      <div className="stats">
        {[["Active projects", s.active], ["Completed", s.completed], ["AI agents working", s.agents_working], ["Tasks today", s.tasks_today],
          ["AI usage (30d)", data?.llm?.is_mock ? "Local mode" : fmtUsd(s.ai_cost_usd)]].map(([l, v]) =>
          <div key={l as string} className="card stat"><div className="v">{v ?? 0}</div><div className="l">{l}</div></div>)}
      </div>

      <div className="page-title"><h2 style={{ fontSize: 19 }}>Your Projects</h2>{projects.length > 0 && <a href="#/projects">View all</a>}</div>
      {projects.length === 0 ? <div className="card"><Empty icon={LuSparkles} title="No projects yet">Describe your idea above, or start from a <a href="#/templates">template</a>.</Empty></div> :
        <div className="projects-grid">{projects.slice(0, 9).map((p) => <ProjectCard key={p.id} p={p} />)}</div>}
    </div>
    <FocusPanel project={focus} recent={data?.recent_activity || []} />
  </div>;
}

function Pipeline({ project }: { project?: any }) {
  const detail = useApi<any>(project && project.tasks_total ? `/api/projects/${project.id}` : null, [project?.updated_at]);
  const phases = detail.data?.phases;
  if (!phases) return <div className="pipeline" aria-label="How it works">
    {["Describe your idea", "Clarify requirements", "Plan the team & tasks", "Build & review", "Test & secure", "Approve & launch"].map((t, i) =>
      <div key={t} className="step"><span className="badge b-purple">{i + 1}</span>{t}</div>)}
    <div className="flow">Your idea <LuArrowRight /> Real product</div>
  </div>;
  const working = detail.data.team.filter((m: any) => m.status === "WORKING");
  return <div className="pipeline" aria-label={`${project.name} pipeline`}>
    <div className="small muted">{project.name}{working.length > 0 && <> · <b style={{ color: "var(--text)" }}>{working.length} agent{working.length > 1 ? "s" : ""} working</b></>}</div>
    {phases.slice(0, 7).map((ph: any) => <div key={ph.phase} className="step">
      {ph.done === ph.total ? <LuCircleCheck /> : ph.active ? <LuLoader className="spinner" color="#8b7cff" /> : <LuCircle color="#4b5587" />}
      <span style={{ flex: 1, }}>{phaseLabel(ph.phase)}</span><span className="tiny dim">{ph.done}/{ph.total}</span></div>)}
    <a className="flow" href={`#/projects/${project.id}/progress`} style={{ color: "white" }}>Open live build <LuArrowRight /></a>
  </div>;
}

function FocusPanel({ project, recent }: { project?: any; recent: any[] }) {
  const detail = useApi<any>(project ? `/api/projects/${project.id}` : null, [project?.updated_at]);
  const d = detail.data;
  const deployApproval = d?.pending_approvals?.find((a: any) => a.gate === "deploy");
  return <aside className="side-panel" aria-label="Project focus">
    {project && <div className="card" style={{ overflow: "hidden" }}>
      <div style={{ height: 120, position: "relative", borderBottom: "1px solid var(--border)", overflow: "hidden", background: "#0a1029" }}>
        {project.has_preview ? <iframe src={`/api/projects/${project.id}/preview/index.html`} title="preview" tabIndex={-1} sandbox="allow-same-origin" style={{ width: 1280, height: 640, transform: "scale(.29)", transformOrigin: "0 0", border: 0, pointerEvents: "none" }} />
          : <div className="pcard"><div className="thumb" style={{ height: 120, border: 0 }}><div className="ph">No preview yet</div></div></div>}
      </div>
      <div style={{ padding: 16 }} className="stack">
        <div className="row between"><a href={`#/projects/${project.id}`} style={{ color: "var(--text)", fontWeight: 700, fontSize: 16 }}>{project.name}</a><Status s={project.status} /></div>
        <div className="row"><div style={{ flex: 1 }}><Progress value={project.progress} tone={toneFor(project.status)} /></div><span className="small muted">{Math.round(project.progress)}%</span></div>
        {d && <>
          <h3 style={{ marginTop: 6 }}>Project Team</h3>
          <div>{d.team.slice(0, 7).map((m: any) => <div key={m.role} className="team-row"><RoleIcon role={m.role} /><div className="nm">{m.name}<small>{m.current_task}</small></div><Status s={m.status} /></div>)}</div>
          {d.team.length > 7 && <a href={`#/projects/${project.id}/team`} className="small">View all agents →</a>}
        </>}
      </div>
    </div>}
    <div className="card pad">
      <h3 style={{ marginBottom: 6 }}>Recent Activity</h3>
      {recent.length === 0 ? <div className="small muted">Activity from your agents appears here in real time.</div> :
        <div className="feed">{recent.slice(0, 6).map((e) => <div key={e.id} className="feed-item"><span className={`ic ${eventTone(e.type)}`}><LuSparkles /></span>
          <div><b>{e.actor}</b><div className="small muted">{e.message}</div><div className="t">{timeAgo(e.created_at)}</div></div></div>)}</div>}
    </div>
    {project && <div className="card pad stack">
      <h3>Quick Actions</h3>
      <button className="btn" onClick={() => go(`projects/${project.id}/files`)}><LuFolderOpen /> View Files</button>
      <button className="btn" onClick={() => go("settings")} title="GitHub is not connected yet"><LuGithub /> Connect GitHub</button>
      <button className="btn primary" disabled={!deployApproval && !project.live_url} title={deployApproval ? "Authorise deployment" : project.live_url ? "Open the live site" : "Available once the build is accepted"}
        onClick={() => deployApproval ? go(`projects/${project.id}/approvals`) : window.open(project.live_url, "_blank", "noopener")}>
        {project.live_url && !deployApproval ? <><LuEye /> Open live site</> : <><LuRocket /> Deploy Project</>}</button>
      <button className="btn" onClick={() => go(`projects/${project.id}/chat`)}><LuMessageSquare /> Request Changes</button>
    </div>}
  </aside>;
}
