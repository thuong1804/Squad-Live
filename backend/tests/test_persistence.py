import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text

from alembic import command
from app.core.errors import DomainError
from app.db.session import make_engine, make_sessions
from app.models.entities import Base, WorkflowEvent, WorkflowRun
from app.schemas.contracts import ApprovalCreate, ProjectCreate, WorkItemCreate
from app.services.projects import create_item, create_project
from app.services.workflows import approve, start, transition
from app.workers.runner import tick
from tests.conftest import migrate


def test_migration_matches_models_and_roundtrip(engine):
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
        command.upgrade(config, "head")


def test_invalid_transition_and_transaction_rollback(app, run):
    with pytest.raises(DomainError):
        with app.state.sessions.begin() as session:
            stored = session.get(WorkflowRun, run["id"])
            transition(session, stored, "completed")
    with pytest.raises(RuntimeError):
        with app.state.sessions.begin() as session:
            stored = session.get(WorkflowRun, run["id"])
            transition(session, stored, "ba_in_progress")
            session.flush()
            raise RuntimeError("simulate crash before commit")
    with app.state.sessions() as session:
        assert session.get(WorkflowRun, run["id"]).status == "queued"
        assert len(session.scalars(select(WorkflowEvent)).all()) == 1


@pytest.mark.postgres
def test_postgres_migrations_concurrency_and_restart():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for real PostgreSQL integration")
    engine = make_engine(url)
    schema = "test_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_engine = engine.execution_options(schema_translate_map={None: schema})
    # Alembic version table and reflection also need the test schema search path.
    from sqlalchemy import event

    @event.listens_for(engine, "checkout")
    def search_path(connection, *_):
        with connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}"')
        connection.commit()

    try:
        migrate(test_engine)
        sessions = make_sessions(test_engine)
        with sessions.begin() as session:
            project = create_project(session, ProjectCreate(name="Concurrent"), "owner")
            item = create_item(
                session, project.id, WorkItemCreate(title="Task", description="Test"), "owner"
            )
            item_id = item.id

        def enqueue(_):
            with sessions.begin() as session:
                return start(session, item_id, "same-key", "owner").id

        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(enqueue, range(8)))
        assert len(set(ids)) == 1
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: tick(sessions), range(8)))
        # A fresh session verifies persisted state, independent of worker memory.
        with sessions() as session:
            assert session.get(WorkflowRun, ids[0]).status == "requirements_approval"
            events = session.scalars(select(WorkflowEvent)).all()
            assert sum(e.event_type == "mock_requirements" for e in events) == 1

        def decide(_):
            try:
                with sessions.begin() as session:
                    approve(
                        session,
                        ids[0],
                        ApprovalCreate(
                            step="requirements_approval",
                            attempt=1,
                            gate_id=session.get(WorkflowRun, ids[0]).gate_id,
                            artifact_id=session.get(WorkflowRun, ids[0]).gate_artifact_id,
                            decision="approve",
                        ),
                        "owner",
                    )
                return "accepted"
            except DomainError as error:
                assert error.status == 409
                return "conflict"

        with ThreadPoolExecutor(max_workers=4) as pool:
            decisions = list(pool.map(decide, range(8)))
        assert decisions.count("accepted") == 1
        assert decisions.count("conflict") == 7
        with test_engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
