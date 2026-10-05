const BASE = "";

async function req(path: string, opts: RequestInit = {}) {
  const r = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(opts.headers||{}) },
    ...opts
  });
  const text = await r.text();
  let data: any = {};
  try { data = text? JSON.parse(text): {}; } catch { data = { raw: text }; }
  if (!r.ok) throw new Error(data.error || data.detail || `HTTP ${r.status}`);
  return data;
}

export const api = {
  signup: (email:string,password:string,display_name?:string)=> req("/api/v1/auth/signup",{method:"POST",body: JSON.stringify({email,password,display_name})}),
  login: (email:string,password:string)=> req("/api/v1/auth/login",{method:"POST",body: JSON.stringify({email,password})}),
  me: ()=> req("/api/v1/auth/me"),
  health: ()=> req("/api/v1/health"),
  chat: (message:string, conversation_id?:string)=> req("/api/v1/chat",{method:"POST",body: JSON.stringify({message, conversation_id})}),
  conversations: ()=> req("/api/v1/conversations"),
  conversation: (id:string)=> req(`/api/v1/conversations/${id}`),
  tools: ()=> req("/api/v1/tools"),
  toolExec: (tool:string, args: any)=> req("/api/v1/tools/execute",{method:"POST",body: JSON.stringify({tool,arguments:args})}),
  systemStatus: ()=> req("/api/v1/system/status"),
  diagnostics: ()=> req("/api/v1/system/diagnostics"),
  emergency: ()=> req("/api/v1/system/emergency-stop",{method:"POST"}),
  agents: ()=> req("/api/v1/agents"),
  memories: (q?:string)=> req(`/api/v1/memory${q?`?q=${encodeURIComponent(q)}`:""}`),
  memoryCreate: (content:string,kind:string="episodic")=> req("/api/v1/memory",{method:"POST",body: JSON.stringify({kind,content})}),
  tasks: ()=> req("/api/v1/tasks"),
  tasksCreate: (title:string)=> req("/api/v1/tasks",{method:"POST",body: JSON.stringify({title})}),
  approvals: ()=> req("/api/v1/security/approvals?status=pending"),
  approve: (id:string, decision:string)=> req(`/api/v1/security/approvals/${id}/resolve`,{method:"POST",body: JSON.stringify({decision})}),
  audit: ()=> req("/api/v1/security/audit"),
  notifications: ()=> req("/api/v1/notifications"),
};
