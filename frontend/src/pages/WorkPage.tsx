import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Bug, Milestone, ProjectMember, Requirement, Sprint, Task, TestCase } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useProjects } from "../project/ProjectContext";
import { Badge, Card, EmptyState, ErrorState, LoadingState, PageTitle } from "../ui";

type WorkKind = "tasks" | "bugs" | "test-cases" | "sprints" | "milestones" | "traceability" | "system";
type WorkRow = Task | Bug | TestCase | Sprint | Milestone;
type TaskForm = { title: string; description: string; requirement_id: string; sprint_id: string; assigned_to_user_id: string; priority: string; status: string; due_date: string };
const emptyTaskForm: TaskForm = { title: "", description: "", requirement_id: "", sprint_id: "", assigned_to_user_id: "", priority: "medium", status: "todo", due_date: "" };

export default function WorkPage({ kind }: { kind: WorkKind }) {
  const { canManage } = useAuth();
  const { selectedProject: project } = useProjects();
  const [rows, setRows] = useState<WorkRow[]>([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [formLoading, setFormLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<TaskForm>(emptyTaskForm);

  const load = async () => {
    setLoading(true);
    try {
      if (!project) { setRows([]); return; }
      if (kind === "tasks") {
        const [taskRows, requirementRows, sprintRows, memberRows] = await Promise.all([api.tasks(project.id), api.requirements(project.id), api.sprints(project.id), api.projectMembers(project.id)]);
        setRows(taskRows); setRequirements(requirementRows); setSprints(sprintRows); setMembers(memberRows);
      } else if (kind === "bugs") setRows(await api.bugs(project.id));
      else if (kind === "test-cases") setRows(await api.testCases(project.id));
      else if (kind === "sprints") setRows(await api.sprints(project.id));
      else if (kind === "milestones") setRows(await api.milestones(project.id));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load work items");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [kind, project?.id]);

  const updateForm = (field: keyof TaskForm, value: string) => setForm((current) => ({ ...current, [field]: value }));
  const createTask = async (event: FormEvent) => {
    event.preventDefault();
    if (!project || !form.title.trim()) return;
    setFormLoading(true); setError(""); setSuccess("");
    try {
      const body = { title: form.title.trim(), description: form.description.trim() || undefined, requirement_id: form.requirement_id || undefined, sprint_id: form.sprint_id || undefined, assigned_to_user_id: form.assigned_to_user_id || undefined, priority: form.priority, status: form.status, due_date: form.due_date || undefined };
      await api.createTask(project.id, body);
      setForm(emptyTaskForm); setShowForm(false); setSuccess("Task created successfully."); await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create task");
    } finally {
      setFormLoading(false);
    }
  };

  if (loading) return <LoadingState label="Loading work items…" />;
  if (error && !showForm) return <ErrorState message={error} onRetry={() => void load()} />;

  const labels: Record<WorkKind, [string, string, string]> = {
    tasks: ["TASKS", "Tasks", "Execution work items"], bugs: ["DEFECTS", "Bugs", "Reported defects and their status"], "test-cases": ["QUALITY", "Test cases", "Validation work for the project"], sprints: ["PLANNING", "Sprints", "Time-boxed delivery cycles"], milestones: ["PLANNING", "Milestones", "Project delivery checkpoints"], traceability: ["TRACEABILITY", "Traceability", "Explore links from requirement details"], system: ["ADMINISTRATION", "System", "System-level APIs are not yet exposed"],
  };
  const copy = labels[kind];
  if (kind === "traceability" || kind === "system") return <><PageTitle eyebrow={copy[0]} title={copy[1]} detail={copy[2]} /><EmptyState title={kind === "traceability" ? "Open a requirement to inspect links" : "No system administration API"} detail={kind === "traceability" ? "The backend exposes traceability on requirement and artifact routes." : "No unsupported administrative data is fabricated by this frontend."} /></>;

  const taskColumns = kind === "tasks" ? ["todo", "in_progress", "in_review", "blocked", "completed"] : [];
  const rowCard = (row: WorkRow) => {
    const title = "title" in row ? String(row.title) : String(row.name); const status = String(row.status);
    const detail = "description" in row ? String(row.description || "No description") : "goal" in row ? String(row.goal || "No sprint goal") : "requirement_id" in row ? `Requirement ${row.requirement_id?.slice(0, 8) ?? "—"}` : "Project checkpoint";
    return <div className="work-card" key={row.id}><div className="work-card-head"><span className="mono">{row.id.slice(0, 8)}</span><Badge tone={status === "completed" || status === "passed" ? "good" : status === "failed" || status === "blocked" ? "bad" : "accent"}>{status}</Badge></div><strong>{title}</strong><small>{detail}</small>{"priority" in row && <span className="work-meta">Priority · {row.priority}</span>}{"due_date" in row && row.due_date && <span className="work-meta">Due · {row.due_date}</span>}</div>;
  };

  return <>
    <PageTitle eyebrow={copy[0]} title={copy[1]} detail={project ? `${copy[2]} · ${project.name}` : copy[2]} action={kind === "tasks" && canManage ? <button className="primary-button" onClick={() => { setShowForm((value) => !value); setError(""); }}>{showForm ? "Close form" : "New task"}</button> : undefined} />
    {success && <div className="success-banner" role="status">{success}</div>}
    {showForm && kind === "tasks" && <Card className="form-card"><div className="card-heading"><div><span className="eyebrow">NEW TASK</span><h2>Create implementation work</h2></div></div><form className="form-grid" onSubmit={createTask}>
      <label>Title<input required minLength={1} maxLength={250} value={form.title} onChange={(event) => updateForm("title", event.target.value)} placeholder="Describe the work" /></label>
      <label>Priority<select value={form.priority} onChange={(event) => updateForm("priority", event.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label>
      <label className="span-2">Description<textarea value={form.description} onChange={(event) => updateForm("description", event.target.value)} placeholder="Add implementation context (optional)" /></label>
      <label>Requirement<select value={form.requirement_id} onChange={(event) => updateForm("requirement_id", event.target.value)}><option value="">No requirement</option>{requirements.map((item) => <option key={item.id} value={item.id}>{item.requirement_key} · {item.title}</option>)}</select></label>
      <label>Sprint<select value={form.sprint_id} onChange={(event) => updateForm("sprint_id", event.target.value)}><option value="">No sprint</option>{sprints.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Assignee<select value={form.assigned_to_user_id} onChange={(event) => updateForm("assigned_to_user_id", event.target.value)}><option value="">Unassigned</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.user_id.slice(0, 8)}{member.project_role ? ` · ${member.project_role}` : ""}</option>)}</select></label>
      <label>Status<select value={form.status} onChange={(event) => updateForm("status", event.target.value)}><option value="todo">To do</option><option value="in_progress">In progress</option><option value="in_review">In review</option><option value="blocked">Blocked</option><option value="completed">Completed</option></select></label>
      <label>Due date<input type="date" value={form.due_date} onChange={(event) => updateForm("due_date", event.target.value)} /></label>
      {error && <div className="form-error span-2" role="alert">{error}</div>}
      <div className="span-2 form-actions"><button className="primary-button" disabled={formLoading}>{formLoading ? "Creating…" : "Create task"}</button><button type="button" className="secondary-button" onClick={() => setShowForm(false)} disabled={formLoading}>Cancel</button></div>
    </form></Card>}
    {rows.length ? kind === "tasks" ? <div className="task-board">{taskColumns.map((status) => <section className="task-column" key={status}><div className="column-heading"><span>{status.replace("_", " ")}</span><b>{rows.filter((row) => row.status === status).length}</b></div>{rows.filter((row) => row.status === status).map(rowCard)}</section>)}</div> : <Card><div className="table-list">{rows.map(rowCard)}</div></Card> : <EmptyState title={`No ${copy[1].toLowerCase()} yet`} detail={kind === "tasks" ? "No execution work has been returned for this project yet. Use New task to start tracking delivery." : `Records returned by the backend for ${project?.name ?? "this project"} will appear here.`} />}
  </>;
}
