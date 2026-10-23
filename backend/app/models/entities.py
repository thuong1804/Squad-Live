from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(UTC)


def new_id():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Project(Identity, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    repository_path: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class WorkItem(Identity, Base):
    __tablename__ = "work_items"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(40), default="draft")
    creator: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class WorkflowRun(Identity, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (UniqueConstraint("work_item_id", "idempotency_key"),)
    work_item_id: Mapped[str] = mapped_column(ForeignKey("work_items.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(40), index=True, default="queued")
    current_step: Mapped[str] = mapped_column(String(40), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool] = mapped_column(default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    repair_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_step: Mapped[str | None] = mapped_column(String(40))
    gate_id: Mapped[str | None] = mapped_column(String(36))
    gate_artifact_id: Mapped[str | None] = mapped_column(String(36))
    connection_id: Mapped[str | None] = mapped_column(String(36))


class Approval(Identity, Base):
    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint("run_id", "step", "attempt", "revision", name="uq_approval_revision"),
    )
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    step: Mapped[str] = mapped_column(String(40))
    attempt: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16))
    reviewer: Mapped[str] = mapped_column(String(200))
    comment: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    gate_id: Mapped[str | None] = mapped_column(String(36))
    artifact_id: Mapped[str | None] = mapped_column(String(36))
    return_to: Mapped[str | None] = mapped_column(String(40))


class Artifact(Identity, Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("run_id", "gate_id"),)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    gate_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(40))
    revision: Mapped[int] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSON)


class AgentRun(Identity, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (UniqueConstraint("run_id", "role", "attempt", "revision"),)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="BA")
    attempt: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="running")
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    context_chars: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(60))
    artifact_id: Mapped[str | None] = mapped_column(String(36))
    connection_id: Mapped[str | None] = mapped_column(String(36))


class AIConnection(Identity, Base):
    __tablename__ = "ai_connections"
    owner: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    encrypted_key: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_workflow_events_run_id_id", "run_id", "id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GoogleAccount(Base):
    __tablename__ = "google_accounts"
    subject: Mapped[str] = mapped_column(String(100), primary_key=True)
    identity: Mapped[str] = mapped_column(String(200), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    browser_hash: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[str] = mapped_column(String(128))
    verifier: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PMSession(Base):
    __tablename__ = "pm_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(ForeignKey("google_accounts.subject"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
