from copy import deepcopy

from sqlalchemy import select

from app.core.errors import DomainError, conflict
from app.models.entities import (
    Approval,
    Artifact,
    WorkflowEvent,
    WorkflowRun,
    WorkItem,
    new_id,
    now,
)
from app.services.projects import item_for, project_for

TERMINAL = {"completed", "failed", "cancelled"}
GATES = {
    "requirements_approval": "plan_in_progress",
    "plan_approval": "implementation_in_progress",
    "pm_review": "completed",
}
AUTOMATIC = {
    "queued": "ba_in_progress",
    "ba_in_progress": "requirements_approval",
    "plan_in_progress": "plan_approval",
    "implementation_in_progress": "checks_in_progress",
    "checks_in_progress": "testing_in_progress",
    "testing_in_progress": "pm_review",
}
DEFAULT_SNAPSHOT = {
    "version": "deterministic-v2",
    "mode": "mock",
    "max_attempts": 3,
    "automatic": AUTOMATIC,
    "approval_gates": GATES,
    "revision_targets": {
        "requirements_approval": ["ba_in_progress"],
        "plan_approval": ["plan_in_progress"],
        "pm_review": ["ba_in_progress", "plan_in_progress"],
    },
    "notice": "Simulation only: no code, tests, LLM calls or GitHub PRs are executed.",
}


def event(session, run, kind, **payload):
    session.add(
        WorkflowEvent(
            run_id=run.id,
            event_type=kind,
            payload={"attempt": run.attempt, "revision": run.revision, **payload},
        )
    )


def run_for(session, run_id, user, *, lock=False):
    query = select(WorkflowRun).where(WorkflowRun.id == run_id)
    if lock:
        query = query.with_for_update()
    run = session.scalar(query)
    if run is None:
        raise DomainError(404, "not_found", "Workflow run not found")
    item_for(session, run.work_item_id, user)
    return run


def transition(session, run, target, *, actor="worker", human_decision=False):
    source = run.status
    automatic = run.snapshot["automatic"]
    gates = run.snapshot["approval_gates"]
    allowed = set()
    if source not in TERMINAL:
        allowed.update(("failed", "cancelled"))
    if source in automatic:
        allowed.add(automatic[source])
    if source in gates and human_decision:
        allowed.add(gates[source])
        allowed.update(run.snapshot.get("revision_targets", {}).get(source, []))
    if target not in allowed:
        conflict(f"Cannot transition from {source} to {target}")
    run.status = run.current_step = target
    run.gate_id = run.gate_artifact_id = None
    if target in gates and run.snapshot["version"] != "deterministic-v1":
        open_review(session, run, target)
    if run.started_at is None and target != "cancelled":
        run.started_at = now()
    if target in TERMINAL:
        run.ended_at = now()
    session.get(WorkItem, run.work_item_id).status = target
    event(session, run, "state_changed", previous=source, status=target, actor=actor)


def start(session, item_id, key, user):
    item = item_for(session, item_id, user, lock=True)
    existing = session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.work_item_id == item_id,
            WorkflowRun.idempotency_key == key,
        )
    )
    if existing:
        return existing
    project = project_for(session, item.project_id, user)
    if project.status != "active":
        conflict("Cannot start a workflow in an archived project")
    active = session.scalar(
        select(WorkflowRun.id).where(
            WorkflowRun.work_item_id == item_id,
            WorkflowRun.status.not_in(TERMINAL),
        )
    )
    if active:
        conflict("Work item already has an active workflow")
    run = WorkflowRun(
        work_item_id=item_id, idempotency_key=key, snapshot=deepcopy(DEFAULT_SNAPSHOT)
    )
    session.add(run)
    session.flush()
    item.status = "queued"
    event(session, run, "run_queued", actor=user, mode="mock")
    return run


def approve(session, run_id, data, user):
    run = run_for(session, run_id, user, lock=True)
    if run.status != data.step or run.attempt != data.attempt or run.status not in GATES:
        conflict("Approval does not match the current gate and attempt")
    modern = run.snapshot["version"] != "deterministic-v1"
    target = None
    if modern:
        if (
            not run.gate_id
            or data.gate_id != run.gate_id
            or data.artifact_id != run.gate_artifact_id
        ):
            conflict("Review session or artifact has changed; reload before deciding")
        if data.decision == "reject":
            if not data.comment:
                raise DomainError(422, "feedback_required", "Feedback is required for changes")
            targets = run.snapshot["revision_targets"][run.status]
            target = data.return_to or (targets[0] if len(targets) == 1 else None)
            if target not in targets:
                raise DomainError(422, "revision_target_required", "Select a valid revision target")
        elif data.return_to:
            raise DomainError(422, "invalid_target", "An approval cannot request revision")
    approval = Approval(
        run_id=run.id,
        step=data.step,
        attempt=run.attempt,
        decision=data.decision,
        reviewer=user,
        comment=data.comment,
        revision=run.revision,
        gate_id=run.gate_id,
        artifact_id=run.gate_artifact_id,
        return_to=target,
    )
    session.add(approval)
    session.flush()
    event(
        session,
        run,
        "approval_recorded",
        approval_id=approval.id,
        step=data.step,
        decision=data.decision,
        reviewer=user,
        gate_id=run.gate_id,
        artifact_id=run.gate_artifact_id,
    )
    if data.decision == "reject":
        if modern:
            run.revision += 1
            transition(session, run, target, actor=user, human_decision=True)
        else:
            run.failure_reason = "Rejected by project owner"
            run.retryable = run.attempt < run.snapshot["max_attempts"]
            transition(session, run, "failed", actor=user)
    else:
        transition(
            session, run, run.snapshot["approval_gates"][data.step], actor=user, human_decision=True
        )
    return run


