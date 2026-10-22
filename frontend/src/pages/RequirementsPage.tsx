import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Requirement } from "../api/types";
import { isPotentialDuplicateRequirement, rankTraceabilitySuggestions, relationshipOptions, type SuggestionArtifact, type RankedSuggestion } from "../traceabilitySuggestions";
import { useAuth } from "../auth/AuthContext";
import { useProjects } from "../project/ProjectContext";
import { Badge, Card, EmptyAction, ErrorState, LoadingState, PageTitle } from "../ui";

export default function RequirementsPage() {
  const { canManage } = useAuth();
  const { selectedProject: project } = useProjects();
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [form, setForm] = useState({ requirement_key: "", title: "", description: "", requirement_type: "functional", priority: "medium" });
  const [creating, setCreating] = useState(false);
  const [recommendationRequirement, setRecommendationRequirement] = useState<Requirement | null>(null);
  const [suggestions, setSuggestions] = useState<RankedSuggestion[]>([]);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [recommendationError, setRecommendationError] = useState("");
  const [savingSuggestions, setSavingSuggestions] = useState(false);
  const [suggestionMessage, setSuggestionMessage] = useState("");

  const load = async () => {
    if (!project) {
      setRequirements([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setRequirements(await api.requirements(project.id));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load requirements");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [project?.id]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!project || creating) return;
    setCreating(true);
    setError("");
    try {
      const created = await api.createRequirement(project.id, form);
      setShowForm(false);
      setForm({ requirement_key: "", title: "", description: "", requirement_type: "functional", priority: "medium" });
      setRecommendationRequirement(created);
      setSuggestions([]);
      setRecommendationError("");
      setSuggestionMessage("");
      // Keep the newly created requirement visible even while related artifacts load.
      setRequirements((current) => current.some((item) => item.id === created.id) ? current : [...current, created]);
      setRecommendationLoading(true);

      try {
        const [allRequirements, tasks, bugs, testCases, sprints, existingLinks] = await Promise.all([
          api.requirements(project.id),
          api.tasks(project.id),
          api.bugs(project.id),
          api.testCases(project.id),
          api.sprints(project.id),
          api.traceabilityLinks(project.id, 100, 0),
        ]);
        setRequirements(allRequirements);

        const linkedArtifactKeys = new Set<string>();
        existingLinks.forEach((link) => {
          if (link.source_artifact_type === "requirement" && link.source_artifact_id === created.id) {
            linkedArtifactKeys.add(`${link.target_artifact_type}:${link.target_artifact_id}`);
          }
          if (link.target_artifact_type === "requirement" && link.target_artifact_id === created.id) {
            linkedArtifactKeys.add(`${link.source_artifact_type}:${link.source_artifact_id}`);
          }
        });

        const readText = (value: unknown, fields: string[]) => {
          const record = value as Record<string, unknown>;
          return fields
            .map((field) => record[field])
            .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
            .join(" ");
        };

        const candidates: SuggestionArtifact[] = [
          ...allRequirements
            .filter((item) => item.id !== created.id)
            .map((item) => ({
              id: item.id,
              type: "requirement" as const,
              label: `${item.requirement_key} — ${item.title}`,
              text: `${item.title} ${item.description}`,
              defaultRelationship: "depends_on",
            })),
          ...tasks.map((item) => ({
            id: item.id,
            type: "task" as const,
            label: item.title,
            text: readText(item, ["title", "description", "acceptance_criteria"]),
            defaultRelationship: "implements",
          })),
          ...bugs.map((item) => ({
            id: item.id,
            type: "bug" as const,
            label: item.title,
            text: readText(item, ["title", "description", "steps_to_reproduce", "expected_result"]),
            defaultRelationship: "affects",
          })),
          ...testCases.map((item) => ({
            id: item.id,
            type: "test_case" as const,
            label: item.title,
            text: readText(item, ["title", "description", "steps", "expected_result", "preconditions"]),
            defaultRelationship: "validates",
          })),
          ...sprints.map((item) => ({
            id: item.id,
            type: "sprint" as const,
            label: item.name,
            text: readText(item, ["name", "goal", "description"]),
            defaultRelationship: "belongs_to",
          })),
        ].filter((candidate) => !linkedArtifactKeys.has(`${candidate.type}:${candidate.id}`));

        const queryText = `${created.title} ${created.description}`;
        const ranked = rankTraceabilitySuggestions(queryText, candidates, 24);
        const duplicateCandidates = ranked.filter(isPotentialDuplicateRequirement).slice(0, 4);
        const relationshipCandidates = ranked.filter((suggestion) => !isPotentialDuplicateRequirement(suggestion)).slice(0, 8);
        setSuggestions([...duplicateCandidates, ...relationshipCandidates].map((suggestion) => ({
          ...suggestion,
          relationshipType: suggestion.defaultRelationship,
          selected: false,
        })));
      } catch (suggestionError) {
        setRecommendationError(
          suggestionError instanceof Error
            ? `Requirement created, but related artifacts could not be loaded: ${suggestionError.message}`
            : "Requirement created, but related artifacts could not be loaded."
        );
      } finally {
        setRecommendationLoading(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create requirement");
    } finally {
      setCreating(false);
    }
  };

  const toggleSuggestion = (key: string, selected: boolean) => {
    setSuggestions((current) => current.map((suggestion) =>
      `${suggestion.type}:${suggestion.id}` === key ? { ...suggestion, selected } : suggestion
    ));
  };

  const updateSuggestionRelationship = (key: string, relationshipType: string) => {
    setSuggestions((current) => current.map((suggestion) =>
      `${suggestion.type}:${suggestion.id}` === key ? { ...suggestion, relationshipType } : suggestion
    ));
  };

  const saveSelectedSuggestions = async () => {
    if (!project || !recommendationRequirement || savingSuggestions) return;
    const selected = suggestions.filter((suggestion) => suggestion.selected && !isPotentialDuplicateRequirement(suggestion));
    if (!selected.length) return;
    setSavingSuggestions(true);
    setRecommendationError("");
    setSuggestionMessage("");
    const savedKeys = new Set<string>();
    const failures: string[] = [];

    for (const suggestion of selected) {
      try {
        await api.createTraceabilityLink(project.id, {
          source_artifact_type: "requirement",
          source_artifact_id: recommendationRequirement.id,
          target_artifact_type: suggestion.type,
          target_artifact_id: suggestion.id,
          relationship_type: suggestion.relationshipType,
        });
        savedKeys.add(`${suggestion.type}:${suggestion.id}`);
      } catch (e) {
        failures.push(`${suggestion.label}: ${e instanceof Error ? e.message : "Unable to save link"}`);
      }
    }

    if (savedKeys.size) {
      setSuggestions((current) => current.filter((suggestion) => !savedKeys.has(`${suggestion.type}:${suggestion.id}`)));
      setSuggestionMessage(`Saved ${savedKeys.size} traceability ${savedKeys.size === 1 ? "link" : "links"}.`);
    }
    if (failures.length) {
      setRecommendationError(`Some links could not be saved: ${failures.join(" · ")}`);
    }
    setSavingSuggestions(false);
  };

  const duplicateSuggestions = suggestions.filter(isPotentialDuplicateRequirement);
  const relationshipSuggestions = suggestions.filter((suggestion) => !isPotentialDuplicateRequirement(suggestion));

  const renderSuggestionCard = (suggestion: RankedSuggestion) => {
    const key = `${suggestion.type}:${suggestion.id}`;
    const isDuplicate = isPotentialDuplicateRequirement(suggestion);
    return (
      <div key={key} style={{ display: "grid", gridTemplateColumns: "auto minmax(0, 1fr)", gap: 12, padding: 14, border: "1px solid #e5e8f0", borderRadius: 10, background: suggestion.selected ? "#f5f5ff" : "#fff" }}>
        <div style={{ marginTop: 3 }}>
          {isDuplicate ? (
            <Badge tone="warn">Review</Badge>
          ) : (
            <input
              type="checkbox"
              aria-label={`Select ${suggestion.label}`}
              checked={suggestion.selected}
              onChange={(event) => toggleSuggestion(key, event.target.checked)}
              style={{ width: 16, height: 16, accentColor: "#595ce9" }}
            />
          )}
        </div>
        <div style={{ minWidth: 0, display: "grid", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <Badge tone={isDuplicate ? "warn" : "accent"}>{isDuplicate ? "Potential duplicate / overlap" : suggestion.type.replace("_", " ")}</Badge>
            <strong style={{ minWidth: 0, color: "#26304f", fontSize: 13, overflowWrap: "anywhere" }}>{suggestion.label}</strong>
            <Badge tone={suggestion.similarity >= 0.3 ? "good" : "neutral"}>{Math.round(suggestion.similarity * 100)}% match score</Badge>
          </div>
          <div style={{ color: "#65718d", fontSize: 11, lineHeight: 1.5, display: "grid", gap: 3 }}>
            {suggestion.sharedTerms.length > 0 && <span>Shared terms: {suggestion.sharedTerms.join(", ")}</span>}
            {suggestion.matchedConcepts.length > 0 && <span>Related concepts: {suggestion.matchedConcepts.join(" · ")}</span>}
            {suggestion.sharedTerms.length === 0 && suggestion.matchedConcepts.length === 0 && <span>Matched by combined text features</span>}
            {suggestion.semanticSimilarity > 0 && <span>Concept similarity: {Math.round(suggestion.semanticSimilarity * 100)}%</span>}
          </div>
          {isDuplicate ? (
            <div style={{ display: "grid", gap: 5 }}>
              <span style={{ color: "#8b6a25", fontSize: 11 }}>The title and description overlap with the new requirement. Compare scope before creating a dependency; this suggestion will not create a traceability link.</span>
              <span><Link className="text-link" to={`/requirements/${suggestion.id}`}>Review requirement</Link></span>
            </div>
          ) : (
            <>
              <label style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", color: "#59637f", fontSize: 11, fontWeight: 700 }}>
                Relationship from {recommendationRequirement?.requirement_key ?? "new requirement"}
                <select
                  value={suggestion.relationshipType}
                  onChange={(event) => updateSuggestionRelationship(key, event.target.value)}
                  style={{ maxWidth: "100%", padding: "7px 9px", border: "1px solid #dfe3ee", borderRadius: 7, background: "#fbfcff", color: "#26304d", fontSize: 11 }}
                >
                  {relationshipOptions(suggestion.type).map((relationship) => (
                    <option key={relationship} value={relationship}>{relationship.replace("_", " ")}</option>
                  ))}
                </select>
              </label>
              {suggestion.type === "requirement" && suggestion.relationshipType === "depends_on" && (
                <span style={{ color: "#8b6a25", fontSize: 10 }}>This means the new requirement depends on the selected requirement.</span>
              )}
            </>
          )}
        </div>
      </div>
    );
  };

  // Natural sort for requirement keys (e.g., IAP-2 before IAP-10)
  const naturalSort = (a: Requirement, b: Requirement) => {
    const aKey = a.requirement_key;
    const bKey = b.requirement_key;
    const aMatch = aKey.match(/^([A-Z]+)-(\d+)$/i);
    const bMatch = bKey.match(/^([A-Z]+)-(\d+)$/i);
    if (aMatch && bMatch) {
      const aPrefix = aMatch[1].toUpperCase();
      const bPrefix = bMatch[1].toUpperCase();
      if (aPrefix !== bPrefix) return aPrefix.localeCompare(bPrefix);
      return parseInt(aMatch[2], 10) - parseInt(bMatch[2], 10);
    }
    return aKey.localeCompare(bKey);
  };

  // Priority order: critical > high > medium > low
  const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

  // Group requirements by priority, sort within each group by natural key order
  const groupedRequirements = useMemo(() => {
    const priorityGroups: Record<string, Requirement[]> = { critical: [], high: [], medium: [], low: [] };
    requirements.forEach((r) => {
      const priority = r.priority.toLowerCase();
      if (priorityGroups[priority]) priorityGroups[priority].push(r);
      else priorityGroups.medium.push(r);
    });
    return Object.entries(priorityGroups)
      .sort(([aPriority], [bPriority]) => priorityOrder[aPriority] - priorityOrder[bPriority])
      .map(([priority, items]) => ({ priority, items: items.sort(naturalSort) }));
  }, [requirements]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  const visible = groupedRequirements
    .flatMap((g) => g.items)
    .filter((item) => {
      const haystack = `${item.requirement_key} ${item.title} ${item.description}`.toLowerCase();
      return haystack.includes(query.toLowerCase()) && (statusFilter === "all" || item.status === statusFilter);
    });

  return (
    <>
      <PageTitle
        eyebrow="REQUIREMENT MANAGEMENT"
        title="Requirements"
        detail={project ? `Working in ${project.name} · ${requirements.length} recorded` : "Select a project to view requirements."}
        action={canManage && project ? (
          <button className="primary-button" onClick={() => setShowForm((value) => !value)}>
            {showForm ? "Close form" : "New requirement"}
          </button>
        ) : undefined}
      />
      {showForm && (
        <Card className="form-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">NEW REQUIREMENT</span>
              <h2>Capture a requirement</h2>
            </div>
          </div>
          <form className="form-grid" onSubmit={submit}>
            <label>Requirement key<input required value={form.requirement_key} onChange={(e) => setForm({ ...form, requirement_key: e.target.value })} placeholder="REQ-001" /></label>
            <label>Title<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Short, searchable title" /></label>
            <label className="span-2">Description<textarea required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What should the system do?" /></label>
            <label>Type<select value={form.requirement_type} onChange={(e) => setForm({ ...form, requirement_type: e.target.value })}><option value="functional">Functional</option><option value="non_functional">Non-functional</option></select></label>
            <label>Priority<select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}><option>low</option><option>medium</option><option>high</option><option>critical</option></select></label>
            <div className="span-2 form-actions">
              <button className="primary-button" disabled={creating}>{creating ? "Creating…" : "Create requirement"}</button>
              <button type="button" className="secondary-button" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </Card>
      )}
      {recommendationRequirement && (
        <Card className="form-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">TRACEABILITY SUGGESTIONS</span>
              <h2>Potential links for {recommendationRequirement.requirement_key}</h2>
              <p style={{ margin: "6px 0 0", color: "#65718d", fontSize: 12, lineHeight: 1.5 }}>
                Suggestions combine text similarity with recognized software-domain concepts. Match scores are relevance signals, not probabilities; review each relationship before approving it.
              </p>
            </div>
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                setRecommendationRequirement(null);
                setSuggestions([]);
                setRecommendationError("");
                setSuggestionMessage("");
              }}
            >
              Dismiss
            </button>
          </div>

          {recommendationLoading ? (
            <LoadingState label="Searching this project's artifacts…" />
          ) : (
            <>
              {recommendationError && (
                <div role="alert" className="error-state" style={{ padding: 12, marginBottom: 12, fontSize: 12 }}>
                  {recommendationError}
                </div>
              )}
              {suggestionMessage && (
                <div role="status" className="success-banner">{suggestionMessage}</div>
              )}

              {suggestions.length ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
                    <span style={{ color: "#65718d", fontSize: 11 }}>
                      {relationshipSuggestions.length} relationship {relationshipSuggestions.length === 1 ? "suggestion" : "suggestions"} · {duplicateSuggestions.length} possible requirement {duplicateSuggestions.length === 1 ? "overlap" : "overlaps"} · only approved links are saved
                    </span>
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={relationshipSuggestions.length === 0}
                      onClick={() => {
                        const allSelected = relationshipSuggestions.length > 0 && relationshipSuggestions.every((suggestion) => suggestion.selected);
                        setSuggestions((current) => current.map((suggestion) => ({
                          ...suggestion,
                          selected: !isPotentialDuplicateRequirement(suggestion) && !allSelected,
                        })));
                      }}
                    >
                      {relationshipSuggestions.length > 0 && relationshipSuggestions.every((suggestion) => suggestion.selected) ? "Clear selection" : "Select all links"}
                    </button>
                  </div>

                  {duplicateSuggestions.length > 0 && (
                    <section style={{ display: "grid", gap: 10, marginBottom: 18 }}>
                      <div>
                        <h3 style={{ margin: "0 0 4px", color: "#26304f", fontSize: 14 }}>Potential duplicate or overlapping requirements</h3>
                        <p style={{ margin: 0, color: "#65718d", fontSize: 11, lineHeight: 1.5 }}>These are review warnings, not dependency recommendations. DevFlow will not save them as links.</p>
                      </div>
                      {duplicateSuggestions.map(renderSuggestionCard)}
                    </section>
                  )}

                  {relationshipSuggestions.length > 0 && (
                    <section style={{ display: "grid", gap: 10 }}>
                      <div>
                        <h3 style={{ margin: "0 0 4px", color: "#26304f", fontSize: 14 }}>Suggested traceability relationships</h3>
                        <p style={{ margin: 0, color: "#65718d", fontSize: 11, lineHeight: 1.5 }}>Select only relationships that are true for your project.</p>
                      </div>
                      {relationshipSuggestions.map(renderSuggestionCard)}
                    </section>
                  )}

                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginTop: 16 }}>
                    <button
                      type="button"
                      className="primary-button"
                      disabled={savingSuggestions || !relationshipSuggestions.some((suggestion) => suggestion.selected)}
                      onClick={() => void saveSelectedSuggestions()}
                    >
                      {savingSuggestions ? "Saving links…" : `Save approved links (${relationshipSuggestions.filter((suggestion) => suggestion.selected).length})`}
                    </button>
                    <span style={{ color: "#65718d", fontSize: 10 }}>Potential duplicates are advisory only and aren't saved as relationships.</span>
                  </div>
                </>
              ) : !recommendationError && !suggestionMessage ? (
                <EmptyAction title="No strong matches found" detail="No existing artifacts shared enough distinctive text with this requirement. You can add links later from the Traceability page." />
              ) : null}
            </>
          )}
        </Card>
      )}

      <Card className="toolbar-card">
        <div className="toolbar">
          <label className="search-field">
            <span>Search</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search key, title, description…" />
          </label>
          <label className="filter-field">
            <span>Status</span>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="all">All statuses</option>
              <option value="draft">Draft</option>
              <option value="proposed">Proposed</option>
              <option value="approved">Approved</option>
              <option value="in_progress">In progress</option>
              <option value="completed">Completed</option>
              <option value="rejected">Rejected</option>
            </select>
          </label>
        </div>
      </Card>
      {visible.length ? (
        <div className="requirement-groups">
          {groupedRequirements.map((group) => {
            const groupItems = group.items.filter((item) =>
              `${item.requirement_key} ${item.title} ${item.description}`.toLowerCase().includes(query.toLowerCase()) &&
              (statusFilter === "all" || item.status === statusFilter)
            );
            if (groupItems.length === 0) return null;
            return (
              <div key={group.priority} className="priority-group">
                <div className="priority-group-header">
                  <span className="priority-label">{group.priority.charAt(0).toUpperCase() + group.priority.slice(1)}</span>
                  <Badge tone="neutral">{groupItems.length}</Badge>
                </div>
                <div className="project-list">
                  {groupItems.map((requirement) => (
                    <Link className="project-row" to={`/requirements/${requirement.id}`} key={requirement.id}>
                      <span className="project-icon">{requirement.requirement_key.slice(0, 1)}</span>
                      <span>
                        <strong>{requirement.requirement_key} · {requirement.title}</strong>
                        <small>{requirement.description}</small>
                      </span>
                      <Badge tone={requirement.status === "completed" ? "good" : requirement.status === "rejected" ? "bad" : "accent"}>{requirement.status}</Badge>
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyAction
          title="No requirements match your filters"
          detail="Adjust your search or status filter to find requirements."
        />
      )}
    </>
  );
}