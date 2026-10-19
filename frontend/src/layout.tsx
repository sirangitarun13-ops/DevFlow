import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import type { RoleCode } from "./api/types";
import { useProjects } from "./project/ProjectContext";

export interface NavItem { label: string; to: string; roles: RoleCode[]; projectScoped?: boolean }
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/", roles: ["admin", "project_manager", "team_lead", "developer", "tester", "client"] },
  { label: "Projects", to: "/projects", roles: ["admin", "project_manager", "team_lead", "client"] },
  { label: "Requirements", to: "/requirements", roles: ["project_manager", "team_lead", "developer", "tester", "client"] },
  { label: "Milestones", to: "/milestones", roles: ["project_manager", "client"] },
  { label: "Sprints", to: "/sprints", roles: ["project_manager", "team_lead", "developer"] },
  { label: "Tasks", to: "/tasks", roles: ["project_manager", "team_lead", "developer"] },
  { label: "Team", to: "/team", roles: ["admin", "project_manager", "team_lead"], projectScoped: true },
  { label: "Bugs", to: "/bugs", roles: ["team_lead", "developer", "tester"] },
  { label: "Test Cases", to: "/test-cases", roles: ["tester"] },
  { label: "Traceability", to: "/traceability", roles: ["team_lead", "tester", "developer"] },
  { label: "Change Requests", to: "/change-requests", roles: ["project_manager", "team_lead", "client"] },
  { label: "Impact Analysis", to: "/impact-analysis", roles: ["project_manager", "team_lead", "tester", "client"] },
  { label: "Reports", to: "/reports", roles: ["admin", "project_manager", "team_lead", "tester", "client"] },
  { label: "System", to: "/system", roles: ["admin"] },
];

export function navigationForRoles(roles: RoleCode[], canManageProject?: (projectId: string) => boolean, selectedProjectId?: string | null) {
  return NAV_ITEMS.filter((item) => {
    const hasGlobalRole = item.roles.some((role) => roles.includes(role));
    if (item.projectScoped && canManageProject && selectedProjectId) {
      // For project-scoped items, project-scoped permission takes precedence over global role
      return canManageProject(selectedProjectId);
    }
    return hasGlobalRole;
  });
}

const NAV_GROUPS: Array<[string, string[]]> = [["Workspace", ["Dashboard", "Projects", "Team"]], ["Delivery", ["Requirements", "Milestones", "Sprints", "Tasks", "Bugs", "Test Cases"]], ["Impact & insight", ["Traceability", "Change Requests", "Impact Analysis", "Reports", "System"]]];

export function AppShell() {
  const { user, logout, canManageProject } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const roles = user?.roles.map((role) => role.code) ?? [];
  const { projects, selectedProject, selectedProjectId, selectProject, loading: projectsLoading } = useProjects();
  const navigation = navigationForRoles(roles, canManageProject, selectedProjectId);
  const currentLabel = navigation.find((item) => location.pathname === item.to || (item.to !== "/" && location.pathname.startsWith(item.to)))?.label ?? "Workspace";
  const changeProject = (projectId: string) => {
    selectProject(projectId);
    const projectRoute = location.pathname.match(/^\/projects\/[^/]+(\/analytics|\/reports)?$/);
    if (projectRoute) navigate(`/projects/${projectId}${projectRoute[1] ?? ""}`);
  };
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">D</span><span>Dev<span>Flow</span></span></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav aria-label="Primary navigation">{NAV_GROUPS.map(([group, labels]) => { const items = navigation.filter((item) => labels.includes(item.label)); return items.length ? <div className="nav-group" key={group}><div className="nav-group-label">{group}</div>{items.map((item) => <NavLink key={item.to} to={item.to} end={item.to === "/"} className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}><span className="nav-dot" />{item.label}</NavLink>)}</div> : null; })}</nav>
      <div className="sidebar-footer"><div className="support-card"><span className="support-dot" />API connection is client-configured</div><button className="user-chip" onClick={() => navigate("/profile")}><span className="avatar">{user?.full_name.slice(0, 1).toUpperCase()}</span><span><strong>{user?.full_name}</strong><small>Active role · {user?.roles[0]?.name ?? "Member"}</small></span></button></div>
    </aside>
    <main className="main-content"><header className="topbar"><div className="topbar-context"><div className="breadcrumb">DEVFLOW <span>/</span> {currentLabel}</div><label className="project-context-selector"><span className="context-dot" /><span className="project-selector-label">Current project</span><select aria-label="Current project" value={selectedProjectId ?? ""} onChange={(event) => changeProject(event.target.value)} disabled={projectsLoading || projects.length === 0}><option value="" disabled>{projectsLoading ? "Loading projects…" : "Select a project"}</option>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div><div className="top-actions"><span className="role-pill">Active role · {user?.roles[0]?.name ?? "Member"}</span><button className="ghost-button" onClick={logout}>Log out</button></div></header><div className="content-wrap"><Outlet /></div></main>
  </div>;
}
