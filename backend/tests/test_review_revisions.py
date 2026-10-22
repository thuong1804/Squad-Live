from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models.entities import Artifact, WorkflowRun
from app.services.workflows import fail_execution, transition
from tests.conftest import OTHER_TOKEN, TOKEN
from tests.test_api import drain


def decision(client, path, **changes):
    run = client.get(path).json()
    return {
        "step": run["status"],
        "attempt": run["attempt"],
        "gate_id": run["gate_id"],
        "artifact_id": run["gate_artifact_id"],
        "decision": "approve",
        **changes,
    }


def test_revision_preserves_evidence_rejects_stale_and_survives_restart(client, app, engine, run):
    path = f"/api/v1/workflow-runs/{run['id']}"
    drain(app)
    old = decision(client, path)
    original = client.get(f"{path}/artifacts/{old['artifact_id']}").json()
    assert client.post(f"{path}/approvals", json={**old, "decision": "reject"}).status_code == 422
    for revision in range(1, 5):
        result = client.post(
            f"{path}/approvals",
            json=decision(client, path, decision="reject", comment=f"Clarify case {revision}"),
        )
        assert result.status_code == 202
        assert result.json()["status"] == "ba_in_progress"
        assert result.json()["attempt"] == 1
        assert result.json()["revision"] == revision + 1
        restarted = create_app(app.state.settings, engine)
        drain(restarted)
        with TestClient(restarted) as restored:
            restored.headers["Authorization"] = f"Bearer {TOKEN}"
            assert restored.get(path).json()["status"] == "requirements_approval"
        assert client.post(f"{path}/approvals", json=old).status_code == 409
    assert client.get(f"{path}/artifacts/{old['artifact_id']}").json() == original
    current = client.get(path).json()
    artifact = client.get(f"{path}/artifacts/{current['gate_artifact_id']}").json()
    assert artifact["content"]["feedback"] == "Clarify case 4"
    assert len(client.get(f"{path}/approvals").json()["items"]) == 4
    assert client.post(f"{path}/approvals", json=decision(client, path)).status_code == 202
    drain(app)
    assert client.get(path).json()["status"] == "plan_approval"


def test_all_gates_and_final_revision_targets(client, app, run):
    path = f"/api/v1/workflow-runs/{run['id']}"
    drain(app)
    assert client.post(f"{path}/approvals", json=decision(client, path)).status_code == 202
    drain(app)
    assert (
        client.post(
            f"{path}/approvals",
            json=decision(client, path, decision="reject", comment="Different plan"),
        ).json()["status"]
        == "plan_in_progress"
    )
    drain(app)
    for target in ("ba_in_progress", "plan_in_progress"):
        while client.get(path).json()["status"] != "pm_review":
            assert client.post(f"{path}/approvals", json=decision(client, path)).status_code == 202
            drain(app)
        missing_target = decision(client, path, decision="reject", comment="Scope change")
        assert client.post(f"{path}/approvals", json=missing_target).status_code == 422
        result = client.post(f"{path}/approvals", json={**missing_target, "return_to": target})
        assert result.json()["status"] == target
        drain(app)
    while client.get(path).json()["status"] != "completed":
        assert client.post(f"{path}/approvals", json=decision(client, path)).status_code == 202
        drain(app)
    result = client.get(path).json()
    assert result["attempt"] == 1 and result["repair_count"] == 0
    assert result["gate_id"] is None
    assert client.post(f"{path}/retry").status_code == 409


def test_retry_resumes_failed_step_not_approvals(client, app, run):
    path = f"/api/v1/workflow-runs/{run['id']}"
    drain(app)
    client.post(f"{path}/approvals", json=decision(client, path))
    for attempt in (1, 2, 3):
        with app.state.sessions.begin() as session:
            stored = session.get(WorkflowRun, run["id"])
            assert stored.status == "plan_in_progress"
            fail_execution(session, stored)
        result = client.post(f"{path}/retry")
        assert result.status_code == (202 if attempt < 3 else 409)
        if attempt < 3:
            assert result.json()["status"] == "plan_in_progress"
            assert result.json()["attempt"] == attempt + 1
    assert len(client.get(f"{path}/approvals").json()["items"]) == 1


def test_review_requires_exact_artifact_and_human_command(client, app, run):
    import pytest

    from app.core.errors import DomainError

    path = f"/api/v1/workflow-runs/{run['id']}"
    drain(app)
    with pytest.raises(DomainError):
        with app.state.sessions.begin() as session:
            transition(session, session.get(WorkflowRun, run["id"]), "plan_in_progress")
    current = decision(client, path)
    assert (
        client.post(f"{path}/approvals", json={**current, "artifact_id": "other"}).status_code
        == 409
    )
    assert client.post(f"{path}/approvals", json={**current, "gate_id": None}).status_code == 409
    client.headers["Authorization"] = f"Bearer {OTHER_TOKEN}"
    assert client.get(f"{path}/artifacts").status_code == 404
    assert client.get(f"{path}/artifacts/{current['artifact_id']}").status_code == 404
    assert client.get("/api/v1/dashboard").json()["counts"] == {}


def test_artifact_and_gate_rollback_together(app, run):
    import pytest

    with pytest.raises(RuntimeError):
        with app.state.sessions.begin() as session:
            stored = session.get(WorkflowRun, run["id"])
            transition(session, stored, "ba_in_progress")
            transition(session, stored, "requirements_approval")
            raise RuntimeError("crash")
    with app.state.sessions() as session:
        assert session.get(WorkflowRun, run["id"]).status == "queued"
        assert session.scalars(select(Artifact)).all() == []
