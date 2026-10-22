import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Requirement, Task, Bug, TestCase, Sprint, TraceabilityLink, TraceabilityLinkCreate } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useProjects } from "../project/ProjectContext";
import { Badge, Card, EmptyState, ErrorState, LoadingState, PageTitle } from "../ui";
import { ReactFlow, Background, Controls, MiniMap, Handle, Position, Node, Edge, useNodesState, useEdgesState } from "reactflow";
import "reactflow/dist/style.css";

type ArtifactKind = "requirement" | "task" | "bug" | "test_case" | "sprint";

interface ArtifactNodeData {
  label: string;
  type: string;
  id: string;
  key?: string;
}

type ArtifactNode = Node<{ label: string; type: string; id: string; key?: string }, "artifact">;

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
    {/* Match the Impact Analysis node UI and expose connection points for graph edges. */}
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

// Register the custom artifact renderer so Traceability uses the same polished cards as Impact Analysis.
const nodeTypes = { artifact: ArtifactNode };

export default function TraceabilityPage() {
  const { id } = useParams();
  const { canManage } = useAuth();
  const { selectedProject: project } = useProjects();
  const projectId = id;

  const [requirements, setRequirements] = useState<import("../api/types").Requirement[]>([]);
  const [tasks, setTasks] = useState<import("../api/types").Task[]>([]);
  const [bugs, setBugs] = useState<import("../api/types").Bug[]>([]);
  const [testCases, setTestCases] = useState<import("../api/types").TestCase[]>([]);
  const [sprints, setSprints] = useState<import("../api/types").Sprint[]>([]);
  const [links, setLinks] = useState<import("../api/types").TraceabilityLink[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"list" | "graph">("list");
  const [viewMode, setViewMode] = useState<"full" | "focused">("focused");
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [focusDepth, setFocusDepth] = useState<1 | 2>(1);
  const [focusDirection, setFocusDirection] = useState<"both" | "outgoing" | "incoming">("both");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const layoutInitialized = useRef(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<import("reactflow").Node<{ label: string; type: string; id: string; key?: string }, "artifact">>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Apply layout to nodes when graph inputs change
  const applyLayout = useCallback((newNodes: import("reactflow").Node<{ label: string; type: string; id: string; key?: string }, "artifact">[]) => {
    setNodes(newNodes as any);
    layoutInitialized.current = true;
  }, [setNodes]);

  // Reset layout initialization when view mode or focus changes
  useEffect(() => {
    layoutInitialized.current = false;
  }, [viewMode, selectedArtifactId, focusDepth, focusDirection]);

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

  const load = async () => {
    if (!project) return;
    try {
      setLoading(true);
      setError("");
      const [requirements, tasks, bugs, testCases, sprints, links] = await Promise.all([
        api.requirements(project.id),
        api.tasks(project.id),
        api.bugs(project.id),
        api.testCases(project.id),
        api.sprints(project.id),
        api.traceabilityLinks(project.id, 100, 0),
      ]);
      setRequirements(requirements);
      setTasks(tasks);
      setBugs(bugs);
      setTestCases(testCases);
      setSprints(sprints);
      setLinks(links);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load traceability data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [project?.id]);

  // Auto-select a relevant artifact when data loads
  useEffect(() => {
    if (requirements.length > 0 && !selectedArtifactId && viewMode === "focused") {
      // Select the requirement with the most connections
      const connectionCounts = new Map<string, number>();
      links.forEach((link) => {
        const sourceKey = `${link.source_artifact_type}:${link.source_artifact_id}`;
        const targetKey = `${link.target_artifact_type}:${link.target_artifact_id}`;
        connectionCounts.set(sourceKey, (connectionCounts.get(sourceKey) || 0) + 1);
        connectionCounts.set(targetKey, (connectionCounts.get(targetKey) || 0) + 1);
      });
      let bestArtifact: string | null = null;
      let maxConnections = 0;
      requirements.forEach((r) => {
        const key = `requirement:${r.id}`;
        const count = connectionCounts.get(key) || 0;
        if (count > maxConnections) {
          maxConnections = count;
          bestArtifact = key;
        }
      });
      if (bestArtifact) {
        setSelectedArtifactId(bestArtifact);
      } else if (requirements.length > 0) {
        setSelectedArtifactId(`requirement:${requirements[0].id}`);
      }
    }
  }, [requirements, links, selectedArtifactId, viewMode]);

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

    // Only compute new positions if layout hasn't been initialized
    if (!layoutInitialized.current) {
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
          const centerY = START_Y + (maxDepth * LAYER_HORIZONTAL_SPACING) / 2; // rough center
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

      // Apply the computed layout
      if (newNodes.length > 0) {
        applyLayout(newNodes);
      }
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

    return { nodes: [], edges: newEdges }; // Return empty nodes since we manage them via state
  }, [requirements, tasks, bugs, testCases, sprints, links, viewMode, selectedArtifactId, focusDepth, focusDirection, applyLayout]);

  // onConnect removed - connections must be created via the Add Link form to persist via backend

  const handleDeleteLink = async (linkId: string) => {
    if (!project) return;
    if (!confirm("Delete this traceability link?")) return;
    try {
      setError("");
      await api.deleteTraceabilityLink(project.id, linkId);
      setLinks((prev) => prev.filter((l) => l.id !== linkId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete link");
    }
  };

  const handleCreateLink = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!project) return;
    const formData = new FormData(event.currentTarget);
    const data: import("../api/types").TraceabilityLinkCreate = {
      source_artifact_type: formData.get("source_type") as string,
      source_artifact_id: formData.get("source_id") as string,
      target_artifact_type: formData.get("target_type") as string,
      target_artifact_id: formData.get("target_id") as string,
      relationship_type: formData.get("relationship_type") as string,
    };
    try {
      setError("");
      const link = await api.createTraceabilityLink(project.id, data);
      setLinks((prev) => [...prev, link]);
      setShowForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create link");
    }
  };

  const getArtifactOptions = (type: string) => {
    switch (type) {
      case "requirement": return requirements.map((r) => ({ value: r.id, label: `${r.requirement_key} · ${r.title}` }));
      case "task": return tasks.map((t) => ({ value: t.id, label: t.title }));
      case "bug": return bugs.map((b) => ({ value: b.id, label: b.title }));
      case "test_case": return testCases.map((tc) => ({ value: tc.id, label: tc.title }));
      case "sprint": return sprints.map((s) => ({ value: s.id, label: s.name }));
      default: return [];
    }
  };

  const allowedRelationships: Record<string, Record<string, string[]>> = {
    requirement: {
      task: ["implements", "affects", "belongs_to", "associated_with"],
      bug: ["affects", "associated_with"],
      test_case: ["validates", "associated_with"],
      sprint: ["belongs_to", "associated_with"],
      requirement: ["depends_on", "blocks"],
    },
  };

  const [showForm, setShowForm] = useState(false);
  const [sourceType, setSourceType] = useState<"requirement" | "task" | "bug" | "test_case" | "sprint">("requirement");
  const [targetType, setTargetType] = useState<"requirement" | "task" | "bug" | "test_case" | "sprint">("task");
  const [relationshipType, setRelationshipType] = useState("");

  // Artifact label resolver for list view
  const resolveArtifactLabel = useMemo(() => {
    const map = new Map<string, { label: string; type: string }>();
    requirements.forEach((r) => map.set(r.id, { label: `${r.requirement_key} — ${r.title}`, type: "requirement" }));
    tasks.forEach((t) => map.set(t.id, { label: t.title, type: "task" }));
    bugs.forEach((b) => map.set(b.id, { label: b.title, type: "bug" }));
    testCases.forEach((tc) => map.set(tc.id, { label: tc.title, type: "test_case" }));
    sprints.forEach((s) => map.set(s.id, { label: s.name, type: "sprint" }));
    return (artifactType: string, artifactId: string) => {
      const found = map.get(artifactId);
      if (found) return found;
      return { label: `Unknown ${artifactType} (${artifactId.slice(0, 8)})`, type: artifactType };
    };
  }, [requirements, tasks, bugs, testCases, sprints]);

  const sourceTypeOptions = [
    { value: "requirement", label: "Requirement" },
    { value: "task", label: "Task" },
    { value: "bug", label: "Bug" },
    { value: "test_case", label: "Test Case" },
    { value: "sprint", label: "Sprint" },
  ];
  const targetTypeOptions = [
    { value: "requirement", label: "Requirement" },
    { value: "task", label: "Task" },
    { value: "bug", label: "Bug" },
    { value: "test_case", label: "Test Case" },
    { value: "sprint", label: "Sprint" },
  ];

  const formState: Record<string, string> = { source_type: "requirement", source_id: "", target_type: "task", target_id: "", relationship_type: "" };
  const [form, setForm] = useState({ source_type: "requirement", source_id: "", target_type: "task", target_id: "", relationship_type: "" });


  if (loading) return <LoadingState label="Loading traceability…" />;
  if (error && !showForm) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!project) return <EmptyState title="Select a project" detail="Choose a project from the header to view its traceability." />;

  return (
    <>
      <PageTitle
        eyebrow="TRACEABILITY"
        title="Traceability"
        detail="Manage links between requirements, tasks, bugs, tests, and sprints."
        action={canManage && (
          <button className="primary-button" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Close form" : "Add link"}
          </button>
        )}
      />
      <div className="toolbar-card">
        <div className="toolbar">
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <button
              className={`secondary-button ${activeTab === "list" ? "primary-button" : ""}`}
              onClick={() => setActiveTab("list")}
            >
              List
            </button>
            <button
              className={`secondary-button ${activeTab === "graph" ? "primary-button" : ""}`}
              onClick={() => setActiveTab("graph")}
            >
              Graph
            </button>
          </div>
        </div>
      </div>

      {activeTab === "list" && (
        <>
          {showForm && (
            <Card className="form-card">
              <form className="form-grid" onSubmit={handleCreateLink}>
                <label>
                  Source artifact type
                  <select
                    value={form.source_type}
                    onChange={(e) => setForm({ ...form, source_type: e.target.value })}
                    required
                  >
                    <option value="requirement">Requirement</option>
                    <option value="task">Task</option>
                    <option value="bug">Bug</option>
                    <option value="test_case">Test Case</option>
                    <option value="sprint">Sprint</option>
                  </select>
                </label>
                <label>
                  Source artifact
                  <select
                    value={form.source_id}
                    onChange={(e) => setForm({ ...form, source_id: e.target.value })}
                    required
                  >
                    <option value="">Select source artifact</option>
                    {requirements.map((r) => <option key={r.id} value={r.id}>{r.requirement_key} · {r.title}</option>)}
                    {tasks.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
                    {bugs.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
                    {testCases.map((tc) => <option key={tc.id} value={tc.id}>{tc.title}</option>)}
                    {sprints.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </label>
                <label>
                  Relationship
                  <select
                    value={form.relationship_type}
                    onChange={(e) => setForm({ ...form, relationship_type: e.target.value })}
                    required
                    disabled={!form.source_type || !form.target_type}
                  >
                    <option value="">Select relationship</option>
                    {allowedRelationships[form.source_type]?.[form.target_type]?.map((rel) => (
                      <option key={rel} value={rel}>{rel.charAt(0).toUpperCase() + rel.slice(1).replace("_", " ")}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Target artifact type
                  <select
                    value={form.target_type}
                    onChange={(e) => setForm({ ...form, target_type: e.target.value })}
                    required
                  >
                    <option value="requirement">Requirement</option>
                    <option value="task">Task</option>
                    <option value="bug">Bug</option>
                    <option value="test_case">Test Case</option>
                    <option value="sprint">Sprint</option>
                  </select>
                </label>
                <label>
                  Target artifact
                  <select
                    value={form.target_id}
                    onChange={(e) => setForm({ ...form, target_id: e.target.value })}
                    required
                    disabled={!form.target_type}
                  >
                    <option value="">Select target artifact</option>
                    {requirements.map((r) => <option key={r.id} value={r.id}>{r.requirement_key} · {r.title}</option>)}
                    {tasks.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
                    {bugs.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
                    {testCases.map((tc) => <option key={tc.id} value={tc.id}>{tc.title}</option>)}
                    {sprints.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </label>
                <div className="span-2 form-actions">
                  <button className="primary-button" type="submit">Create link</button>
                  <button type="button" className="secondary-button" onClick={() => setShowForm(false)}>Cancel</button>
                </div>
              </form>
            </Card>
          )}
          {links.length ? (
            <div className="table-list">
              {links.map((link) => {
                const source = resolveArtifactLabel(link.source_artifact_type, link.source_artifact_id);
                const target = resolveArtifactLabel(link.target_artifact_type, link.target_artifact_id);
                return (
                  <div className="table-row" key={link.id}>
                    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Badge tone="accent">{link.source_artifact_type}</Badge>
                      <span style={{ fontSize: 13 }}>{source.label}</span>
                    </span>
                    <Badge tone="accent">{link.relationship_type}</Badge>
                    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Badge tone="accent">{link.target_artifact_type}</Badge>
                      <span style={{ fontSize: 13 }}>{target.label}</span>
                    </span>
                    {canManage && (
                      <button
                        className="ghost-button danger-text"
                        onClick={() => handleDeleteLink(link.id)}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState title="No traceability links" detail="Create links between requirements, tasks, bugs, tests, and sprints." />
          )}
        </>
      )}
      {activeTab === "graph" && (
        <div>
          {/* Graph Toolbar */}
          <div className="toolbar-card" style={{ marginBottom: 12 }}>
            <div className="toolbar">
              <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
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
              edges={buildGraph.edges}
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
      )}
    </>
  );
}