import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { DirectoryUser, ProjectMember, Requirement, Sprint, Task } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useProjects } from "../project/ProjectContext";
import { Badge, Card, EmptyState, ErrorState, LoadingState, Metric, PageTitle } from "../ui";

function isDeveloper(member: ProjectMember) { return member.roles.some((role) => role.code === "developer"); }

export default function TeamPage() {
  const { canManageProject, fetchProjectMembers } = useAuth();
  const { selectedProject: project } = useProjects();
  const canManageTeam = project ? canManageProject(project.id) : false;
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [developers, setDevelopers] = useState<DirectoryUser[]>([]);
  const [selectedDeveloper, setSelectedDeveloper] = useState<ProjectMember | null>(null);
  const [developerTasks, setDeveloperTasks] = useState<Task[]>([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [loading, setLoading] = useState(true);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [directoryError, setDirectoryError] = useState("");
  const [taskError, setTaskError] = useState("");
  const [success, setSuccess] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState(false);

  const loadMembers = async () => {
    if (!project) { setMembers([]); setLoading(false); return; }
    setLoading(true);
    try { setMembers(await api.projectMembers(project.id)); setError(""); }
    catch (value) { setError(value instanceof Error ? value.message : "Unable to load project team."); }
    finally { setLoading(false); }
  };
  const loadDevelopers = async (term = search) => {
    if (!project || !canManageTeam) return;
    setDirectoryLoading(true);
    try { setDevelopers(await api.developerDirectory(project.id, term)); setDirectoryError(""); }
    catch (value) { setDirectoryError(value instanceof Error ? value.message : "Unable to load available developers."); }
    finally { setDirectoryLoading(false); }
  };
  useEffect(() => {
    void loadMembers();
    setSelectedDeveloper(null);
    setDeveloperTasks([]);
    if (project) {
      void fetchProjectMembers(project.id);
    }
  }, [project?.id, fetchProjectMembers]);
  useEffect(() => { if (showForm) void loadDevelopers(""); }, [showForm, project?.id, canManageTeam]);

  const developerMembers = useMemo(() => members.filter(isDeveloper), [members]);
  const assignedTasks = useMemo(() => developerMembers.reduce((total, member) => total + member.assigned_task_count, 0), [developerMembers]);
  const openTasks = useMemo(() => developerMembers.reduce((total, member) => total + member.in_progress_task_count + member.pending_task_count, 0), [developerMembers]);

  const addDeveloper = async (event: FormEvent) => {
    event.preventDefault();
    if (!project || !selectedUserId) return;
    setSaving(true); setError(""); setSuccess("");
    try { await api.addProjectMember(project.id, { user_id: selectedUserId, project_role: "developer" }); setSelectedUserId(""); setShowForm(false); setSuccess("Developer added to the project."); await loadMembers(); await loadDevelopers(""); }
    catch (value) { setError(value instanceof Error ? value.message : "Unable to add developer."); }
    finally { setSaving(false); }
  };
  const showTasks = async (member: ProjectMember) => {
    if (!project || !isDeveloper(member)) return;
    setSelectedDeveloper(member); setTasksLoading(true); setTaskError("");
    try { const [tasks, requirementRows, sprintRows] = await Promise.all([api.memberTasks(project.id, member.user_id), api.requirements(project.id), api.sprints(project.id)]); setDeveloperTasks(tasks); setRequirements(requirementRows); setSprints(sprintRows); }
    catch (value) { setTaskError(value instanceof Error ? value.message : "Unable to load developer tasks."); }
    finally { setTasksLoading(false); }
  };
  const removeDeveloper = async (member: ProjectMember) => {
    if (!project || !isDeveloper(member) || !window.confirm(`Remove ${member.full_name} from ${project.name}?`)) return;
    setSaving(true); setError(""); setSuccess("");
    try { await api.removeProjectMember(project.id, member.user_id); setSuccess(`${member.full_name} was removed from the project.`); if (selectedDeveloper?.user_id === member.user_id) { setSelectedDeveloper(null); setDeveloperTasks([]); } await loadMembers(); await loadDevelopers(""); }
    catch (value) { setError(value instanceof Error ? value.message : "Unable to remove developer."); }
    finally { setSaving(false); }
  };

  if (loading) return <LoadingState label="Loading project team…" />;
  if (!project) return <EmptyState title="Select a project" detail="Choose a project from the header to manage its team." />;
  if (error && !members.length) return <ErrorState message={error} onRetry={() => void loadMembers()} />;

  return <>
    <PageTitle eyebrow="TEAM MANAGEMENT" title="Team & developers" detail={`Review developers, assignment workload, and project-scoped tasks for ${project.name}.`} action={canManageTeam ? <button className="primary-button" onClick={() => { setShowForm((value) => !value); setError(""); }}>{showForm ? "Close form" : "Add developer"}</button> : undefined} />
    {success && <div className="success-banner" role="status">{success}</div>}
    {error && <div className="form-error team-error" role="alert">{error}</div>}
    <div className="metrics-grid"><Metric label="Developers" value={developerMembers.length} accent /><Metric label="Assigned tasks" value={assignedTasks} /><Metric label="In progress / pending" value={openTasks} /><Metric label="Team members" value={members.length} /></div>
    {showForm && canManageTeam && <Card className="form-card"><div className="card-heading"><div><span className="eyebrow">ADD DEVELOPER</span><h2>Assign an existing Developer</h2></div></div><form className="form-grid" onSubmit={addDeveloper}>
      <label className="span-2">Search developers<input value={search} onChange={(event) => setSearch(event.target.value)} onBlur={() => void loadDevelopers()} placeholder="Search by name or email" /></label>
      <label className="span-2">Developer<select required value={selectedUserId} onChange={(event) => setSelectedUserId(event.target.value)} disabled={directoryLoading}><option value="">{directoryLoading ? "Loading developers…" : "Select a Developer"}</option>{developers.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.full_name} · {candidate.email}</option>)}</select></label>
      {directoryError && <div className="form-error span-2" role="alert">{directoryError}</div>}
      {!directoryLoading && !directoryError && !developers.length && <p className="empty-inline span-2">No eligible Developers are available. Register a Developer or check whether they already belong to this project.</p>}
      <div className="span-2 form-actions"><button className="primary-button" disabled={saving || !selectedUserId}>{saving ? "Adding…" : "Add developer"}</button><button type="button" className="secondary-button" onClick={() => setShowForm(false)} disabled={saving}>Cancel</button></div>
    </form></Card>}
    {developerMembers.length ? <Card><div className="card-heading"><div><span className="eyebrow">DEVELOPER WORKLOAD</span><h2>Project developers</h2></div><span className="count-label">Select a developer to inspect assigned tasks</span></div><div className="team-list">{developerMembers.map((member) => <div className="team-row developer-row" key={member.user_id}><div className="avatar">{member.full_name.slice(0, 1).toUpperCase()}</div><button className="team-person team-person-button" onClick={() => void showTasks(member)}><strong>{member.full_name}</strong><small>{member.email}</small><div className="team-role-list"><Badge tone="accent">Developer</Badge></div></button><div className="team-workload"><strong>{member.assigned_task_count}</strong><small>assigned</small></div><div className="team-workload"><strong>{member.completed_task_count}</strong><small>completed</small></div><div className="team-workload"><strong>{member.in_progress_task_count}</strong><small>in progress</small></div><div className="team-workload"><strong>{member.pending_task_count}</strong><small>todo</small></div><div className="team-workload"><strong>{member.completion_percent}%</strong><small>completion</small></div>{canManageTeam && <button className="ghost-button danger-text" onClick={() => void removeDeveloper(member)} disabled={saving}>Remove</button>}</div>)}</div></Card> : <EmptyState title="No Developers assigned" detail="Add an existing Developer to start tracking project workload." />}
    {selectedDeveloper && <Card className="developer-task-card"><div className="card-heading"><div><span className="eyebrow">ASSIGNED TASKS</span><h2>{selectedDeveloper.full_name}</h2></div><Badge tone="accent">{selectedDeveloper.completion_percent}% complete</Badge></div>{tasksLoading ? <LoadingState label="Loading assigned tasks…" /> : taskError ? <ErrorState message={taskError} onRetry={() => void showTasks(selectedDeveloper)} /> : developerTasks.length ? <div className="table-list">{developerTasks.map((task) => <div className="table-row developer-task-row" key={task.id}><span className="mono">{task.id.slice(0, 8)}</span><span><strong>{task.title}</strong><small>{task.description || "No description"}</small></span><Badge tone={task.status === "completed" ? "good" : task.status === "blocked" ? "bad" : "accent"}>{task.status.replaceAll("_", " ")}</Badge><span className="task-detail-meta">Priority · {task.priority}</span><span className="task-detail-meta">{task.requirement_id ? `Requirement · ${requirements.find((item) => item.id === task.requirement_id)?.requirement_key ?? task.requirement_id.slice(0, 8)}` : "No requirement"}</span><span className="task-detail-meta">{task.sprint_id ? `Sprint · ${sprints.find((item) => item.id === task.sprint_id)?.name ?? task.sprint_id.slice(0, 8)}` : "No sprint"}</span><span className="task-detail-meta">{task.due_date ? `Due · ${task.due_date}` : "No due date"}</span></div>)}</div> : <EmptyState title="No assigned tasks" detail="This Developer has no tasks assigned in the selected project." />}</Card>}
  </>;
}