def cancel(session, run_id, data, user):
    run = run_for(session, run_id, user, lock=True)
    if run.status == "cancelled":
        return run
    if run.status in TERMINAL:
        conflict("Terminal runs cannot be cancelled")
    run.cancellation_reason = data.reason
    run.retryable = False
    transition(session, run, "cancelled", actor=user)
    return run


def retry(session, run_id, user):
    run = run_for(session, run_id, user, lock=True)
    item = item_for(session, run.work_item_id, user, lock=True)
    project = project_for(session, item.project_id, user)
    if project.status != "active":
        conflict("Cannot retry a workflow in an archived project")
    if run.status != "failed" or not run.retryable:
        conflict("Only retryable failed runs may be retried")
    if run.attempt >= run.snapshot["max_attempts"]:
        conflict("Retry limit reached")
    active = session.scalar(
        select(WorkflowRun.id).where(
            WorkflowRun.work_item_id == run.work_item_id,
            WorkflowRun.id != run.id,
            WorkflowRun.status.not_in(TERMINAL),
        )
    )
    if active:
        conflict("Work item already has an active workflow")
    target = "queued" if run.snapshot["version"] == "deterministic-v1" else run.failed_step
    if target not in run.snapshot["automatic"]:
        conflict("Failed step cannot be safely resumed")
    run.attempt += 1
    run.status = run.current_step = item.status = target
    run.failure_reason = None
    run.ended_at = None
    run.retryable = False
    event(session, run, "run_retried", actor=user, status=target)
    return run


def fail_execution(session, run, *, retryable=True):
    """Record a safe failure checkpoint; external executors must call after rollback."""
    if run.status not in run.snapshot["automatic"]:
        conflict("Only an execution step can fail")
    run.failed_step = run.status
    run.failure_reason = "Execution could not finish. Review evidence before retrying."
    run.retryable = retryable and run.attempt < run.snapshot["max_attempts"]
    transition(session, run, "failed")


def open_review(session, run, gate):
    """Persist the exact immutable evidence being reviewed in this gate session."""
    item = session.get(WorkItem, run.work_item_id)
    last_feedback = session.scalar(
        select(Approval)
        .where(Approval.run_id == run.id, Approval.decision == "reject")
        .order_by(Approval.created_at.desc(), Approval.id.desc())
    )
    kind = {
        "requirements_approval": "requirements",
        "plan_approval": "plan",
        "pm_review": "delivery",
    }[gate]
    content = {
        "simulated": True,
        "executed": False,
        "title": item.title,
        "description": item.description,
        "acceptance_criteria": item.acceptance_criteria,
        "feedback": last_feedback.comment if last_feedback else None,
        "notice": "Mock artifact only. No AI, source changes, tests or PR were executed.",
    }
    if kind == "plan":
        content["steps"] = [
            "Inspect repository",
            "Implement approved criteria",
            "Run checks in sandbox",
        ]
    if kind == "delivery":
        content["artifact_ids"] = list(
            session.scalars(select(Artifact.id).where(Artifact.run_id == run.id))
        )
    artifact = Artifact(
        id=new_id(),
        run_id=run.id,
        gate_id=new_id(),
        kind=kind,
        revision=run.revision,
        attempt=run.attempt,
        content=content,
    )
    session.add(artifact)
    session.flush()
    run.gate_id, run.gate_artifact_id = artifact.gate_id, artifact.id
    event(
        session, run, "review_opened", gate_id=artifact.gate_id, artifact_id=artifact.id, step=gate
    )


def advance_mock(session, run):
    """One bounded mock step; future external executors must run outside transactions."""
    if run.status not in AUTOMATIC:
        return
    if run.snapshot["mode"] != "mock":
        conflict("Unsupported execution mode")
    item = session.get(WorkItem, run.work_item_id)
    if run.status == "ba_in_progress":
        event(
            session,
            run,
            "mock_requirements",
            content={
                "title": item.title,
                "description": item.description,
                "acceptance_criteria": item.acceptance_criteria,
                "simulated": True,
            },
        )
    elif run.status == "plan_in_progress":
        event(
            session,
            run,
            "mock_plan",
            content={
                "steps": ["Inspect repository", "Implement acceptance criteria", "Run real checks"],
                "simulated": True,
            },
        )
    elif run.status in {"checks_in_progress", "testing_in_progress"}:
        event(
            session,
            run,
            "mock_evidence",
            simulated=True,
            executed=False,
            summary="Simulation only; no tests or review were executed.",
        )
    transition(session, run, run.snapshot["automatic"][run.status])
