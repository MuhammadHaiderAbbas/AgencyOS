import { useEffect, useRef, useState } from "react";
import {
  LuArchive, LuBot, LuCheck, LuCircle, LuCircleCheck, LuCopy, LuDownload, LuExternalLink, LuGitCommitHorizontal, LuHistory, LuLoader, LuPlay,
  LuRefreshCw, LuRocket, LuRotateCcw, LuSend, LuSparkles, LuTrash2, LuTriangleAlert, LuX,
} from "react-icons/lu";
import { api, clock, timeAgo } from "../api";
import { go, useMe } from "../main";
import {
  Drawer, Empty, Loading, Markdown, Modal, Progress, RoleIcon, Status, eventTone, fmtUsd, toneFor, useApi, useDebounced, useLive, useToast,
  phaseLabel,
} from "../ui";

const TABS: [string, string][] = [["chat", "Chat"], ["progress", "Progress"], ["tasks", "Tasks"], ["team", "Team"], ["artifacts", "Artifacts"],
  ["approvals", "Approvals"], ["preview", "Preview"], ["files", "Code"], ["deliverables", "Deliverables"], ["activity", "Activity"], ["trace", "Trace"], ["settings", "Settings"]];

export function ProjectPage({ id, tab }: { id: string; tab: string }) {
  const { data: p, error, reload } = useApi<any>(`/api/projects/${id}`);
  const [tick, setTick] = useState(0);
  const refresh = useDebounced(() => { reload(); setTick((t) => t + 1); }, 300);
  const live = useLive(`/api/stream/projects/${id}`, refresh);
  if (error) return <Empty title="Project not available">{error}</Empty>;
  if (!p) return <Loading />;
  const pendingN = p.pending_approvals.filter((a: any) => a.gate !== "requirements").length;
  return <div>
    <div className="proj-head">
      <h1>{p.name}</h1>{p.is_demo && <span className="demo-flag">DEMO</span>}<Status s={p.status} />
      <div style={{ flex: 1, minWidth: 160, maxWidth: 320 }}><Progress value={p.progress} tone={toneFor(p.status)} /></div>
      <span className="small muted">{Math.round(p.progress)}% · {p.tasks_done}/{p.tasks_total} tasks</span>
      <span className="small dim" title="Realtime connection">{live ? "● live" : "○ reconnecting"}</span>
    </div>
    <div className="tabs" role="tablist">{TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => go(`projects/${id}/${k}`)}>
      {l}{k === "approvals" && pendingN > 0 && <span className="n">{pendingN}</span>}</button>)}</div>
    <div style={{ marginTop: 16 }}>
      {tab === "chat" && <ChatTab p={p} tick={tick} onChange={refresh} />}
      {tab === "progress" && <ProgressTab p={p} tick={tick} />}
      {tab === "tasks" && <TasksTab p={p} tick={tick} />}
      {tab === "team" && <TeamTab p={p} />}
      {tab === "artifacts" && <ArtifactsTab p={p} tick={tick} />}
      {tab === "approvals" && <ApprovalsTab p={p} onChange={refresh} />}
      {tab === "preview" && <PreviewTab p={p} tick={tick} />}
      {tab === "files" && <FilesTab p={p} tick={tick} />}
      {tab === "deliverables" && <DeliverablesTab p={p} tick={tick} onChange={refresh} />}
      {tab === "activity" && <ActivityTab p={p} tick={tick} />}
      {tab === "trace" && <TraceTab p={p} tick={tick} />}
      {tab === "settings" && <SettingsTab p={p} onChange={refresh} />}
    </div>
  </div>;
}

// ================================================================ chat
function ChatTab({ p, tick, onChange }: { p: any; tick: number; onChange: () => void }) {
  const { data: msgs, reload } = useApi<any[]>(`/api/projects/${p.id}/messages`, [tick]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const toast = useToast();
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" }); }, [msgs?.length]);
  const send = async (content: string) => {
    if (!content.trim() || sending) return;
    setSending(true);
    try { await api(`/api/projects/${p.id}/messages`, { method: "POST", body: { content } }); setText(""); await reload(); onChange(); }
    catch (e: any) { toast(e.message, true); } finally { setSending(false); inputRef.current?.focus(); }
  };
  const action = async (path: string) => {
    try { await api(path, { method: "POST" }); await reload(); onChange(); } catch (e: any) { toast(e.message, true); }
  };
  const working = p.team.filter((m: any) => m.status === "WORKING");
  const lastIdx = (msgs || []).length - 1;
  return <div className="proj-layout">
    <section className="card chat" aria-label="Project chat">
      <div className="chat-log" ref={logRef} aria-live="polite">
        {(msgs || []).map((m, i) => <Message key={m.id} m={m} p={p} last={i === lastIdx} onOption={send} onAction={action} focusInput={() => inputRef.current?.focus()} />)}
      </div>
      {working.length > 0 && <div className="typing"><i /><i /><i /> {working.map((w: any) => w.name).join(", ")} {working.length > 1 ? "are" : "is"} working…</div>}
      {sending && <div className="typing"><i /><i /><i /> Thinking…</div>}
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <textarea ref={inputRef} className="textarea" rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder={p.status === "COMPLETED" ? "Request a change, e.g. “Make the homepage more luxurious”" : "Type your message…"}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }} aria-label="Message" maxLength={4000} />
        <button className="btn primary" disabled={sending || !text.trim()} aria-label="Send"><LuSend /></button>
      </form>
    </section>
    <StatusPanel p={p} />
  </div>;
}

