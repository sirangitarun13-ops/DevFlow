import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, tokenStore } from "../api/client";
import type { RoleCode, User, ProjectMember } from "../api/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (fullName: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (...roles: RoleCode[]) => boolean;
  canManage: boolean;
  canManageProject: (projectId: string) => boolean;
  getProjectRole: (projectId: string) => string | null;
  fetchProjectMembers: (projectId: string) => Promise<ProjectMember[]>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function getUserProjectRole(user: User | null, projectMembers: ProjectMember[]): string | null {
  if (!user) return null;
  const member = projectMembers.find((m) => m.user_id === user.id);
  return member?.project_role ?? null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [projectMembersCache, setProjectMembersCache] = useState<Map<string, ProjectMember[]>>(new Map());

  useEffect(() => {
    const restore = async () => {
      if (tokenStore.get()) {
        try {
          setUser(await api.me());
        } catch {
          tokenStore.clear();
        }
      }
      setLoading(false);
    };
    void restore();
    const expired = () => setUser(null);
    window.addEventListener("devflow:session-expired", expired);
    // Periodically validate session by calling /auth/me
    const interval = setInterval(async () => {
      if (tokenStore.get()) {
        try {
          await api.me();
        } catch {
          tokenStore.clear();
          setUser(null);
        }
      }
    }, 5 * 60 * 1000); // Check every 5 minutes
    return () => {
      window.removeEventListener("devflow:session-expired", expired);
      clearInterval(interval);
    };
  }, []);

  const fetchProjectMembers = async (projectId: string): Promise<ProjectMember[]> => {
    const cached = projectMembersCache.get(projectId);
    if (cached) return cached;
    try {
      const members = await api.projectMembers(projectId);
      setProjectMembersCache((prev) => new Map(prev).set(projectId, members));
      return members;
    } catch {
      // On failure (e.g., 403), return empty array so canManageProject safely returns false
      // without unhandled promise rejection. Do not grant permissions on lookup failure.
      return [];
    }
  };

  const getProjectRole = (projectId: string): string | null => {
    const members = projectMembersCache.get(projectId);
    if (!members) return null;
    return getUserProjectRole(user, members);
  };

  const canManageProject = (projectId: string): boolean => {
    if (!user) return false;
    const codes = user.roles.map((role) => role.code);
    // Global admin has access to all projects
    if (codes.includes("admin")) return true;
    // Check project access: user must be a member of the project (or creator, which makes them a member)
    const members = projectMembersCache.get(projectId);
    if (!members) return false;
    const isMember = members.some((m) => m.user_id === user.id);
    if (!isMember) return false;
    // User has project access - now check management authority
    // Global project_manager and team_lead have management authority within accessible projects
    if (codes.includes("project_manager") || codes.includes("team_lead")) return true;
    // Project-specific project_manager role
    const projectRole = getUserProjectRole(user, members);
    if (projectRole === "project_manager") return true;
    return false;
  };

  const value = useMemo<AuthContextValue>(() => {
    const codes = user?.roles.map((role) => role.code) ?? [];
    return {
      user,
      loading,
      login: async (email, password) => { const result = await api.login(email, password); tokenStore.set(result.access_token); setUser(await api.me(result.access_token)); },
      register: async (fullName, email, password) => { await api.register({ full_name: fullName, email, password }); },
      logout: () => { tokenStore.clear(); setUser(null); setProjectMembersCache(new Map()); },
      hasRole: (...roles) => roles.some((role) => codes.includes(role)),
      canManage: codes.some((role) => ["admin", "project_manager", "team_lead"].includes(role)),
      canManageProject,
      getProjectRole,
      fetchProjectMembers,
    };
  }, [user, loading, projectMembersCache]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error("useAuth must be used inside AuthProvider"); return value; }