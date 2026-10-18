import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { AppShell } from "./layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ProjectsPage from "./pages/ProjectsPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import RequirementsPage from "./pages/RequirementsPage";
import RequirementDetailPage from "./pages/RequirementDetailPage";
import ChangeRequestsPage from "./pages/ChangeRequestsPage";
import ChangeRequestDetailPage from "./pages/ChangeRequestDetailPage";
import AnalysisPage, { ImpactAnalysisIndex } from "./pages/AnalysisPage";
import WorkPage from "./pages/WorkPage";
import TasksPage from "./pages/TasksPage";
import ProfilePage from "./pages/ProfilePage";
import AnalyticsPage from "./pages/AnalyticsPage";
import ReportsPage from "./pages/ReportsPage";
import TeamPage from "./pages/TeamPage";
import { LoadingState } from "./ui";
import { ProjectProvider } from "./project/ProjectContext";

function Protected() { const { user, loading } = useAuth(); const location = useLocation(); if (loading) return <LoadingState />; return user ? <ProjectProvider><AppShell /></ProjectProvider> : <Navigate to="/login" replace state={{ from: location.pathname }} />; }
export default function App() { return <Routes><Route path="/login" element={<LoginPage />} /><Route element={<Protected />}><Route path="/" element={<DashboardPage />} /><Route path="/projects" element={<ProjectsPage />} /><Route path="/projects/:id" element={<ProjectDetailPage />} /><Route path="/projects/:id/analytics" element={<AnalyticsPage />} /><Route path="/projects/:id/reports" element={<ReportsPage />} /><Route path="/reports" element={<ReportsPage />} /><Route path="/requirements" element={<RequirementsPage />} /><Route path="/requirements/:id" element={<RequirementDetailPage />} /><Route path="/change-requests" element={<ChangeRequestsPage />} /><Route path="/change-requests/:id" element={<ChangeRequestDetailPage />} /><Route path="/impact-analysis" element={<ImpactAnalysisIndex />} /><Route path="/impact-analysis/:id" element={<AnalysisPage />} /><Route path="/tasks" element={<TasksPage />} /><Route path="/bugs" element={<WorkPage kind="bugs" />} /><Route path="/test-cases" element={<WorkPage kind="test-cases" />} /><Route path="/sprints" element={<WorkPage kind="sprints" />} /><Route path="/milestones" element={<WorkPage kind="milestones" />} /><Route path="/team" element={<TeamPage />} /><Route path="/traceability" element={<WorkPage kind="traceability" />} /><Route path="/system" element={<WorkPage kind="system" />} /><Route path="/profile" element={<ProfilePage />} /></Route><Route path="*" element={<Navigate to="/" replace />} /></Routes>; }
