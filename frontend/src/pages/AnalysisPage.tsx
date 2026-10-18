import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ChangeRequest, ImpactAnalysis, ImpactResult, Requirement } from "../api/types";
import { Badge, Card, EmptyState, ErrorState, LoadingState, Metric, PageTitle } from "../ui";
import { useProjects } from "../project/ProjectContext";

export default function AnalysisPage() {
  const { id } = useParams(); const { selectedProject: project } = useProjects(); const [analysis, setAnalysis] = useState<ImpactAnalysis | null>(null); const [results, setResults] = useState<ImpactResult[]>([]); const [change, setChange] = useState<ChangeRequest | null>(null); const [requirement, setRequirement] = useState<Requirement | null>(null); const [error, setError] = useState("");
  useEffect(() => { const load = async () => { try { if (!project || !id) throw new Error("Select a project to view this analysis"); const [a, rows, changes, requirements] = await Promise.all([api.analysis(project.id, id), api.analysisResults(project.id, id), api.changeRequests(project.id), api.requirements(project.id)]); setAnalysis(a); setResults(rows); setChange(changes.find((item) => item.id === a.change_request_id) ?? null); setRequirement(requirements.find((item) => item.id === a.requirement_id) ?? null); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Unable to load analysis"); } }; void load(); }, [id, project?.id]);
  if (error) return <ErrorState message={error} />; if (!analysis || !project) return <LoadingState />;
  const direct = results.filter((result) => result.impact_category === "direct"); const indirect = results.filter((result) => result.impact_category === "indirect");
  const resultList = (rows: ImpactResult[]) => rows.length ? <div className="impact-list">{rows.map((result) => <div className="impact-row" key={result.id}><div className="impact-icon">{result.artifact_type.slice(0, 1).toUpperCase()}</div><div className="impact-main"><div><strong>{result.artifact_type.replace("_", " ")}</strong><span className="mono">{result.artifact_id}</span></div><div className="path-line">{result.relationship_path?.map((step, index) => <span key={`${step.link_id}-${index}`}><Badge tone="accent">{step.relationship_type}</Badge>{index < (result.relationship_path?.length ?? 0) - 1 && <span className="path-arrow">→</span>}</span>)}</div><p>{result.explanation}</p></div><Badge tone={result.impact_category === "direct" ? "good" : "warn"}>{result.impact_category}</Badge></div>)}</div> : <EmptyState title="No impacts in this group" detail="No propagating traceability path produced this classification." />;
  return <><PageTitle eyebrow="IMPACT ANALYSIS" title="Requirement change impact" detail={change?.change_summary ?? "Persisted deterministic analysis"} action={<Link className="secondary-button" to={change ? `/change-requests/${change.id}` : "/change-requests"}>Back to request</Link>} /><Card className="analysis-summary"><div><span className="eyebrow">CHANGED REQUIREMENT</span><h2>{requirement?.requirement_key ?? analysis.requirement_id}</h2><p>{requirement?.title ?? "Requirement details"}</p></div><div className="analysis-meta"><Badge tone="good">{analysis.status}</Badge><span>{new Date(analysis.started_at).toLocaleString()}</span></div></Card><div className="metrics-grid"><Metric label="Total impacted" value={results.length} accent /><Metric label="Direct impacts" value={direct.length} /><Metric label="Indirect impacts" value={indirect.length} /><Metric label="Project" value={project.name} /></div><div className="analysis-section"><div className="section-heading"><div><span className="eyebrow">DIRECT IMPACTS</span><h2>Immediate downstream artifacts</h2></div><span className="count-label">{direct.length} artifacts</span></div>{resultList(direct)}</div><div className="analysis-section"><div className="section-heading"><div><span className="eyebrow">INDIRECT IMPACTS</span><h2>Connected through the traceability path</h2></div><span className="count-label">{indirect.length} artifacts</span></div>{resultList(indirect)}</div></>;
}

export function ImpactAnalysisIndex() {
  const { selectedProject: project } = useProjects();
  const [changes, setChanges] = useState<ChangeRequest[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        if (!project) return;
        setChanges(await api.changeRequests(project.id));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unable to load change requests");
      }
    };
    void load();
  }, [project?.id]);

  if (error) return <ErrorState message={error} />;
  if (!project) return <LoadingState />;
  return <>
    <PageTitle eyebrow="RCIA" title="Impact Analysis" detail="Open a change request to view or run its persisted deterministic analysis." />
    {changes.length ? <Card><div className="table-list">{changes.map((change) => <Link className="table-row" key={change.id} to={`/change-requests/${change.id}`}><span className="mono">{change.id.slice(0, 8)}</span><span><strong>{change.change_summary}</strong><small>{change.status}</small></span><Badge tone={change.status === "approved" ? "good" : "neutral"}>{change.status}</Badge><span className="arrow">→</span></Link>)}</div></Card> : <EmptyState title="No change requests yet" detail="Create a change request from a requirement before running deterministic RCIA." />}
  </>;
}
