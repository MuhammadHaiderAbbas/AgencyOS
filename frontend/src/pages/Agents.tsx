import { useEffect, useState } from "react";
import { LuBot, LuDownload, LuExternalLink, LuPlus, LuRefreshCw, LuShieldCheck } from "react-icons/lu";
import { api, timeAgo } from "../api";
import { query, useMe } from "../main";
import { Drawer, Empty, Loading, Modal, Status, fmtUsd, useApi, useToast } from "../ui";

export function AgentsPage({ mode }: { mode: "registry" | "marketplace" }) {
  const { me } = useMe();
  const toast = useToast();
  const [f, setF] = useState({ q: "", source: mode === "marketplace" ? "" : "", framework: "", industry: "" });
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as any).toString();
  const { data, reload } = useApi<any>(`/api/agents?${qs}`, [qs]);
  const [sel, setSel] = useState<string | null>(query().get("id"));
  const [importing, setImporting] = useState(false);
  const [custom, setCustom] = useState(false);
  useEffect(() => { const id = query().get("id"); if (id) setSel(id); }, []);
  const doImport = async () => {
    setImporting(true);
    try { const r = await api<any>("/api/agents/import", { method: "POST" }); toast(`Imported ${r.runnable.length} runnable agents and ${r.catalogue_entries} catalogue entries (commit ${String(r.commit).slice(0, 7)})`); reload(); }
    catch (e: any) { toast(e.message, true); } finally { setImporting(false); }
  };
  if (!data) return <Loading />;
  const agents = mode === "registry" ? data.agents.filter((a: any) => a.source !== "catalogue") : data.agents;
  return <div>
    <div className="page-title"><div><h1>{mode === "registry" ? "Agents" : "Agent Marketplace"}</h1>
      <div className="small muted">{mode === "registry" ? "Every agent AgencyOS can route work to: its contract, permissions, health and track record." :
        "Browse built-in, custom and imported agents — including the 500-AI-Agents-Projects catalogue."}</div></div>
      {me.user.is_admin && <div className="row wrap">
        <button className="btn" onClick={doImport} disabled={importing}>{importing ? <LuRefreshCw className="spinner" /> : <LuDownload />} Sync GitHub catalogue</button>
        <button className="btn primary" onClick={() => setCustom(true)}><LuPlus /> Custom agent</button></div>}
    </div>
    <div className="row wrap" style={{ marginBottom: 14 }}>
      <input className="input" style={{ maxWidth: 280 }} placeholder="Search capability, name…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} aria-label="Search agents" />
      {(["source", "framework", "industry"] as const).map((k) => <select key={k} className="select" style={{ width: "auto" }} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} aria-label={k}>
        <option value="">All {k === "source" ? "sources" : k === "framework" ? "frameworks" : "industries"}</option>{(data.facets[k] || []).filter((x: string) => mode === "marketplace" || x !== "catalogue").map((x: string) => <option key={x}>{x}</option>)}</select>)}
      <span className="small muted">{data.counts.builtin} built-in · {data.counts.custom} custom · {data.counts.github} GitHub{mode === "marketplace" && ` · ${data.counts.catalogue} catalogue`}</span>
    </div>
    {agents.length === 0 ? <div className="card"><Empty icon={LuBot} title="No agents match">{me.user.is_admin && data.counts.github === 0 ? "Use “Sync GitHub catalogue” to import the agent repository." : "Try another filter."}</Empty></div> :
      <div className="card table-wrap"><table className="table"><thead><tr><th>Agent</th><th>Category</th><th>Framework</th><th>Capabilities</th><th>Success</th><th>Avg cost</th><th>Status</th></tr></thead>
        <tbody>{agents.map((a: any) => <tr key={a.id} style={{ cursor: "pointer" }} onClick={() => setSel(a.id)}>
          <td><b>{a.name}</b><div className="tiny dim">{a.source}{a.role && ` · ${a.role}`}</div></td><td className="small">{a.category || a.industry || "—"}</td><td><span className="badge b-gray">{a.framework}</span></td>
          <td className="small">{a.capabilities.slice(0, 3).join(", ")}</td><td className="small">{a.metrics.runs ? `${Math.round(a.metrics.success_rate * 100)}% of ${a.metrics.runs}` : "—"}</td>
          <td className="small">{a.metrics.runs ? fmtUsd(a.metrics.avg_cost_usd) : "—"}</td>
          <td><div className="row" style={{ gap: 4 }}><Status s={a.enabled ? a.health_status : "DISABLED"} /></div></td></tr>)}</tbody></table></div>}
    {sel && <AgentDrawer id={sel} onClose={() => setSel(null)} onChange={reload} admin={me.user.is_admin} />}
    {custom && <CustomAgent onClose={() => setCustom(false)} onDone={() => { setCustom(false); reload(); }} />}
  </div>;
}