function Message({ m, p, last, onOption, onAction, focusInput }: any) {
  const meta = m.meta || {};
  const user = m.role === "user";
  return <div className={`msg ${user ? "user" : ""}`}>
    {user ? <div className="avatar sm">{(m.author || "U")[0]}</div> : <div className="agent-av"><LuBot /></div>}
    <div>
      <div className="bubble">
        {!user && <div className="who">{m.author}</div>}
        {user ? <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div> : <Markdown text={m.content} />}
        {meta.type === "question" && last && (meta.options?.length > 0 || meta.optional) && <div className="opts">{(meta.options || []).map((o: string) => <button key={o} className="chip" onClick={() => onOption(o)}>{o}</button>)}
          {meta.optional && <button className="chip" onClick={() => onOption("skip")}>Skip</button>}</div>}
        {meta.type === "requirements_summary" && last && p.status === "REQUIREMENTS" && <div className="opts">
          <button className="btn success sm" onClick={() => onAction(`/api/projects/${p.id}/approve-requirements`)}><LuCheck /> Approve Project</button>
          <button className="btn sm" onClick={focusInput}>Make Changes</button></div>}
        {meta.type === "plan_ready" && <PlanCard meta={meta} p={p} onStart={() => onAction(`/api/projects/${p.id}/start`)} />}
        {meta.type === "approval" && last && <div className="opts"><a className="btn sm primary" href={`#/projects/${p.id}/approvals`}>Review & approve</a></div>}
        {meta.type === "escalation" && last && <div className="opts"><a className="btn sm" href={`#/projects/${p.id}/approvals`}><LuTriangleAlert /> Decide</a></div>}
        {meta.type === "change_request" && last && <div className="opts"><button className="btn success sm" onClick={() => onOption("yes")}>Apply change</button><button className="btn sm" onClick={() => onOption("no")}>Cancel</button></div>}
        {meta.type === "link" && meta.tab && <div className="opts"><a className="btn sm" href={`#/projects/${p.id}/${meta.tab}`}>Open {meta.tab}</a></div>}
      </div>
      <div className="time">{clock(m.created_at)}</div>
    </div>
  </div>;
}

function PlanCard({ meta, p, onStart }: any) {
  return <div className="plan-card" style={{ marginTop: 10 }}>
    <div className="row between"><b>BUILD PLAN READY</b><span className={`badge ${meta.risk === "Low" ? "b-green" : "b-orange"}`}>Risk: {meta.risk}</span></div>
    <div className="plan-grid"><div><b>{meta.team.length}</b><span className="tiny muted">AI specialists</span></div><div><b>{meta.tasks}</b><span className="tiny muted">tasks</span></div>
      <div><b>{meta.phases}</b><span className="tiny muted">phases</span></div><div><b>{fmtUsd(meta.estimate?.estimated_cost_usd)}</b><span className="tiny muted">est. AI cost</span></div></div>
    <div className="small muted">Team: {meta.team.join(", ")}</div>
    {meta.integrations?.length > 0 && <div className="small muted">Integrations: {meta.integrations.join(", ")}</div>}
    <div className="tiny dim" style={{ marginTop: 6 }}>{meta.estimate?.note} Estimated agent time ~{meta.estimate?.estimated_minutes} min (estimate).</div>
    {p.status === "PLANNING" && <button className="btn primary" style={{ marginTop: 10 }} onClick={onStart}><LuPlay /> START BUILD</button>}
  </div>;
}

function StatusPanel({ p }: { p: any }) {
  return <aside className="stack">
    <div className="card pad stack">
      <div className="row between"><h3>Status</h3><Status s={p.status} /></div>
      {p.phases.length === 0 ? <div className="small muted">The Requirements Agent is gathering what's needed. The plan appears once you approve the summary.</div> :
        p.phases.map((ph: any) => <div key={ph.phase} className="row" style={{ gap: 8 }}>
          {ph.done === ph.total ? <LuCircleCheck color="#4ade80" /> : ph.active ? <LuLoader className="spinner" color="#8b7cff" /> : ph.blocked ? <LuTriangleAlert color="#fbbf24" /> : <LuCircle color="#4b5587" />}
          <span style={{ flex: 1, }}>{phaseLabel(ph.phase)}</span><span className="small muted">{ph.progress}%</span></div>)}
    </div>
    {p.team.length > 0 && <div className="card pad"><h3 style={{ marginBottom: 6 }}>Project Team</h3>
      {p.team.map((m: any) => <div key={m.role} className="team-row"><RoleIcon role={m.role} /><div className="nm">{m.name}<small>{m.current_task}</small></div><Status s={m.status} /></div>)}</div>}
    <div className="card pad small"><h3 style={{ marginBottom: 6 }}>AI usage</h3>
      <dl className="kv"><dt>Provider</dt><dd>{p.llm.is_mock ? "Local deterministic (no LLM)" : p.llm.provider}</dd>
        <dt>Estimated</dt><dd>{fmtUsd(p.estimated_cost_usd)}</dd><dt>Actual</dt><dd>{fmtUsd(p.usage.cost)}</dd>
        <dt>Tokens</dt><dd>{(p.usage.tokens_in + p.usage.tokens_out).toLocaleString()}{p.llm.is_mock && " (estimated, local)"}</dd>
        <dt>Executions</dt><dd>{p.executions.n}</dd></dl></div>
  </aside>;
}

