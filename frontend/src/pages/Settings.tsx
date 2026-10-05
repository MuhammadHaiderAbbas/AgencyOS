import { useEffect, useState } from "react";
import { LuDownload, LuKey, LuServerCog, LuMail, LuGithub, LuCreditCard, LuRocket, LuUsers, LuGift, LuExternalLink, LuRefreshCw, LuCopy, LuCheck, LuTriangleAlert } from "react-icons/lu";
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
  const github = typeof integ.github === "object" ? integ.github : { configured: !!integ.github, note: "GitHub" };
  const email = typeof integ.email === "object" ? integ.email : { configured: !!integ.email };
  const stripe = typeof integ.stripe === "object" ? integ.stripe : { configured: !!integ.stripe };
  return <div className="stack">
    <div className="page-title"><h1>Settings</h1><span className="small muted">All integrations earning-ready — add keys to activate real payments & emails; mock mode works without them.</span></div>
    <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))" }}>
      <div className="card pad stack"><h3><LuKey /> AI providers</h3>
        <div className="small">Active: <b>{data.llm.is_mock ? "Local deterministic mode (no LLM)" : `${data.llm.provider} — fast: ${data.llm.models.fast}, strong: ${data.llm.models.strong}`}</b></div>
        <div className="small muted">Without a key, agents run rule-based implementations labelled “local”. Add a key for model language work; outputs are schema-validated with deterministic fallback.</div>
        <label className="field">Provider<select className="select" disabled={!canEdit} value={prov || data.provider_preference} onChange={(e) => setProv(e.target.value)}>
          <option value="auto">Auto (Anthropic → OpenAI → local)</option><option value="anthropic">Anthropic</option><option value="openai">OpenAI</option><option value="mock">Local only</option></select></label>
        {(["anthropic", "openai"] as const).map((k) => <div key={k} className="field"><span style={{ textTransform: "capitalize" }}>{k} API key</span>
          <div className="row"><input className="input" type="password" autoComplete="off" disabled={!canEdit} placeholder={data.keys[k].org ? `Stored: ${data.keys[k].masked}` : data.keys[k].env ? "Using server environment key" : "Not set"}
            value={k === "anthropic" ? akey : okey} onChange={(e) => (k === "anthropic" ? setAkey : setOkey)(e.target.value)} />
            {data.keys[k].org && canEdit && <button className="btn sm" onClick={() => removeKey(`${k}_api_key` as any)}>Remove</button>}</div></div>)}
        {canEdit ? <button className="btn primary" onClick={save}>Save</button> : <div className="small muted">Only owners/admins can change providers.</div>}
        <div className="tiny dim">Keys encrypted at rest, never sent to browser, prompts or exports.</div>
      </div>

      <div className="card pad stack"><h3><LuRocket /> Integrations — earning</h3>
        <div className="row between"><div><b className="small">Web search (Tavily)</b><div className="tiny dim">Set TAVILY_API_KEY — powers Researcher agent</div></div><span className={`badge ${integ.web_search ? "b-green" : "b-gray"}`}>{integ.web_search ? "connected" : "not configured"}</span></div>
        <div className="row between"><div><b className="small">Docker sandbox</b><div className="tiny dim">Run imported 500-agents safely</div></div><span className={`badge ${integ.docker_sandbox ? "b-green" : "b-gray"}`}>{integ.docker_sandbox ? "ready" : "not available"}</span></div>
        <div className="row between"><div><b className="small">External agents</b><div className="tiny dim">AGENCYOS_ENABLE_EXTERNAL_AGENTS</div></div><span className={`badge ${integ.external_agents_enabled ? "b-green" : "b-gray"}`}>{integ.external_agents_enabled ? "enabled" : "disabled"}</span></div>
        <div className="row between" style={{ padding: "8px", background: github.configured ? "rgba(34,197,94,.08)" : "rgba(239,68,68,.05)", borderRadius: 10, border: `1px solid ${github.configured ? "#22c55e33" : "#1d2756"}` }}>
          <div><b className="small"><LuGithub /> GitHub</b><div className="tiny dim">{github.configured ? github.note || "Ready to push" : "Set GITHUB_TOKEN (PAT) — pushes local git to GitHub; otherwise local history kept"}</div></div>
          <span className={`badge ${github.configured ? "b-green" : "b-gray"}`}>{github.configured ? "connected" : "local only"}</span>
        </div>
        <div className="row between" style={{ padding: "8px", background: email.configured ? "rgba(34,197,94,.08)" : "rgba(245,158,11,.07)", borderRadius: 10, border: `1px solid ${email.configured ? "#22c55e33" : "#f59e0b33"}` }}>
          <div><b className="small"><LuMail /> Email (SMTP)</b><div className="tiny dim">{email.configured ? `From ${email.from} — real booking & enquiry emails` : "Set SMTP_HOST/PORT/USER/PASSWORD/FROM — mock logs until then (in-app notifications still work)"}</div></div>
          <span className={`badge ${email.configured ? "b-green" : "b-orange"}`}>{email.configured ? "connected" : "mock mode"}</span>
        </div>
        <div className="row between" style={{ padding: "8px", background: stripe.configured ? "rgba(34,197,94,.08)" : "rgba(109,94,252,.08)", borderRadius: 10, border: `1px solid ${stripe.configured ? "#22c55e33" : "#6d5efc33"}` }}>
          <div><b className="small"><LuCreditCard /> Stripe (billing + client checkout)</b><div className="tiny dim">{stripe.configured ? `Live payments — publishable ${stripe.publishable_key ? "set" : "missing"} — pro/business price ${stripe.price_pro && stripe.price_business ? "set" : "add STRIPE_PRICE_* to enable paid plans"} ` : "Demo earning: instant upgrades, mock client checkout — add STRIPE_SECRET_KEY for real cards"}</div></div>
          <span className={`badge ${stripe.configured ? "b-green" : "b-purple"}`}>{stripe.configured ? "live" : "demo earning"}</span>
        </div>
        <div className="tiny dim">Mock mode keeps whole site working & earning demo without keys. Add keys in <code>.env</code> or server env, restart — no code change.</div>
        <h3 style={{ marginTop: 8 }}>Deployment targets</h3>
        {integ.deployment.map((d: any) => <div key={d.name} className="row between small"><span>{d.name}</span><span className={`badge ${d.configured ? "b-green" : "b-gray"}`}>{d.configured ? "ready" : d.note ? "interface only" : "not configured"}</span></div>)}
      </div>

      <div className="card pad stack"><h3>Safety limits</h3>
        <dl className="kv small"><dt>Task retries</dt><dd>{data.limits.max_task_retries}</dd><dt>Revision rounds</dt><dd>{data.limits.max_revisions}</dd>
          <dt>Executions / project</dt><dd>{data.limits.max_project_executions}</dd><dt>Budget / project</dt><dd>{fmtUsd(data.limits.max_project_budget_usd)}</dd></dl>
        <div className="tiny dim">Via env `AGENCYOS_*` (see .env.example). Prevents loops & runaway cost. Billing plan also enforces project/execution caps.</div>
        <div className="card pad small" style={{ background: "rgba(109,94,252,.08)", borderColor: "#6d5efc33" }}><b>Earning tip:</b> <span className="small muted">Upgrade client sites to Business to unlock GitHub push + SMTP + Vercel — hottest earning combo. Track referrals in Billing.</span></div>
      </div>

      <div className="card pad stack"><h3>Privacy & account</h3>
        <div className="small">Signed in as <b>{me.user.email}</b> ({me.user.org_role}{me.user.is_admin ? ", platform admin" : ""})</div>
        <a className="btn" href="/api/auth/export" onClick={async (e) => { e.preventDefault(); const r = await api("/api/auth/export"); const b = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" }); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "agencyos-export.json"; a.click(); }}><LuDownload /> Export my data</a>
        <button className="btn danger" onClick={() => setDel(true)}>Delete account</button>
        <div className="tiny dim">Base URL: <code>{data.base_url}</code> — used for Stripe success/cancel redirects & OAuth.</div>
      </div>
    </div>
    {me.user.is_admin && <Observability />}
    {del && <Modal title="Delete account" onClose={() => setDel(false)}>
      <p className="small">Deletes your account and every workspace you own, including projects, files and deployments. Type your email to confirm.</p>
      <input className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-label="Email" />
      <div className="row" style={{ marginTop: 12 }}><button className="btn danger" disabled={confirm !== me.user.email} onClick={async () => { await api("/api/auth/me", { method: "DELETE", body: { confirm } }); setToken(null); location.reload(); }}>Delete my account</button></div>
    </Modal>}
  </div>;
}

function Observability() {
  const { data, reload } = useApi<any>("/api/admin/observability");
  if (!data) return <Loading />;
  return <div className="card pad stack">
    <div className="row between"><h3><LuServerCog /> Platform observability (admin)</h3><button className="btn sm" onClick={reload}><LuRefreshCw /> Refresh</button></div>
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
  const { data, reload } = useApi<any>("/api/billing");
  const [busy, setBusy] = useState<string | null>(null);
  const [refer, setRefer] = useState<any>(null);
  const toast = useToast();
  useEffect(() => { api<any>("/api/referrals").then(setRefer).catch(()=>{}); const q = new URLSearchParams(location.hash.split("?")[1]||"");
    if(q.get("mock_checkout")==="success"||q.get("checkout")==="success"){ toast(`Plan upgraded to ${q.get("plan")||"pro"} — earning unlocked!`); reload(); history.replaceState(null,"",location.pathname+location.hash.split("?")[0]);}
    if(q.get("checkout")==="cancel") toast("Checkout cancelled.", true);
  }, []);
  if (!data) return <Loading />;
  const plan = data.plans.find((p: any) => p.id === data.plan);
  const isStripeLive = data.payment_provider.configured;
  const goCheckout = async (planId:string) => {
    setBusy(planId);
    try{
      const res:any = await api("/api/billing/checkout",{method:"POST",body:{plan:planId}});
      if(res.url){
        if(res.mock){
          toast(`Upgraded to ${planId} — demo earning (add Stripe for real charges)`);
          reload();
        } else {
          location.href=res.url;
        }
      }
    } catch(e:any){ toast(e.message,true); } finally { setBusy(null); }
  };
  const goPortal = async () => {
    setBusy("portal");
    try{ const r:any = await api("/api/billing/portal",{method:"POST"}); if(r.url) location.href=r.url; } catch(e:any){ toast(e.message,true);} finally{ setBusy(null); }
  };
  const downgrade = async () => {
    if(!confirm("Downgrade to Free? You keep data but hit limits.")) return;
    setBusy("free"); try{ await api("/api/billing/downgrade",{method:"POST",body:{plan:"free"}}); toast("Downgraded to Free"); reload(); } catch(e:any){toast(e.message,true)} finally{setBusy(null)}
  };
  return <div className="stack">
    <div className="page-title"><h1>Billing & Earning</h1><span className="badge b-purple">Current plan: {plan?.name}</span></div>
    <div className={`card pad small ${isStripeLive?"":""}`} style={{ borderColor: isStripeLive?"#22c55e66":"#6d5efc66", background: isStripeLive?"rgba(34,197,94,.07)":"rgba(109,94,252,.07)" }}>
      <div className="row" style={{ gap:8 }}><LuCreditCard /> <b>{isStripeLive?"Stripe live — real charges":"Demo earning mode — instant, no card"}</b> <span className={`badge ${isStripeLive?"b-green":"b-purple"}`}>{isStripeLive?"LIVE":"DEMO"}</span></div>
      <div className="small muted" style={{ marginTop:6 }}>{data.payment_provider.note} {isStripeLive?"Add STRIPE_PRICE_PRO/BUSINESS env to enable Pro/Business buy buttons.":"You can still earn: client sites generate mock checkout URLs that work end-to-end for demos; add Stripe keys + prices to charge real money."}</div>
      {plan?.id!=="free" && <div className="row" style={{ marginTop:8 }}><button className="btn sm" onClick={goPortal} disabled={busy==="portal"}>{busy==="portal"?"...":"Manage subscription via Stripe portal"} <LuExternalLink /></button><button className="btn sm" onClick={downgrade} disabled={busy==="free"}>Downgrade to Free</button></div>}
    </div>
    {/* earning summary */}
    <div className="grid" style={{ gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))" }}>
      <div className="card pad"><div className="row between"><h3><LuRocket /> Platform earnings</h3><LuGift /></div>
        <div style={{ fontSize:22,fontWeight:700 }}>{fmtUsd((data.earnings?.total_cents||0)/100)}</div><div className="small muted">{data.earnings?.count||0} earnings events · referrals + client payments you record via <code>/api/earnings</code></div>
        {data.earnings?.recent?.length>0 && <div className="stack" style={{ marginTop:8 }}>{data.earnings.recent.slice(0,3).map((e:any)=><div key={e.id} className="small row between"><span><span className="badge b-gray">{e.source}</span> {e.description}</span><b>{fmtUsd(e.amount_cents/100)}</b></div>)}</div>}
      </div>
      <div className="card pad stack"><h3><LuUsers /> Refer & earn</h3>
        {refer ? <>
          <div className="small muted">Share your link — when a referred org upgrades, you get credited automatically.</div>
          <div className="row"><input className="input" readOnly value={refer.link} onFocus={e=>e.currentTarget.select()} /><button className="btn sm" onClick={()=>{navigator.clipboard.writeText(refer.link); toast("Copied referral link");}}><LuCopy /> Copy</button></div>
          <div className="small">Code <code>{refer.code}</code> · {refer.referrals.length} referrals · {refer.reward}</div>
          {refer.referrals.length>0 && <div className="small">{refer.referrals.map((r:any)=><div key={r.id} className="row between"><span>{r.referred_org_id.slice(0,8)} — {r.status}</span><span className="badge b-green">{fmtUsd(r.reward_cents/100)}</span></div>)}</div>}
        </> : <div className="small muted">Loading referral info…</div>}
      </div>
    </div>
    <div className="stats" style={{ margin: 0 }}>{[["Projects", data.usage.projects, plan?.limits.projects], ["Agent executions", data.usage.agent_executions, plan?.limits.agent_executions],
      ["LLM tokens", data.usage.llm_tokens], ["LLM cost", fmtUsd(data.usage.llm_cost_usd)], ["Storage", `${data.usage.storage_mb} MB`, plan?.limits.storage_mb ? `${plan.limits.storage_mb} MB` : undefined]].map(([l, v, lim]: any) =>
      <div key={l} className="card stat"><div className="v">{v}</div><div className="l">{l}{lim ? ` / ${lim}` : ""} · {data.period}</div></div>)}</div>
    <div className="card small pad" style={{ display:"flex", gap:10, alignItems:"center", flexWrap:"wrap", background:"rgba(245,158,11,.07)", borderColor:"#f59e0b44" }}><LuTriangleAlert color="#f59e0b" /> <span>When you hit a limit, project creation returns 402 — upgrade instantly (mock) or via Stripe (live). All limits are enforced server-side in <code>/api/projects</code>.</span></div>
    <div className="projects-grid">{data.plans.map((p: any) => {
      const isCurrent = p.id === data.plan;
      const canBuy = (p.id==="pro"||p.id==="business") && (p.has_price ?? true);
      const locked = !canBuy && (p.id==="pro"||p.id==="business") && isStripeLive;
      return <div key={p.id} className={`card pad stack ${isCurrent ? "approval" : ""}`} style={{ borderColor: isCurrent?"#6d5efc":undefined }}>
      <div className="row between"><b style={{ fontSize: 16 }}>{p.name}</b>{isCurrent && <span className="badge b-green">current</span>}{p.id!=="free" && p.id!=="enterprise" && !isStripeLive && <span className="badge b-purple">demo buy</span>}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{p.price}</div>
      <ul className="small muted" style={{ paddingLeft: 18, margin: 0 }}>{Object.entries(p.limits).map(([k, v]: any) => <li key={k}>{v.toLocaleString()} {k.replace(/_/g, " ")}</li>)}{!Object.keys(p.limits).length && <li>Custom limits, SSO, dedicated sandboxes</li>}
        {p.features?.map((f:string)=><li key={f} style={{ color: isCurrent?"var(--text)":undefined }}>{f}</li>)}
      </ul>
      {isCurrent ? <button className="btn sm" disabled>Current plan</button>
        : p.id==="enterprise" ? <a className="btn sm primary" href="mailto:hello@agencyos.local?subject=Enterprise">Contact us</a>
        : locked ? <button className="btn sm" disabled title="Set STRIPE_PRICE_* env to enable this plan">Requires Stripe price</button>
        : <button className="btn sm primary" disabled={busy===p.id} onClick={()=>goCheckout(p.id)}>{busy===p.id?"Redirecting...": isStripeLive? `Upgrade to ${p.name} → Stripe` : `Upgrade to ${p.name} (instant demo)`}</button>}
      {!isCurrent && p.id!=="enterprise" && <div className="tiny dim">{isStripeLive? "You’ll be redirected to Stripe Checkout (secure).":"No card — updates locally so you can demo earning end-to-end."}</div>}
    </div>;})}</div>
    {data.billing_history?.length>0 && <div className="card pad"><h3>Billing history</h3><table className="table"><thead><tr><th>When</th><th>Kind</th><th>Plan</th><th>Amount</th><th>Status</th></tr></thead><tbody>{data.billing_history.map((b:any)=><tr key={b.id}><td className="small dim">{timeAgo(b.created_at)}</td><td className="small">{b.kind}</td><td>{b.plan||"—"}</td><td>{fmtUsd((b.amount_cents||0)/100)}</td><td><Status s={b.status.toUpperCase()} /></td></tr>)}</tbody></table></div>}
    <div className="card pad small" style={{ background:"linear-gradient(135deg, #6d5efc11, #22d3ee11)", borderColor:"#6d5efc33" }}><b>How to earn with AgencyOS today:</b><ol style={{ margin:"6px 0 0 18px" }}><li><b>Platform:</b> Upgrade to Pro/Business (mock instant, live Stripe) — unlock more projects & deploys you sell to clients.</li><li><b>Client sites:</b> Every hotel/ecommerce site your agents build now includes Stripe Checkout (real when <code>STRIPE_SECRET_KEY</code> set in generated <code>source/api/.env</code>, mock otherwise), newsletter list building, and SEO — so bookings/orders convert.</li><li><b>Referrals:</b> Copy your link above — each upgrade credits £5/£15 earnings you see here. Pay out via manual.</li><li><b>Deploy & deliver:</b> Finish a project → Deliverables → Deploy (local/Netlify/Vercel/Render) → hand client the live URL + API; they pay you.</li></ol></div>
  </div>;
}
