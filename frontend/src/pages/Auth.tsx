import { useState } from "react";
import { api, setToken } from "../api";

export function AuthPage({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const body = mode === "signup" ? form : { email: form.email, password: form.password };
      const r = await api<{ token: string }>(`/api/auth/${mode}`, { method: "POST", body });
      setToken(r.token);
      onAuthed();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return <div className="auth-wrap">
    <div style={{ display: "grid", gap: 26, justifyItems: "center", width: "100%" }}>
      <div style={{ textAlign: "center", maxWidth: 640 }}>
        <h1 style={{ fontSize: "clamp(28px,5vw,44px)", lineHeight: 1.1 }}>Describe your idea.<br /><span style={{ background: "linear-gradient(90deg,#8b7cff,#b18cff)", WebkitBackgroundClip: "text", color: "transparent" }}>Our AI team builds it.</span></h1>
        <p className="muted" style={{ fontSize: 15 }}>AgencyOS interviews you, plans the work, and coordinates specialist agents — designers, developers, QA and security — with your approval at every milestone.</p>
        <div className="steps6">{["Describe", "Clarify", "Plan", "Build", "Test", "Launch"].map((s, i) => <div key={s}><b>{i + 1}</b>{s}</div>)}</div>
      </div>
      <form className="card auth-card stack" onSubmit={submit}>
        <h2 style={{ fontSize: 20 }}>{mode === "signup" ? "Create your workspace" : "Welcome back"}</h2>
        {mode === "signup" && <label className="field">Name<input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoComplete="name" /></label>}
        <label className="field">Email<input className="input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} autoComplete="email" /></label>
        <label className="field">Password<input className="input" type="password" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete={mode === "signup" ? "new-password" : "current-password"} /></label>
        {err && <div className="badge b-red" style={{ padding: "8px 12px", borderRadius: 8 }} role="alert">{err}</div>}
        <button className="btn primary" disabled={busy}>{busy ? "Please wait…" : mode === "signup" ? "Start building" : "Sign in"}</button>
        <button type="button" className="btn ghost" onClick={() => { setMode(mode === "signup" ? "login" : "signup"); setErr(null); }}>
          {mode === "signup" ? "I already have an account" : "Create a new account"}</button>
      </form>
    </div>
  </div>;
}
