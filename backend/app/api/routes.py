from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.models.entities import Approval, Artifact, Project, WorkflowEvent, WorkflowRun, WorkItem
from app.schemas.contracts import (
    ApprovalCreate,
    ApprovalRead,
    ArtifactRead,
    CancelCreate,
    DashboardRead,
    EventRead,
    Page,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    RunRead,
    SessionRead,
    WorkItemCreate,
    WorkItemRead,
)
from app.services import projects, workflows

router = APIRouter(prefix="/api/v1")


def session_dependency(request: Request):
    with request.app.state.sessions.begin() as session:
        yield session


DB = Annotated[Session, Depends(session_dependency, scope="function")]
User = Annotated[str, Depends(current_user)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
Key = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
]


@router.get("/session", response_model=SessionRead)
def session_identity(user: User):
    return {"identity": user}


def page(session, query, limit, offset):
    return {
        "items": session.scalars(query.limit(limit).offset(offset)).all(),
        "limit": limit,
        "offset": offset,
    }


@router.post("/projects", response_model=ProjectRead, status_code=201)
def create_project(data: ProjectCreate, db: DB, user: User):
    return projects.create_project(db, data, user)


@router.get("/projects", response_model=Page[ProjectRead])
def list_projects(db: DB, user: User, limit: Limit = 25, offset: Offset = 0):
    return page(
        db,
        select(Project).where(Project.owner == user).order_by(Project.created_at, Project.id),
        limit,
        offset,
    )


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: UUID, db: DB, user: User):
    return projects.project_for(db, str(project_id), user)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: UUID, data: ProjectUpdate, db: DB, user: User):
    return projects.update_project(db, str(project_id), data, user)


@router.post("/projects/{project_id}/work-items", response_model=WorkItemRead, status_code=201)
def create_item(project_id: UUID, data: WorkItemCreate, db: DB, user: User):
    return projects.create_item(db, str(project_id), data, user)


@router.get("/projects/{project_id}/work-items", response_model=Page[WorkItemRead])
def list_items(project_id: UUID, db: DB, user: User, limit: Limit = 25, offset: Offset = 0):
    projects.project_for(db, str(project_id), user)
    return page(
        db,
        select(WorkItem)
        .where(WorkItem.project_id == str(project_id))
        .order_by(WorkItem.created_at, WorkItem.id),
        limit,
        offset,
    )


@router.get("/work-items/{work_item_id}", response_model=WorkItemRead)
def get_item(work_item_id: UUID, db: DB, user: User):
    return projects.item_for(db, str(work_item_id), user)


@router.post("/work-items/{work_item_id}/workflow-runs", response_model=RunRead, status_code=202)
def start_run(work_item_id: UUID, db: DB, user: User, key: Key):
    return workflows.start(db, str(work_item_id), key, user)


@router.get("/work-items/{work_item_id}/workflow-runs", response_model=Page[RunRead])
def list_runs(work_item_id: UUID, db: DB, user: User, limit: Limit = 25, offset: Offset = 0):
    projects.item_for(db, str(work_item_id), user)
    return page(
        db,
        select(WorkflowRun)
        .where(WorkflowRun.work_item_id == str(work_item_id))
        .order_by(WorkflowRun.created_at, WorkflowRun.id),
        limit,
        offset,
    )


@router.get("/workflow-runs/{run_id}", response_model=RunRead)
def get_run(run_id: UUID, db: DB, user: User):
    return workflows.run_for(db, str(run_id), user)


@router.get("/workflow-runs/{run_id}/events", response_model=Page[EventRead])
def list_events(run_id: UUID, db: DB, user: User, limit: Limit = 25, offset: Offset = 0):
    workflows.run_for(db, str(run_id), user)
    return page(
        db,
        select(WorkflowEvent).where(WorkflowEvent.run_id == str(run_id)).order_by(WorkflowEvent.id),
        limit,
        offset,
    )


@router.get("/workflow-runs/{run_id}/approvals", response_model=Page[ApprovalRead])
def list_approvals(run_id: UUID, db: DB, user: User, limit: Limit = 25, offset: Offset = 0):
    workflows.run_for(db, str(run_id), user)
    return page(
        db,
        select(Approval)
        .where(Approval.run_id == str(run_id))
        .order_by(Approval.created_at, Approval.id),
        limit,
        offset,
    )


@router.get("/workflow-runs/{run_id}/artifacts", response_model=Page[ArtifactRead])
def list_artifacts(run_id: UUID, db: DB, user: User, limit: Limit = 25, offset: Offset = 0):
    workflows.run_for(db, str(run_id), user)
    return page(
        db,
        select(Artifact)
        .where(Artifact.run_id == str(run_id))
        .order_by(Artifact.created_at, Artifact.id),
        limit,
        offset,
    )


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(db: DB, user: User):
    owned = select(WorkflowRun).join(WorkItem).join(Project).where(Project.owner == user)
    counts = db.execute(
        select(WorkflowRun.status, func.count())
        .join(WorkItem)
        .join(Project)
        .where(Project.owner == user)
        .group_by(WorkflowRun.status)
    ).all()
    recent = db.scalars(
        owned.order_by(WorkflowRun.created_at.desc(), WorkflowRun.id).limit(10)
    ).all()
    waiting = db.scalars(
        owned.where(WorkflowRun.status.in_(workflows.GATES))
        .order_by(WorkflowRun.created_at.desc())
        .limit(10)
    ).all()
    events = db.scalars(
        select(WorkflowEvent)
        .join(WorkflowRun)
        .join(WorkItem)
        .join(Project)
        .where(Project.owner == user)
        .order_by(WorkflowEvent.id.desc())
        .limit(10)
    ).all()
    return {
        "counts": dict(counts),
        "recent_runs": [RunRead.model_validate(r) for r in recent],
        "waiting_runs": [RunRead.model_validate(r) for r in waiting],
        "recent_events": [EventRead.model_validate(e) for e in events],
    }


@router.post("/workflow-runs/{run_id}/approvals", response_model=RunRead, status_code=202)
def approve_run(run_id: UUID, data: ApprovalCreate, db: DB, user: User):
    return workflows.approve(db, str(run_id), data, user)


@router.get("/workflow-runs/{run_id}/artifacts/{artifact_id}", response_model=ArtifactRead)
def get_artifact(run_id: UUID, artifact_id: UUID, db: DB, user: User):
    workflows.run_for(db, str(run_id), user)
    artifact = db.get(Artifact, str(artifact_id))
    if artifact is None or artifact.run_id != str(run_id):
        from app.core.errors import DomainError

        raise DomainError(404, "not_found", "Artifact not found")
    return artifact


@router.post("/workflow-runs/{run_id}/cancel", response_model=RunRead)
def cancel_run(run_id: UUID, db: DB, user: User, data: CancelCreate = CancelCreate()):
    return workflows.cancel(db, str(run_id), data, user)


@router.post("/workflow-runs/{run_id}/retry", response_model=RunRead, status_code=202)
def retry_run(run_id: UUID, db: DB, user: User):
    return workflows.retry(db, str(run_id), user)
