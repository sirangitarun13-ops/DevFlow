export type RoleCode = "admin" | "project_manager" | "team_lead" | "developer" | "tester" | "client";

export interface Role { code: RoleCode; name: string }
export interface User { id: string; full_name: string; email: string; account_status: string; roles: Role[] }
export interface ProjectMember { user_id: string; full_name: string; email: string; account_status: string; roles: Role[]; project_role: string | null; joined_at: string; assigned_task_count: number; completed_task_count: number; in_progress_task_count: number; pending_task_count: number; completion_percent: number }
export interface DirectoryUser { id: string; full_name: string; email: string; account_status: string; roles: Role[] }
export interface Project { id: string; name: string; description: string | null; status: string; start_date: string | null; end_date: string | null; created_by_user_id: string; created_at: string; updated_at: string }
export interface Requirement { id: string; project_id: string; requirement_key: string; title: string; description: string; requirement_type: string; priority: string; status: string; version: number }
export interface Task { id: string; project_id: string; requirement_id: string | null; sprint_id: string | null; title: string; description?: string | null; assigned_to_user_id: string | null; priority: string; status: string; due_date?: string | null }
export interface Bug { id: string; project_id: string; requirement_id: string | null; task_id: string | null; title: string; severity: string; status: string; assigned_to_user_id: string | null }
export interface TestCase { id: string; project_id: string; requirement_id: string; title: string; status: string }
export interface Sprint { id: string; project_id: string; name: string; goal: string | null; start_date: string; end_date: string; status: string }
export interface Milestone { id: string; project_id: string; name: string; description: string | null; due_date: string | null; status: string }
export interface TraceabilityLink { id: string; project_id: string; source_artifact_type: string; source_artifact_id: string; target_artifact_type: string; target_artifact_id: string; relationship_type: string; created_by_user_id: string; created_at: string }
export interface ChangeRequest { id: string; requirement_id: string; requested_by_user_id: string; reviewed_by_user_id: string | null; change_summary: string; proposed_description: string | null; proposed_priority: string | null; proposed_status: string | null; status: string; reviewed_at: string | null; implemented_at: string | null; created_at: string; updated_at: string }
export interface ImpactAnalysis { id: string; project_id: string; requirement_id: string; change_request_id: string | null; initiated_by_user_id: string; status: string; summary: string | null; started_at: string; completed_at: string | null }
export interface ImpactResult { id: string; impact_analysis_id: string; artifact_type: string; artifact_id: string; impact_category: "direct" | "indirect"; relationship_path: Array<Record<string, string>> | null; explanation: string; created_at: string }
export interface AnalyticsSummary {
  project: { id: string; name: string; status: string; progress_percent: number; progress_formula: string; start_date: string | null; end_date: string | null };
  requirements: { total: number; by_status: Record<string, number>; by_priority: Record<string, number> };
  milestones: { total: number; by_status: Record<string, number> };
  tasks: { total: number; by_status: Record<string, number> };
  sprints: { total: number; by_status: Record<string, number>; active: { id: string; name: string; status: string; task_total: number; task_completed: number; progress_percent: number } | null };
  bugs: { total: number; by_status: Record<string, number> };
  bugs_by_severity: Record<string, number>;
  test_cases: { total: number; by_status: Record<string, number> };
  change_requests: { total: number; by_status: Record<string, number> };
  impact_analysis: { total_analyses: number; by_status: Record<string, number>; impacted_artifacts: number; by_category: Record<string, number> };
  personal: { tasks_total: number; tasks_completed: number; bugs_total: number } | null;
  generated_at: string;
}
