import { useEffect, useState, useRef } from "react"
import { api } from "./api"

type Msg = { role: string; content: string }
type Conv = { id:string; title:string }

export default function App(){
  const [user,setUser]=useState<any>(null)
  const [authMode,setAuthMode]=useState<"login"|"signup">("login")
  const [email,setEmail]=useState("demo@jarvis.local")
  const [password,setPassword]=useState("jarvis123")
  const [displayName,setDisplayName]=useState("Alex")
  const [status,setStatus]=useState<any>(null)
  const [sys,setSys]=useState<any>(null)
  const [conversations,setConversations]=useState<Conv[]>([])
  const [activeConv,setActiveConv]=useState<string|null>(null)
  const [messages,setMessages]=useState<Msg[]>([])
  const [input,setInput]=useState("")
  const [tools,setTools]=useState<any[]>([])
  const [agents,setAgents]=useState<any[]>([])
  const [approvals,setApprovals]=useState<any[]>([])
  const [busy,setBusy]=useState(false)
  const [listening,setListening]=useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  const logged = !!user

  async function refresh(){
    try{
      const h = await api.health(); setStatus(h)
      const s = await api.systemStatus().catch(()=>null); if(s) setSys(s)
      const t = await api.tools().catch(()=>null); if(t) setTools(t.tools||[])
      const a = await api.agents().catch(()=>null); if(a) setAgents(a.agents||[])
      const ap = await api.approvals().catch(()=>null); if(ap) setApprovals(ap.approvals||[])
      const convs = await api.conversations().catch(()=>null); if(convs) setConversations(convs.conversations||[])
    }catch{}
  }

  async function loadMe(){
    try{ const r=await api.me(); setUser(r.user); refresh(); if(r.user) loadConvs() }catch{}
  }
  async function loadConvs(){
    try{ const r=await api.conversations(); setConversations(r.conversations||[]) }catch{}
  }
  async function loadMessages(cid:string){
    try{ const r=await api.conversation(cid); setMessages(r.messages||[]); setActiveConv(cid)}catch{}
  }

  useEffect(()=>{ loadMe(); const id=setInterval(()=>{ if(user) refresh()}, 7000); return ()=>clearInterval(id)},[user])
  useEffect(()=>{ endRef.current?.scrollIntoView({behavior:"smooth"})},[messages])

  async function doAuth(){
    try{
      const r = authMode==="signup" ? await api.signup(email,password,displayName) : await api.login(email,password)
      setUser(r.user); refresh(); loadConvs()
    }catch(e:any){ alert(e.message)}
  }

  async function send(msg?:string){
    const text = msg || input
    if(!text.trim()) return
    setInput("")
    const userMsg: Msg = {role:"user", content:text}
    setMessages(m=>[...m,userMsg])
    setBusy(true)
    try{
      const r = await api.chat(text, activeConv||undefined)
      if(!activeConv && r.conversation_id){ setActiveConv(r.conversation_id); loadConvs() }
      setMessages(m=>[...m, {role:"assistant", content: r.message.content}])
      refresh()
    }catch(e:any){
      setMessages(m=>[...m,{role:"assistant", content: "Error: "+e.message}])
    }finally{ setBusy(false)}
  }

  async function quickSystem(){
    try{ const s=await api.systemStatus(); setSys(s); send("What's using the most RAM?")}catch{}
  }

  // voice stub — uses Web Speech API if available
  function toggleVoice(){
    const SR = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
    if(!SR){ alert("Voice not supported in this browser. Use Chrome."); return}
    if(listening){ setListening(false); return}
    const rec = new SR()
    rec.lang="en-US"; rec.interimResults=false
    rec.onstart=()=>setListening(true)
    rec.onend=()=>setListening(false)
    rec.onresult=(e:any)=>{ const t=e.results[0][0].transcript; setInput(t); send(t)}
    rec.start()
  }

  if(!logged){
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="glass p-8 w-full max-w-md">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-400 to-indigo-500 grid place-items-center font-bold">J</div>
            <div>
              <h1 className="text-xl font-semibold leading-none">JARVIS</h1>
              <p className="text-xs text-zinc-400">Just Another Rather Very Intelligent System</p>
            </div>
            <span className="ml-auto text-xs px-2 py-1 rounded-full bg-white/10 border border-white/10">v0.1.0 — Phase 1</span>
          </div>

          <div className="flex gap-2 mb-4">
            <button onClick={()=>setAuthMode("login")} className={`flex-1 py-2 rounded-xl text-sm ${authMode==="login"?"bg-white text-black":"bg-white/10"}`}>Login</button>
            <button onClick={()=>setAuthMode("signup")} className={`flex-1 py-2 rounded-xl text-sm ${authMode==="signup"?"bg-white text-black":"bg-white/10"}`}>Sign up</button>
          </div>

          <div className="space-y-3">
            <input value={email} onChange={e=>setEmail(e.target.value)} placeholder="email" className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none focus:border-cyan-400/50" />
            {authMode==="signup" && <input value={displayName} onChange={e=>setDisplayName(e.target.value)} placeholder="display name" className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none" />}
            <input value={password} onChange={e=>setPassword(e.target.value)} type="password" placeholder="password" className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none" />
            <button onClick={doAuth} className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-400 to-indigo-500 text-black font-semibold">Continue →</button>
            <p className="text-xs text-zinc-500 text-center">First account becomes <b className="text-zinc-300">admin</b>. Try: demo@jarvis.local / jarvis123</p>
          </div>

          <div className="mt-6 grid grid-cols-3 gap-2 text-xs">
            <div className="glass p-3 text-center"><div className="text-zinc-400">Auth</div><div className="font-mono text-cyan-300">JWT + Cookie</div></div>
            <div className="glass p-3 text-center"><div className="text-zinc-400">Bus</div><div className="font-mono text-indigo-300">WS + SSE</div></div>
            <div className="glass p-3 text-center"><div className="text-zinc-400">DB</div><div className="font-mono text-emerald-300">{status?.db==="ok"?"Ready":"…"}</div></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-black/30 border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-4 h-[56px] flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-indigo-500 grid place-items-center font-bold text-sm">J</div>
          <div>
            <div className="font-semibold leading-none">JARVIS</div>
            <div className="text-xs text-zinc-400">Good evening, {user.display_name}.</div>
          </div>
          <div className="ml-6 hidden md:flex items-center gap-2 text-xs">
            <span className={`px-2 py-1 rounded-full border ${status?.status==="ok"?"bg-emerald-500/15 text-emerald-300 border-emerald-500/20":"bg-amber-500/15 text-amber-300 border-amber-500/20"}`}>● {status?.status||"…"}</span>
            <span className="px-2 py-1 rounded-full bg-white/5 border border-white/10">LLM: {status?.llm||"…"} </span>
            <span className="px-2 py-1 rounded-full bg-white/5 border border-white/10">Redis: {status?.redis||"…"}</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button onClick={()=>api.emergency()} className="text-xs px-3 py-1.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 hover:bg-red-500/30">Emergency Stop</button>
            <button onClick={async()=>{ await fetch("/api/v1/auth/logout",{method:"POST",credentials:"include"}); location.reload()}} className="text-xs px-3 py-1.5 rounded-full bg-white/10 border border-white/10">Logout</button>
          </div>
        </div>
      </header>

      <div className="max-w-[1400px] mx-auto p-4 grid grid-cols-12 gap-4">
        {/* Left — system + tasks */}
        <div className="col-span-12 lg:col-span-3 space-y-4">
          <div className="glass p-4">
            <div className="text-xs tracking-widest text-zinc-400 mb-3">SYSTEM</div>
            <div className="space-y-3 font-mono text-sm">
              <div className="flex justify-between"><span className="text-zinc-400">CPU</span><span className="text-cyan-300">{sys?.cpu?.cpu_percent ?? "—"}%</span></div>
              <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-cyan-400 to-indigo-500 rounded-full" style={{width: `${sys?.cpu?.cpu_percent ?? 21}%`}} /></div>
              <div className="flex justify-between"><span className="text-zinc-400">RAM</span><span className="text-indigo-300">{sys?.ram?.percent ?? "—"}%</span></div>
              <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden"><div className="h-full bg-indigo-500 rounded-full" style={{width: `${sys?.ram?.percent ?? 48}%`}} /></div>
              <div className="flex justify-between"><span className="text-zinc-400">DISK</span><span className="text-emerald-300">{sys?.ram ? sys?.disk?.percent : "—"}%</span></div>
              <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden"><div className="h-full bg-emerald-500 rounded-full" style={{width: `${sys?.disk?.percent ?? 62}%`}} /></div>
            </div>
            <button onClick={quickSystem} className="mt-4 w-full text-xs py-2 rounded-xl bg-white/10 border border-white/10 hover:bg-white/15">Diagnose</button>
          </div>

          <div className="glass p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs tracking-widest text-zinc-400">TODAY</div>
              <button onClick={()=>send("What's on my calendar today?")} className="text-xs text-cyan-300">Calendar</button>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex gap-3 p-2 rounded-xl bg-white/5 border border-white/5">
                <span className="text-cyan-300 font-mono text-xs">09:00</span><span>Standup — Teams</span>
              </div>
              <div className="flex gap-3 p-2 rounded-xl bg-white/5 border border-white/5">
                <span className="text-indigo-300 font-mono text-xs">12:00</span><span>Focus block</span>
              </div>
              <div className="flex gap-3 p-2 rounded-xl bg-white/5 border border-white/5 opacity-60">
                <span className="text-zinc-400 font-mono text-xs">16:00</span><span>Review</span>
              </div>
            </div>
          </div>

          <div className="glass p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs tracking-widest text-zinc-400">ACTIVE</div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/20">{approvals.length? `${approvals.length} pending`:"Idle"}</span>
            </div>
            {approvals.length? (
              <div className="space-y-2">
                {approvals.map((a:any)=>(
                  <div key={a.id} className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs">
                    <div className="font-medium">{a.tool}</div>
                    <div className="text-zinc-400 line-clamp-2">{a.what}</div>
                    <div className="flex gap-2 mt-2">
                      <button onClick={async()=>{ await api.approve(a.id,"granted"); refresh()}} className="flex-1 py-1.5 rounded-lg bg-emerald-500 text-black font-medium">Approve</button>
                      <button onClick={async()=>{ await api.approve(a.id,"denied"); refresh()}} className="flex-1 py-1.5 rounded-lg bg-white/10 border border-white/10">Deny</button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-zinc-500">No active approvals. System monitoring is quiet.</div>
            )}
          </div>

          <div className="glass p-4">
            <div className="text-xs tracking-widest text-zinc-400 mb-2">QUICK ACTIONS</div>
            <div className="grid grid-cols-3 gap-2">
              {[
                ["Search","search.web"], ["Calendar","calendar"], ["Files","files"],
                ["Computer","computer"], ["Automate","auto"], ["Settings","cog"]
              ].map(([label])=>(
                <button key={label} onClick={()=>{
                  if(label==="Search") send("Search for today's UK cybersecurity news")
                  if(label==="Calendar") send("What's on my calendar today?")
                  if(label==="Files") send("Find my latest document")
                  if(label==="Computer") send("Open calculator")
                  if(label==="Automate") send("Prepare my morning briefing")
                }} className="py-3 rounded-xl bg-white/5 border border-white/10 text-xs hover:bg-white/10">{label}</button>
              ))}
            </div>
          </div>
        </div>

        {/* Center — conversation */}
        <div className="col-span-12 lg:col-span-6 flex flex-col min-h-[600px]">
          <div className="glass flex-1 flex flex-col overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-400 to-indigo-500 animate-pulse" />
                <div>
                  <div className="text-sm font-medium">JARVIS</div>
                  <div className="text-xs text-zinc-400 flex items-center gap-1">{busy?<span className="text-cyan-300">● Thinking…</span>:<span className="text-emerald-300">● Listening</span>} <span className="hidden sm:inline">— try “Jarvis, good morning”</span></div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={toggleVoice} className={`text-xs px-3 py-1.5 rounded-full border ${listening?"bg-red-500 text-white border-red-500":"bg-white/10 border-white/10"}`}>{listening?"● Stop":"🎤 Voice"}</button>
                <span className="text-xs px-2 py-1 rounded-full bg-white/5 border border-white/10 hidden sm:inline">{conversations.length} chats</span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4 max-h-[560px]">
              {messages.length===0 && (
                <div className="grid gap-3">
                  <div className="p-4 rounded-xl bg-gradient-to-br from-cyan-500/10 to-indigo-500/10 border border-cyan-500/20">
                    <div className="text-sm font-medium">Try these</div>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {["Good morning","What's using the most RAM?","Open calculator","Prepare my morning briefing","Create a reminder for tomorrow at 9 AM"].map(t=>(
                        <button key={t} onClick={()=>send(t)} className="text-xs px-3 py-1.5 rounded-full bg-white/10 border border-white/10 hover:bg-white/15">{t}</button>
                      ))}
                    </div>
                  </div>
                  <div className="text-xs text-zinc-500">Pro tip: say “Jarvis, emergency stop” to cancel everything instantly (deterministic, no AI).</div>
                </div>
              )}
              {messages.map((m,i)=>(
                <div key={i} className={`flex ${m.role==="user"?"justify-end":"justify-start"}`}>
                  <div className={`max-w-[80%] p-3 rounded-2xl text-sm leading-relaxed ${m.role==="user"?"bg-white text-black rounded-br-sm":"bg-white/5 border border-white/10 rounded-bl-sm"}`}>
                    <div className="whitespace-pre-wrap">{m.content}</div>
                  </div>
                </div>
              ))}
              <div ref={endRef} />
            </div>

            <div className="p-3 border-t border-white/10 flex gap-2">
              <input
                value={input}
                onChange={e=>setInput(e.target.value)}
                onKeyDown={e=>{ if(e.key==="Enter" && !e.shiftKey) { e.preventDefault(); send()}}}
                placeholder="Ask Jarvis… (Enter to send, voice with 🎤)"
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-cyan-400/50"
              />
              <button onClick={()=>send()} disabled={busy} className="px-5 py-2.5 rounded-xl bg-white text-black text-sm font-semibold disabled:opacity-50">Send</button>
            </div>
          </div>

          <div className="mt-3 flex items-center gap-2 text-xs text-zinc-500">
            <span className={`w-2 h-2 rounded-full ${listening?"bg-red-500 animate-pulse":"bg-emerald-500"}`} />
            <span>{listening?"Microphone active":"Microphone idle"} — camera off — screen analysis off</span>
            <span className="ml-auto font-mono">{new Date().toLocaleString()}</span>
          </div>
        </div>

        {/* Right — agents/tools/memory */}
        <div className="col-span-12 lg:col-span-3 space-y-4">
          <div className="glass p-4">
            <div className="text-xs tracking-widest text-zinc-400 mb-3">AGENTS</div>
            <div className="space-y-2 max-h-[220px] overflow-auto pr-1">
              {agents.map((ag:any)=>(
                <div key={ag.id} className="p-2.5 rounded-xl bg-white/5 border border-white/5">
                  <div className="text-sm font-medium flex items-center gap-2">{ag.name} <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/10 border border-white/10">{ag.model_tier}</span></div>
                  <div className="text-xs text-zinc-400 line-clamp-2">{ag.description}</div>
                  <div className="text-[10px] font-mono text-zinc-500 mt-1 truncate">{(ag.allowed_tools||[]).slice(0,3).join(", ")}</div>
                </div>
              ))}
              {!agents.length && <div className="text-xs text-zinc-500">Loading agents…</div>}
            </div>
          </div>

          <div className="glass p-4">
            <div className="text-xs tracking-widest text-zinc-400 mb-3">TOOLS</div>
            <div className="space-y-1 max-h-[220px] overflow-auto pr-1">
              {tools.slice(0,12).map((t:any)=>(
                <div key={t.name} className="flex items-center justify-between p-2 rounded-lg hover:bg-white/5">
                  <div>
                    <div className="text-xs font-mono">{t.name}</div>
                    <div className="text-[11px] text-zinc-500">{t.description}</div>
                  </div>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${t.risk==="high"||t.risk==="critical"?"bg-red-500/20 text-red-300 border-red-500/30":t.risk==="moderate"?"bg-amber-500/20 text-amber-300 border-amber-500/20":"bg-emerald-500/15 text-emerald-300 border-emerald-500/20"}`}>{t.risk}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="glass p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs tracking-widest text-zinc-400">CONVERSATIONS</div>
              <button onClick={loadConvs} className="text-xs text-zinc-400">↻</button>
            </div>
            <div className="space-y-1 max-h-[200px] overflow-auto pr-1">
              {conversations.map((c:any)=>(
                <button key={c.id} onClick={()=>loadMessages(c.id)} className={`w-full text-left p-2 rounded-xl border text-xs ${activeConv===c.id?"bg-white text-black border-white":"bg-white/5 border-white/10 hover:bg-white/10"}`}>
                  <div className="truncate font-medium">{c.title||"Conversation"}</div>
                  <div className="text-[11px] opacity-60">{new Date(c.updated_at).toLocaleString()}</div>
                </button>
              ))}
              {!conversations.length && <div className="text-xs text-zinc-500">No conversations yet.</div>}
            </div>
            <button onClick={()=>{ setMessages([]); setActiveConv(null)}} className="mt-3 w-full text-xs py-2 rounded-xl bg-white/5 border border-white/10">New chat</button>
          </div>
        </div>
      </div>

      <footer className="max-w-[1400px] mx-auto px-4 py-6 text-xs text-zinc-500 flex flex-wrap gap-3">
        <span>JARVIS v0.1.0 — Phase 1 Core Runtime</span>
        <span className="hidden sm:inline">•</span>
        <span>Audited tools • Permission tiers L0-L4 • Audit logs • Event bus</span>
        <span className="ml-auto font-mono">PERCEIVE → UNDERSTAND → REMEMBER → PLAN → ACT → VERIFY → REPORT</span>
      </footer>
    </div>
  )
}
