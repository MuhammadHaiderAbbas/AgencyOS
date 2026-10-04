import { useState } from "react";
import { LuDownload, LuKey, LuServerCog } from "react-icons/lu";
import { api, setToken, timeAgo } from "../api";
import { useMe } from "../main";
import { Loading, Modal, Status, fmtUsd, useApi, useToast } from "../ui";

export function SettingsPage() {
  const { me, refreshMe } = useMe();
  const { data, reload } = useApi<any>("/api/settings");
  const toast = useToast();
  const [prov, setProv] = useState<string | null>(null);
  const [akey, setAkey] = useState("");
  const [okey, setOkey] = useState("");
  const [del, setDel] = useState(false);
  const [confirm, setConfirm] = useState("");
  if (!data) return <Loading />;
  const canEdit = ["owner", "admin"].includes(data.role);
  const save = async () => {
    try {
      const body: any = { provider: prov || data.provider_preference };
      if (akey) body.anthropic_api_key = akey;
      if (okey) body.openai_api_key = okey;
      await api("/api/settings/providers", { method: "PUT", body });
      setAkey(""); setOkey(""); toast("AI provider settings saved (keys encrypted server-side)"); reload(); refreshMe();
    } catch (e: any) { toast(e.message, true); }
  };
  const removeKey = async (which: "anthropic_api_key" | "openai_api_key") => {
    await api("/api/settings/providers", { method: "PUT", body: { provider: data.provider_preference, [which]: "" } }); reload(); refreshMe();
  };
  const integ = data.integrations;
  return <div className="stack">
    <div className="page-title"><h1>Settings</h1></div>
    <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))" }}>
      <div className="card pad stack"><h3><LuKey /> AI providers</h3>
        <div className="small">Active: <b>{data.llm.is_mock ? "Local deterministic mode (no LLM)" : `${data.llm.provider} — fast: ${data.llm.models.fast}, strong: ${data.llm.models.strong}`}</b></div>
        <div className="small muted">Without a key, agents run their rule-based implementations and every execution is labelled “local”. Add a key to let agents use a model; outputs are still schema-validated with a deterministic fallback.</div>
        <label className="field">Provider<select className="select" disabled={!canEdit} value={prov || data.provider_preference} onChange={(e) => setProv(e.target.value)}>
          <option value="auto">Auto (Anthropic → OpenAI → local)</option><option value="anthropic">Anthropic</option><option value="openai">OpenAI</option><option value="mock">Local only</option></select></label>
        {(["anthropic", "openai"] as const).map((k) => <div key={k} className="field"><span style={{ textTransform: "capitalize" }}>{k} API key</span>
          <div className="row"><input className="input" type="password" autoComplete="off" disabled={!canEdit} placeholder={data.keys[k].org ? `Stored: ${data.keys[k].masked}` : data.keys[k].env ? "Using server environment key" : "Not set"}
            value={k === "anthropic" ? akey : okey} onChange={(e) => (k === "anthropic" ? setAkey : setOkey)(e.target.value)} />
            {data.keys[k].org && canEdit && <button className="btn sm" onClick={() => removeKey(`${k}_api_key` as any)}>Remove</button>}</div></div>)}
        {canEdit ? <button className="btn primary" onClick={save}>Save</button> : <div className="small muted">Only owners/admins can change providers.</div>}
        <div className="tiny dim">Keys are encrypted at rest and never sent to the browser, agents' prompts or exports.</div>
      </div>
      <div className="card pad stack"><h3>Integrations</h3>
        {[["Web search (Tavily)", integ.web_search, "Set TAVILY_API_KEY on the server"], ["Docker sandbox", integ.docker_sandbox, "Required to run imported third-party agents"],
          ["External agents", integ.external_agents_enabled, "AGENCYOS_ENABLE_EXTERNAL_AGENTS"], ["GitHub", integ.github, "OAuth app not configured — projects keep a local git history"],
          ["Email notifications", integ.email, "SMTP not configured — in-app notifications only"], ["Stripe (billing)", integ.stripe, "Not configured"]].map(([n, ok, hint]: any) =>
          <div key={n} className="row between"><div><b className="small">{n}</b><div className="tiny dim">{hint}</div></div><span className={`badge ${ok ? "b-green" : "b-gray"}`}>{ok ? "connected" : "not configured"}</span></div>)}
        <h3 style={{ marginTop: 8 }}>Deployment targets</h3>
        {integ.deployment.map((d: any) => <div key={d.name} className="row between small"><span>{d.name}</span><span className={`badge ${d.configured ? "b-green" : "b-gray"}`}>{d.configured ? "ready" : d.note ? "interface only" : "not configured"}</span></div>)}
      </div>
      <div className="card pad stack"><h3>Safety limits</h3>
        <dl className="kv small"><dt>Task retries</dt><dd>{data.limits.max_task_retries}</dd><dt>Revision rounds</dt><dd>{data.limits.max_revisions}</dd>
          <dt>Executions / project</dt><dd>{data.limits.max_project_executions}</dd><dt>Budget / project</dt><dd>{fmtUsd(data.limits.max_project_budget_usd)}</dd></dl>
        <div className="tiny dim">Configured via environment variables (see .env.example). Prevents agent loops, ping-pong and runaway cost.</div></div>
      <div className="card pad stack"><h3>Privacy & account</h3>
        <div className="small">Signed in as <b>{me.user.email}</b> ({me.user.org_role}{me.user.is_admin ? ", platform admin" : ""})</div>
        <a className="btn" href="/api/auth/export" onClick={async (e) => { e.preventDefault(); const r = await api("/api/auth/export"); const b = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" }); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "agencyos-export.json"; a.click(); }}><LuDownload /> Export my data</a>
        <button className="btn danger" onClick={() => setDel(true)}>Delete account</button></div>
    </div>
    {me.user.is_admin && <Observability />}
    {del && <Modal title="Delete account" onClose={() => setDel(false)}>
      <p className="small">This deletes your account and every workspace you own, including projects, files and deployments. Type your email to confirm.</p>
      <input className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-label="Email" />
      <div className="row" style={{ marginTop: 12 }}><button className="btn danger" disabled={confirm !== me.user.email} onClick={async () => { await api("/api/auth/me", { method: "DELETE", body: { confirm } }); setToken(null); location.reload(); }}>Delete my account</button></div>
    </Modal>}
  </div>;
}

function Observability() {
  const { data, reload } = useApi<any>("/api/admin/observability");
  if (!data) return <Loading />;
  return <div className="card pad stack">
    <div className="row between"><h3><LuServerCog /> Platform observability (admin)</h3><button className="btn sm" onClick={reload}>Refresh</button></div>
    <div className="stats" style={{ margin: 0 }}>{[["Executions 24h", data.executions_24h], ["Failures 24h", data.failed_24h], ["Avg latency", `${data.avg_latency_ms} ms`], ["Tokens 24h", data.tokens_24h],
      ["Queue", `${data.queue.queue} queued · ${data.queue.workers} workers`]].map(([l, v]) => <div key={l} className="card stat"><div className="v" style={{ fontSize: 18 }}>{v}</div><div className="l">{l}</div></div>)}</div>
    <div className="row wrap small"><span>Database: <Status s={data.database.healthy ? "HEALTHY" : "BROKEN"} /> {data.database.engine}</span><span>Redis: <span className="badge b-gray">not used</span> <span className="dim">{data.redis.note}</span></span>
      <span>Docker sandbox: <Status s={data.docker_sandbox ? "HEALTHY" : "WARNING"} /></span></div>
    {data.llm_calls_by_provider.length > 0 && <table className="table"><thead><tr><th>Provider</th><th>Model</th><th>Calls</th><th>Tokens</th><th>Cost</th></tr></thead><tbody>{data.llm_calls_by_provider.map((r: any, i: number) =>
      <tr key={i}><td>{r.provider}</td><td>{r.model}</td><td>{r.calls}</td><td>{r.tokens}</td><td>{fmtUsd(r.cost)}</td></tr>)}</tbody></table>}
    <h3>Recent agent errors</h3>{data.recent_errors.length === 0 ? <div className="small muted">None</div> : data.recent_errors.map((e: any) => <div key={e.id} className="small"><b>{e.role}</b> in {e.project_name}: <span className="muted">{String(e.errors).slice(0, 200)}</span> <span className="dim">{timeAgo(e.started_at)}</span></div>)}
    <h3>Audit log</h3>{data.audit.map((a: any) => <div key={a.id} className="small"><code>{a.action}</code> {a.target && <span className="dim">{a.target}</span>} {a.detail && <span className="muted">— {a.detail}</span>} <span className="dim">{timeAgo(a.created_at)}</span></div>)}
  </div>;
}

export function BillingPage() {
  const { data } = useApi<any>("/api/billing");
  if (!data) return <Loading />;
  const plan = data.plans.find((p: any) => p.id === data.plan);
  return <div className="stack">
    <div className="page-title"><h1>Billing</h1><span className="badge b-purple">Current plan: {plan?.name}</span></div>
    <div className="card pad small" style={{ borderColor: "#7c5a10" }}>{data.payment_provider.note}</div>
    <div className="stats" style={{ margin: 0 }}>{[["Projects", data.usage.projects, plan?.limits.projects], ["Agent executions", data.usage.agent_executions, plan?.limits.agent_executions],
      ["LLM tokens", data.usage.llm_tokens], ["LLM cost", fmtUsd(data.usage.llm_cost_usd)], ["Storage", `${data.usage.storage_mb} MB`, plan?.limits.storage_mb ? `${plan.limits.storage_mb} MB` : undefined]].map(([l, v, lim]: any) =>
      <div key={l} className="card stat"><div className="v">{v}</div><div className="l">{l}{lim ? ` / ${lim}` : ""} · {data.period}</div></div>)}</div>
    <div className="projects-grid">{data.plans.map((p: any) => <div key={p.id} className={`card pad stack ${p.id === data.plan ? "approval" : ""}`}>
      <div className="row between"><b style={{ fontSize: 16 }}>{p.name}</b>{p.id === data.plan && <span className="badge b-green">current</span>}</div><div style={{ fontSize: 22, fontWeight: 700 }}>{p.price}</div>
      <ul className="small muted" style={{ paddingLeft: 18, margin: 0 }}>{Object.entries(p.limits).map(([k, v]: any) => <li key={k}>{v.toLocaleString()} {k.replace(/_/g, " ")}</li>)}{!Object.keys(p.limits).length && <li>Custom limits, SSO, dedicated sandboxes</li>}</ul>
      <button className="btn sm" disabled title="No payment provider configured">{p.id === data.plan ? "Current plan" : "Upgrade unavailable"}</button></div>)}</div>
  </div>;
}
