import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ProjectMember, Requirement, Sprint, Task } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useProjects } from "../project/ProjectContext";
import { Badge, Card, EmptyState, ErrorState, LoadingState, PageTitle } from "../ui";

const TASK_STATUSES = ["todo", "in_progress", "in_review", "completed", "blocked"] as const;
const TASK_PRIORITIES = ["low", "medium", "high", "critical"] as const;

type TaskForm = {
  title: string;
  description: string;
  requirement_id: string;
  sprint_id: string;
  assigned_to_user_id: string;
  priority: string;
  status: string;
  due_date: string;
};

const emptyTaskForm: TaskForm = {
  title: "",
  description: "",
  requirement_id: "",
  sprint_id: "",
  assigned_to_user_id: "",
  priority: "medium",
  status: "todo",
  due_date: "",
};

export default function TasksPage() {
  const { canManage } = useAuth();
  const { selectedProject: project } = useProjects();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [formLoading, setFormLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<TaskForm>(emptyTaskForm);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      if (!project) {
        setTasks([]);
        return;
      }
      const [taskRows, requirementRows, sprintRows, memberRows] = await Promise.all([
        api.tasks(project.id),
        api.requirements(project.id),
        api.sprints(project.id),
        api.projectMembers(project.id),
      ]);
      setTasks(taskRows);
      setRequirements(requirementRows);
      setSprints(sprintRows);
      setMembers(memberRows);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load tasks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [project?.id]);

  const updateForm = (field: keyof TaskForm, value: string) =>
    setForm((current) => ({ ...current, [field]: value }));

  const startEdit = (task: Task) => {
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
    setEditingTaskId(task.id);
    setShowForm(true);
    setError("");
  };

  const cancelEdit = () => {
    setForm(emptyTaskForm);
    setEditingTaskId(null);
    setShowForm(false);
    setError("");
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!project || !form.title.trim()) return;
    setFormLoading(true);
    setError("");
    setSuccess("");
    try {
      const body = {
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        requirement_id: form.requirement_id || undefined,
        sprint_id: form.sprint_id || undefined,
        assigned_to_user_id: form.assigned_to_user_id || undefined,
        priority: form.priority,
        status: form.status,
        due_date: form.due_date || undefined,
      };
      if (editingTaskId) {
        await api.updateTask(editingTaskId, body);
        setSuccess("Task updated successfully.");
      } else {
        await api.createTask(project.id, body);
        setSuccess("Task created successfully.");
      }
      setForm(emptyTaskForm);
      setEditingTaskId(null);
      setShowForm(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : editingTaskId ? "Unable to update task" : "Unable to create task");
    } finally {
      setFormLoading(false);
    }
  };

  if (loading) return <LoadingState label="Loading tasks…" />;
  if (error && !showForm) return <ErrorState message={error} onRetry={() => void load()} />;

  const filteredTasks = tasks.filter((task) => {
    const matchesStatus = filterStatus === "all" || task.status === filterStatus;
    const haystack = `${task.title} ${task.description || ""}`.toLowerCase();
    const matchesSearch = haystack.includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const taskColumns = TASK_STATUSES;

  const taskCard = (task: Task) => {
    const requirement = task.requirement_id ? requirements.find((r) => r.id === task.requirement_id) : null;
    return (
      <div className="work-card" key={task.id}>
        <div className="work-card-head">
          <span className="mono">{task.id.slice(0, 8)}</span>
          <Badge tone={task.status === "completed" ? "good" : task.status === "blocked" ? "bad" : "accent"}>
            {task.status.replace("_", " ")}
          </Badge>
        </div>
        <strong>{task.title}</strong>
        <small>{task.description || "No description"}</small>
        {task.priority && <span className="work-meta">Priority · {task.priority}</span>}
        {task.due_date && <span className="work-meta">Due · {task.due_date}</span>}
        {requirement && (
          <div className="work-meta requirement-link">
            <Link to={`/requirements/${requirement.id}`} className="requirement-ref" onClick={(e) => e.stopPropagation()}>
              Requirement: {requirement.requirement_key} · {requirement.title}
            </Link>
          </div>
        )}
        {!requirement && task.requirement_id && <span className="work-meta requirement-link">Requirement not found</span>}
        {!task.requirement_id && <span className="work-meta requirement-link">No linked requirement</span>}
        <div className="task-actions">
        <select
          value={task.status}
          onChange={(e) => {
            e.stopPropagation();
            const newStatus = e.target.value;
            if (newStatus !== task.status) {
              api.updateTask(task.id, { status: newStatus })
                .then(() => load())
                .catch((err) => setError(err instanceof Error ? err.message : "Failed to update status"));
            }
          }}
          className="status-select"
          title="Change status"
        >
          {TASK_STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace("_", " ")}</option>
          ))}
        </select>
        <button className="ghost-button" onClick={() => startEdit(task)}>Edit</button>
      </div>
    </div>
  );
  };

  return (
    <>
      <PageTitle
        eyebrow="TASKS"
        title="Tasks"
        detail={project ? `Execution work items · ${project.name}` : "Select a project to manage tasks."}
        action={canManage && project ? (
          <button className="primary-button" onClick={() => { setShowForm(true); setEditingTaskId(null); setForm(emptyTaskForm); setError(""); }}>
            New task
          </button>
        ) : undefined}
      />
      {success && <div className="success-banner" role="status">{success}</div>}
      <Card className="toolbar-card">
        <div className="toolbar">
          <label className="search-field" style={{ flex: 1 }}>
            <span>Search</span>
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search title, description…"
            />
          </label>
          <label className="filter-field">
            <span>Status</span>
            <select value={filterStatus} onChange={(event) => setFilterStatus(event.target.value)}>
              <option value="all">All statuses</option>
              {TASK_STATUSES.map((status) => (
                <option key={status} value={status}>{status.replace("_", " ")}</option>
              ))}
            </select>
          </label>
        </div>
      </Card>
      {showForm && (
        <Card className="form-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">{editingTaskId ? "EDIT TASK" : "NEW TASK"}</span>
              <h2>{editingTaskId ? "Update implementation work" : "Create implementation work"}</h2>
            </div>
          </div>
          <form className="form-grid" onSubmit={handleSubmit}>
            <label>Title<input required minLength={1} maxLength={250} value={form.title} onChange={(event) => updateForm("title", event.target.value)} placeholder="Describe the work" /></label>
            <label>Priority<select value={form.priority} onChange={(event) => updateForm("priority", event.target.value)}>{TASK_PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}</select></label>
            <label className="span-2">Description<textarea value={form.description} onChange={(event) => updateForm("description", event.target.value)} placeholder="Add implementation context (optional)" /></label>
            <label>Requirement<select value={form.requirement_id} onChange={(event) => updateForm("requirement_id", event.target.value)}><option value="">No requirement</option>{requirements.map((item) => <option key={item.id} value={item.id}>{item.requirement_key} · {item.title}</option>)}</select></label>
            <label>Sprint<select value={form.sprint_id} onChange={(event) => updateForm("sprint_id", event.target.value)}><option value="">No sprint</option>{sprints.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label>Assignee<select value={form.assigned_to_user_id} onChange={(event) => updateForm("assigned_to_user_id", event.target.value)}><option value="">Unassigned</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.user_id.slice(0, 8)}{member.project_role ? ` · ${member.project_role}` : ""}</option>)}</select></label>
            <label>Status<select value={form.status} onChange={(event) => updateForm("status", event.target.value)}>{TASK_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></label>
            <label>Due date<input type="date" value={form.due_date} onChange={(event) => updateForm("due_date", event.target.value)} /></label>
            {error && <div className="form-error span-2" role="alert">{error}</div>}
            <div className="span-2 form-actions">
              <button className="primary-button" disabled={formLoading}>
                {formLoading ? (editingTaskId ? "Saving…" : "Creating…") : (editingTaskId ? "Save changes" : "Create task")}
              </button>
              <button type="button" className="secondary-button" onClick={cancelEdit} disabled={formLoading}>
                Cancel
              </button>
            </div>
          </form>
        </Card>
      )}
      {filteredTasks.length ? (
        <div className="task-board">
          {taskColumns.map((status) => (
            <section className="task-column" key={status}>
              <div className="column-heading">
                <span>{status.replace("_", " ")}</span>
                <b>{filteredTasks.filter((task) => task.status === status).length}</b>
              </div>
              {filteredTasks.filter((task) => task.status === status).map(taskCard)}
            </section>
          ))}
        </div>
      ) : (
        <EmptyState
          title={project ? "No tasks match your filters" : "No tasks yet"}
          detail={project
            ? `Adjust filters or search to find tasks in ${project.name}.`
            : "Select a project to view and manage tasks."}
        />
      )}
</>
  );
}