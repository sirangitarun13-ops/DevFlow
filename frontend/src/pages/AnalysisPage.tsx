import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ChangeRequest, ImpactAnalysis, ImpactResult, Requirement } from "../api/types";
import { Badge, Card, EmptyState, ErrorState, LoadingState, Metric, PageTitle } from "../ui";
import { useProjects } from "../project/ProjectContext";
import { ReactFlow, Background, Controls, MiniMap, Handle, Position, useNodesState, useEdgesState } from "reactflow";
import "reactflow/dist/style.css";

type ArtifactKind = "requirement" | "task" | "bug" | "test_case" | "sprint";

interface ArtifactNodeData {
  label: string;
  type: string;
  id: string;
  key?: string;
}


const graphContainerStyle: React.CSSProperties = {
  height: "60vh",
  width: "100%",
  border: "1px solid #e5e8f0",
  borderRadius: 13,
  background: "#fff",
};

const typeColor: Record<string, string> = {
  requirement: "#595ce9",
  task: "#168b66",
  bug: "#c34d61",
  test_case: "#ac7416",
  sprint: "#595ce9",
};

const relationshipColors: Record<string, string> = {
  implements: "#168b66",
  validates: "#595ce9",
  affects: "#c34d61",
  belongs_to: "#ac7416",
  associated_with: "#6b7280",
  depends_on: "#d97706",
  blocks: "#dc2626",
};

const typeLabel: Record<string, string> = {
  requirement: "REQ",
  task: "TASK",
  bug: "BUG",
  test_case: "TEST",
  sprint: "SPRINT",
};

const ArtifactNode = ({ data }: { data: { label: string; type: string; id: string; key?: string } }) => (
  <div
    style={{
      position: "relative",
      border: `2px solid ${typeColor[data.type]}`,
      borderRadius: 8,
      padding: 8,
      background: "#fff",
      minWidth: 140,
      maxWidth: 200,
      boxShadow: "0 2px 6px rgba(0,0,0,0.1)",
    }}
  >
    {/* React Flow needs explicit connection handles on custom nodes to draw edges. */}
    <Handle
      type="target"
      position={Position.Left}
      style={{ width: 8, height: 8, background: "#94a3b8", border: "1px solid #fff" }}
    />
    <Handle
      type="source"
      position={Position.Right}
      style={{ width: 8, height: 8, background: "#94a3b8", border: "1px solid #fff" }}
    />
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 20,
          height: 20,
          borderRadius: 4,
          fontSize: 9,
          fontWeight: 700,
          color: "#fff",
          background: typeColor[data.type],
        }}
      >
        {typeLabel[data.type]}
      </span>
      <strong style={{ fontSize: 11 }}>{data.label}</strong>
    </div>
    <div style={{ fontSize: 9, color: "#8992a9", fontFamily: "monospace" }}>{data.id.slice(0, 8)}</div>
  </div>
);

const nodeTypes = { artifact: ArtifactNode };

