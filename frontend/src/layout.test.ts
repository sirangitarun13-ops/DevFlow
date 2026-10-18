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
});
