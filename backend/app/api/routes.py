from ipaddress import ip_address
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.contracts import ProviderError
from app.agents.providers import list_models
from app.core.errors import DomainError
from app.core.security import current_user
from app.models.entities import (
    AgentRun,
    AIConnection,
    Approval,
    Artifact,
    Project,
    WorkflowEvent,
    WorkflowRun,
    WorkItem,
)
from app.schemas.contracts import (
    AgentRunRead,
    ApprovalCreate,
    ApprovalRead,
    ArtifactRead,
    CancelCreate,
    CapabilitiesRead,
    ConnectionCreate,
    ConnectionProbe,
    ConnectionRead,
    DashboardRead,
    EventRead,
    Page,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    RepositoryConnect,
    RepositoryFileRead,
    RepositoryRead,
    RetryCreate,
    RunCreate,
    RunRead,
    SessionRead,
    WorkItemCreate,
    WorkItemRead,
)
from app.services import ai_access, projects, repositories, sites, workflows

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


@router.get("/capabilities", response_model=CapabilitiesRead)
def capabilities(request: Request, user: User, db: DB):
    settings = request.app.state.settings
    available = db.scalar(
        select(AIConnection.id)
        .where(AIConnection.owner == user, AIConnection.enabled.is_(True))
        .limit(1)
    )
    return {
        "ba_live_available": bool(available) and ai_access.storage_ready(settings),
        "provider": None,
        "model": None,
        "key_storage_available": ai_access.storage_ready(settings),
    }


def discover(data):
    try:
        return list_models(data.provider, data.api_key)
    except ProviderError as error:
        # Never forward raw provider errors or submitted credentials.
        raise DomainError(422, error.code, "Could not verify provider credentials/models") from None


@router.post("/ai-connections/models")
def connection_models(data: ConnectionProbe, request: Request, user: User):
    ai_access.cipher(request.app.state.settings)
    return {"models": discover(data)}


@router.post("/ai-connections", response_model=ConnectionRead, status_code=201)
def create_connection(data: ConnectionCreate, request: Request, user: User, db: DB):
    cipher = ai_access.cipher(request.app.state.settings)
    if data.model not in discover(data):
        raise DomainError(422, "model_unavailable", "Model is not available to this connection")
    connection = AIConnection(
        owner=user,
        name=data.name,
        provider=data.provider,
        model=data.model,
        encrypted_key=cipher.encrypt(data.api_key.encode()).decode(),
    )
    db.add(connection)
    db.flush()
    return connection


@router.get("/ai-connections", response_model=Page[ConnectionRead])
def connections(user: User, db: DB, limit: Limit = 25, offset: Offset = 0):
    return page(
        db,
        select(AIConnection)
        .where(AIConnection.owner == user)
        .order_by(AIConnection.created_at.desc(), AIConnection.id),
        limit,
        offset,
    )


@router.post("/ai-connections/{connection_id}/disable", response_model=ConnectionRead)
def disable_connection(connection_id: UUID, user: User, db: DB):
    connection = ai_access.connection_for(db, str(connection_id), user, lock=True)
    connection.enabled = False
    connection.encrypted_key = ""  # Retain metadata for history, erase the stored credential.
    return connection


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


@router.post("/projects/{project_id}/repository", response_model=ProjectRead)
def connect_repository(project_id: UUID, data: RepositoryConnect, db: DB, user: User):
    return repositories.connect(db, str(project_id), user, data.path)


@router.post("/projects/{project_id}/repository/pick", response_model=ProjectRead)
def pick_repository(project_id: UUID, request: Request, db: DB, user: User):
    try:
        local_client = request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:
        local_client = False
    if not local_client:
        raise DomainError(403, "local_only", "Folder picker is only available on this computer")
    return repositories.pick_and_connect(db, str(project_id), user)


@router.delete("/projects/{project_id}/repository", response_model=ProjectRead)
def disconnect_repository(project_id: UUID, db: DB, user: User):
    return repositories.disconnect(db, str(project_id), user)


@router.get("/projects/{project_id}/repository", response_model=RepositoryRead)
def inspect_repository(project_id: UUID, db: DB, user: User, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return repositories.inspect(db, str(project_id), user)


@router.get("/projects/{project_id}/repository/file", response_model=RepositoryFileRead)
def read_repository_file(project_id: UUID, path: str, db: DB, user: User, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return repositories.read_file(db, str(project_id), user, path)


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
def start_run(
    work_item_id: UUID,
    db: DB,
    user: User,
    key: Key,
    request: Request,
    data: RunCreate = RunCreate(),
):
    return workflows.start(
        db,
        str(work_item_id),
        key,
        user,
        mode=data.mode,
        settings=request.app.state.settings,
        connection_id=str(data.connection_id) if data.connection_id else None,
    )


@router.get("/workflow-runs/{run_id}/agent-runs", response_model=Page[AgentRunRead])
def list_agent_runs(run_id: UUID, db: DB, user: User, limit: Limit = 25, offset: Offset = 0):
    workflows.run_for(db, str(run_id), user)
    return page(
        db,
        select(AgentRun)
        .where(AgentRun.run_id == str(run_id))
        .order_by(AgentRun.created_at, AgentRun.id),
        limit,
        offset,
    )


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


@router.get("/workflow-runs/{run_id}/websites")
def websites(run_id: UUID, db: DB, user: User, limit: Limit = 25, offset: Offset = 0):
    workflows.run_for(db, str(run_id), user)
    artifacts = db.scalars(
        select(Artifact)
        .where(Artifact.run_id == str(run_id), Artifact.kind == "website")
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [
            {"id": a.id, "revision": a.revision, "attempt": a.attempt, "created_at": a.created_at}
            for a in artifacts
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/workflow-runs/{run_id}/websites/{artifact_id}")
def website(run_id: UUID, artifact_id: UUID, db: DB, user: User):
    run = workflows.run_for(db, str(run_id), user)
    artifact, site = sites.site_for(db, run, str(artifact_id))
    return {
        "id": artifact.id,
        "revision": artifact.revision,
        "attempt": artifact.attempt,
        **site.model_dump(),
        "preview_html": sites.preview(site),
    }


@router.get("/workflow-runs/{run_id}/websites/{artifact_id}/download")
def download_website(run_id: UUID, artifact_id: UUID, db: DB, user: User):
    run = workflows.run_for(db, str(run_id), user)
    artifact, site = sites.site_for(db, run, str(artifact_id))
    return Response(
        sites.archive(site),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="website-{artifact.id}.zip"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/workflow-runs/{run_id}/websites/{artifact_id}/browser-report")
def website_browser_report(run_id: UUID, artifact_id: UUID, db: DB, user: User, response: Response):
    run = workflows.run_for(db, str(run_id), user)
    sites.site_for(db, run, str(artifact_id))
    report = db.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == str(run_id),
            Artifact.kind == "browser_report",
            Artifact.content["website_artifact_id"].as_string() == str(artifact_id),
        )
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    )
    response.headers["Cache-Control"] = "no-store"
    return {"report": report.content["specification"] if report else None}


@router.post("/workflow-runs/{run_id}/retry", response_model=RunRead, status_code=202)
def retry_run(
    run_id: UUID, db: DB, user: User, request: Request, data: RetryCreate = RetryCreate()
):
    return workflows.retry(
        db,
        str(run_id),
        user,
        settings=request.app.state.settings,
        connection_id=str(data.connection_id) if data.connection_id else None,
    )
