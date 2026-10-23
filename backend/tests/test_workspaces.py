"""Run workspaces isolate source files and expose a reviewable Git diff."""

from pathlib import Path

from tests.conftest import OTHER_TOKEN, TOKEN
from tests.test_repository import git


def connected_run(client, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init")
    git(source, "config", "user.email", "test@example.invalid")
    git(source, "config", "user.name", "Test")
    (source / "index.html").write_text("<h1>Old</h1>\n", encoding="utf-8")
    (source / "old.css").write_text("body { color: black; }\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-m", "initial")
    project = client.post("/api/v1/projects", json={"name": "Repo project"}).json()
    assert (
        client.post(
            f"/api/v1/projects/{project['id']}/repository", json={"path": str(source)}
        ).status_code
        == 200
    )
    item = client.post(
        f"/api/v1/projects/{project['id']}/work-items",
        json={
            "title": "Update site",
            "description": "Change the home page",
            "acceptance_criteria": "Home page is changed",
        },
    ).json()
    response = client.post(
        f"/api/v1/work-items/{item['id']}/workflow-runs",
        headers={"Idempotency-Key": "workspace-test"},
    )
    assert response.status_code == 202
    return source, response.json()["id"]


def test_worktree_is_separate_and_diff_is_scoped_to_owner(client, app, tmp_path):
    app.state.settings.workspace_root = tmp_path / "workspaces"
    source, run_id = connected_run(client, tmp_path)
    endpoint = f"/api/v1/workflow-runs/{run_id}/workspace"
    assert client.get(endpoint).json() == {"workspace": None}

    prepared = client.post(endpoint)
    assert prepared.status_code == 200
    data = prepared.json()["workspace"]
    target = Path(data["worktree_path"])
    assert target.parent == app.state.settings.workspace_root
    assert data["source_path"] == str(source)
    assert len(data["base_commit"]) == 40
    assert client.post(endpoint).json()["workspace"]["worktree_path"] == str(target)

    (target / "index.html").write_text("<h1>New</h1>\n", encoding="utf-8")
    (target / "old.css").unlink()
    (target / "new.css").write_text("h1 { color: red; }\n", encoding="utf-8")
    (target / "staged.js").write_text("console.log('ready');\n", encoding="utf-8")
    git(target, "add", "staged.js")
    (target / ".env").write_text("SECRET=private\n", encoding="utf-8")
    result = client.get(endpoint)
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    diff = result.json()["workspace"]
    assert diff["changed_files"] == ["index.html", "old.css", "staged.js"]
    assert diff["untracked_files"] == ["new.css"]
    assert [(file["path"], file["status"]) for file in diff["files"]] == [
        ("index.html", "modified"),
        ("old.css", "deleted"),
        ("staged.js", "added"),
        ("new.css", "untracked"),
    ]
    assert "+<h1>New</h1>" in diff["files"][0]["diff"]
    assert "h1 { color: red; }" in diff["files"][3]["diff"]
    assert "SECRET=private" not in str(diff["files"])
    assert (source / "index.html").read_text(encoding="utf-8") == "<h1>Old</h1>\n"

    client.headers["Authorization"] = f"Bearer {OTHER_TOKEN}"
    assert client.get(endpoint).status_code == 404
    assert client.post(endpoint).status_code == 404
    client.headers["Authorization"] = f"Bearer {TOKEN}"


def test_dirty_source_cannot_create_workspace(client, app, tmp_path):
    app.state.settings.workspace_root = tmp_path / "workspaces"
    source, run_id = connected_run(client, tmp_path)
    (source / "index.html").write_text("Changed locally\n", encoding="utf-8")
    response = client.post(f"/api/v1/workflow-runs/{run_id}/workspace")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "workspace_source_dirty"
    assert not app.state.settings.workspace_root.exists()