export default function AnalysisPage() {
  const { id } = useParams();
  const { selectedProject: project } = useProjects();
  const [analysis, setAnalysis] = useState<ImpactAnalysis | null>(null);
  const [results, setResults] = useState<ImpactResult[]>([]);
  const [change, setChange] = useState<ChangeRequest | null>(null);
  const [requirement, setRequirement] = useState<Requirement | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Graph state
  const [viewMode, setViewMode] = useState<"full" | "focused">("focused");
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [focusDepth, setFocusDepth] = useState<1 | 2>(1);
  const [focusDirection, setFocusDirection] = useState<"both" | "outgoing" | "incoming">("both");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<ArtifactNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [tasks, setTasks] = useState<import("../api/types").Task[]>([]);
  const [bugs, setBugs] = useState<import("../api/types").Bug[]>([]);
  const [testCases, setTestCases] = useState<import("../api/types").TestCase[]>([]);
  const [sprints, setSprints] = useState<import("../api/types").Sprint[]>([]);
  const [links, setLinks] = useState<import("../api/types").TraceabilityLink[]>([]);

  const load = async () => {
    if (!project || !id) return;
    try {
      setLoading(true);
      setError("");
      const [a, rows, changes, requirements, tasks, bugs, testCases, sprints, links] = await Promise.all([
        api.analysis(project.id, id),
        api.analysisResults(project.id, id),
        api.changeRequests(project.id),
        api.requirements(project.id),
        api.tasks(project.id),
        api.bugs(project.id),
        api.testCases(project.id),
        api.sprints(project.id),
        api.traceabilityLinks(project.id, 100, 0),
      ]);
      setAnalysis(a);
      setResults(rows);
      setChange(changes.find((item) => item.id === a.change_request_id) ?? null);
      setRequirement(requirements.find((item) => item.id === a.requirement_id) ?? null);
      setRequirements(requirements);
      setTasks(tasks);
      setBugs(bugs);
      setTestCases(testCases);
      setSprints(sprints);
      setLinks(links);
      setLoading(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load analysis");
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [project?.id, id]);

  // Auto-select the analysis's requirement when data loads
  useEffect(() => {
    if (requirements.length > 0 && !selectedArtifactId && viewMode === "focused" && analysis) {
      const analysisReqKey = `requirement:${analysis.requirement_id}`;
      if (requirements.some((r) => r.id === analysis.requirement_id)) {
        setSelectedArtifactId(analysisReqKey);
      } else if (requirements.length > 0) {
        setSelectedArtifactId(`requirement:${requirements[0].id}`);
      }
    }
  }, [requirements, links, selectedArtifactId, viewMode, analysis]);

  // Apply layout to nodes when graph inputs change


  // Fullscreen handling
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    if (isFullscreen) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isFullscreen]);





  // Artifact label resolver for list view and graph
  const resolveArtifactLabel = useMemo(() => {
    return (artifactType: string, artifactId: string, artifactKey?: string | null, artifactTitle?: string | null) => {
      if (artifactKey) return `${artifactKey} — ${artifactTitle}`;
      if (artifactTitle) return artifactTitle;
      return `${artifactType} ${artifactId.slice(0, 8)}`;
    };
  }, []);

  const getArtifactDisplay = (result: ImpactResult) => {
    const typeLabel = result.artifact_type.replace("_", " ");
    const displayName = resolveArtifactLabel(
      result.artifact_type,
      result.artifact_id,
      result.artifact_key,
      result.artifact_title
    );
    return (
      <div className="artifact-display">
        <span className="artifact-type">{typeLabel}</span>
        <span className="artifact-title">{displayName}</span>
      </div>
    );
  };

  // Graph building
  const buildGraph = useMemo(() => {
    // Build artifact lookup map
    const artifactMap = new Map<string, { type: string; id: string; label: string; key?: string }>();
    requirements.forEach((r) => artifactMap.set(`requirement:${r.id}`, { type: "requirement", id: r.id, label: `${r.requirement_key} — ${r.title}`, key: r.requirement_key }));
    tasks.forEach((t) => artifactMap.set(`task:${t.id}`, { type: "task", id: t.id, label: t.title }));
    bugs.forEach((b) => artifactMap.set(`bug:${b.id}`, { type: "bug", id: b.id, label: b.title }));
    testCases.forEach((tc) => artifactMap.set(`test_case:${tc.id}`, { type: "test_case", id: tc.id, label: tc.title }));
    sprints.forEach((s) => artifactMap.set(`sprint:${s.id}`, { type: "sprint", id: s.id, label: s.name }));

    // Build adjacency lists from links
    const outgoing = new Map<string, Array<{ target: string; rel: string }>>();
    const incoming = new Map<string, Array<{ source: string; rel: string }>>();
    links.forEach((link) => {
      const sourceKey = `${link.source_artifact_type}:${link.source_artifact_id}`;
      const targetKey = `${link.target_artifact_type}:${link.target_artifact_id}`;
      if (!outgoing.has(sourceKey)) outgoing.set(sourceKey, []);
      outgoing.get(sourceKey)!.push({ target: targetKey, rel: link.relationship_type });
      if (!incoming.has(targetKey)) incoming.set(targetKey, []);
      incoming.get(targetKey)!.push({ source: sourceKey, rel: link.relationship_type });
    });

    let nodes: import("reactflow").Node<{ label: string; type: string; id: string; key?: string }, "artifact">[] = [];
    let edges: import("reactflow").Edge[] = [];
    let includedArtifactKeys = new Set<string>();

    if (viewMode === "focused" && selectedArtifactId) {
      // Focused view: selected artifact + neighbors up to focusDepth
      const visited = new Set<string>();
      const queue: Array<{ key: string; depth: number }> = [{ key: selectedArtifactId, depth: 0 }];
      visited.add(selectedArtifactId);

      while (queue.length > 0) {
        const { key, depth } = queue.shift()!;
        includedArtifactKeys.add(key);
        if (depth >= focusDepth) continue;

        // Outgoing edges
        if (focusDirection === "both" || focusDirection === "outgoing") {
          const outEdges = outgoing.get(key) || [];
          outEdges.forEach(({ target, rel }) => {
            includedArtifactKeys.add(target);
            if (!visited.has(target)) {
              visited.add(target);
              queue.push({ key: target, depth: depth + 1 });
            }
          });
        }
        // Incoming edges
        if (focusDirection === "both" || focusDirection === "incoming") {
          const inEdges = incoming.get(key) || [];
          inEdges.forEach(({ source, rel }) => {
            includedArtifactKeys.add(source);
            if (!visited.has(source)) {
              visited.add(source);
              queue.push({ key: source, depth: depth + 1 });
            }
          });
        }
      }
    } else {
      // Full view: include all artifacts
      artifactMap.forEach((_, key) => includedArtifactKeys.add(key));
    }

    // Create nodes for included artifacts
    const includedArtifacts = Array.from(includedArtifactKeys)
      .map((key) => artifactMap.get(key))
      .filter((a): a is { type: string; id: string; label: string; key?: string } => !!a);

    // Determine layout
    const isFullView = viewMode === "full";
    const typeOrder: ArtifactKind[] = ["requirement", "task", "bug", "test_case", "sprint"];

    // Compute node positions from the current graph inputs.
    let newNodes: import("reactflow").Node<{ label: string; type: string; id: string; key?: string }, "artifact">[] = [];

      if (isFullView) {
        // Column-based layout for full view
        const NODE_WIDTH = 220;
        const NODE_HEIGHT = 90;
        const HORIZONTAL_GAP = 60;
        const VERTICAL_GAP = 20;

        let typeIndex = 0;
        typeOrder.forEach((type) => {
          const artifactsOfType = includedArtifacts.filter((a) => a.type === type);
          const count = artifactsOfType.length;
          if (count === 0) return;

          const startY = 100;
          artifactsOfType.forEach((a, index) => {
            newNodes.push({
              id: `${a.type}:${a.id}`,
              type: "artifact",
              position: {
                x: 100 + typeIndex * (NODE_WIDTH + HORIZONTAL_GAP),
                y: startY + index * (NODE_HEIGHT + VERTICAL_GAP),
              },
              data: { label: a.label, type: a.type, id: a.id, key: a.key },
            });
          });
          typeIndex++;
        });
      } else if (selectedArtifactId) {
        // Layered layout for focused view
        // Build depth map from selected artifact
        const depthMap = new Map<string, number>();
        const visited = new Set<string>();
        const queue: Array<{ key: string; depth: number }> = [{ key: selectedArtifactId, depth: 0 }];
        visited.add(selectedArtifactId);

        while (queue.length > 0) {
          const { key, depth } = queue.shift()!;
          depthMap.set(key, depth);
          if (depth >= focusDepth) continue;

          if (focusDirection === "both" || focusDirection === "outgoing") {
            const outEdges = outgoing.get(key) || [];
            outEdges.forEach(({ target }) => {
              if (!visited.has(target)) {
                visited.add(target);
                queue.push({ key: target, depth: depth + 1 });
              }
            });
          }
          if (focusDirection === "both" || focusDirection === "incoming") {
            const inEdges = incoming.get(key) || [];
            inEdges.forEach(({ source }) => {
              if (!visited.has(source)) {
                visited.add(source);
                queue.push({ key: source, depth: depth + 1 });
              }
            });
          }
        }

        // Group artifacts by depth
        const artifactsByDepth = new Map<number, Array<{ type: string; id: string; label: string; key?: string }>>();
        includedArtifacts.forEach((a) => {
          const key = `${a.type}:${a.id}`;
          const depth = depthMap.get(key) ?? 0;
          if (!artifactsByDepth.has(depth)) artifactsByDepth.set(depth, []);
          artifactsByDepth.get(depth)!.push(a);
        });

        // Layout constants
        const LAYER_HORIZONTAL_SPACING = 350;
        const NODE_VERTICAL_SPACING = 130;
        const START_X = 150;
        const START_Y = 100;

        // Find max depth
        const maxDepth = Math.max(...Array.from(artifactsByDepth.keys()), 0);

        // Position nodes in layers
        artifactsByDepth.forEach((artifacts, depth) => {
          const layerX = START_X + depth * LAYER_HORIZONTAL_SPACING;
          const count = artifacts.length;
          const totalHeight = (count - 1) * NODE_VERTICAL_SPACING;
          const centerY = START_Y + (maxDepth * LAYER_HORIZONTAL_SPACING) / 2;
          const startY = centerY - totalHeight / 2;

          artifacts.forEach((a, index) => {
            const nodeId = `${a.type}:${a.id}`;
            const isCenter = nodeId === selectedArtifactId;
            newNodes.push({
              id: nodeId,
              type: "artifact",
              position: {
                x: layerX,
                y: startY + index * NODE_VERTICAL_SPACING,
              },
              data: { label: a.label, type: a.type, id: a.id, key: a.key },
              style: isCenter
                ? { border: `3px solid ${typeColor[a.type]}`, boxShadow: "0 0 16px rgba(89,92,233,0.5)" }
                : undefined,
            });
          });
        });
      }


// Create edges for included artifacts
    const newEdges = links
      .filter((link) => {
        const sourceKey = `${link.source_artifact_type}:${link.source_artifact_id}`;
        const targetKey = `${link.target_artifact_type}:${link.target_artifact_id}`;
        return includedArtifactKeys.has(sourceKey) && includedArtifactKeys.has(targetKey);
      })
      .map((link) => {
        const sourceKey = `${link.source_artifact_type}:${link.source_artifact_id}`;
        const targetKey = `${link.target_artifact_type}:${link.target_artifact_id}`;
        const relColor = relationshipColors[link.relationship_type] || "#595ce9";
        return {
          id: link.id,
          source: sourceKey,
          target: targetKey,
          label: link.relationship_type,
          animated: true,
          style: { strokeWidth: 2, stroke: relColor },
          labelStyle: { fontSize: 10, fill: relColor, fontWeight: 600 },
          labelBgStyle: { fill: "#fff", padding: 2, borderRadius: 4 },
          data: { traversal_direction: link.relationship_type === "depends_on" ? "reverse" : "forward" },
        };
      });

    return { nodes: newNodes, edges: newEdges };
  }, [requirements, tasks, bugs, testCases, sprints, links, viewMode, selectedArtifactId, focusDepth, focusDirection]);

  useEffect(() => {
    setNodes(buildGraph.nodes);
    setEdges(buildGraph.edges);
  }, [buildGraph, setNodes, setEdges]);










  // These hooks must run before conditional loading/error returns on every render.
  // The initial empty arrays are safe while the analysis data is loading.
  const impactsByType = useMemo(() => {
    const counts: Record<string, number> = {};
    results.forEach((r) => {
      counts[r.artifact_type] = (counts[r.artifact_type] || 0) + 1;
    });
    return counts;
  }, [results]);

  const highPriorityCount = useMemo(() => {
    return results.filter((r) =>
      r.artifact_type === "requirement" &&
      (requirements.find((req) => req.id === r.artifact_id)?.priority === "critical" ||
       requirements.find((req) => req.id === r.artifact_id)?.priority === "high")
    ).length;
  }, [results, requirements]);

  if (error) return <ErrorState message={error} />;
  if (!analysis || !project) return <LoadingState />;

  const direct = results.filter((result) => result.impact_category === "direct");
  const indirect = results.filter((result) => result.impact_category === "indirect");

  // Calculate max depth from relationship paths
  const maxDepth = results.reduce((max, r) => Math.max(max, (r.relationship_path?.length ?? 0)), 0);

  const resultList = (rows: ImpactResult[]) => rows.length ? (
    <div className="impact-list">
      {rows.map((result) => {
        const path = result.relationship_path?.map((step, index) => (
          <span key={`${step.link_id}-${index}`}>
            <Badge tone="accent">{step.relationship_type}</Badge>
            {step.traversal_direction === "reverse" && (
              <span className="path-reverse-badge" title="Reverse traversal (depends_on)">↶</span>
            )}
            {index < (result.relationship_path?.length ?? 0) - 1 && <span className="path-arrow">→</span>}
          </span>
        ));
        return (
          <div className="impact-row" key={result.id}>
            <div className="impact-icon">{result.artifact_type.slice(0, 1).toUpperCase()}</div>
            <div className="impact-main">
              <div>{getArtifactDisplay(result)}</div>
              <div className="path-line">{path}</div>
              <p>{result.explanation}</p>
            </div>
            <Badge tone={result.impact_category === "direct" ? "good" : "warn"}>{result.impact_category}</Badge>
          </div>
        );
      })}
    </div>
  ) : (
    <EmptyState title="No impacts in this group" detail="No propagating traceability path produced this classification." />
  );

  const reqKey = requirement?.requirement_key ?? "Unknown";
  const reqTitle = requirement?.title ?? "Requirement details";

  return (
    <div>
      <PageTitle
        eyebrow="IMPACT ANALYSIS"
        title="Requirement change impact"
        detail={change?.change_summary ?? "Persisted deterministic analysis"}
        action={<Link className="secondary-button" to={change ? `/change-requests/${change.id}` : "/change-requests"}>Back to request</Link>}
      />
      <Card className="analysis-summary">
        <div>
          <span className="eyebrow">CHANGED REQUIREMENT</span>
          <h2>{reqKey} — {reqTitle}</h2>
          <p>{reqTitle}</p>
        </div>
        <div className="analysis-meta">
          <Badge tone="good">{analysis.status}</Badge>
          <span>{new Date(analysis.started_at).toLocaleString()}</span>
        </div>
      </Card>
      <div className="metrics-grid">
        <Metric label="Total impacted" value={results.length} accent />
        <Metric label="Direct impacts" value={direct.length} />
        <Metric label="Indirect impacts" value={indirect.length} />
        <Metric label="Max impact depth" value={maxDepth} />
        <Metric label="Impacted by type" value={`${Object.entries(impactsByType).map(([type, count]) => `${type}: ${count}`).join(", ")}`} />
        <Metric label="High-priority impacted" value={highPriorityCount} />
        <Metric label="Project" value={project.name} />
      </div>

      {/* Impact Graph */}
      <div className="analysis-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">IMPACT GRAPH</span>
            <h2>Traceability-based impact propagation</h2>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <button
              className={`secondary-button ${viewMode === "focused" ? "primary-button" : ""}`}
              onClick={() => setViewMode("focused")}
            >
              Focused
            </button>
            <button
              className={`secondary-button ${viewMode === "full" ? "primary-button" : ""}`}
              onClick={() => setViewMode("full")}
            >
              Full Project
            </button>
            {viewMode === "focused" && (
              <>
                <select
                  value={selectedArtifactId || ""}
                  onChange={(e) => setSelectedArtifactId(e.target.value || null)}
                  style={{ minWidth: 300, padding: "6 10", fontSize: 13, borderRadius: 8, border: "1px solid #dfe3eb" }}
                >
                  <option value="">Select an artifact to explore…</option>
                  {requirements.map((r) => <option key={r.id} value={`requirement:${r.id}`}>{r.requirement_key} — {r.title}</option>)}
                  {tasks.map((t) => <option key={t.id} value={`task:${t.id}`}>Task: {t.title}</option>)}
                  {bugs.map((b) => <option key={b.id} value={`bug:${b.id}`}>Bug: {b.title}</option>)}
                  {testCases.map((tc) => <option key={tc.id} value={`test_case:${tc.id}`}>Test: {tc.title}</option>)}
                  {sprints.map((s) => <option key={s.id} value={`sprint:${s.id}`}>Sprint: {s.name}</option>)}
                </select>
                <select
                  value={focusDepth}
                  onChange={(e) => setFocusDepth(Number(e.target.value) as 1 | 2)}
                  style={{ padding: "6 10", fontSize: 13, borderRadius: 8, border: "1px solid #dfe3eb" }}
                >
                  <option value={1}>1-hop</option>
                  <option value={2}>2-hop</option>
                </select>
                <select
                  value={focusDirection}
                  onChange={(e) => setFocusDirection(e.target.value as "both" | "outgoing" | "incoming")}
                  style={{ padding: "6 10", fontSize: 13, borderRadius: 8, border: "1px solid #dfe3eb" }}
                >
                  <option value="both">Both directions</option>
                  <option value="outgoing">Outgoing only</option>
                  <option value="incoming">Incoming only</option>
                </select>
                {selectedArtifactId && (
                  <button className="secondary-button" onClick={() => setSelectedArtifactId(null)}>
                    Clear focus
                  </button>
                )}
              </>
            )}
            <button
              className={`secondary-button ${isFullscreen ? "primary-button" : ""}`}
              onClick={() => setIsFullscreen(!isFullscreen)}
              style={{ marginLeft: "auto" }}
            >
              {isFullscreen ? "Exit Fullscreen" : "Expand Graph"}
            </button>
          </div>
        </div>

        {/* Graph Legend */}
        <div className="toolbar-card" style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center", fontSize: 12 }}>
            <span style={{ fontWeight: 600, color: "#3a4055" }}>Legend:</span>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {Object.entries(typeColor).map(([type, color]) => (
                <span key={type} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ width: 12, height: 12, borderRadius: 3, background: color, border: `2px solid ${color}` }} />
                  <span style={{ textTransform: "capitalize" }}>{type.replace("_", " ")}</span>
                </span>
              ))}
            </div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginLeft: 16, paddingLeft: 16, borderLeft: "1px solid #e5e8f0" }}>
              {Object.entries(relationshipColors).map(([rel, color]) => (
                <span key={rel} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ width: 20, height: 3, background: color, borderRadius: 2 }} />
                  <span>{rel.replace("_", " ")}</span>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Graph Container */}
        <div
          style={{
            ...graphContainerStyle,
            position: isFullscreen ? "fixed" : "relative",
            top: isFullscreen ? 0 : undefined,
            left: isFullscreen ? 0 : undefined,
            right: isFullscreen ? 0 : undefined,
            bottom: isFullscreen ? 0 : undefined,
            height: isFullscreen ? "100vh" : "60vh",
            width: isFullscreen ? "100vw" : "100%",
            borderRadius: isFullscreen ? 0 : 13,
            border: isFullscreen ? "none" : "1px solid #e5e8f0",
            zIndex: isFullscreen ? 9999 : undefined,
            background: isFullscreen ? "#f8f9fc" : "#fff",
          }}
        >
          <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodesConnectable={false}
          fitView
          nodesDraggable={true}
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
        </div>
      </div>

      <div className="analysis-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">DIRECT IMPACTS</span>
            <h2>Immediate downstream artifacts</h2>
          </div>
          <span className="count-label">{direct.length} artifacts</span>
        </div>
        {resultList(direct)}
      </div>
      <div className="analysis-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">INDIRECT IMPACTS</span>
            <h2>Connected through the traceability path</h2>
          </div>
          <span className="count-label">{indirect.length} artifacts</span>
        </div>
        {resultList(indirect)}
      </div>
    </div>
  );
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
