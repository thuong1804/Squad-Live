import logging
import signal
from threading import Event

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.agents.dev import STAGES
from app.agents.execution import claim, execute
from app.agents.quality import STAGES as QUALITY_STAGES
from app.core.config import Settings
from app.db.session import make_engine, make_sessions
from app.models.entities import AgentRun, WorkflowRun, now
from app.services.sites import advance_site
from app.services.workflows import AUTOMATIC, advance_mock

logger = logging.getLogger(__name__)


def tick(sessions, settings=None, provider=None) -> bool:
    # PostgreSQL row locks make duplicate delivery safe and allow multiple workers.
    # A crash before commit rolls the whole deterministic step back.
    settings = settings or Settings(_env_file=None)
    job = None
    with sessions.begin() as session:
        busy = (
            select(AgentRun.id)
            .where(
                AgentRun.run_id == WorkflowRun.id,
                AgentRun.status == "running",
                AgentRun.lease_expires_at > now(),
            )
            .exists()
        )
        run = session.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.status.in_(AUTOMATIC),
                ~busy,
            )
            .order_by(WorkflowRun.created_at, WorkflowRun.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if run is None:
            return False
        if (
            run.status == "ba_in_progress"
            and run.snapshot["mode"] == "ba_live"
            or run.snapshot["mode"] == "static_site"
            and (
                run.status in STAGES
                or run.snapshot.get("quality_prompt_version")
                and run.status in QUALITY_STAGES
            )
        ):
            job = claim(session, run, settings)
        elif run.snapshot["mode"] == "static_site":
            advance_site(session, run)
        else:
            advance_mock(session, run)
    if job:
        execute(sessions, job, settings, provider)
    return True


def main():
    logging.basicConfig(
        level=logging.INFO, format='{"level":"%(levelname)s","event":"%(message)s"}'
    )
    settings = Settings()
    engine = make_engine(settings.database_url.get_secret_value())
    if engine.dialect.name != "postgresql":
        raise SystemExit("The production worker requires PostgreSQL row locking")
    sessions = make_sessions(engine)
    stopped = Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    failures = 0
    try:
        while not stopped.is_set():
            try:
                worked = tick(sessions, settings)
                failures = 0
                if not worked:
                    stopped.wait(settings.worker_poll_seconds)
            except SQLAlchemyError:
                # Never log raw DB exceptions: they may contain credentials or request data.
                failures += 1
                logger.error("worker_database_unavailable")
                if failures >= 5:
                    raise SystemExit("Worker stopped after five database failures") from None
                stopped.wait(min(2**failures, 30))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