function AgentDrawer({ id, onClose, onChange, admin }: { id: string; onClose: () => void; onChange: () => void; admin: boolean }) {
  const { data: a, reload } = useApi<any>(`/api/agents/${encodeURIComponent(id)}`);
  const toast = useToast();
  const [test, setTest] = useState<any>(null);
  const act = async (path: string, msg: string) => { try { const r = await api<any>(`/api/agents/${encodeURIComponent(id)}/${path}`, { method: "POST" }); if (path === "test") setTest(r); toast(msg + (r.detail ? ` — ${r.detail}` : "")); reload(); onChange(); } catch (e: any) { toast(e.message, true); } };
  return <Drawer onClose={onClose}>{!a ? <Loading /> : <div className="stack">
    <div className="row wrap"><h2 style={{ fontSize: 20 }}>{a.name}</h2><Status s={a.enabled ? a.health_status : "DISABLED"} /><span className="badge b-gray">{a.framework}</span><span className="badge b-gray">risk: {a.risk_level}</span></div>
    <div className="muted">{a.description}</div>
    {a.health_detail && <div className="small"><LuShieldCheck /> {a.health_detail}</div>}
    {admin && <div className="row wrap">
      {a.executable && <button className="btn sm" onClick={() => act(a.enabled ? "disable" : "enable", a.enabled ? "Disabled" : "Enabled")}>{a.enabled ? "Disable" : "Enable"}</button>}
      {a.executable && <button className="btn sm" onClick={() => act("health", "Health check run")}>Run health check</button>}
      {a.execution_mode === "prompt" && <button className="btn sm" onClick={() => act("test", "Test finished")}>Test agent</button>}
      {a.source_url && <a className="btn sm" href={a.source_url} target="_blank" rel="noopener noreferrer"><LuExternalLink /> Source</a>}</div>}
    {test && <div className="card pad small"><b>Test: {test.status}</b><div>{test.summary}</div>{test.errors?.length > 0 && <div className="muted">{test.errors.join("; ")}</div>}{test.output && <pre className="code">{test.output}</pre>}</div>}
    <dl className="kv small">
      <dt>ID</dt><dd><code>{a.id}</code></dd><dt>Source</dt><dd>{a.source}{a.commit_hash && <> @ <code>{a.commit_hash.slice(0, 10)}</code></>}</dd><dt>Execution</dt><dd>{a.execution_mode}</dd>
      <dt>License</dt><dd>{a.license || "unknown"}</dd><dt>Capabilities</dt><dd>{a.capabilities.join(", ") || "—"}</dd><dt>Permissions</dt><dd>{a.permissions.join(", ") || "—"}</dd>
      <dt>Tools</dt><dd>{a.tools.join(", ") || "—"}</dd><dt>Credentials</dt><dd>{a.required_credentials.join(", ") || "none"}</dd>
      {a.entrypoint && <><dt>Entrypoint</dt><dd><code>{a.entrypoint.split("/").slice(-2).join("/")}</code></dd></>}
      {a.input_schema?.cli_args && <><dt>Inputs</dt><dd>{a.input_schema.cli_args.map((x: any) => x.flag).join(" ")}</dd></>}
      {a.dependencies?.length > 0 && <><dt>Dependencies</dt><dd className="tiny">{a.dependencies.join(", ")}</dd></>}
    </dl>
    {a.contract && <div className="card pad small"><h3 style={{ marginBottom: 6 }}>Contract</h3>
      <dl className="kv"><dt>Task</dt><dd>{a.contract.task}</dd><dt>Inputs</dt><dd>{a.contract.inputs?.join(", ") || "—"}</dd><dt>Expected output</dt><dd>{a.contract.expected_output?.join(", ") || "—"}</dd>
        <dt>Quality criteria</dt><dd>{a.contract.quality_criteria?.join("; ") || "—"}</dd><dt>Constraints</dt><dd>{a.contract.constraints?.join("; ") || "—"}</dd><dt>Do not</dt><dd>{a.contract.do_not?.join("; ") || "—"}</dd></dl></div>}
    <div className="card pad small"><h3 style={{ marginBottom: 6 }}>Performance</h3><dl className="kv"><dt>Runs</dt><dd>{a.metrics.runs}</dd><dt>Success rate</dt><dd>{Math.round(a.metrics.success_rate * 100)}%</dd>
      <dt>Review pass rate</dt><dd>{Math.round(a.metrics.review_pass_rate * 100)}%</dd><dt>Avg duration</dt><dd>{a.metrics.avg_duration_ms} ms</dd><dt>Avg cost</dt><dd>{fmtUsd(a.metrics.avg_cost_usd)}</dd></dl></div>
    {a.recent_executions?.length > 0 && <div className="card pad small"><h3 style={{ marginBottom: 6 }}>Recent executions</h3>{a.recent_executions.map((e: any) => <div key={e.id} className="row between" style={{ padding: "3px 0" }}><span>{e.project_name}: {e.output_summary}</span><span className="dim">{timeAgo(e.started_at)}</span></div>)}</div>}
  </div>}</Drawer>;
}

