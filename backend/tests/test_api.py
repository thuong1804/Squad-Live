from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.models.entities import WorkflowRun
from app.services.workflows import DEFAULT_SNAPSHOT
from app.workers.runner import tick
from tests.conftest import OTHER_TOKEN


def drain(app):
    for _ in range(20):
        if not tick(app.state.sessions):
            return
    raise AssertionError("Worker did not pause at a gate")


def test_health_docs_ready_and_cors(client):
    client.headers.pop("Authorization")
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 200
    assert client.get("/docs").status_code == 200
    assert "/api/v1/projects" in client.get("/openapi.json").json()["paths"]
    response = client.options(
        "/api/v1/projects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert client.get("/api/v1/projects").status_code == 401


def test_closed_by_default(engine):
    with TestClient(create_app(Settings(_env_file=None, auth_tokens={}), engine)) as client:
        assert client.post("/api/v1/projects", json={"name": "Denied"}).status_code == 401


def test_projects_items_validation_and_archive(client, item):
    project_id = item["project_id"]
    path = f"/api/v1/projects/{project_id}"
    assert client.get(path).json()["owner"] == "owner"
    assert client.get("/api/v1/projects?limit=1&offset=0").json()["limit"] == 1
    assert client.get(f"{path}/work-items").json()["items"][0]["id"] == item["id"]
    assert client.get(f"/api/v1/work-items/{item['id']}").status_code == 200
    assert client.patch(path, json={"owner": "other"}).status_code == 422
    assert client.patch(path, json={"name": None}).status_code == 422
    assert client.post("/api/v1/projects", json={"name": "  "}).status_code == 422
    assert client.get("/api/v1/projects?limit=101").status_code == 422
    assert client.patch(path, json={"name": "Renamed"}).json()["name"] == "Renamed"
    assert client.patch(path, json={"status": "archived"}).status_code == 200
    assert (
        client.post(f"{path}/work-items", json={"title": "x", "description": "y"}).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/work-items/{item['id']}/workflow-runs",
            headers={"Idempotency-Key": "archived"},
        ).status_code
        == 409
    )


def test_resource_isolation(client, item, run):
    client.headers["Authorization"] = f"Bearer {OTHER_TOKEN}"
    assert client.get("/api/v1/projects").json()["items"] == []
    assert client.get(f"/api/v1/projects/{item['project_id']}").status_code == 404
    assert client.get(f"/api/v1/work-items/{item['id']}").status_code == 404
    for suffix in ("", "/events", "/approvals"):
        assert client.get(f"/api/v1/workflow-runs/{run['id']}{suffix}").status_code == 404
    assert client.post(f"/api/v1/workflow-runs/{run['id']}/cancel").status_code == 404
    assert (
        client.post(
            f"/api/v1/workflow-runs/{run['id']}/approvals",
            json={
                "step": "requirements_approval",
                "attempt": 1,
                "decision": "approve",
            },
        ).status_code
        == 404
    )


def test_enqueue_is_idempotent_and_not_executed_in_http(client, item, run):
    assert run["status"] == "queued"
    path = f"/api/v1/work-items/{item['id']}/workflow-runs"
    assert client.post(path, headers={"Idempotency-Key": "initial"}).json()["id"] == run["id"]
    assert client.post(path, headers={"Idempotency-Key": "second"}).status_code == 409
    assert client.post(path).status_code == 422
    assert len(client.get(path).json()["items"]) == 1


def test_full_workflow_and_stale_approval(client, app, legacy_run):
    run = legacy_run
    path = f"/api/v1/workflow-runs/{run['id']}"
    assert (
        client.post(
            f"{path}/approvals",
            json={
                "step": "requirements_approval",
                "attempt": 1,
                "decision": "approve",
            },
        ).status_code
        == 409
    )
    for gate in ("requirements_approval", "plan_approval", "pm_review"):
        drain(app)
        assert client.get(path).json()["status"] == gate
        decision = {"step": gate, "attempt": 1, "decision": "approve", "comment": "Reviewed"}
        assert client.post(f"{path}/approvals", json=decision).status_code == 202
        assert client.post(f"{path}/approvals", json=decision).status_code == 409
    result = client.get(path).json()
    assert result["status"] == "completed"
    assert result["ended_at"].endswith("+00:00")
    approvals = client.get(f"{path}/approvals").json()["items"]
    assert len(approvals) == 3
    assert all(a["reviewer"] == "owner" and a["comment"] == "Reviewed" for a in approvals)
    events = client.get(f"{path}/events?limit=100").json()["items"]
    assert any(e["event_type"] == "mock_requirements" for e in events)
    assert any(e["event_type"] == "mock_plan" for e in events)
    assert all(
        e["payload"]["executed"] is False for e in events if e["event_type"] == "mock_evidence"
    )
    assert client.post(f"{path}/cancel").status_code == 409
    assert client.post(f"{path}/retry").status_code == 409


def test_rejection_retry_limit_and_stale_attempt(client, app, legacy_run):
    run = legacy_run
    path = f"/api/v1/workflow-runs/{run['id']}"
    for attempt in (1, 2, 3):
        drain(app)
        if attempt > 1:
            assert (
                client.post(
                    f"{path}/approvals",
                    json={
                        "step": "requirements_approval",
                        "attempt": attempt - 1,
                        "decision": "approve",
                    },
                ).status_code
                == 409
            )
        result = client.post(
            f"{path}/approvals",
            json={
                "step": "requirements_approval",
                "attempt": attempt,
                "decision": "reject",
            },
        )
        assert result.json()["status"] == "failed"
        retry = client.post(f"{path}/retry")
        assert retry.status_code == (202 if attempt < 3 else 409)
    assert len(client.get(f"{path}/approvals").json()["items"]) == 3


def test_cancel_stops_worker_and_is_idempotent(client, app, run):
    path = f"/api/v1/workflow-runs/{run['id']}"
    assert tick(app.state.sessions)
    assert client.post(f"{path}/cancel", json={"reason": "No longer needed"}).status_code == 200
    assert not tick(app.state.sessions)
    result = client.post(f"{path}/cancel").json()
    assert result["status"] == "cancelled"
    assert result["cancellation_reason"] == "No longer needed"
    assert client.post(f"{path}/retry").status_code == 409


def test_snapshot_and_restart(client, app, engine, run, monkeypatch):
    monkeypatch.setitem(DEFAULT_SNAPSHOT, "max_attempts", 99)
    assert tick(app.state.sessions)
    restarted = create_app(app.state.settings, engine)
    drain(restarted)
    with restarted.state.sessions() as session:
        stored = session.scalar(select(WorkflowRun).where(WorkflowRun.id == run["id"]))
        assert stored.status == "requirements_approval"
        assert stored.snapshot["max_attempts"] == 3


def test_errors_do_not_echo_input(client):
    secret = "sensitive-invalid-input"
    response = client.post("/api/v1/projects", json={"name": secret, "token": secret})
    assert response.status_code == 422
    assert secret not in response.text
    assert set(response.json()) == {"error"}


def test_retry_cannot_compete_with_new_run(client, app, legacy_run, item):
    run = legacy_run
    drain(app)
    path = f"/api/v1/workflow-runs/{run['id']}"
    client.post(
        f"{path}/approvals",
        json={
            "step": "requirements_approval",
            "attempt": 1,
            "decision": "reject",
        },
    )
    assert (
        client.post(
            f"/api/v1/work-items/{item['id']}/workflow-runs", headers={"Idempotency-Key": "new-run"}
        ).status_code
        == 202
    )
    assert client.post(f"{path}/retry").status_code == 409
