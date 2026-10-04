import { useState } from "react";
import { LuCircleCheck, LuLayoutTemplate, LuSearch } from "react-icons/lu";
import { timeAgo } from "../api";
import { query } from "../main";
import { Empty, Loading, Status, useApi, useDebounced, useLive } from "../ui";
import { useCreateProject } from "./Dashboard";
import { ApprovalCard, ArtifactViewer, EventList } from "./Project";
import { Drawer } from "../ui";

export function TasksPage() {
  const [status, setStatus] = useState("");
  const { data, reload } = useApi<any[]>(`/api/tasks${status ? `?status=${status}` : ""}`, [status]);
  const r = useDebounced(reload, 500);
  useLive("/api/stream/org", r);
  return <div>
    <div className="page-title"><h1>Tasks</h1><select className="select" style={{ width: "auto" }} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
      {["", "IN_PROGRESS", "READY", "BACKLOG", "BLOCKED", "FAILED", "COMPLETED", "APPROVED"].map((s) => <option key={s} value={s}>{s || "All statuses"}</option>)}</select></div>
    {!data ? <Loading /> : data.length === 0 ? <div className="card"><Empty title="No tasks">Tasks are created when a project's requirements are approved.</Empty></div> :
      <div className="card table-wrap"><table className="table"><thead><tr><th>Task</th><th>Project</th><th>Agent</th><th>Phase</th><th>Status</th><th>Revisions</th><th>Updated</th></tr></thead>
        <tbody>{data.map((t) => <tr key={t.id}><td><a href={`#/projects/${t.project_id}/tasks`}>{t.title}</a></td><td className="small">{t.project_name}</td><td className="small">{t.role_label}</td><td className="small">{t.phase}</td>
          <td><Status s={t.status} /></td><td className="small">{t.revision_count}</td><td className="small dim">{timeAgo(t.completed_at || t.started_at || t.created_at)}</td></tr>)}</tbody></table></div>}
  </div>;
}

export function ArtifactsPage() {
  const { data } = useApi<any[]>("/api/artifacts");
  const [sel, setSel] = useState<string | null>(null);
  return <div>
    <div className="page-title"><h1>Artifacts</h1><span className="small muted">Versioned deliverables agents hand to each other — never silently overwritten.</span></div>
    {!data ? <Loading /> : data.length === 0 ? <div className="card"><Empty title="No artifacts yet" /></div> :
      <div className="card table-wrap"><table className="table"><thead><tr><th>Artifact</th><th>Project</th><th>Phase</th><th>Author</th><th>Version</th><th>Status</th><th>Updated</th></tr></thead>
        <tbody>{data.map((a) => <tr key={a.id} style={{ cursor: "pointer" }} onClick={() => setSel(a.id)}><td><b>{a.name}</b></td><td className="small">{a.project_name}</td><td className="small">{a.phase}</td><td className="small">{a.author_agent}</td>
          <td className="small">v{a.current_version}{a.approved_version ? ` (approved v${a.approved_version})` : ""}</td><td><Status s={a.status} /></td><td className="small dim">{timeAgo(a.updated_at)}</td></tr>)}</tbody></table></div>}
    {sel && <Drawer onClose={() => setSel(null)}><ArtifactViewer artifactId={sel} /></Drawer>}
  </div>;
}

export function ApprovalsPage() {
  const { data, reload } = useApi<any[]>("/api/approvals");
  const hist = useApi<any[]>("/api/approvals?status=ALL", [data]);
  const r = useDebounced(reload, 400);
  useLive("/api/stream/org", r);
  return <div>
    <div className="page-title"><h1>Approvals</h1><span className="small muted">Humans stay in control: nothing is built, accepted or deployed past a gate without you.</span></div>
    {!data ? <Loading /> : <div className="stack">
      {data.length === 0 ? <div className="card"><Empty icon={LuCircleCheck} title="You're all caught up" /></div> : data.map((a) => a.gate === "requirements" ?
        <div key={a.id} className="card pad row between wrap approval"><div><span className="badge b-orange">REQUIREMENTS</span> <b>{a.title}</b> · {a.project_name}</div><a className="btn primary sm" href={`#/projects/${a.project_id}/chat`}>Review in chat</a></div> :
        <ApprovalCard key={a.id} a={a} onDone={reload} showProject />)}
      <h3 style={{ marginTop: 10 }}>Decision history</h3>
      <div className="card table-wrap"><table className="table"><thead><tr><th>Project</th><th>Gate</th><th>Decision</th><th>Note</th><th>When</th></tr></thead>
        <tbody>{(hist.data || []).filter((a) => a.status !== "PENDING").map((a) => <tr key={a.id}><td className="small">{a.project_name}</td><td className="small">{a.gate}</td><td><Status s={a.status} /></td><td className="small">{a.decision_note}</td><td className="small dim">{timeAgo(a.decided_at || a.created_at)}</td></tr>)}</tbody></table></div>
    </div>}
  </div>;
}

