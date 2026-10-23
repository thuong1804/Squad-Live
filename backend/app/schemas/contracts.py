from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

Name = Annotated[str, Field(min_length=1, max_length=200)]
Description = Annotated[str, Field(min_length=1, max_length=20000)]
Priority = Literal["low", "medium", "high", "critical", "urgent"]
Gate = Literal["requirements_approval", "plan_approval", "pm_review"]
RunStatus = Literal[
    "queued",
    "ba_in_progress",
    "requirements_approval",
    "plan_in_progress",
    "plan_approval",
    "implementation_in_progress",
    "checks_in_progress",
    "testing_in_progress",
    "reviewing_in_progress",
    "pm_review",
    "completed",
    "failed",
    "cancelled",
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", check_fields=False)
    def utc_dates(self, value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC).isoformat()
        return value


class ProjectCreate(Input):
    name: Name
    description: str = Field(default="", max_length=20000)


class ProjectUpdate(Input):
    name: Name | None = None
    description: str | None = Field(default=None, max_length=20000)
    status: Literal["active", "archived"] | None = None

    @model_validator(mode="after")
    def no_nulls(self):
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Update fields cannot be null")
        return self


class ProjectRead(Output):
    id: str
    name: str
    description: str
    owner: str
    status: Literal["active", "archived"]
    repository_path: str | None
    created_at: datetime
    updated_at: datetime


class RepositoryConnect(Input):
    path: str = Field(min_length=1, max_length=4096)


class RepositoryRead(Output):
    path: str
    branch: str | None
    head: str
    dirty: bool
    files: list[str]


class RepositoryFileRead(Output):
    path: str
    content: str


class WorkspaceFileRead(BaseModel):
    path: str
    status: str
    diff: str
    truncated: bool


class WorkspaceRead(Output):
    run_id: str
    source_path: str
    worktree_path: str
    base_commit: str
    base_branch: str | None
    created_at: datetime
    changed_files: list[str]
    untracked_files: list[str]
    files: list[WorkspaceFileRead]
    truncated: bool


class WorkspaceState(BaseModel):
    workspace: WorkspaceRead | None


class WorkspaceEditCreate(Input):
    connection_id: UUID
    paths: list[str] = Field(default_factory=list, max_length=12)


class WorkspaceEditRead(Output):
    id: str
    status: str
    summary: str | None
    files: list[str]
    source_files: list[str]
    error_code: str | None
    created_at: datetime


class WorkItemCreate(Input):
    title: Name
    description: Description
    acceptance_criteria: str = Field(default="", max_length=20000)
    priority: Priority = "medium"


class WorkItemRead(Output):
    id: str
    project_id: str
    title: str
    description: str
    acceptance_criteria: str
    priority: Priority
    status: RunStatus | Literal["draft"]
    creator: str
    created_at: datetime
    updated_at: datetime


class RunRead(Output):
    id: str
    work_item_id: str
    snapshot: dict
    status: RunStatus
    current_step: RunStatus
    attempt: int
    retryable: bool
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    failure_reason: str | None
    cancellation_reason: str | None
    revision: int
    repair_count: int
    failed_step: str | None
    gate_id: str | None
    gate_artifact_id: str | None


class ApprovalCreate(Input):
    step: Gate
    attempt: int = Field(ge=1)
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=4000)
    gate_id: str | None = Field(default=None, max_length=36)
    artifact_id: str | None = Field(default=None, max_length=36)
    return_to: Literal["ba_in_progress", "plan_in_progress"] | None = None


class ApprovalRead(Output):
    id: str
    run_id: str
    step: str
    attempt: int
    decision: str
    reviewer: str
    comment: str | None
    created_at: datetime
    revision: int
    gate_id: str | None
    artifact_id: str | None
    return_to: str | None


class ArtifactRead(Output):
    id: str
    run_id: str
    gate_id: str
    kind: str
    revision: int
    attempt: int
    content: dict
    created_at: datetime


class CancelCreate(Input):
    reason: str | None = Field(default=None, max_length=4000)


class EventRead(Output):
    id: int
    run_id: str
    event_type: str
    payload: dict
    created_at: datetime


class Page[T](BaseModel):
    items: list[T]
    limit: int
    offset: int


class DashboardRead(Output):
    counts: dict[str, int]
    recent_runs: list[RunRead]
    waiting_runs: list[RunRead]
    recent_events: list[EventRead]


class SessionRead(Output):
    identity: str


class RunCreate(Input):
    mode: Literal["mock", "ba_live", "static_site"] = "mock"
    connection_id: UUID | None = None


class CapabilitiesRead(Output):
    ba_live_available: bool
    provider: str | None
    model: str | None
    key_storage_available: bool


class AgentRunRead(Output):
    id: str
    run_id: str
    role: str
    attempt: int
    revision: int
    provider: str
    model: str
    prompt_version: str
    status: str
    created_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    context_chars: int
    error_code: str | None
    artifact_id: str | None
    connection_id: str | None


class ConnectionProbe(Input):
    provider: Literal["openai", "gemini", "deepseek"]
    api_key: str = Field(min_length=8, max_length=512, pattern=r"^[A-Za-z0-9._-]+$")


class ConnectionCreate(ConnectionProbe):
    name: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")


class ConnectionRead(Output):
    id: str
    name: str
    provider: str
    model: str
    enabled: bool
    created_at: datetime


class RetryCreate(Input):
    connection_id: UUID | None = None