function CustomAgent({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ name: "", description: "", role: "", capabilities: "", system_instructions: "", model_tier: "strong", cost_limit_usd: 1 });
  const toast = useToast();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api("/api/agents/custom", { method: "POST", body: { ...f, role: f.role || null, capabilities: f.capabilities.split(",").map((x) => x.trim()).filter(Boolean) } });
      toast("Agent created (disabled). Test it, then enable it."); onDone();
    } catch (e: any) { toast(e.message, true); }
  };
  return <Modal title="Create custom agent" onClose={onClose}><form className="stack" onSubmit={submit}>
    <label className="field">Name<input className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Video Editor Agent" /></label>
    <label className="field">Description<input className="input" required value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></label>
    <label className="field">Role (optional, to make it routable)<input className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} placeholder="video_editor" /></label>
    <label className="field">Capabilities (comma separated)<input className="input" value={f.capabilities} onChange={(e) => setF({ ...f, capabilities: e.target.value })} /></label>
    <label className="field">System instructions<textarea className="textarea" required minLength={10} value={f.system_instructions} onChange={(e) => setF({ ...f, system_instructions: e.target.value })} /></label>
    <div className="row"><label className="field" style={{ flex: 1 }}>Model tier<select className="select" value={f.model_tier} onChange={(e) => setF({ ...f, model_tier: e.target.value })}><option>fast</option><option>strong</option><option>code</option></select></label>
      <label className="field" style={{ flex: 1 }}>Cost limit (USD)<input className="input" type="number" min={0} step={0.5} value={f.cost_limit_usd} onChange={(e) => setF({ ...f, cost_limit_usd: Number(e.target.value) })} /></label></div>
    <div className="small muted">Prompt agents get READ_PROJECT + WRITE_ARTIFACT only. Deploy/execute permissions are never granted to prompt agents.</div>
    <button className="btn primary">Create agent</button>
  </form></Modal>;
}
