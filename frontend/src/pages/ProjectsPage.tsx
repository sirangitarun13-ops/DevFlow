import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Project } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Badge, Card, EmptyState, ErrorState, LoadingState, PageTitle } from "../ui";

export default function ProjectsPage() {
  const { canManage } = useAuth(); const [projects, setProjects] = useState<Project[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [showForm, setShowForm] = useState(false); const [name, setName] = useState("");
  const load = () => api.projects().then(setProjects).catch((e) => setError(e instanceof Error ? e.message : "Unable to load projects")).finally(() => setLoading(false));
  useEffect(() => { void load(); }, []);
  const submit = async (event: FormEvent) => { event.preventDefault(); try { await api.createProject({ name, status: "planned" }); setName(""); setShowForm(false); setLoading(true); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Unable to create project"); } };
  if (loading) return <LoadingState />; if (error) return <ErrorState message={error} />;
  return <><PageTitle eyebrow="PORTFOLIO" title="Projects" detail="Projects you can access through the DevFlow API." action={canManage && <button className="primary-button" onClick={() => setShowForm((value) => !value)}>New project</button>} />{showForm && <Card className="form-card"><form className="inline-form" onSubmit={submit}><label>Project name<input required value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Atlas release" /></label><button className="primary-button">Create project</button></form></Card>}{projects.length ? <div className="project-grid">{projects.map((project) => <Card key={project.id}><div className="project-card-top"><span className="project-icon">{project.name.slice(0, 1)}</span><Badge tone={project.status === "active" ? "good" : "neutral"}>{project.status.replace("_", " ")}</Badge></div><h2>{project.name}</h2><p className="muted">{project.description || "No description provided."}</p><div className="project-meta"><span>{project.start_date || "No start date"}</span><Link className="text-link" to={`/projects/${project.id}`}>Open project →</Link></div></Card>)}</div> : <EmptyState title="No accessible projects" detail="Ask a project manager to add you to a project." />}</>;
}