export function ActivityPage() {
  const { data, setData } = useApi<any[]>("/api/activity");
  const [type, setType] = useState("");
  useLive("/api/stream/org", (e) => setData((d) => [{ ...e, project_name: d?.find((x) => x.project_id === e.project_id)?.project_name }, ...(d || [])].slice(0, 400)));
  const rows = (data || []).filter((e) => !type || e.type.startsWith(type));
  return <div>
    <div className="page-title"><h1>Activity</h1><select className="select" style={{ width: "auto" }} value={type} onChange={(e) => setType(e.target.value)} aria-label="Event type">
      {[["", "All events"], ["TASK_", "Tasks"], ["AGENT_", "Agents"], ["ARTIFACT_", "Artifacts"], ["REVIEW_", "Reviews"], ["APPROVAL_", "Approvals"], ["DEPLOYMENT_", "Deployments"], ["BUG_", "Bugs"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
    {!data ? <Loading /> : rows.length === 0 ? <div className="card"><Empty title="No activity yet" /></div> : <div className="card pad"><EventList events={rows} showProject /></div>}
  </div>;
}

export function TemplatesPage() {
  const { data } = useApi<any[]>("/api/templates");
  const { create, busy } = useCreateProject();
  return <div>
    <div className="page-title"><h1>Templates</h1><span className="small muted">Templates speed up planning — the interview still adapts to you.</span></div>
    {!data ? <Loading /> : <div className="projects-grid">{data.map((t) => <div key={t.id} className="card pad stack">
      <div className="row"><span className="role-ic"><LuLayoutTemplate /></span><b>{t.name}</b></div><div className="small muted" style={{ flex: 1 }}>{t.description}</div>
      <button className="btn primary sm" disabled={busy} onClick={() => create(t.idea, t.id)}>Start from template</button></div>)}</div>}
  </div>;
}

export function SearchPage() {
  const q = (query().get("q") || "").toLowerCase();
  const projects = useApi<any[]>("/api/projects");
  const agents = useApi<any>(`/api/agents?q=${encodeURIComponent(q)}`, [q]);
  const tasks = useApi<any[]>("/api/tasks");
  const arts = useApi<any[]>("/api/artifacts");
  const m = (s?: string) => (s || "").toLowerCase().includes(q);
  const P = (projects.data || []).filter((p) => m(p.name) || m(p.idea));
  const T = (tasks.data || []).filter((t) => m(t.title) || m(t.role_label)).slice(0, 20);
  const A = (arts.data || []).filter((a) => m(a.name)).slice(0, 20);
  const G = (agents.data?.agents || []).slice(0, 20);
  return <div className="stack">
    <div className="page-title"><h1><LuSearch /> “{q}”</h1></div>
    {[["Projects", P.map((p) => <a key={p.id} className="list-item" style={{ display: "block" }} href={`#/projects/${p.id}`}>{p.name} <Status s={p.status} /></a>)],
      ["Agents", G.map((a: any) => <a key={a.id} className="list-item" style={{ display: "block" }} href={`#/marketplace?id=${encodeURIComponent(a.id)}`}>{a.name} <span className="tiny dim">{a.source}</span></a>)],
      ["Tasks", T.map((t) => <a key={t.id} className="list-item" style={{ display: "block" }} href={`#/projects/${t.project_id}/tasks`}>{t.title} <span className="tiny dim">{t.project_name}</span></a>)],
      ["Artifacts", A.map((a) => <a key={a.id} className="list-item" style={{ display: "block" }} href={`#/projects/${a.project_id}/artifacts`}>{a.name} <span className="tiny dim">{a.project_name}</span></a>)]].map(([title, items]: any) =>
      <div key={title} className="card pad"><h3 style={{ marginBottom: 6 }}>{title} ({items.length})</h3>{items.length ? items : <div className="small muted">No matches</div>}</div>)}
  </div>;
}
