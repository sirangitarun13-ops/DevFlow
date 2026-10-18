import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Project } from "../api/types";

const SELECTED_PROJECT_KEY = "devflow.selected_project_id";

interface ProjectContextValue {
  projects: Project[];
  selectedProject: Project | null;
  selectedProjectId: string | null;
  loading: boolean;
  error: string;
  selectProject: (projectId: string) => void;
  reloadProjects: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(() => localStorage.getItem(SELECTED_PROJECT_KEY));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reloadProjects = async () => {
    setLoading(true);
    try {
      const accessible = await api.projects();
      setProjects(accessible);
      setSelectedProjectId((current) => {
        const routeId = location.pathname.match(/^\/projects\/([^/]+)/)?.[1];
        const preferred = routeId && accessible.some((project) => project.id === routeId) ? routeId : current;
        const next = preferred && accessible.some((project) => project.id === preferred) ? preferred : accessible[0]?.id ?? null;
        if (next) localStorage.setItem(SELECTED_PROJECT_KEY, next);
        else localStorage.removeItem(SELECTED_PROJECT_KEY);
        return next;
      });
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load projects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!user) {
      setProjects([]);
      setSelectedProjectId(null);
      setLoading(false);
      return;
    }
    void reloadProjects();
  }, [user?.id]);

  useEffect(() => {
    const routeId = location.pathname.match(/^\/projects\/([^/]+)/)?.[1];
    if (routeId && projects.some((project) => project.id === routeId) && routeId !== selectedProjectId) {
      setSelectedProjectId(routeId);
      localStorage.setItem(SELECTED_PROJECT_KEY, routeId);
    }
  }, [location.pathname, projects, selectedProjectId]);

  const selectProject = (projectId: string) => {
    if (!projects.some((project) => project.id === projectId)) return;
    setSelectedProjectId(projectId);
    localStorage.setItem(SELECTED_PROJECT_KEY, projectId);
  };

  const value = useMemo(() => ({ projects, selectedProject: projects.find((project) => project.id === selectedProjectId) ?? null, selectedProjectId, loading, error, selectProject, reloadProjects }), [projects, selectedProjectId, loading, error]);
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProjects() {
  const value = useContext(ProjectContext);
  if (!value) throw new Error("useProjects must be used inside ProjectProvider");
  return value;
}