// ================================================================ progress / tasks / team
function ProgressTab({ p, tick }: { p: any; tick: number }) {
  const { data: tasks } = useApi<any[]>(`/api/projects/${p.id}/tasks`, [tick]);
  if (!p.phases.length) return <Empty title="No plan yet">Approve the requirements in Chat to generate the build plan.</Empty>;
  return <div className="proj-layout">
    <div className="card pad">
      <h3 style={{ marginBottom: 8 }}>Project timeline</h3>
      {p.phases.map((ph: any) => <div key={ph.phase} className="phase">
        <span className={`chk ${ph.done === ph.total ? "done" : ph.active ? "active" : ""}`}>{ph.done === ph.total ? <LuCheck size={13} /> : ph.active ? <LuLoader className="spinner" size={12} /> : null}</span>
        <b>{phaseLabel(ph.phase)}</b><Progress value={ph.progress} tone={ph.done === ph.total ? "green" : undefined} /><span className="small muted">{ph.done === ph.total ? "✓" : `${ph.progress}%`}</span></div>)}
      <h3 style={{ margin: "18px 0 8px" }}>Live build</h3>
      {(tasks || []).map((t) => <div key={t.id} className="team-row"><RoleIcon role={t.role} /><div className="nm">{t.role_label}<small>{t.title}{t.revision_count > 0 && ` · revision ${t.revision_count}`}</small></div><Status s={t.status} /></div>)}
    </div>
    <StatusPanel p={p} />
  </div>;
}

const COLS: [string, string[]][] = [["Backlog", ["BACKLOG"]], ["Ready", ["READY", "REVISION_REQUIRED"]], ["In progress", ["IN_PROGRESS"]], ["Waiting / blocked", ["BLOCKED", "FAILED", "REVIEW"]], ["Done", ["COMPLETED", "APPROVED"]]];

function TasksTab({ p, tick }: { p: any; tick: number }) {
  const { data: tasks } = useApi<any[]>(`/api/projects/${p.id}/tasks`, [tick]);
  const [sel, setSel] = useState<any>(null);
  if (!tasks) return <Loading />;
  if (!tasks.length) return <Empty title="No tasks yet">Tasks are created by the Project Manager after you approve the requirements.</Empty>;
  const byId = Object.fromEntries(tasks.map((t) => [t.id, t]));
  return <>
    <div className="kanban">{COLS.map(([name, sts]) => { const items = tasks.filter((t) => sts.includes(t.status)); return <div key={name} className="col">
      <h4>{name}<span>{items.length}</span></h4>
      {items.map((t) => <div key={t.id} className="tcard" role="button" tabIndex={0} onClick={() => setSel(t)} onKeyDown={(e) => e.key === "Enter" && setSel(t)} style={{ cursor: "pointer" }}>
        <div className="row between"><b style={{ fontSize: 13 }}>{t.title}</b>{t.kind === "approval" && <span className="badge b-orange">gate</span>}{t.kind === "fix" && <span className="badge b-red">bug fix</span>}</div>
        <div className="r">{t.role_label} · {phaseLabel(t.phase)}</div></div>)}</div>; })}</div>
    {sel && <Drawer onClose={() => setSel(null)}>
      <h2 style={{ fontSize: 19 }}>{sel.title}</h2>
      <div className="row wrap" style={{ margin: "10px 0" }}><Status s={sel.status} /><span className="badge b-gray">{sel.kind}</span><span className="badge b-gray">{sel.phase}</span>{sel.review_status && <Status s={sel.review_status} />}</div>
      <dl className="kv small"><dt>Assigned</dt><dd>{sel.role_label} {sel.assigned_agent && <code>{sel.assigned_agent}</code>}</dd><dt>Inputs</dt><dd>{sel.inputs.join(", ") || "—"}</dd>
        <dt>Outputs</dt><dd>{sel.outputs.join(", ") || "—"}</dd><dt>Depends on</dt><dd>{sel.dependencies.map((d: string) => byId[d]?.title).join(", ") || "—"}</dd>
        <dt>Attempts / revisions</dt><dd>{sel.attempt_count} / {sel.revision_count}</dd><dt>Started</dt><dd>{sel.started_at ? new Date(sel.started_at).toLocaleString() : "—"}</dd>
        <dt>Completed</dt><dd>{sel.completed_at ? new Date(sel.completed_at).toLocaleString() : "—"}</dd></dl>
      {sel.feedback?.length > 0 && <><h3 style={{ margin: "16px 0 6px" }}>Feedback / issues</h3><ul className="small">{sel.feedback.map((f: any, i: number) => <li key={i}>{typeof f === "string" ? f : `[${f.severity}] ${f.message}${f.page ? ` (${f.page})` : ""}`}</li>)}</ul></>}
    </Drawer>}
  </>;
}

function TeamTab({ p }: { p: any }) {
  if (!p.team.length) return <Empty title="Team not assembled yet">The team is generated from your approved requirements.</Empty>;
  return <div className="projects-grid">{p.team.map((m: any) => <div key={m.role} className="card pad stack">
    <div className="row"><RoleIcon role={m.role} /><b style={{ flex: 1 }}>{m.name}</b><Status s={m.status} /></div>
    <div className="small muted">Current: {m.current_task}</div><Progress value={m.progress} tone={m.progress === 100 ? "green" : undefined} />
    <div className="tiny dim">{m.tasks} task(s) · last activity {timeAgo(m.last_activity) || "—"}</div>
    {m.agent_id && <a className="tiny" href={`#/agents?id=${encodeURIComponent(m.agent_id)}`}>{m.agent_id}</a>}
  </div>)}</div>;
}

