"""Exercise an upgrade with actual v1 history, not just an empty schema."""

from copy import deepcopy
from datetime import UTC, datetime

from alembic.config import Config
from sqlalchemy import MetaData, Table, select

from alembic import command
from app.models.entities import Approval, WorkflowRun
from app.services.workflows import DEFAULT_SNAPSHOT


def test_upgrade_preserves_v1_snapshot_and_decision(engine, app):
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0001_initial")
        metadata = MetaData()
        tables = {
            name: Table(name, metadata, autoload_with=connection)
            for name in ("projects", "work_items", "workflow_runs", "approvals")
        }
        stamp = datetime.now(UTC)
        snapshot = deepcopy(DEFAULT_SNAPSHOT)
        snapshot["version"] = "deterministic-v1"
        snapshot.pop("revision_targets")
        connection.execute(
            tables["projects"].insert(),
            {
                "id": "project",
                "name": "Existing",
                "description": "",
                "owner": "owner",
                "status": "active",
                "created_at": stamp,
                "updated_at": stamp,
            },
        )
        connection.execute(
            tables["work_items"].insert(),
            {
                "id": "item",
                "project_id": "project",
                "title": "Existing",
                "description": "Task",
                "acceptance_criteria": "",
                "priority": "urgent",
                "status": "plan_in_progress",
                "creator": "owner",
                "created_at": stamp,
                "updated_at": stamp,
            },
        )
        connection.execute(
            tables["workflow_runs"].insert(),
            {
                "id": "run",
                "work_item_id": "item",
                "idempotency_key": "original",
                "snapshot": snapshot,
                "status": "plan_in_progress",
                "current_step": "plan_in_progress",
                "attempt": 1,
                "retryable": False,
                "created_at": stamp,
            },
        )
        connection.execute(
            tables["approvals"].insert(),
            {
                "id": "approval",
                "run_id": "run",
                "step": "requirements_approval",
                "attempt": 1,
                "decision": "approve",
                "reviewer": "owner",
                "comment": "Original",
                "created_at": stamp,
            },
        )
        command.upgrade(config, "head")
    with app.state.sessions() as session:
        run = session.get(WorkflowRun, "run")
        assert run.snapshot == snapshot
        assert run.status == "plan_in_progress" and run.revision == 1 and run.gate_id is None
        approval = session.scalar(select(Approval))
        assert approval.comment == "Original" and approval.reviewer == "owner"
        assert approval.revision == 1 and approval.artifact_id is None
