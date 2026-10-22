import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ChangeRequest, Requirement, Task, Bug, TestCase, Sprint, TraceabilityLink } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useProjects } from "../project/ProjectContext";
import { Badge, Card, EmptyState, ErrorState, LoadingState, PageTitle } from "../ui";

export default function RequirementDetailPage() {
  const { id = "" } = useParams();
  const { canManage } = useAuth();
  const { selectedProject: project } = useProjects();
  const [requirement, setRequirement] = useState<Requirement | null>(null);
  const [links, setLinks] = useState<TraceabilityLink[]>([]);
  const [changes, setChanges] = useState<ChangeRequest[]>([]);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [summary, setSummary] = useState("");
  const [artifacts, setArtifacts] = useState<{
    requirements: Requirement[];
    tasks: Task[];
    bugs: Bug[];
    testCases: TestCase[];
    sprints: Sprint[];
  } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        if (!project) throw new Error("Select a project to view this requirement");
        const [reqs, tasks, bugs, testCases, sprints, linksData, changesData] = await Promise.all([
          api.requirements(project.id),
          api.tasks(project.id),
          api.bugs(project.id),
          api.testCases(project.id),
          api.sprints(project.id),
          api.traceability(project.id, id),
          api.changeRequests(project.id),
        ]);
        const current = reqs.find((item) => item.id === id);
        if (!current) throw new Error("Requirement not found in the current project");
        setRequirement(current);
        setLinks(linksData);
        setChanges(changesData.filter((change) => change.requirement_id === id));
        setArtifacts({ requirements: reqs, tasks, bugs, testCases, sprints });
        setError("");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unable to load requirement");
      }
    };
    void load();
  }, [id, project?.id]);
  const submit = async (event: FormEvent) => { event.preventDefault(); if (!requirement) return; const projectId = requirement.project_id; try { await api.createChangeRequest(projectId, requirement.id, { change_summary: summary }); setSummary(""); setShowForm(false); setChanges((await api.changeRequests(projectId)).filter((change) => change.requirement_id === id)); } catch (e) { setError(e instanceof Error ? e.message : "Unable to create change request"); } };

  // Artifact label resolver for traceability panel
  const resolveArtifactLabel = useMemo(() => {
    if (!artifacts) return () => ({ label: "Loading...", type: "" });
    const map = new Map<string, { label: string; type: string }>();
    artifacts.requirements.forEach((r) => map.set(r.id, { label: `${r.requirement_key} — ${r.title}`, type: "requirement" }));
    artifacts.tasks.forEach((t) => map.set(t.id, { label: t.title, type: "task" }));
    artifacts.bugs.forEach((b) => map.set(b.id, { label: b.title, type: "bug" }));
    artifacts.testCases.forEach((tc) => map.set(tc.id, { label: tc.title, type: "test_case" }));
    artifacts.sprints.forEach((s) => map.set(s.id, { label: s.name, type: "sprint" }));
    return (artifactType: string, artifactId: string) => {
      const found = map.get(artifactId);
      if (found) return found;
      return { label: `Unknown ${artifactType} (${artifactId.slice(0, 8)})`, type: artifactType };
    };
  }, [artifacts]);

  if (error) return <ErrorState message={error} />; if (!requirement) return <LoadingState />;
return (
    <>
      <PageTitle
        eyebrow={requirement.requirement_key}
        title={requirement.title}
        detail={requirement.description}
        action={canManage && (
          <button className="primary-button" onClick={() => setShowForm((value) => !value)}>
            Create change request
          </button>
        )}
      />
      <div className="requirement-detail-grid">
        {/* Top section: Requirement Profile (25%) + Traceability (75%) */}
        <div className="requirement-top-section">
          {/* Requirement Profile - ~25% */}
          <Card className="requirement-profile-card">
            <div className="card-heading">
              <h2>Requirement profile</h2>
              <Badge tone="accent">v{requirement.version}</Badge>
            </div>
            <dl className="facts">
              <div>
                <dt>Type</dt>
                <dd>{requirement.requirement_type.replace("_", " ")}</dd>
              </div>
              <div>
                <dt>Priority</dt>
                <dd>
                  <Badge tone={requirement.priority === "critical" ? "bad" : "accent"}>
                    {requirement.priority}
                  </Badge>
                </dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  <Badge>{requirement.status}</Badge>
                </dd>
              </div>
            </dl>
          </Card>

          {/* Traceability - ~75% */}
          <Card className="traceability-card">
            <div className="card-heading">
              <h2>Traceability</h2>
              <Link className="text-link" to="/traceability">
                Explore
              </Link>
            </div>
            {links.length ? (
              <div className="link-list">
                {links.map((link) => {
                  const source = resolveArtifactLabel(link.source_artifact_type, link.source_artifact_id);
                  const target = resolveArtifactLabel(link.target_artifact_type, link.target_artifact_id);
                  return (
                    <div className="link-row" key={link.id}>
                      <div className="link-source">
                        <Badge tone="accent">{source.type}</Badge>
                        <span className="link-artifact-title" title={source.label}>{source.label}</span>
                      </div>
                      <div className="link-relationship">
                        <Badge tone="accent">{link.relationship_type}</Badge>
                      </div>
                      <div className="link-target">
                        <Badge tone="accent">{target.type}</Badge>
                        <span className="link-artifact-title" title={target.label}>{target.label}</span>
                      </div>
                      <span className="muted link-direction">
                        {link.source_artifact_id === requirement.id ? "outgoing" : "incoming"}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState title="No linked artifacts" detail="Traceability links will appear here when available." />
            )}
          </Card>
        </div>

        {/* Change History / Requests - Full width below */}
        <Card className="change-history-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">CHANGE HISTORY</span>
              <h2>Requests for this requirement</h2>
            </div>
            <Link className="text-link" to="/change-requests">
              All requests
            </Link>
          </div>
          {changes.length ? (
            <div className="table-list">
              {changes.map((change) => (
                <Link className="table-row" to={`/change-requests/${change.id}`} key={change.id}>
                  <span>
                    <strong>{change.change_summary}</strong>
                    <small>{new Date(change.created_at).toLocaleDateString()}</small>
                  </span>
                  <Badge>{change.status}</Badge>
                  <span className="arrow">→</span>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState title="No change requests" detail="This requirement has no recorded change requests." />
          )}
        </Card>

        {showForm && (
          <Card className="form-card">
            <form onSubmit={submit}>
              <label>
                Change summary
                <textarea
                  required
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="Describe what should change and why"
                />
              </label>
              <button className="primary-button">Submit change request</button>
            </form>
          </Card>
        )}
      </div>
    </>
  );
}
