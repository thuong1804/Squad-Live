import subprocess

from fastapi.testclient import TestClient

from app.services import repositories
from tests.conftest import OTHER_TOKEN, TOKEN


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_connect_browse_and_disconnect_local_repository(client, tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    (root / "app.py").write_bytes(b"print('hello')\n")
    (root / ".env").write_text("TOKEN=private\n", encoding="utf-8")
    (root / "binary.dat").write_bytes(b"\0data")
    git(root, "add", ".")
    git(root, "commit", "-m", "initial")

    project = client.post("/api/v1/projects", json={"name": "Repo project"}).json()
    base = f"/api/v1/projects/{project['id']}/repository"
    assert client.get(base).status_code == 404
    assert client.post(base, json={"path": str(root / "app.py")}).status_code == 422
    assert client.post(base, json={"path": str(root)}).status_code == 200

    response = client.get(base)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["files"] == ["app.py", "binary.dat"]
    assert not response.json()["dirty"]
    assert len(response.json()["head"]) == 40
    file_response = client.get(f"{base}/file", params={"path": "app.py"})
    assert file_response.json()["content"] == "print('hello')\n"
    assert client.get(f"{base}/file", params={"path": ".env"}).status_code == 404
    assert client.get(f"{base}/file", params={"path": "../outside"}).status_code == 404
    assert client.get(f"{base}/file", params={"path": "binary.dat"}).status_code == 415

    (root / "app.py").write_bytes(b"print('changed')\n")
    assert client.get(base).json()["dirty"]
    file_response = client.get(f"{base}/file", params={"path": "app.py"})
    assert file_response.json()["content"] == "print('changed')\n"

    client.headers["Authorization"] = f"Bearer {OTHER_TOKEN}"
    assert client.get(base).status_code == 404
    assert client.get(f"{base}/file", params={"path": "app.py"}).status_code == 404
    assert client.post(base, json={"path": str(root)}).status_code == 404
    client.headers.pop("Authorization")
    assert client.get(base).status_code == 401
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    assert client.delete(base).json()["repository_path"] is None
    assert client.get(base).status_code == 404


def test_rejects_repository_subfolder(client, tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    folder = root / "nested"
    folder.mkdir()
    (folder / "file.txt").write_text("hello", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "initial")
    project = client.post("/api/v1/projects", json={"name": "Repo project"}).json()
    base = f"/api/v1/projects/{project['id']}/repository"
    assert client.post(base, json={"path": str(folder)}).status_code == 422


def test_local_folder_picker_connects_without_typing_path(client, app, tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("hello", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "initial")
    project = client.post("/api/v1/projects", json={"name": "Picker"}).json()
    endpoint = f"/api/v1/projects/{project['id']}/repository/pick"
    monkeypatch.setattr(repositories, "_choose_directory", lambda: str(root))

    assert client.post(endpoint).status_code == 403
    with TestClient(app, client=("127.0.0.1", 50001)) as local:
        local.headers["Authorization"] = f"Bearer {TOKEN}"
        response = local.post(endpoint)
        assert response.status_code == 200
        assert response.json()["repository_path"] == str(root)
        monkeypatch.setattr(repositories, "_choose_directory", lambda: "")
        assert local.post(endpoint).json()["repository_path"] == str(root)
