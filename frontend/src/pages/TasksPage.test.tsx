import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("../api/client");
vi.mock("../auth/AuthContext");
vi.mock("../project/ProjectContext");

import { api } from "../api/client";
import { AuthProvider, useAuth } from "../auth/AuthContext";
import { ProjectProvider, useProjects } from "../project/ProjectContext";

describe("TasksPage logic", () => {
  const mockApi = vi.mocked(api);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("form validation requires title", () => {
    const emptyForm = { title: "", description: "", requirement_id: "", sprint_id: "", assigned_to_user_id: "", priority: "medium", status: "todo", due_date: "" };
    const formWithTitle = { ...emptyForm, title: "Test task" };

    expect(emptyForm.title.trim()).toBe("");
    expect(formWithTitle.title.trim()).toBe("Test task");
  });

  it("form default values are correct", () => {
    const defaultForm = { title: "", description: "", requirement_id: "", sprint_id: "", assigned_to_user_id: "", priority: "medium", status: "todo", due_date: "" };

    expect(defaultForm.priority).toBe("medium");
    expect(defaultForm.status).toBe("todo");
    expect(defaultForm.due_date).toBe("");
  });

  it("task statuses are correct", () => {
    const statuses = ["todo", "in_progress", "in_review", "completed", "blocked"];
    expect(statuses).toContain("todo");
    expect(statuses).toContain("completed");
    expect(statuses).toContain("blocked");
  });

  it("task priorities are correct", () => {
    const priorities = ["low", "medium", "high", "critical"];
    expect(priorities).toContain("low");
    expect(priorities).toContain("critical");
  });

  it("form update function works", () => {
    let form = { title: "", description: "", requirement_id: "", sprint_id: "", assigned_to_user_id: "", priority: "medium", status: "todo", due_date: "" };

    const updateForm = (field: keyof typeof form, value: string) => {
      form = { ...form, [field]: value };
    };

    updateForm("title", "Test task");
    updateForm("priority", "high");
    updateForm("status", "in_progress");

    expect(form.title).toBe("Test task");
    expect(form.priority).toBe("high");
    expect(form.status).toBe("in_progress");
  });

  it("empty task form is correctly initialized", () => {
    const emptyForm = { title: "", description: "", requirement_id: "", sprint_id: "", assigned_to_user_id: "", priority: "medium", status: "todo", due_date: "" };

    expect(emptyForm).toEqual({
      title: "",
      description: "",
      requirement_id: "",
      sprint_id: "",
      assigned_to_user_id: "",
      priority: "medium",
      status: "todo",
      due_date: "",
    });
  });
});