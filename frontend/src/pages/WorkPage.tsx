import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Bug, Milestone, ProjectMember, Requirement, Sprint, Task, TestCase } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useProjects } from "../project/ProjectContext";
import { Badge, Card, EmptyState, ErrorState, LoadingState, PageTitle } from "../ui";

type WorkKind = "tasks" | "bugs" | "test-cases" | "sprints" | "milestones" | "traceability" | "system";
type WorkRow = Task | Bug | TestCase | Sprint | Milestone;

type TaskForm = { title: string; description: string; requirement_id: string; sprint_id: string; assigned_to_user_id: string; priority: string; status: string; due_date: string };
const emptyTaskForm: TaskForm = { title: "", description: "", requirement_id: "", sprint_id: "", assigned_to_user_id: "", priority: "medium", status: "todo", due_date: "" };

type SprintForm = { name: string; goal: string; start_date: string; end_date: string; status: string; requirement_id: string };
const emptySprintForm: SprintForm = { name: "", goal: "", start_date: "", end_date: "", status: "planned", requirement_id: "" };

type MilestoneForm = { name: string; description: string; due_date: string; status: string };
const emptyMilestoneForm: MilestoneForm = { name: "", description: "", due_date: "", status: "planned" };

const TASK_STATUSES = ["todo", "in_progress", "in_review", "completed", "blocked"] as const;
const SPRINT_STATUSES = ["planned", "active", "completed", "cancelled"] as const;
const MILESTONE_STATUSES = ["planned", "in_progress", "completed", "cancelled"] as const;
const BUG_STATUSES = ["open", "in_progress", "resolved", "closed", "reopened"] as const;
const BUG_SEVERITIES = ["low", "medium", "high", "critical"] as const;

const bugColumns = BUG_STATUSES;

type BugForm = { title: string; description: string; requirement_id: string; task_id: string; severity: string; status: string; assigned_to_user_id: string };
const emptyBugForm: BugForm = { title: "", description: "", requirement_id: "", task_id: "", severity: "medium", status: "open", assigned_to_user_id: "" };

