"""Dev AI may write only validated files in a run's isolated worktree."""

from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.agents.contracts import Generation
from app.agents.repo_dev import EditedFile, RepositoryEdit
from tests.conftest import OTHER_TOKEN, TOKEN
from tests.test_workspaces import connected_run


def setup(client, app, monkeypatch, tmp_path):
    app.state.settings.workspace_root = tmp_path / "workspaces"
    app.state.settings.connection_encryption_key = SecretStr(Fernet.generate_key().decode())
    monkeypatch.setattr("app.api.routes.list_models", lambda *_: ["test-model"])
    source, run_id = connected_run(client, tmp_path)
    connection = client.post(
        "/api/v1/ai-connections",
        json={
            "name": "Test model",
            "provider": "gemini",
            "model": "test-model",
            "api_key": "private-credential-for-test",
        },
    )
    assert connection.status_code == 201
    endpoint = f"/api/v1/workflow-runs/{run_id}/workspace"
    workspace = client.post(endpoint).json()["workspace"]
    return source, Path(workspace["worktree_path"]), endpoint, connection.json()["id"]


def test_dev_edits_worktree_and_reuses_idempotent_result(client, app, monkeypatch, tmp_path):
    source, target, endpoint, connection_id = setup(client, app, monkeypatch, tmp_path)
    calls = []

    class Provider:
        def generate(self, context, model):
            calls.append((context, model))
            if len(calls) == 2:
                return Generation(
                    RepositoryEdit(
                        summary="Refined styles",
                        files=[EditedFile(path="new.css", content="h1 { color: blue; }\n")],
                        notes=[],
                    )
                )
            return Generation(
                RepositoryEdit(
                    summary="Updated homepage and styles",
                    files=[
                        EditedFile(path="index.html", content="<h1>New</h1>\n"),
                        EditedFile(path="new.css", content="h1 { color: red; }\n"),
                    ],
                    notes=["Tests were not run"],
                ),
                100,
                50,
            )

    monkeypatch.setattr(
        "app.services.workspace_edits.make_provider", lambda *_args, **_kw: Provider()
    )
    key = str(uuid4())
    response = client.post(
        endpoint + "/edits",
        json={"connection_id": connection_id},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "succeeded"
    assert response.json()["files"] == ["index.html", "new.css"]
    assert "<h1>Old</h1>" in calls[0][0]
    assert "private-credential-for-test" not in calls[0][0]
    assert (target / "index.html").read_text(encoding="utf-8") == "<h1>New</h1>\n"
    assert (target / "new.css").is_file()
    assert (source / "index.html").read_text(encoding="utf-8") == "<h1>Old</h1>\n"
    assert client.get(endpoint).json()["workspace"]["changed_files"] == ["index.html"]

    repeated = client.post(
        endpoint + "/edits",
        json={"connection_id": connection_id},
        headers={"Idempotency-Key": key},
    )
    assert repeated.json()["id"] == response.json()["id"]
    assert len(calls) == 1
    refined = client.post(
        endpoint + "/edits",
        json={"connection_id": connection_id},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert refined.json()["status"] == "succeeded"
    assert "h1 { color: red; }" in calls[1][0]
    assert (target / "new.css").read_text(encoding="utf-8") == "h1 { color: blue; }\n"
    assert client.get(endpoint + "/edits").json()[0]["status"] == "succeeded"
    client.headers["Authorization"] = f"Bearer {OTHER_TOKEN}"
    assert client.get(endpoint + "/edits").status_code == 404
    assert (
        client.post(
            endpoint + "/edits",
            json={"connection_id": connection_id},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 404
    )
    client.headers["Authorization"] = f"Bearer {TOKEN}"


def test_rejects_unsafe_or_unread_files_without_partial_write(client, app, monkeypatch, tmp_path):
    source, target, endpoint, connection_id = setup(client, app, monkeypatch, tmp_path)

    class Provider:
        def generate(self, _context, _model):
            return Generation(
                RepositoryEdit(
                    summary="Attempted invalid edit",
                    files=[
                        EditedFile(path="index.html", content="Changed\n"),
                        EditedFile(path="../escape.py", content="bad\n"),
                    ],
                    notes=[],
                )
            )

    monkeypatch.setattr(
        "app.services.workspace_edits.make_provider", lambda *_args, **_kw: Provider()
    )
    response = client.post(
        endpoint + "/edits",
        json={"connection_id": connection_id},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "workspace_invalid_edit"
    assert (target / "index.html").read_text(encoding="utf-8") == "<h1>Old</h1>\n"
    assert not (source.parent / "escape.py").exists()


def test_does_not_overwrite_file_changed_while_model_runs(client, app, monkeypatch, tmp_path):
    _source, target, endpoint, connection_id = setup(client, app, monkeypatch, tmp_path)

    class Provider:
        def generate(self, _context, _model):
            (target / "index.html").write_text("Human update\n", encoding="utf-8")
            return Generation(
                RepositoryEdit(
                    summary="Updated homepage",
                    files=[EditedFile(path="index.html", content="AI update\n")],
                    notes=[],
                )
            )

    monkeypatch.setattr(
        "app.services.workspace_edits.make_provider", lambda *_args, **_kw: Provider()
    )
    response = client.post(
        endpoint + "/edits",
        json={"connection_id": connection_id},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "workspace_changed"
    assert (target / "index.html").read_text(encoding="utf-8") == "Human update\n"


def test_selected_source_files_limit_existing_edits(client, app, monkeypatch, tmp_path):
    _source, target, endpoint, connection_id = setup(client, app, monkeypatch, tmp_path)

    class Provider:
        def generate(self, context, _model):
            assert "old.css" in context
            assert "<h1>Old</h1>" not in context
            return Generation(
                RepositoryEdit(
                    summary="Tried a different file",
                    files=[EditedFile(path="index.html", content="Wrong file\n")],
                    notes=[],
                )
            )

    monkeypatch.setattr(
        "app.services.workspace_edits.make_provider", lambda *_args, **_kw: Provider()
    )
    response = client.post(
        endpoint + "/edits",
        json={"connection_id": connection_id, "paths": ["old.css"]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "workspace_invalid_edit"
    assert response.json()["source_files"] == ["old.css"]
    assert (target / "index.html").read_text(encoding="utf-8") == "<h1>Old</h1>\n"
