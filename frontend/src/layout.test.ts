import { describe, expect, it } from "vitest";
import { navigationForRoles } from "./layout";

describe("role-aware navigation", () => {
  it("keeps clients in read-oriented navigation", () => {
    const paths = navigationForRoles(["client"]).map((item) => item.to);
    expect(paths).toContain("/");
    expect(paths).toContain("/projects");
    expect(paths).not.toContain("/tasks");
    expect(paths).toContain("/impact-analysis");
  });

  it("exposes management and RCIA navigation to project managers", () => {
    const paths = navigationForRoles(["project_manager"]).map((item) => item.to);
    expect(paths).toContain("/change-requests");
    expect(paths).toContain("/impact-analysis");
    expect(paths).toContain("/tasks");
    expect(paths).toContain("/team");
  });

  it("keeps team mutation controls out of non-management navigation", () => {
    expect(navigationForRoles(["team_lead"]).map((item) => item.to)).toContain("/team");
    expect(navigationForRoles(["developer"]).map((item) => item.to)).not.toContain("/team");
    expect(navigationForRoles(["client"]).map((item) => item.to)).not.toContain("/team");
  });

  it("shows Team for project-scoped project_manager when project is selected", () => {
    const canManageProject = (projectId: string) => projectId === "project-1";
    const paths = navigationForRoles(["client"], canManageProject, "project-1").map((item) => item.to);
    expect(paths).toContain("/team");
  });

  it("hides Team for project-scoped project_manager when different project is selected", () => {
    const canManageProject = (projectId: string) => projectId === "project-1";
    const paths = navigationForRoles(["client"], canManageProject, "project-2").map((item) => item.to);
    expect(paths).not.toContain("/team");
  });

  it("does not show Team when no project is selected even with project-scoped permissions", () => {
    const canManageProject = (projectId: string) => projectId === "project-1";
    const paths = navigationForRoles(["client"], canManageProject, null).map((item) => item.to);
    expect(paths).not.toContain("/team");
  });

  it("global project_manager sees Team only for projects they are a member of", () => {
    const canManageProject = (projectId: string) => projectId === "project-1";
    // Member of project-1 -> should see Team
    const paths1 = navigationForRoles(["project_manager"], canManageProject, "project-1").map((item) => item.to);
    expect(paths1).toContain("/team");
    // Not a member of project-2 -> should NOT see Team
    const paths2 = navigationForRoles(["project_manager"], canManageProject, "project-2").map((item) => item.to);
    expect(paths2).not.toContain("/team");
  });

  it("global team_lead sees Team only for projects they are a member of", () => {
    const canManageProject = (projectId: string) => projectId === "project-1";
    // Member of project-1 -> should see Team
    const paths1 = navigationForRoles(["team_lead"], canManageProject, "project-1").map((item) => item.to);
    expect(paths1).toContain("/team");
    // Not a member of project-2 -> should NOT see Team
    const paths2 = navigationForRoles(["team_lead"], canManageProject, "project-2").map((item) => item.to);
    expect(paths2).not.toContain("/team");
  });

  it("global admin sees Team regardless of project (canManageProject returns true for admin)", () => {
    const canManageProject = () => true; // Admin's canManageProject returns true for all projects
    const paths = navigationForRoles(["admin"], canManageProject, "project-2").map((item) => item.to);
    expect(paths).toContain("/team");
  });
});
