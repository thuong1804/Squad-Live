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


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_workflow_events_run_id_id", "run_id", "id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
