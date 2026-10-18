"""Response schemas for project analytics."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalyticsModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectAnalytics(AnalyticsModel):
    id: UUID
    name: str
    status: str
    progress_percent: float
    progress_formula: str
    start_date: date | None
    end_date: date | None


class CountSummary(BaseModel):
    total: int
    by_status: dict[str, int]


class PrioritySummary(CountSummary):
    by_priority: dict[str, int]


class SprintAnalytics(BaseModel):
    total: int
    by_status: dict[str, int]
    active: dict[str, object] | None = None


class ImpactSummary(BaseModel):
    total_analyses: int
    by_status: dict[str, int]
    impacted_artifacts: int
    by_category: dict[str, int]


class PersonalAnalytics(BaseModel):
    tasks_total: int
    tasks_completed: int
    bugs_total: int


class ProjectAnalyticsSummary(BaseModel):
    project: ProjectAnalytics
    requirements: PrioritySummary
    milestones: CountSummary
    tasks: CountSummary
    sprints: SprintAnalytics
    bugs: CountSummary
    bugs_by_severity: dict[str, int]
    test_cases: CountSummary
    change_requests: CountSummary
    impact_analysis: ImpactSummary
    personal: PersonalAnalytics | None = None
    generated_at: datetime
