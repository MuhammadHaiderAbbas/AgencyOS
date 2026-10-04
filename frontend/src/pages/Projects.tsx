import { useState } from "react";
import { LuPlus, LuSparkles } from "react-icons/lu";
import { go } from "../main";
import { Empty, Loading, Modal, useApi } from "../ui";
import { ProjectCard, useCreateProject } from "./Dashboard";

export function ProjectsPage() {
  const [archived, setArchived] = useState(false);
  const [filter, setFilter] = useState("ALL");
  const { data } = useApi<any[]>(`/api/projects${archived ? "?archived=1" : ""}`, [archived]);
  const [open, setOpen] = useState(false);
  if (!data) return <Loading />;
  const statuses = ["ALL", ...Array.from(new Set(data.map((p) => p.status)))];
  const rows = data.filter((p) => filter === "ALL" || p.status === filter);
  return <div>
    <div className="page-title"><h1>Projects</h1>
      <div className="row wrap">
        <select className="select" style={{ width: "auto" }} value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter by status">{statuses.map((s) => <option key={s}>{s}</option>)}</select>
        <button className={`btn ${archived ? "primary" : ""}`} onClick={() => setArchived(!archived)}>{archived ? "Showing archived" : "Show archived"}</button>
        <button className="btn primary" onClick={() => setOpen(true)}><LuPlus /> New project</button>
      </div></div>
    {rows.length === 0 ? <div className="card"><Empty icon={LuSparkles} title={archived ? "No archived projects" : "No projects yet"}>Start one from the dashboard or a <a href="#/templates">template</a>.</Empty></div> :
      <div className="projects-grid">{rows.map((p) => <ProjectCard key={p.id} p={p} />)}</div>}
    {open && <NewProject onClose={() => setOpen(false)} />}
  </div>;
}

function NewProject({ onClose }: { onClose: () => void }) {
  const [idea, setIdea] = useState("");
  const { create, busy } = useCreateProject();
  return <Modal title="Start a new project" onClose={onClose}>
    <form className="stack" onSubmit={(e) => { e.preventDefault(); if (idea.trim()) create(idea.trim()); }}>
      <label className="field">What do you want to build?<textarea className="textarea" autoFocus value={idea} onChange={(e) => setIdea(e.target.value)} placeholder="I want a modern website for my hotel…" /></label>
      <div className="small muted">The Requirements Agent will ask a few questions, then show you a summary to approve before anything is built.</div>
      <div className="row"><button className="btn primary" disabled={busy || !idea.trim()}>Start project</button><button type="button" className="btn" onClick={() => go("templates")}>Browse templates</button></div>
    </form>
  </Modal>;
}
