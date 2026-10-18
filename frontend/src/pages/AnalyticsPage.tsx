import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AnalyticsSummary } from "../api/types";
import { Badge, Card, EmptyState, ErrorState, LoadingState, Metric, PageTitle } from "../ui";

export function distributionTotal(values: Record<string, number>): number { return Object.values(values).reduce((sum, value) => sum + value, 0); }
export function boundedPercent(value: number): number { return Math.max(0, Math.min(100, value)); }

function Distribution({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = Object.entries(values);
  const max = Math.max(...entries.map(([, value]) => value), 1);
  return <Card><div className="card-heading"><h2>{title}</h2><span className="count-label">{entries.reduce((sum, [, value]) => sum + value, 0)} total</span></div>{entries.length ? <div className="distribution-list">{entries.map(([label, value]) => <div className="distribution-row" key={label}><div className="distribution-label"><span>{label.replaceAll("_", " ")}</span><strong>{value}</strong></div><div className="distribution-track"><span style={{ width: `${(value / max) * 100}%` }} /></div></div>)}</div> : <EmptyState title="No data" detail="No records currently exist for this category." />}</Card>;
}

export default function AnalyticsPage() {
  const { id: projectId = "" } = useParams();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.analyticsSummary(projectId).then(setSummary).catch((e) => setError(e instanceof Error ? e.message : "Unable to load analytics")); }, [projectId]);
  if (error) return <ErrorState message={error} />;
  if (!summary) return <LoadingState />;
  const active = summary.sprints.active;
  return <>
    <PageTitle eyebrow="PROJECT INSIGHTS" title={`${summary.project.name} analytics`} detail="Deterministic metrics calculated from the project records." action={<Link className="secondary-button" to={`/projects/${projectId}`}>Back to project</Link>} />
    <Card className="analytics-overview"><div><span className="eyebrow">PROJECT PROGRESS</span><p>{summary.project.progress_formula}</p></div><div className="progress-ring" role="img" aria-label={`${boundedPercent(summary.project.progress_percent)}% project progress`}><span style={{ background: `conic-gradient(#7c86ff ${boundedPercent(summary.project.progress_percent) * 3.6}deg, #253052 0deg)` }}><strong>{boundedPercent(summary.project.progress_percent)}%</strong><i /></span></div></Card>
    <div className="metrics-grid"><Metric label="Requirements" value={summary.requirements.total} accent /><Metric label="Tasks" value={summary.tasks.total} /><Metric label="Open bugs" value={summary.bugs.total - (summary.bugs.by_status.resolved ?? 0) - (summary.bugs.by_status.closed ?? 0)} /><Metric label="Test cases" value={summary.test_cases.total} /><Metric label="Change requests" value={summary.change_requests.total} /><Metric label="Impacted artifacts" value={summary.impact_analysis.impacted_artifacts} /></div>
    <div className="analytics-grid"><Distribution title="Requirement status" values={summary.requirements.by_status} /><Distribution title="Task status" values={summary.tasks.by_status} /><Distribution title="Bug status" values={summary.bugs.by_status} /><Distribution title="Bug severity" values={summary.bugs_by_severity} /><Distribution title="Test status" values={summary.test_cases.by_status} /><Distribution title="Change requests" values={summary.change_requests.by_status} /></div>
    <div className="dashboard-grid"><Card><div className="card-heading"><div><span className="eyebrow">DEVELOPMENT</span><h2>Sprint progress</h2></div><Badge tone={active ? "good" : "neutral"}>{active ? "Active" : "No active sprint"}</Badge></div>{active ? <><h3>{active.name}</h3><div className="progress-bar"><span style={{ width: `${active.progress_percent}%` }} /></div><p className="muted">{active.task_completed} of {active.task_total} sprint tasks completed ({active.progress_percent}%).</p></> : <EmptyState title="No active sprint" detail="Create or activate a sprint to see sprint progress." />}</Card><Card><div className="card-heading"><div><span className="eyebrow">CHANGE IMPACT</span><h2>RCIA workload</h2></div><Link className="text-link" to="/impact-analysis">Open RCIA</Link></div><div className="signal-list"><div><span>Analyses</span><strong>{summary.impact_analysis.total_analyses}</strong></div><div><span>Direct impacts</span><strong>{summary.impact_analysis.by_category.direct ?? 0}</strong></div><div><span>Indirect impacts</span><strong>{summary.impact_analysis.by_category.indirect ?? 0}</strong></div></div></Card></div>
  </>;
}
