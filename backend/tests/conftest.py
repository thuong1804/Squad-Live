import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event

from alembic import command
from app.core.config import Settings
from app.db.session import make_engine
from app.main import create_app

TOKEN = "test-owner-token-" + "a" * 32
OTHER_TOKEN = "test-other-token-" + "b" * 32


def migrate(engine):
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    migrate(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def app(engine):
    return create_app(
        Settings(
            _env_file=None,
            auth_tokens={
                "owner": TOKEN,
                "other": OTHER_TOKEN,
            },
        ),
        engine,
    )


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        yield client


@pytest.fixture
def item(client):
    project = client.post("/api/v1/projects", json={"name": "Example"})
    assert project.status_code == 201
    response = client.post(
        f"/api/v1/projects/{project.json()['id']}/work-items",
        json={
            "title": "Feature",
            "description": "Build the requested feature",
            "acceptance_criteria": "Expected behavior is verified",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def run(client, item):
    response = client.post(
        f"/api/v1/work-items/{item['id']}/workflow-runs", headers={"Idempotency-Key": "initial"}
    )
    assert response.status_code == 202
    return response.json()


@pytest.fixture
def legacy_run(run, app):
    from app.models.entities import WorkflowRun

    with app.state.sessions.begin() as session:
        stored = session.get(WorkflowRun, run["id"])
        snapshot = dict(stored.snapshot)
        snapshot["version"] = "deterministic-v1"
        snapshot.pop("revision_targets", None)
        stored.snapshot = snapshot
    return run