// ================================================================ artifacts
export function ArtifactViewer({ artifactId }: { artifactId: string }) {
  const [version, setVersion] = useState<number | null>(null);
  const { data: a, reload } = useApi<any>(`/api/artifacts/${artifactId}${version ? `?version=${version}` : ""}`, [version]);
  const [diff, setDiff] = useState<string | null>(null);
  const toast = useToast();
  if (!a) return <Loading />;
  const doPost = async (path: string, v: number, msg: string) => { try { await api(path, { method: "POST", body: { version: v } }); toast(msg); setVersion(null); reload(); } catch (e: any) { toast(e.message, true); } };
  let body: any = a.content;
  let parsed: any = null;
  if (a.content_type === "application/json") { try { parsed = JSON.parse(a.content); } catch { /* raw */ } }
  return <div className="stack">
    <div className="row wrap between"><div className="row"><h3>{a.name}</h3><span className="badge b-gray">v{a.version}</span><Status s={a.status} /></div>
      <div className="row wrap">
        <select className="select" style={{ width: "auto" }} value={a.version} onChange={(e) => { setDiff(null); setVersion(Number(e.target.value)); }} aria-label="Version">
          {a.versions.map((v: any) => <option key={v.version} value={v.version}>v{v.version} · {v.author_agent} · {timeAgo(v.created_at)}</option>)}</select>
        {a.versions.length > 1 && <button className="btn sm" onClick={async () => { const r = await api<any>(`/api/artifacts/${a.id}/diff?a=${a.versions[1].version}&b=${a.versions[0].version}`); setDiff(r.diff || "(no differences)"); }}><LuHistory /> Compare latest</button>}
        {a.version !== a.current_version && <button className="btn sm" onClick={() => doPost(`/api/artifacts/${a.id}/restore`, a.version, `Restored v${a.version} as a new version`)}><LuRotateCcw /> Restore</button>}
        {a.approved_version !== a.version && <button className="btn sm success" onClick={() => doPost(`/api/artifacts/${a.id}/approve`, a.version, "Version approved")}><LuCheck /> Approve</button>}
      </div></div>
    {diff ? <pre className="code">{diff}</pre> : parsed && a.name === "design-system.json" ? <DesignSystemView ds={parsed} raw={a.content} /> :
      parsed && /report/.test(a.name) ? <ReportView r={parsed} raw={a.content} projectId={a.project_id} /> :
      a.content_type === "text/markdown" ? <div className="card pad"><Markdown text={body} /></div> : <pre className="code">{body}</pre>}
  </div>;
}

function DesignSystemView({ ds, raw }: { ds: any; raw: string }) {
  return <div className="stack">
    <div className="card pad"><h3 style={{ marginBottom: 10 }}>Colours</h3><div className="row wrap" style={{ gap: 14 }}>{Object.entries(ds.colors).map(([k, v]: any) =>
      <div key={k} className="row" style={{ gap: 6 }}><span className="swatch" style={{ background: v }} /><div className="small"><b>{k}</b><div className="dim">{v}</div></div></div>)}</div></div>
    <div className="card pad small"><h3 style={{ marginBottom: 6 }}>Typography</h3><div style={{ fontFamily: ds.typography.heading, fontSize: 26 }}>Heading — {ds.typography.heading.split(",")[0]}</div><div style={{ fontFamily: ds.typography.body }}>Body — {ds.typography.body.split(",")[0]}</div></div>
    {ds.decisions?.length > 0 && <div className="card pad small"><h3 style={{ marginBottom: 6 }}>Design decisions</h3><ul>{ds.decisions.map((d: string, i: number) => <li key={i}>{d}</li>)}</ul></div>}
    <details><summary className="small muted">Raw JSON</summary><pre className="code">{raw}</pre></details>
  </div>;
}

function ReportView({ r, raw, projectId }: { r: any; raw: string; projectId: string }) {
  return <div className="stack">
    <div className="row"><Status s={r.status} />{r.standard && <span className="small muted">{r.standard}</span>}</div>
    {r.passed?.length > 0 && <div className="card pad small"><h3 style={{ marginBottom: 6 }}>Passed</h3><ul>{r.passed.map((x: string, i: number) => <li key={i}>✓ {x}</li>)}</ul></div>}
    <div className="card pad small"><h3 style={{ marginBottom: 6 }}>Issues ({r.failed?.length || 0})</h3>{!r.failed?.length ? <div className="muted">None</div> :
      <table className="table"><tbody>{r.failed.map((f: any, i: number) => <tr key={i}><td><Status s={f.severity === "critical" || f.severity === "high" ? "FAILED" : "WARNING"} /></td><td>{f.message}</td><td className="dim">{f.page}</td></tr>)}</tbody></table>}</div>
    {r.warnings?.length > 0 && <div className="card pad small"><h3 style={{ marginBottom: 6 }}>Warnings</h3><ul>{r.warnings.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></div>}
    {r.visual?.screenshots?.length > 0 && <div className="card pad"><h3 style={{ marginBottom: 8 }}>Visual QA screenshots</h3><div className="row wrap">{r.visual.screenshots.map((s: string) =>
      <a key={s} href={`/api/projects/${projectId}/screenshots/${s}`} target="_blank" rel="noopener"><img alt={`Screenshot ${s}`} src={`/api/projects/${projectId}/screenshots/${s}`} style={{ height: 160, borderRadius: 8, border: "1px solid var(--border)" }} /></a>)}</div></div>}
    {r.notes && <div className="small muted">{r.notes.join(" ")}</div>}
    <details><summary className="small muted">Raw JSON</summary><pre className="code">{raw}</pre></details>
  </div>;
}

function ArtifactsTab({ p, tick }: { p: any; tick: number }) {
  const { data } = useApi<any[]>(`/api/projects/${p.id}/artifacts`, [tick]);
  const [sel, setSel] = useState<string | null>(null);
  if (!data) return <Loading />;
  if (!data.length) return <Empty title="No artifacts yet">Agents communicate through versioned artifacts — they'll appear here as work progresses.</Empty>;
  const current = sel || data[0].id;
  return <div className="split">
    <div className="card" style={{ padding: 8, alignSelf: "start" }}>{data.map((a) => <div key={a.id} className={`list-item ${current === a.id ? "active" : ""}`} onClick={() => setSel(a.id)} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setSel(a.id)}>
      <div className="row between"><b style={{ fontSize: 13 }}>{a.name}</b><span className="tiny dim">v{a.current_version}</span></div><div className="tiny muted">{a.author_agent} · {a.phase}</div></div>)}</div>
    <div key={current + tick}><ArtifactViewer artifactId={current} /></div>
  </div>;
}