export default function WorkPage({ kind }: { kind: WorkKind }) {
  const { canManage } = useAuth();
  const { selectedProject: project } = useProjects();
  const [rows, setRows] = useState<WorkRow[]>([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [formLoading, setFormLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [linkWarning, setLinkWarning] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<TaskForm | SprintForm | MilestoneForm | BugForm>(emptyTaskForm);

  const load = async () => {
    setLoading(true);
    try {
      if (!project) { setRows([]); return; }
      if (kind === "tasks") {
        const [taskRows, requirementRows, sprintRows, memberRows] = await Promise.all([api.tasks(project.id), api.requirements(project.id), api.sprints(project.id), api.projectMembers(project.id)]);
        setRows(taskRows); setRequirements(requirementRows); setSprints(sprintRows); setMembers(memberRows);
      } else if (kind === "bugs") {
        const [bugRows, requirementRows, taskRows, memberRows] = await Promise.all([api.bugs(project.id), api.requirements(project.id), api.tasks(project.id), api.projectMembers(project.id)]);
        setRows(bugRows); setRequirements(requirementRows); setTasks(taskRows); setMembers(memberRows);
      } else if (kind === "test-cases") setRows(await api.testCases(project.id));
      else if (kind === "sprints") {
        const [sprintRows, requirementRows] = await Promise.all([api.sprints(project.id), api.requirements(project.id)]);
        setRows(sprintRows);
        setRequirements(requirementRows);
      }
      else if (kind === "milestones") setRows(await api.milestones(project.id));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load work items");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [kind, project?.id]);

  const updateForm = (field: string, value: string) => setForm((current) => ({ ...current, [field]: value }));

  const startCreate = (kind: "task" | "sprint" | "milestone" | "bug") => {
    if (kind === "task") setForm(emptyTaskForm);
    else if (kind === "sprint") setForm(emptySprintForm);
    else if (kind === "milestone") setForm(emptyMilestoneForm);
    else setForm(emptyBugForm);
    setEditingId(null);
    setShowForm(true);
    setError("");
    setLinkWarning("");
  };

  const startEdit = (row: WorkRow) => {
    if ("title" in row && "due_date" in row && !("goal" in row)) {
      // Task
      const task = row as Task;
      setForm({
        title: task.title,
        description: task.description || "",
        requirement_id: task.requirement_id || "",
        sprint_id: task.sprint_id || "",
        assigned_to_user_id: task.assigned_to_user_id || "",
        priority: task.priority,
        status: task.status,
        due_date: task.due_date || "",
      });
    } else if ("goal" in row) {
      // Sprint
      const sprint = row as Sprint;
      setForm({
        name: sprint.name,
        goal: sprint.goal || "",
        start_date: sprint.start_date,
        end_date: sprint.end_date,
        status: sprint.status,
        requirement_id: "",
      });
    } else if ("severity" in row) {
      // Bug
      const bug = row as Bug;
      setForm({
        title: bug.title,
        description: bug.description || "",
        requirement_id: bug.requirement_id || "",
        task_id: bug.task_id || "",
        severity: bug.severity,
        status: bug.status,
        assigned_to_user_id: bug.assigned_to_user_id || "",
      });
    } else {
      // Milestone
      const milestone = row as Milestone;
      setForm({
        name: milestone.name,
        description: milestone.description || "",
        due_date: milestone.due_date || "",
        status: milestone.status,
      });
    }
    setEditingId(row.id);
    setShowForm(true);
    setError("");
    setLinkWarning("");
  };

  const cancelEdit = () => {
    if (kind === "sprints") setForm(emptySprintForm);
    else if (kind === "milestones") setForm(emptyMilestoneForm);
    else if (kind === "bugs") setForm(emptyBugForm);
    else setForm(emptyTaskForm);
    setEditingId(null);
    setShowForm(false);
    setError("");
    setLinkWarning("");
  };

  // Create a persisted traceability edge after an artifact is created with a requirement association.
  // Keep artifact creation successful if the separate link request fails and report that partial success.
  const tryCreateRequirementLink = async (
    projectId: string,
    requirementId: string,
    targetArtifactType: "task" | "bug" | "sprint",
    targetArtifactId: string,
    relationshipType: "implements" | "affects" | "belongs_to",
  ): Promise<string | null> => {
    try {
      await api.createTraceabilityLink(projectId, {
        source_artifact_type: "requirement",
        source_artifact_id: requirementId,
        target_artifact_type: targetArtifactType,
        target_artifact_id: targetArtifactId,
        relationship_type: relationshipType,
      });
      return null;
    } catch (e) {
      return e instanceof Error ? e.message : "Unknown error";
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!project) return;
    const titleField = kind === "sprints" ? (form as SprintForm).name : kind === "bugs" ? (form as BugForm).title : (form as TaskForm).title ?? (form as MilestoneForm).name;
    if (!titleField?.trim()) return;
    setFormLoading(true); setError(""); setSuccess(""); setLinkWarning("");
    let traceabilityWarning = "";
    try {
      if (kind === "tasks") {
        const body = { title: (form as TaskForm).title.trim(), description: (form as TaskForm).description.trim() || undefined, requirement_id: (form as TaskForm).requirement_id || undefined, sprint_id: (form as TaskForm).sprint_id || undefined, assigned_to_user_id: (form as TaskForm).assigned_to_user_id || undefined, priority: (form as TaskForm).priority, status: (form as TaskForm).status, due_date: (form as TaskForm).due_date || undefined };
        if (editingId) {
          await api.updateTask(editingId, body);
          setSuccess("Task updated successfully.");
        } else {
          const createdTask = await api.createTask(project.id, body);
          if (body.requirement_id) {
            const linkError = await tryCreateRequirementLink(project.id, body.requirement_id, "task", createdTask.id, "implements");
            if (linkError) traceabilityWarning = `Task created, but its traceability link could not be saved: ${linkError}`;
          }
          setSuccess("Task created successfully.");
        }
      } else if (kind === "sprints") {
        const sprintForm = form as SprintForm;
        const body = { name: sprintForm.name.trim(), goal: sprintForm.goal.trim() || undefined, start_date: sprintForm.start_date, end_date: sprintForm.end_date, status: sprintForm.status };
        if (editingId) {
          await api.updateSprint(editingId, body);
          setSuccess("Sprint updated successfully.");
        } else {
          const createdSprint = await api.createSprint(project.id, body);
          if (sprintForm.requirement_id) {
            const linkError = await tryCreateRequirementLink(project.id, sprintForm.requirement_id, "sprint", createdSprint.id, "belongs_to");
            if (linkError) traceabilityWarning = `Sprint created, but its traceability link could not be saved: ${linkError}`;
          }
          setSuccess("Sprint created successfully.");
        }
      } else if (kind === "milestones") {
        const body = { name: (form as MilestoneForm).name.trim(), description: (form as MilestoneForm).description.trim() || undefined, due_date: (form as MilestoneForm).due_date || undefined, status: (form as MilestoneForm).status };
        if (editingId) { await api.updateMilestone(editingId, body); setSuccess("Milestone updated successfully."); }
        else { await api.createMilestone(project.id, body); setSuccess("Milestone created successfully."); }
      } else if (kind === "bugs") {
        const body = { title: (form as BugForm).title.trim(), description: (form as BugForm).description.trim() || undefined, requirement_id: (form as BugForm).requirement_id || undefined, task_id: (form as BugForm).task_id || undefined, severity: (form as BugForm).severity, status: (form as BugForm).status, assigned_to_user_id: (form as BugForm).assigned_to_user_id || undefined };
        if (editingId) {
          await api.updateBug(editingId, body);
          setSuccess("Bug updated successfully.");
        } else {
          const createdBug = await api.createBug(project.id, body);
          if (body.requirement_id) {
            const linkError = await tryCreateRequirementLink(project.id, body.requirement_id, "bug", createdBug.id, "affects");
            if (linkError) traceabilityWarning = `Bug created, but its traceability link could not be saved: ${linkError}`;
          }
          setSuccess("Bug created successfully.");
        }
      }
      if (kind === "tasks") setForm(emptyTaskForm);
      else if (kind === "sprints") setForm(emptySprintForm);
      else if (kind === "milestones") setForm(emptyMilestoneForm);
      else setForm(emptyBugForm);
      setEditingId(null);
      setShowForm(false);
      if (traceabilityWarning) setLinkWarning(traceabilityWarning);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : editingId ? "Unable to update" : "Unable to create");
    } finally {
      setFormLoading(false);
    }
  };

  const handleStatusChange = async (id: string, newStatus: string) => {
    if (!project) return;
    try {
      if (kind === "tasks") await api.updateTask(id, { status: newStatus });
      else if (kind === "sprints") await api.updateSprint(id, { status: newStatus });
      else if (kind === "milestones") await api.updateMilestone(id, { status: newStatus });
      else if (kind === "bugs") await api.updateBug(id, { status: newStatus });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status");
    }
  };

  if (loading) return <LoadingState label="Loading work items…" />;
  if (error && !showForm) return <ErrorState message={error} onRetry={() => void load()} />;

  const labels: Record<WorkKind, [string, string, string]> = {
    tasks: ["TASKS", "Tasks", "Execution work items"], bugs: ["DEFECTS", "Bugs", "Reported defects and their status"], "test-cases": ["QUALITY", "Test cases", "Validation work for the project"], sprints: ["PLANNING", "Sprints", "Time-boxed delivery cycles"], milestones: ["PLANNING", "Milestones", "Project delivery checkpoints"], traceability: ["TRACEABILITY", "Traceability", "Explore links from requirement details"], system: ["ADMINISTRATION", "System", "System-level APIs are not yet exposed"],
  };
  const copy = labels[kind];
  if (kind === "traceability" || kind === "system") return <><PageTitle eyebrow={copy[0]} title={copy[1]} detail={copy[2]} /><EmptyState title={kind === "traceability" ? "Open a requirement to inspect links" : "No system administration API"} detail={kind === "traceability" ? "The backend exposes traceability on requirement and artifact routes." : "No unsupported administrative data is fabricated by this frontend."} /></>;

  const sprintColumns = kind === "sprints" ? SPRINT_STATUSES : [];
  const milestoneColumns = kind === "milestones" ? MILESTONE_STATUSES : [];

const rowCard = (row: WorkRow) => {
    const isTask = kind === "tasks";
    const isSprint = kind === "sprints";
    const isMilestone = kind === "milestones";
    const isBug = kind === "bugs";
    const title = isTask ? (row as Task).title : isSprint ? (row as Sprint).name : isBug ? (row as Bug).title : (row as Milestone).name;
    const status = String(row.status);
    const detail = isTask ? String((row as Task).description || "No description") : isSprint ? String((row as Sprint).goal || "No sprint goal") : isBug ? String((row as Bug).description || "No description") : String((row as Milestone).description || "Project checkpoint");
    const canUpdateStatus = canManage && (isTask || isSprint || isMilestone || isBug);

    // Bug associations
    const bug = isBug ? row as Bug : null;
    const bugTask = bug && bug.task_id ? tasks.find((t) => t.id === bug.task_id) : null;
    const bugRequirement = bug && bug.requirement_id ? requirements.find((r) => r.id === bug.requirement_id) : null;

    return (
      <div className="work-card" key={row.id}>
        <div className="work-card-head">
          <span className="mono">{row.id.slice(0, 8)}</span>
          <Badge tone={status === "completed" || status === "passed" ? "good" : status === "failed" || status === "blocked" || status === "cancelled" ? "bad" : "accent"}>
            {status.replace("_", " ")}
          </Badge>
        </div>
        <strong>{title}</strong>
        <small>{detail}</small>
        {"priority" in row && <span className="work-meta">Priority · {row.priority}</span>}
        {"due_date" in row && row.due_date && <span className="work-meta">{isMilestone ? "Target" : "Due"} · {row.due_date}</span>}
        {"start_date" in row && "end_date" in row && <span className="work-meta">{row.start_date} → {row.end_date}</span>}
        {isBug && bugTask && (
          <div className="work-meta bug-assoc">
            <Link to={`/tasks/${bugTask.id}`} className="assoc-ref" onClick={(e) => e.stopPropagation()}>
              Task: {bugTask.title}
            </Link>
          </div>
        )}
        {isBug && bugRequirement && (
          <div className="work-meta bug-assoc">
            <Link to={`/requirements/${bugRequirement.id}`} className="assoc-ref" onClick={(e) => e.stopPropagation()}>
              Requirement: {bugRequirement.requirement_key} · {bugRequirement.title}
            </Link>
          </div>
        )}
        {!isBug && "due_date" in row && row.due_date && <span className="work-meta">{isMilestone ? "Target" : "Due"} · {row.due_date}</span>}
        {"start_date" in row && "end_date" in row && <span className="work-meta">{row.start_date} → {row.end_date}</span>}
        <div className="task-actions">
          {canUpdateStatus && (
            <select
              value={status}
              onChange={(e) => {
                e.stopPropagation();
                const newStatus = e.target.value;
                if (newStatus !== status) handleStatusChange(row.id, newStatus);
              }}
              className="status-select"
              title="Change status"
            >
              {isTask ? TASK_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>) : isSprint ? SPRINT_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>) : isBug ? BUG_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>) : MILESTONE_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
            </select>
          )}
          {canManage && <button className="ghost-button" onClick={(e) => { e.stopPropagation(); startEdit(row); }}>Edit</button>}
        </div>
      </div>
    );
  };

  return (
    <>
      <PageTitle
        eyebrow={copy[0]}
        title={copy[1]}
        detail={project ? `${copy[2]} · ${project.name}` : copy[2]}
        action={canManage && project && ["tasks", "sprints", "milestones", "bugs"].includes(kind) ? (
          <button className="primary-button" onClick={() => startCreate(kind as "task" | "sprint" | "milestone" | "bug")}>
            {showForm ? "Close form" : kind === "tasks" ? "New task" : kind === "sprints" ? "New sprint" : kind === "milestones" ? "New milestone" : "New bug"}
          </button>
        ) : undefined}
      />
      {success && <div className="success-banner" role="status">{success}</div>}
      {linkWarning && (
        <div
          role="alert"
          style={{ marginBottom: 18, padding: "11px 14px", color: "#9a5b00", border: "1px solid #f3d7a3", borderRadius: 9, background: "#fff8e6", fontSize: 12, fontWeight: 700 }}
        >
          {linkWarning}
        </div>
      )}
      {showForm && (
        <Card className="form-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">{editingId ? "EDIT" : "NEW"} {kind === "sprints" ? "SPRINT" : kind === "milestones" ? "MILESTONE" : "TASK"}</span>
              <h2>{editingId ? "Update" : "Create"} {kind === "sprints" ? "sprint" : kind === "milestones" ? "milestone" : "task"}</h2>
            </div>
          </div>
          <form className="form-grid" onSubmit={handleSubmit}>
            {kind === "tasks" && (
              <>
                <label>Title<input required minLength={1} maxLength={250} value={(form as TaskForm).title} onChange={(event) => updateForm("title", event.target.value)} placeholder="Describe the work" /></label>
                <label>Priority<select value={(form as TaskForm).priority} onChange={(event) => updateForm("priority", event.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label>
                <label className="span-2">Description<textarea value={(form as TaskForm).description} onChange={(event) => updateForm("description", event.target.value)} placeholder="Add implementation context (optional)" /></label>
                <label>Requirement<select value={(form as TaskForm).requirement_id} onChange={(event) => updateForm("requirement_id", event.target.value)}><option value="">No requirement</option>{requirements.map((item) => <option key={item.id} value={item.id}>{item.requirement_key} · {item.title}</option>)}</select></label>
                <label>Sprint<select value={(form as TaskForm).sprint_id} onChange={(event) => updateForm("sprint_id", event.target.value)}><option value="">No sprint</option>{sprints.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
                <label>Assignee<select value={(form as TaskForm).assigned_to_user_id} onChange={(event) => updateForm("assigned_to_user_id", event.target.value)}><option value="">Unassigned</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.user_id.slice(0, 8)}{member.project_role ? ` · ${member.project_role}` : ""}</option>)}</select></label>
                <label>Status<select value={(form as TaskForm).status} onChange={(event) => updateForm("status", event.target.value)}>{TASK_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></label>
                <label>Due date<input type="date" value={(form as TaskForm).due_date} onChange={(event) => updateForm("due_date", event.target.value)} /></label>
              </>
            )}
            {kind === "sprints" && (
              <>
                <label>Name<input required minLength={1} maxLength={150} value={(form as SprintForm).name} onChange={(event) => updateForm("name", event.target.value)} placeholder="Sprint name" /></label>
                <label>Status<select value={(form as SprintForm).status} onChange={(event) => updateForm("status", event.target.value)}>{SPRINT_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></label>
                <label className="span-2">Goal<textarea value={(form as SprintForm).goal} onChange={(event) => updateForm("goal", event.target.value)} placeholder="Sprint goal (optional)" /></label>
                {!editingId && (
                  <label className="span-2">Related requirement (optional)
                    <select value={(form as SprintForm).requirement_id} onChange={(event) => updateForm("requirement_id", event.target.value)}>
                      <option value="">No requirement link</option>
                      {requirements.map((item) => <option key={item.id} value={item.id}>{item.requirement_key} · {item.title}</option>)}
                    </select>
                  </label>
                )}
                <label>Start date<input type="date" required value={(form as SprintForm).start_date} onChange={(event) => updateForm("start_date", event.target.value)} /></label>
                <label>End date<input type="date" required value={(form as SprintForm).end_date} onChange={(event) => updateForm("end_date", event.target.value)} /></label>
              </>
            )}
            {kind === "milestones" && (
              <>
                <label>Name<input required minLength={1} maxLength={200} value={(form as MilestoneForm).name} onChange={(event) => updateForm("name", event.target.value)} placeholder="Milestone name" /></label>
                <label>Status<select value={(form as MilestoneForm).status} onChange={(event) => updateForm("status", event.target.value)}>{MILESTONE_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></label>
                <label className="span-2">Description<textarea value={(form as MilestoneForm).description} onChange={(event) => updateForm("description", event.target.value)} placeholder="Description (optional)" /></label>
                <label>Target date<input type="date" value={(form as MilestoneForm).due_date} onChange={(event) => updateForm("due_date", event.target.value)} /></label>
              </>
            )}
            {kind === "bugs" && (
              <>
                <label>Title<input required minLength={1} maxLength={250} value={(form as BugForm).title} onChange={(event) => updateForm("title", event.target.value)} placeholder="Bug title" /></label>
                <label>Severity<select value={(form as BugForm).severity} onChange={(event) => updateForm("severity", event.target.value)}>{BUG_SEVERITIES.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}</select></label>
                <label className="span-2">Description<textarea value={(form as BugForm).description} onChange={(event) => updateForm("description", event.target.value)} placeholder="Description (optional)" /></label>
                <label>Requirement<select value={(form as BugForm).requirement_id} onChange={(event) => updateForm("requirement_id", event.target.value)}><option value="">No requirement</option>{requirements.map((item) => <option key={item.id} value={item.id}>{item.requirement_key} · {item.title}</option>)}</select></label>
                <label>Task<select value={(form as BugForm).task_id} onChange={(event) => updateForm("task_id", event.target.value)}><option value="">No task</option>{tasks.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
                <label>Assignee<select value={(form as BugForm).assigned_to_user_id} onChange={(event) => updateForm("assigned_to_user_id", event.target.value)}><option value="">Unassigned</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.user_id.slice(0, 8)}{member.project_role ? ` · ${member.project_role}` : ""}</option>)}</select></label>
                <label>Status<select value={(form as BugForm).status} onChange={(event) => updateForm("status", event.target.value)}>{BUG_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></label>
              </>
            )}
            {error && <div className="form-error span-2" role="alert">{error}</div>}
            <div className="span-2 form-actions">
              <button className="primary-button" disabled={formLoading}>{formLoading ? "Saving…" : editingId ? "Save changes" : kind === "sprints" ? "Create sprint" : kind === "milestones" ? "Create milestone" : kind === "bugs" ? "Create bug" : "Create task"}</button>
              <button type="button" className="secondary-button" onClick={cancelEdit} disabled={formLoading}>Cancel</button>
            </div>
          </form>
        </Card>
      )}
      {rows.length ? (
        (() => {
          if (kind === "tasks" && sprintColumns.length) {
            return (
              <div className="task-board">
                {sprintColumns.map((status) => (
                  <section className="task-column" key={status}>
                    <div className="column-heading">
                      <span>{status.replace("_", " ")}</span>
                      <b>{rows.filter((row) => "title" in row && "due_date" in row && row.status === status).length}</b>
                    </div>
                    {rows.filter((row) => "title" in row && "due_date" in row && row.status === status).map(rowCard)}
                  </section>
                ))}
              </div>
            );
          }
          if (kind === "sprints" && sprintColumns.length) {
            return (
              <div className="task-board">
                {sprintColumns.map((status) => (
                  <section className="task-column" key={status}>
                    <div className="column-heading">
                      <span>{status.replace("_", " ")}</span>
                      <b>{rows.filter((row) => "goal" in row && row.status === status).length}</b>
                    </div>
                    {rows.filter((row) => "goal" in row && row.status === status).map(rowCard)}
                  </section>
                ))}
              </div>
            );
          }
          if (kind === "milestones" && milestoneColumns.length) {
            return (
              <div className="task-board">
                {milestoneColumns.map((status) => (
                  <section className="task-column" key={status}>
                    <div className="column-heading">
                      <span>{status.replace("_", " ")}</span>
                      <b>{rows.filter((row) => "target_date" in row && !("due_date" in row) && row.status === status).length}</b>
                    </div>
                    {rows.filter((row) => "target_date" in row && !("due_date" in row) && row.status === status).map(rowCard)}
                  </section>
                ))}
              </div>
            );
          }
          if (kind === "bugs" && bugColumns.length) {
            return (
              <div className="task-board">
                {bugColumns.map((status) => (
                  <section className="task-column" key={status}>
                    <div className="column-heading">
                      <span>{status.replace("_", " ")}</span>
                      <b>{rows.filter((row) => "severity" in row && row.status === status).length}</b>
                    </div>
                    {rows.filter((row) => "severity" in row && row.status === status).map(rowCard)}
                  </section>
                ))}
              </div>
            );
          }
          return <Card><div className="table-list">{rows.map(rowCard)}</div></Card>;
        })()
      ) : (
        <EmptyState
          title={`No ${copy[1].toLowerCase()} yet`}
          detail={kind === "tasks" ? "No execution work has been returned for this project yet. Use New task to start tracking delivery." : `Records returned by the backend for ${project?.name ?? "this project"} will appear here.`}
        />
      )}
    </>
  );
}