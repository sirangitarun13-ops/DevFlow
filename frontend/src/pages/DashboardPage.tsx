import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { AnalyticsSummary, Requirement, Task, Bug, TestCase, ChangeRequest } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useProjects } from "../project/ProjectContext";
import { Badge, Card, EmptyAction, ErrorState, LoadingState, Metric, PageTitle } from "../ui";

const roleCopy: Record<string, { eyebrow: string; title: string; detail: string }> = {
  client: { eyebrow: "PROJECT VIEW", title: "What is happening with your project?", detail: "A read-only view of delivery progress, requirements, and project signals." },
  project_manager: { eyebrow: "PROJECT CONTROL", title: "Keep delivery moving", detail: "Monitor requirements, execution, team workload, and change impact from one place." },
  team_lead: { eyebrow: "TECHNICAL EXECUTION", title: "Coordinate the work", detail: "Track sprint momentum, team tasks, defects, and requirement dependencies." },
  developer: { eyebrow: "MY WORK", title: "Focus on the work assigned to you", detail: "Your tasks, current progress, and the requirements behind them." },
  tester: { eyebrow: "QUALITY", title: "Protect the next release", detail: "Monitor test execution, defects, and requirements under test." },
  admin: { eyebrow: "SYSTEM OVERVIEW", title: "DevFlow at a glance", detail: "Platform-level visibility from the APIs currently available." },
};

export default function DashboardPage() {
  const { user } = useAuth();
  const { projects, selectedProject } = useProjects();
  const role = user?.roles[0]?.code ?? "client";
  const copy = roleCopy[role] ?? roleCopy.client;
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [bugs, setBugs] = useState<Bug[]>([]);
  const [tests, setTests] = useState<TestCase[]>([]);
  const [changes, setChanges] = useState<ChangeRequest[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        if (!selectedProject) {
          setRequirements([]); setTasks([]); setBugs([]); setTests([]); setChanges([]); setAnalytics(null); return;
        }
        const [req, task, bug, test, cr, summary] = await Promise.all([api.requirements(selectedProject.id), api.tasks(selectedProject.id), api.bugs(selectedProject.id), api.testCases(selectedProject.id), api.changeRequests(selectedProject.id), api.analyticsSummary(selectedProject.id)]);
        setRequirements(req); setTasks(task); setBugs(bug); setTests(test); setChanges(cr); setAnalytics(summary); setError("");
      } catch (e) { setError(e instanceof Error ? e.message : "Unable to load dashboard data"); }
      finally { setLoading(false); }
    };
    void load();
  }, [selectedProject?.id]);

  if (loading) return <LoadingState label="Loading project dashboard…" />;
  if (error) return <ErrorState message="Unable to load the project dashboard." />;
  if (!selectedProject) return <><PageTitle eyebrow={copy.eyebrow} title={copy.title} detail="Select a project from the header to focus your dashboard." /><EmptyAction title="No project selected" detail="Choose an accessible project to see its requirements, delivery progress, and quality signals." to="/projects" label="View projects" /></>;

  const pendingChanges = analytics ? Object.entries(analytics.change_requests.by_status).filter(([status]) => !["implemented", "rejected", "withdrawn"].includes(status)).reduce((sum, [, count]) => sum + count, 0) : changes.filter((change) => !["implemented", "rejected", "withdrawn"].includes(change.status)).length;
  const openBugs = analytics ? analytics.bugs.total - (analytics.bugs.by_status.resolved ?? 0) - (analytics.bugs.by_status.closed ?? 0) : bugs.filter((bug) => !["resolved", "closed"].includes(bug.status)).length;
  return <><PageTitle eyebrow={copy.eyebrow} title={copy.title} detail={`${selectedProject.name} · ${copy.detail}`} action={<Link className="primary-button" to={`/projects/${selectedProject.id}/analytics`}>Open analytics</Link>} /><div className="metrics-grid"><Metric label="Projects" value={projects.length} accent /><Metric label="Progress" value={analytics ? `${analytics.project.progress_percent}%` : "—"} /><Metric label="Requirements" value={analytics?.requirements.total ?? requirements.length} /><Metric label={role === "tester" ? "Test cases" : "Tasks"} value={analytics ? (role === "tester" ? analytics.test_cases.total : analytics.tasks.total) : (role === "tester" ? tests.length : tasks.length)} /><Metric label="Open bugs" value={openBugs} /></div><div className="dashboard-grid"><Card><div className="card-heading"><div><span className="eyebrow">CURRENT PROJECT</span><h2>{selectedProject.name}</h2></div><Link to={`/requirements`} className="text-link">View requirements</Link></div>{requirements.length ? <div className="project-list">{requirements.slice(0, 5).map((requirement) => <Link className="project-row" to={`/requirements/${requirement.id}`} key={requirement.id}><span className="project-icon">{requirement.requirement_key.slice(0, 1)}</span><span><strong>{requirement.requirement_key} · {requirement.title}</strong><small>{requirement.description}</small></span><Badge tone={requirement.status === "completed" ? "good" : "accent"}>{requirement.status}</Badge></Link>)}</div> : <EmptyAction title="No requirements yet" detail="Capture the product behavior this project needs to deliver." to="/requirements" label="Open requirements" />}</Card><Card><div className="card-heading"><div><span className="eyebrow">DELIVERY SIGNALS</span><h2>Current focus</h2></div></div><div className="signal-list"><div><span>Pending change requests</span><strong>{pendingChanges}</strong></div><div><span>In-progress tasks</span><strong>{analytics?.tasks.by_status.in_progress ?? tasks.filter((task) => task.status === "in_progress").length}</strong></div><div><span>Failed tests</span><strong>{analytics?.test_cases.by_status.failed ?? tests.filter((test) => test.status === "failed").length}</strong></div></div></Card></div></>;
}
