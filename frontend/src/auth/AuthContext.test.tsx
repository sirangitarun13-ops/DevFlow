import { describe, expect, it, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";

// Mock the api client module
vi.mock("../api/client", () => {
  const mockTokenStore = {
    get: vi.fn(),
    set: vi.fn(),
    clear: vi.fn(),
  };
  const mockApi = {
    me: vi.fn(),
    projectMembers: vi.fn(),
  };
  return {
    api: mockApi,
    tokenStore: mockTokenStore,
  };
});

import { AuthProvider, useAuth } from "./AuthContext";
import { api, tokenStore } from "../api/client";

const mockApi = vi.mocked(api);
const mockTokenStore = vi.mocked(tokenStore);

const TestComponent = () => {
  const auth = useAuth();
  const [project1CanManage, setProject1CanManage] = React.useState(false);
  const [project2CanManage, setProject2CanManage] = React.useState(false);
  const [projectRole1, setProjectRole1] = React.useState<string | null>(null);

  React.useEffect(() => {
    const fetchAndSet = async () => {
      await auth.fetchProjectMembers("project-1");
      await auth.fetchProjectMembers("project-2");
      setProject1CanManage(auth.canManageProject("project-1"));
      setProject2CanManage(auth.canManageProject("project-2"));
      setProjectRole1(auth.getProjectRole("project-1"));
    };
    fetchAndSet();
  }, [auth]);

  return (
    <div>
      <span data-testid="user-id">{auth.user?.id ?? "none"}</span>
      <span data-testid="loading">{String(auth.loading)}</span>
      <span data-testid="can-manage">{String(auth.canManage)}</span>
      <span data-testid="can-manage-project-1">{String(project1CanManage)}</span>
      <span data-testid="can-manage-project-2">{String(project2CanManage)}</span>
      <span data-testid="project-role-1">{projectRole1 ?? "none"}</span>
      <span data-testid="project-role-2">{auth.getProjectRole("project-2") ?? "none"}</span>
      <button onClick={() => auth.logout()} data-testid="logout-btn">Logout</button>
    </div>
  );
};

const renderWithAuth = (component: React.ReactNode, { withToken = false } = {}) => {
  (tokenStore.get as any).mockReturnValue(withToken ? "test-token" : null);
  return render(<BrowserRouter><AuthProvider>{component}</AuthProvider></BrowserRouter>);
};

const waitForUser = async () => {
  await waitFor(() => {
    expect(screen.getByTestId("user-id").textContent).not.toBe("none");
  });
};

describe("AuthContext project-aware permissions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns false for canManageProject when no user is logged in", async () => {
    renderWithAuth(<TestComponent />, { withToken: false });

    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("false");
      expect(screen.getByTestId("can-manage-project-2").textContent).toBe("false");
    });
  });

  it("returns true for canManageProject for global admin", async () => {
    mockApi.me.mockResolvedValue({
      id: "admin-1",
      full_name: "Admin User",
      email: "admin@example.com",
      account_status: "active",
      roles: [{ code: "admin", name: "Administrator" }],
    });

    renderWithAuth(<TestComponent />, { withToken: true });

    await waitForUser();
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("true");
      expect(screen.getByTestId("can-manage-project-2").textContent).toBe("true");
    });
  });

  it("returns true for canManageProject for global project_manager who is a project member", async () => {
    mockApi.me.mockResolvedValue({
      id: "pm-1",
      full_name: "Project Manager",
      email: "pm@example.com",
      account_status: "active",
      roles: [{ code: "project_manager", name: "Project Manager" }],
    });

    // Mock project members - user is a member of project-1 but NOT project-2
    mockApi.projectMembers.mockImplementation(async (projectId: string) => {
      if (projectId === "project-1") {
        return [
          {
            user_id: "pm-1",
            full_name: "Project Manager",
            email: "pm@example.com",
            account_status: "active",
            roles: [{ code: "project_manager", name: "Project Manager" }],
            project_role: "project_manager",
            joined_at: "2024-01-01T00:00:00Z",
            assigned_task_count: 0,
            completed_task_count: 0,
            in_progress_task_count: 0,
            pending_task_count: 0,
            completion_percent: 0,
          },
        ];
      }
      // Project 2 - user is NOT a member
      return [];
    });

    renderWithAuth(<TestComponent />, { withToken: true });

    await waitForUser();
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("true");
    });

    // Project 2 should be false since user is not a member
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-2").textContent).toBe("false");
    });
  });

  it("returns true for canManageProject for global team_lead who is a project member", async () => {
    mockApi.me.mockResolvedValue({
      id: "tl-1",
      full_name: "Team Lead",
      email: "tl@example.com",
      account_status: "active",
      roles: [{ code: "team_lead", name: "Team Lead" }],
    });

    // Mock project members - user is a member of project-1 but NOT project-2
    mockApi.projectMembers.mockImplementation(async (projectId: string) => {
      if (projectId === "project-1") {
        return [
          {
            user_id: "tl-1",
            full_name: "Team Lead",
            email: "tl@example.com",
            account_status: "active",
            roles: [{ code: "team_lead", name: "Team Lead" }],
            project_role: "team_lead",
            joined_at: "2024-01-01T00:00:00Z",
            assigned_task_count: 0,
            completed_task_count: 0,
            in_progress_task_count: 0,
            pending_task_count: 0,
            completion_percent: 0,
          },
        ];
      }
      // Project 2 - user is NOT a member
      return [];
    });

    renderWithAuth(<TestComponent />, { withToken: true });

    await waitForUser();
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("true");
    });

    // Project 2 should be false since user is not a member
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-2").textContent).toBe("false");
    });
  });

  it("returns false for canManageProject for global project_manager who is not a project member", async () => {
    mockApi.me.mockResolvedValue({
      id: "pm-1",
      full_name: "Project Manager",
      email: "pm@example.com",
      account_status: "active",
      roles: [{ code: "project_manager", name: "Project Manager" }],
    });

    // User is NOT a member of either project
    mockApi.projectMembers.mockResolvedValue([]);

    renderWithAuth(<TestComponent />, { withToken: true });

    await waitForUser();
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("false");
      expect(screen.getByTestId("can-manage-project-2").textContent).toBe("false");
    });
  });

  it("returns false for canManageProject for global team_lead who is not a project member", async () => {
    mockApi.me.mockResolvedValue({
      id: "tl-1",
      full_name: "Team Lead",
      email: "tl@example.com",
      account_status: "active",
      roles: [{ code: "team_lead", name: "Team Lead" }],
    });

    // User is NOT a member of either project
    mockApi.projectMembers.mockResolvedValue([]);

    renderWithAuth(<TestComponent />, { withToken: true });

    await waitForUser();
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("false");
      expect(screen.getByTestId("can-manage-project-2").textContent).toBe("false");
    });
  });

  it("returns true for canManageProject for client with project-scoped project_manager role", async () => {
    mockApi.me.mockResolvedValue({
      id: "client-1",
      full_name: "Client User",
      email: "client@example.com",
      account_status: "active",
      roles: [{ code: "client", name: "Client" }],
    });

    // Mock different responses for different project IDs
    mockApi.projectMembers.mockImplementation(async (projectId: string) => {
      if (projectId === "project-1") {
        return [
          {
            user_id: "client-1",
            full_name: "Client User",
            email: "client@example.com",
            account_status: "active",
            roles: [{ code: "client", name: "Client" }],
            project_role: "project_manager",
            joined_at: "2024-01-01T00:00:00Z",
            assigned_task_count: 0,
            completed_task_count: 0,
            in_progress_task_count: 0,
            pending_task_count: 0,
            completion_percent: 0,
          },
        ];
      }
      // Project 2 - user is a developer, not project_manager
      return [
        {
          user_id: "client-1",
          full_name: "Client User",
          email: "client@example.com",
          account_status: "active",
          roles: [{ code: "client", name: "Client" }],
          project_role: "developer",
          joined_at: "2024-01-01T00:00:00Z",
          assigned_task_count: 0,
          completed_task_count: 0,
          in_progress_task_count: 0,
          pending_task_count: 0,
          completion_percent: 0,
        },
      ];
    });

    renderWithAuth(<TestComponent />, { withToken: true });

    await waitForUser();
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("true");
    });

    // Project 2 should be false since user doesn't have project_manager role there
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-2").textContent).toBe("false");
    });
  });

  it("returns false for canManageProject for client without project-scoped role", async () => {
    mockApi.me.mockResolvedValue({
      id: "client-1",
      full_name: "Client User",
      email: "client@example.com",
      account_status: "active",
      roles: [{ code: "client", name: "Client" }],
    });

    mockApi.projectMembers.mockResolvedValue([
      {
        user_id: "client-1",
        full_name: "Client User",
        email: "client@example.com",
        account_status: "active",
        roles: [{ code: "client", name: "Client" }],
        project_role: "developer",
        joined_at: "2024-01-01T00:00:00Z",
        assigned_task_count: 0,
        completed_task_count: 0,
        in_progress_task_count: 0,
        pending_task_count: 0,
        completion_percent: 0,
      },
    ]);

    renderWithAuth(<TestComponent />, { withToken: true });

    await waitForUser();
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("false");
      expect(screen.getByTestId("can-manage-project-2").textContent).toBe("false");
    });
  });

  it("clears project members cache on logout", async () => {
    mockApi.me.mockResolvedValue({
      id: "admin-1",
      full_name: "Admin User",
      email: "admin@example.com",
      account_status: "active",
      roles: [{ code: "admin", name: "Administrator" }],
    });

    renderWithAuth(<TestComponent />, { withToken: true });

    await waitForUser();
    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("true");
    });

    // Click logout
    act(() => {
      screen.getByTestId("logout-btn").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("can-manage-project-1").textContent).toBe("false");
    });
  });

  it("getProjectRole returns project role from cache", async () => {
    mockApi.me.mockResolvedValue({
      id: "client-1",
      full_name: "Client User",
      email: "client@example.com",
      account_status: "active",
      roles: [{ code: "client", name: "Client" }],
    });

    mockApi.projectMembers.mockResolvedValue([
      {
        user_id: "client-1",
        full_name: "Client User",
        email: "client@example.com",
        account_status: "active",
        roles: [{ code: "client", name: "Client" }],
        project_role: "project_manager",
        joined_at: "2024-01-01T00:00:00Z",
        assigned_task_count: 0,
        completed_task_count: 0,
        in_progress_task_count: 0,
        pending_task_count: 0,
        completion_percent: 0,
      },
    ]);

    renderWithAuth(<TestComponent />, { withToken: true });

    await waitForUser();
    await waitFor(() => {
      expect(screen.getByTestId("project-role-1").textContent).toBe("project_manager");
    });
  });
});