// ================================================================ approvals
export function ApprovalCard({ a, onDone, showProject }: { a: any; onDone: () => void; showProject?: boolean }) {
  const [note, setNote] = useState("");
  const [mode, setMode] = useState<"" | "changes">("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const decide = async (decision: string) => {
    setBusy(true);
    try { await api(`/api/approvals/${a.id}/decide`, { method: "POST", body: { decision, note: note || undefined } }); toast(decision === "approve" ? "Approved — the team is continuing" : "Sent back to the team"); onDone(); }
    catch (e: any) { toast(e.message, true); } finally { setBusy(false); }
  };
  const pv = a.preview || {};
  return <div className="card pad stack approval">
    <div className="row between wrap"><div><span className="badge b-orange" style={{ textTransform: "uppercase" }}>{a.gate} gate</span> <b style={{ fontSize: 16, marginLeft: 6 }}>{a.title}</b></div>
      <span className="tiny dim">{showProject && <a href={`#/projects/${a.project_id}`}>{a.project_name}</a>} · {timeAgo(a.created_at)}</span></div>
    <dl className="kv small"><dt>What changed</dt><dd>{a.what_changed || "—"}</dd><dt>Why</dt><dd>{a.why || "—"}</dd><dt>Impact</dt><dd>{a.impact || "—"}</dd></dl>
    {pv.preview_url && <div className="row wrap"><a className="btn sm" href={pv.preview_url} target="_blank" rel="noopener"><LuExternalLink /> Open preview</a><a className="btn sm" href={`#/projects/${a.project_id}/preview`}>Preview in app</a></div>}
    {pv.artifacts && <div className="small muted">Review: {pv.artifacts.map((n: string) => <a key={n} href={`#/projects/${a.project_id}/artifacts`} style={{ marginRight: 8 }}>{n}</a>)}</div>}
    {pv.requirements && <details><summary className="small">Requirements preview</summary><pre className="code">{JSON.stringify(pv.requirements, null, 2)}</pre></details>}
    {mode === "changes" && <textarea className="textarea" placeholder="What should change?" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Requested changes" />}
    <div className="row wrap">
      <button className="btn success" disabled={busy} onClick={() => decide("approve")}><LuCheck /> {a.gate === "decision" ? "Accept & continue" : "Approve"}</button>
      {mode === "changes" ? <button className="btn" disabled={busy || !note.trim()} onClick={() => decide("changes")}>Send to team</button> :
        <button className="btn" onClick={() => setMode("changes")}>{a.gate === "decision" ? "Let the team try again" : "Request changes"}</button>}
    </div>
  </div>;
}

function ApprovalsTab({ p, onChange }: { p: any; onChange: () => void }) {
  const { data: hist, reload } = useApi<any[]>(`/api/approvals?status=ALL`, [p.updated_at]);
  const mine = (hist || []).filter((a) => a.project_id === p.id);
  const pending = p.pending_approvals.filter((a: any) => a.gate !== "requirements");
  return <div className="stack">
    {pending.length === 0 ? <div className="card"><Empty icon={LuCircleCheck} title="Nothing waiting for you">You'll be asked to approve the design, the finished build and deployment.</Empty></div>
      : pending.map((a: any) => <ApprovalCard key={a.id} a={a} onDone={() => { onChange(); reload(); }} />)}
    <h3 style={{ marginTop: 10 }}>History</h3>
    <div className="card table-wrap"><table className="table"><thead><tr><th>Gate</th><th>Title</th><th>Decision</th><th>Note</th><th>When</th></tr></thead>
      <tbody>{mine.filter((a) => a.status !== "PENDING").map((a) => <tr key={a.id}><td>{a.gate}</td><td>{a.title}</td><td><Status s={a.status} /></td><td className="small">{a.decision_note || ""}</td><td className="small dim">{timeAgo(a.decided_at || a.created_at)}</td></tr>)}</tbody></table></div>
  </div>;
}

// ================================================================ preview / code / deliverables
function PreviewTab({ p, tick }: { p: any; tick: number }) {
  const [page, setPage] = useState("index.html");
  const [width, setWidth] = useState<"100%" | "390px">("100%");
  const { data } = useApi<any>(`/api/projects/${p.id}/files`, [tick]);
  if (!p.has_preview) return <Empty title="No build yet">The preview appears after the Frontend Developer builds the first version.</Empty>;
  const pages = (data?.files || []).filter((f: any) => f.path.startsWith("source/site/") && f.path.endsWith(".html")).map((f: any) => f.path.replace("source/site/", ""));
  return <div className="stack">
    <div className="row wrap"><select className="select" style={{ width: "auto" }} value={page} onChange={(e) => setPage(e.target.value)} aria-label="Page">{pages.map((x: string) => <option key={x}>{x}</option>)}</select>
      <button className={`btn sm ${width === "100%" ? "primary" : ""}`} onClick={() => setWidth("100%")}>Desktop</button><button className={`btn sm ${width !== "100%" ? "primary" : ""}`} onClick={() => setWidth("390px")}>Mobile</button>
      <a className="btn sm" href={`/api/projects/${p.id}/preview/${page}`} target="_blank" rel="noopener"><LuExternalLink /> Open in new tab</a>
      {p.live_url && <a className="btn sm success" href={p.live_url} target="_blank" rel="noopener"><LuRocket /> Live site</a>}</div>
    <div style={{ display: "flex", justifyContent: "center" }}><iframe key={tick + page} className="preview-frame" style={{ width }} src={`/api/projects/${p.id}/preview/${page}`} title="Site preview" sandbox="allow-scripts allow-forms allow-same-origin" /></div>
  </div>;
}

function FilesTab({ p, tick }: { p: any; tick: number }) {
  const { data } = useApi<any>(`/api/projects/${p.id}/files`, [tick]);
  const [path, setPath] = useState<string | null>(null);
  const file = useApi<any>(path ? `/api/projects/${p.id}/file?path=${encodeURIComponent(path)}` : null, [path, tick]);
  if (!data) return <Loading />;
  return <div className="split">
    <div className="stack">
      <div className="card" style={{ padding: 8, maxHeight: 460, overflowY: "auto" }}>{data.files.map((f: any) => <div key={f.path} className={`list-item small ${path === f.path ? "active" : ""}`} onClick={() => setPath(f.path)} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setPath(f.path)}>
        <code>{f.path}</code> <span className="tiny dim">{(f.size / 1024).toFixed(1)} KB</span></div>)}</div>
      <div className="card pad"><h3 style={{ marginBottom: 6 }}><LuGitCommitHorizontal /> Commits <span className="tiny dim">({data.head})</span></h3>
        {data.commits.map((c: any) => <div key={c.hash} className="small" style={{ padding: "4px 0" }}><code className="dim">{c.hash}</code> {c.message}</div>)}</div>
    </div>
    <div>{path ? (file.data ? <pre className="code" style={{ maxHeight: "calc(100vh - 240px)" }}>{file.data.content}</pre> : <Loading />) : <Empty title="Select a file">The project's isolated git workspace — every agent commits as <code>agent(role): …</code></Empty>}</div>
  </div>;
}

function DeliverablesTab({ p, tick, onChange }: { p: any; tick: number; onChange: () => void }) {
  const { data, reload } = useApi<any>(`/api/projects/${p.id}/deployments`, [tick]);
  const toast = useToast();
  const rollback = async (id: string) => { try { await api(`/api/projects/${p.id}/deployments/${id}/rollback`, { method: "POST" }); toast("Rolled back"); reload(); onChange(); } catch (e: any) { toast(e.message, true); } };
  const earningReady = p.has_preview;
  return <div className="stack">
    <div className="card pad stack" style={{ borderColor: p.status==="COMPLETED"?"#22c55e66":undefined, background: p.status==="COMPLETED"?"rgba(34,197,94,.06)":undefined }}>
      <div className="row between wrap"><h3>{p.status === "COMPLETED" ? "PROJECT COMPLETE — ready to earn" : "Deliverables so far"}</h3><Status s={p.status} /></div>
      {p.status==="COMPLETED" && <div className="small" style={{ background:"linear-gradient(135deg, #6d5efc11, #22d3ee11)", padding:8, borderRadius:8, border:"1px solid #6d5efc33" }}><b>💰 Earning activated:</b> This site ships with Stripe Checkout (real when you set <code>STRIPE_SECRET_KEY</code> in <code>source/api/.env</code>, mock checkout works without it), newsletter capture that builds your owned list, and SEO that drives traffic. Deploy, set your Stripe keys & email, and hand the live URL + API to your client — they pay you.</div>}
      <div className="row wrap">
        {p.live_url && <a className="btn success" href={p.live_url} target="_blank" rel="noopener"><LuRocket /> Live URL</a>}
        <a className="btn" href={`/api/projects/${p.id}/export`}><LuDownload /> Download source & docs (ZIP)</a>
        <a className="btn" href={`#/projects/${p.id}/files`}>Source code</a><a className="btn" href={`#/projects/${p.id}/artifacts`}>Reports & documentation</a>
        {earningReady && <a className="btn primary" href={`/api/projects/${p.id}/preview/booking.html`} target="_blank" rel="noopener">Test booking checkout →</a>}
      </div>
      <div className="small muted">GitHub: not connected (local git history kept; connect in Settings → paste <code>GITHUB_TOKEN</code> to push). Secrets never leave the server or exports.</div>
    </div>

    {earningReady && <div className="grid" style={{ gridTemplateColumns:"repeat(auto-fit,minmax(280px,1fr))" }}>
      <div className="card pad small stack">
        <h3>💳 How this site earns (client)</h3>
        <ul style={{ margin:"6px 0 0 18px" }}>
          <li><b>Hotel/ecommerce:</b> Room bookings & orders → <code>POST /api/bookings</code> / <code>/api/orders/checkout</code> → Stripe Checkout (demo URL if no key, real Stripe when you set <code>STRIPE_SECRET_KEY</code>). Check <code>source/api/EARNING.md</code> in the export.</li>
          <li><b>Newsletter:</b> <code>POST /api/newsletter</code> builds owned audience (CSV in DB) — monetize via email.</li>
          <li><b>Enquiries:</b> <code>POST /api/enquiries</code> → email notification (real when SMTP set, mock log otherwise).</li>
        </ul>
        <div className="tiny dim">Admin: manage with <code>Authorization: Bearer $ADMIN_TOKEN</code> → <code>GET /api/bookings</code> + <code>/api/orders</code>. Set <code>ADMIN_TOKEN</code> + <code>ALLOWED_ORIGIN</code> when you deploy the API separately (see <code>source/api/.env.example</code>).</div>
      </div>
      <div className="card pad small stack">
        <h3>🚀 Deploy & handover checklist</h3>
        <ol style={{ margin:"6px 0 0 18px" }}>
          <li>Approve → Authorise deploy → Deploy (local/Netlify/Vercel/Render shown below)</li>
          <li>Download ZIP or push to GitHub → deploy <code>source/api</code> (set <code>STRIPE_SECRET_KEY</code> + <code>ADMIN_TOKEN</code>)</li>
          <li>Set <code>assets/config.js</code> <code>apiBase</code> + <code>stripePublishableKey</code> to your API origin</li>
          <li>Test: open <code>booking.html</code> → submit → follow checkout_url (mock or Stripe)</li>
          <li>Hand client live URL + admin token → they see bookings/orders.</li>
        </ol>
        <div className="small muted">Earning health: Preview API check <code>/api/health</code> shows <code>earning:true</code> when Stripe is live.</div>
      </div>
    </div>}

    <div className="card table-wrap"><table className="table"><thead><tr><th>Release</th><th>Provider</th><th>Status</th><th>Commit</th><th>When</th><th /></tr></thead>
      <tbody>{(data?.deployments || []).map((d: any) => <tr key={d.id}><td><code>{d.id.slice(0, 8)}</code> {d.current && <span className="badge b-green">current</span>}</td><td>{d.provider}</td><td><Status s={d.status} /></td><td><code>{d.commit_hash}</code></td><td className="small dim">{timeAgo(d.created_at)}</td>
        <td>{!d.current && d.status === "SUCCEEDED" && <button className="btn sm" onClick={() => rollback(d.id)}><LuRotateCcw /> Roll back</button>}</td></tr>)}</tbody></table>
      {!data?.deployments?.length && <Empty title="Not deployed yet">Deployment only happens after you authorise it — then this site starts earning bookings. Local is always ready; Netlify/Vercel/Render work when you set their tokens.</Empty>}</div>
    <div className="card pad small"><h3 style={{ marginBottom: 6 }}>Deployment targets</h3>{(data?.adapters || []).map((a: any) => <div key={a.name} className="row between" style={{ padding: "3px 0" }}><span>{a.name}</span><span className={`badge ${a.configured ? "b-green" : "b-gray"}`}>{a.configured ? "ready — can earn now" : a.note ? "interface only — set env" : "not configured"}</span></div>)}
      <div className="tiny dim" style={{ marginTop:6 }}>Local = <code>/sites/{p.id}/</code> (always works). Netlify: <code>NETLIFY_AUTH_TOKEN + NETLIFY_SITE_ID</code>. Vercel: <code>VERCEL_TOKEN + VERCEL_PROJECT_ID</code>. Render: <code>RENDER_DEPLOY_HOOK_URL</code>. Cloudflare/GCP/AWS stubs ready — same interface.</div>
    </div>
  </div>;
}

// ================================================================ activity / trace / settings
export function EventList({ events, showProject }: { events: any[]; showProject?: boolean }) {
  return <div className="feed">{events.map((e) => <div key={e.id} className="feed-item"><span className={`ic ${eventTone(e.type)}`}><LuSparkles /></span>
    <div><div className="row wrap" style={{ gap: 6 }}><span className="tiny dim">{clock(e.created_at)}</span><b>{e.actor}</b><span className="badge b-gray" style={{ fontSize: 10 }}>{e.type}</span>
      {showProject && e.project_name && <a className="tiny" href={`#/projects/${e.project_id}`}>{e.project_name}</a>}</div>
      <div className="small muted">{e.message}</div></div></div>)}</div>;
}

function ActivityTab({ p, tick }: { p: any; tick: number }) {
  const { data } = useApi<any[]>(`/api/projects/${p.id}/activity`, [tick]);
  if (!data) return <Loading />;
  return <div className="card pad"><EventList events={data} /></div>;
}

function TraceTab({ p, tick }: { p: any; tick: number }) {
  const { data } = useApi<any[]>(`/api/projects/${p.id}/executions`, [tick]);
  const [sel, setSel] = useState<any>(null);
  if (!data) return <Loading />;
  if (!data.length) return <Empty title="No agent executions yet" />;
  return <>
    <div className="small muted" style={{ marginBottom: 8 }}>Every agent execution: inputs, tools, outputs, cost and review result. Reasoning summaries only — no hidden chain-of-thought or secrets.</div>
    <div className="card table-wrap"><table className="table"><thead><tr><th>Agent</th><th>Task</th><th>Status</th><th>Provider</th><th>Duration</th><th>Tokens</th><th>Cost</th><th>Review</th></tr></thead>
      <tbody>{data.map((e) => <tr key={e.id} style={{ cursor: "pointer" }} onClick={() => setSel(e)}><td>{e.role_label}</td><td className="small">{e.task_title || e.input_summary}</td><td><Status s={e.status} /></td>
        <td className="small">{e.provider === "mock" ? "local" : `${e.provider}/${e.model}`}</td><td className="small">{(e.duration_ms / 1000).toFixed(2)}s</td><td className="small">{e.tokens_in + e.tokens_out}</td><td className="small">{fmtUsd(e.cost_usd)}</td>
        <td>{e.review ? <Status s={e.review.verdict} /> : <span className="dim">—</span>}</td></tr>)}</tbody></table></div>
    {sel && <Drawer onClose={() => setSel(null)}>
      <h2 style={{ fontSize: 18 }}>{sel.role_label} · {sel.task_title}</h2>
      <dl className="kv small" style={{ marginTop: 12 }}><dt>Agent</dt><dd><code>{sel.agent_id}</code></dd><dt>Status</dt><dd><Status s={sel.status} /></dd><dt>Input</dt><dd>{sel.input_summary}</dd>
        <dt>Output</dt><dd>{sel.output_summary}</dd><dt>Tools</dt><dd>{sel.tools_used.join(", ") || "—"}</dd><dt>Model</dt><dd>{sel.provider}/{sel.model}</dd>
        <dt>Tokens in/out</dt><dd>{sel.tokens_in} / {sel.tokens_out}</dd><dt>Cost</dt><dd>{fmtUsd(sel.cost_usd)}</dd><dt>Confidence</dt><dd>{sel.confidence ?? "—"}</dd>
        <dt>Started</dt><dd>{new Date(sel.started_at).toLocaleString()}</dd></dl>
      {sel.review && <><h3 style={{ margin: "14px 0 6px" }}>Review</h3><Status s={sel.review.verdict} /><pre className="code" style={{ marginTop: 6 }}>{sel.review.issues}</pre></>}
      {sel.errors?.length > 0 && <><h3 style={{ margin: "14px 0 6px" }}>Errors</h3><pre className="code">{sel.errors.join("\n")}</pre></>}
      {sel.logs?.length > 0 && <><h3 style={{ margin: "14px 0 6px" }}>Logs</h3><pre className="code">{sel.logs.join("\n")}</pre></>}
    </Drawer>}
  </>;
}

function SettingsTab({ p, onChange }: { p: any; onChange: () => void }) {
  const { me } = useMe();
  const toast = useToast();
  const [del, setDel] = useState(false);
  const [confirm, setConfirm] = useState("");
  const post = async (path: string, msg: string, after?: (r: any) => void) => { try { const r = await api(path, { method: "POST" }); toast(msg); onChange(); after?.(r); } catch (e: any) { toast(e.message, true); } };
  return <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))" }}>
    <div className="card pad stack"><h3>Project</h3>
      <dl className="kv small"><dt>Idea</dt><dd>{p.idea}</dd><dt>Type</dt><dd>{p.project_type}</dd><dt>Industry</dt><dd>{p.industry}</dd><dt>Created</dt><dd>{new Date(p.created_at).toLocaleString()}</dd></dl>
      <div className="row wrap">
        <button className="btn" onClick={() => post(`/api/projects/${p.id}/clone`, "Project cloned (requirements & design, no secrets)", (r) => go(`projects/${r.id}`))}><LuCopy /> Clone</button>
        <button className="btn" onClick={() => post(`/api/projects/${p.id}/${p.archived ? "unarchive" : "archive"}`, p.archived ? "Restored" : "Archived")}><LuArchive /> {p.archived ? "Restore" : "Archive"}</button>
        <a className="btn" href={`/api/projects/${p.id}/export`}><LuDownload /> Export ZIP</a>
        {["owner", "admin"].includes(me.user.org_role) && <button className="btn danger" onClick={() => setDel(true)}><LuTrash2 /> Delete</button>}
      </div></div>
    <div className="card pad"><h3 style={{ marginBottom: 8 }}>Requirement versions</h3>
      {p.requirement_versions.length === 0 ? <div className="small muted">Not approved yet.</div> : p.requirement_versions.map((v: any) => <div key={v.version} className="small row between" style={{ padding: "4px 0" }}><span>v{v.version} — {v.change_note}</span><span className="dim">{timeAgo(v.created_at)}</span></div>)}</div>
    <div className="card pad"><h3 style={{ marginBottom: 8 }}>Project memory</h3><div className="small muted" style={{ marginBottom: 6 }}>Preferences and decisions agents retrieve before acting.</div>
      {p.memory.length === 0 ? <div className="small dim">Nothing remembered yet.</div> : p.memory.map((m: any, i: number) => <div key={i} className="small" style={{ padding: "3px 0" }}><span className="badge b-gray">{m.kind}</span> {m.key.replace("avoid_color:", "avoid colour: ")} {m.kind === "decision" && <span className="muted">— {m.value}</span>}</div>)}</div>
    {del && <Modal title="Delete project" onClose={() => setDel(false)}>
      <p className="small">This permanently deletes the project, its workspace, artifacts and deployments. Type <b>{p.name}</b> to confirm.</p>
      <input className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-label="Project name" />
      <div className="row" style={{ marginTop: 12 }}><button className="btn danger" disabled={confirm !== p.name} onClick={async () => { try { await api(`/api/projects/${p.id}`, { method: "DELETE", body: { confirm } }); go("projects"); } catch (e: any) { toast(e.message, true); } }}>Delete forever</button>
        <button className="btn" onClick={() => setDel(false)}>Cancel</button></div>
    </Modal>}
  </div>;
}
