import type { AnalyticsSummary, Bug, ChangeRequest, DirectoryUser, ImpactAnalysis, ImpactResult, Milestone, Project, ProjectMember, Requirement, Sprint, Task, TestCase, TraceabilityLink, User } from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const TOKEN_KEY = "devflow.access_token";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers ?? {}) },
  });
  if (response.status === 401) {
    tokenStore.clear();
    window.dispatchEvent(new Event("devflow:session-expired"));
  }
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, body?.detail ?? "The request could not be completed.");
  return body as T;
}

async function download(path: string): Promise<Blob> {
  const token = tokenStore.get();
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (response.status === 401) { tokenStore.clear(); window.dispatchEvent(new Event("devflow:session-expired")); }
  if (!response.ok) { const body = await response.json().catch(() => null); throw new ApiError(response.status, body?.detail ?? "The report could not be downloaded."); }
  return response.blob();
}

const json = (method: string, body?: unknown): RequestInit => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

export const api = {
  register: (body: { full_name: string; email: string; password: string }) => request<User>("/auth/register", json("POST", body)),
  login: (email: string, password: string) => request<{ access_token: string; user: User }>("/auth/login", json("POST", { email, password })),
  me: (token?: string) => request<User>("/auth/me", token ? { headers: { Authorization: `Bearer ${token}` } } : {}),
  projects: (limit = 100) => request<Project[]>(`/projects?limit=${limit}`),
  project: (id: string) => request<Project>(`/projects/${id}`),
  projectMembers: (projectId: string) => request<ProjectMember[]>(`/projects/${projectId}/members`),
  developerDirectory: (projectId: string, search = "") => request<DirectoryUser[]>(`/users/developers?project_id=${encodeURIComponent(projectId)}${search ? `&search=${encodeURIComponent(search)}` : ""}`),
  addProjectMember: (projectId: string, body: { user_id: string; project_role?: string }) => request<ProjectMember>(`/projects/${projectId}/members`, json("POST", body)),
  removeProjectMember: (projectId: string, userId: string) => request<void>(`/projects/${projectId}/members/${userId}`, { method: "DELETE" }),
  memberTasks: (projectId: string, userId: string) => request<Task[]>(`/projects/${projectId}/members/${userId}/tasks`),
  createProject: (body: { name: string; description?: string; status?: string }) => request<Project>("/projects", json("POST", body)),
  requirements: (projectId: string) => request<Requirement[]>(`/projects/${projectId}/requirements?limit=100`),
  createRequirement: (projectId: string, body: unknown) => request<Requirement>(`/projects/${projectId}/requirements`, json("POST", body)),
  updateRequirement: (id: string, body: unknown) => request<Requirement>(`/projects/requirements/${id}`, json("PATCH", body)),
  tasks: (projectId: string) => request<Task[]>(`/projects/${projectId}/tasks?limit=100`),
  createTask: (projectId: string, body: { title: string; description?: string; requirement_id?: string; sprint_id?: string; assigned_to_user_id?: string; priority: string; status: string; due_date?: string }) => request<Task>(`/projects/${projectId}/tasks`, json("POST", body)),
  updateTask: (id: string, body: unknown) => request<Task>(`/projects/tasks/${id}`, json("PATCH", body)),
  bugs: (projectId: string) => request<Bug[]>(`/projects/${projectId}/bugs?limit=100`),
  testCases: (projectId: string) => request<TestCase[]>(`/projects/${projectId}/test-cases?limit=100`),
  sprints: (projectId: string) => request<Sprint[]>(`/projects/${projectId}/sprints?limit=100`),
  milestones: (projectId: string) => request<Milestone[]>(`/projects/${projectId}/milestones?limit=100`),
  analyticsSummary: (projectId: string) => request<AnalyticsSummary>(`/projects/${projectId}/analytics/summary`),
  traceability: (projectId: string, requirementId: string) => request<TraceabilityLink[]>(`/projects/${projectId}/requirements/${requirementId}/traceability-links?limit=100`),
  changeRequests: (projectId: string) => request<ChangeRequest[]>(`/projects/${projectId}/change-requests?limit=100`),
  createChangeRequest: (projectId: string, requirementId: string, body: unknown) => request<ChangeRequest>(`/projects/${projectId}/requirements/${requirementId}/change-requests`, json("POST", body)),
  updateChangeRequest: (projectId: string, id: string, status: string) => request<ChangeRequest>(`/projects/${projectId}/change-requests/${id}`, json("PATCH", { status })),
  runAnalysis: (projectId: string, changeRequestId: string) => request<ImpactAnalysis>(`/projects/${projectId}/change-requests/${changeRequestId}/analyses`, json("POST")),
  analysis: (projectId: string, id: string) => request<ImpactAnalysis>(`/projects/${projectId}/analyses/${id}`),
  analysisResults: (projectId: string, id: string) => request<ImpactResult[]>(`/projects/${projectId}/analyses/${id}/results`),
  report: (projectId: string, type: "project-summary" | "sdlc-status", changeRequestId?: string) => download(changeRequestId ? `/projects/${projectId}/reports/change-impact/${changeRequestId}` : `/projects/${projectId}/reports/${type}`),
};
