"""Explicit BYOK Dev edits for an isolated run workspace, with idempotent history."""

import json
from datetime import timedelta
from time import monotonic

from sqlalchemy import select

from app.agents import repo_dev
from app.agents.contracts import ProviderError
from app.agents.execution import redact
from app.agents.providers import make_provider
from app.core.errors import DomainError, conflict
from app.models.entities import Approval, Artifact, WorkItem, new_id, now
from app.services import ai_access, workspaces
from app.services.workflows import event, run_for


def _view(artifact: Artifact) -> dict:
    content = artifact.content
    return {
        "id": artifact.id,
        "status": content["status"],
        "summary": content.get("summary"),
        "files": content.get("files", []),
        "source_files": content.get("source_files", []),
        "error_code": content.get("error_code"),
        "created_at": artifact.created_at,
    }


def list_for(session, run_id: str, user: str) -> list[dict]:
    run_for(session, run_id, user)
    records = session.scalars(
        select(Artifact)
        .where(Artifact.run_id == run_id, Artifact.kind == "repository_edit")
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
        .limit(10)
    )
    return [_view(record) for record in records]


def _approved_documents(session, run_id: str) -> dict:
    result = {}
    for step in ("requirements_approval", "plan_approval"):
        approval = session.scalar(
            select(Approval)
            .where(Approval.run_id == run_id, Approval.step == step, Approval.decision == "approve")
            .order_by(Approval.created_at.desc(), Approval.id.desc())
        )
        artifact = session.get(Artifact, approval.artifact_id) if approval else None
        if artifact and artifact.run_id == run_id:
            document = json.dumps(artifact.content.get("specification"), ensure_ascii=False)
            result[step] = document[:12000]
    return result


def perform(
    sessions,
    run_id: str,
    user: str,
    settings,
    connection_id: str,
    key: str,
    requested_paths: list[str],
) -> dict:
    with sessions.begin() as session:
        run = run_for(session, run_id, user, lock=True)
        existing = session.scalar(
            select(Artifact).where(Artifact.run_id == run_id, Artifact.gate_id == key)
        )
        if existing:
            if existing.kind != "repository_edit":
                conflict("Idempotency key is already used")
            if existing.content.get("connection_id") != connection_id:
                conflict("Idempotency key is already used with another AI connection")
            if existing.content.get("requested_paths", []) != requested_paths:
                conflict("Idempotency key is already used with other source files")
            return _view(existing)
        pending = session.scalar(
            select(Artifact)
            .where(Artifact.run_id == run_id, Artifact.kind == "repository_edit")
            .order_by(Artifact.created_at.desc(), Artifact.id.desc())
        )
        if pending and pending.content.get("status") == "pending":
            if pending.created_at and pending.created_at.replace(
                tzinfo=now().tzinfo
            ) < now() - timedelta(minutes=5):
                pending.content = {
                    **pending.content,
                    "status": "failed",
                    "error_code": "worker_interrupted",
                }
            else:
                conflict("A Dev AI edit is already running for this workspace")
        workspace = workspaces.workspace_for(session, run_id, user)
        if not workspace:
            conflict("Create a workspace before running Dev AI")
        root = workspaces._verify(workspace, settings)
        item = session.get(WorkItem, run.work_item_id)
        selected = ai_access.resolve(session, user, settings, connection_id).model_copy(
            update={"llm_max_output_tokens": settings.dev_max_output_tokens}
        )
        context, allowed, status = repo_dev.context(
            root, item, requested_paths, _approved_documents(session, run_id)
        )
        artifact = Artifact(
            id=new_id(),
            run_id=run_id,
            gate_id=key,
            kind="repository_edit",
            revision=run.revision,
            attempt=run.attempt,
            content={
                "status": "pending",
                "provider": selected.llm_provider,
                "model": selected.llm_model,
                "connection_id": connection_id,
                "prompt_version": repo_dev.PROMPT_VERSION,
                "requested_paths": requested_paths,
                "source_files": sorted(allowed),
            },
        )
        session.add(artifact)
        session.flush()
        edit_id = artifact.id
        event(session, run, "workspace_edit_started", edit_id=edit_id, actor=user)

    started = monotonic()
    result, error = None, None
    try:
        result = make_provider(
            selected,
            output_type=repo_dev.RepositoryEdit,
            system_prompt=repo_dev.SYSTEM_PROMPT,
        ).generate(redact(context, selected), selected.llm_model)
        edit = repo_dev.RepositoryEdit.model_validate(result.specification)
    except ProviderError as exc:
        error = exc.code
    except Exception:
        error = "execution_error"

    with sessions.begin() as session:
        run = run_for(session, run_id, user, lock=True)
        artifact = session.get(Artifact, edit_id)
        if artifact.content["status"] != "pending":
            return _view(artifact)
        if error is None:
            try:
                workspace = workspaces.workspace_for(session, run_id, user)
                root = workspaces._verify(workspace, settings)
                paths = repo_dev.apply(root, edit, allowed, status)
            except DomainError as exc:
                error = exc.code
            except Exception:
                error = "workspace_unavailable"
        if error:
            artifact.content = {**artifact.content, "status": "failed", "error_code": error}
            event(session, run, "workspace_edit_failed", edit_id=edit_id, error_code=error)
        else:
            artifact.content = {
                **artifact.content,
                "status": "succeeded",
                "summary": edit.summary,
                "files": paths,
                "notes": edit.notes,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "duration_ms": int((monotonic() - started) * 1000),
            }
            event(session, run, "workspace_edit_completed", edit_id=edit_id, files=paths)
        session.flush()
        return _view(artifact)
