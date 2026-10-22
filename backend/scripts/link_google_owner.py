"""Explicitly transfer a legacy PM workspace to an already authenticated Google user.

Dry-run by default; --apply performs the transaction. Never selects the first user.
"""

import argparse

from sqlalchemy import func, select, update

from app.core.config import Settings
from app.db.session import make_engine, make_sessions
from app.models.entities import AIConnection, GoogleAccount, Project, WorkItem


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-owner", required=True)
    parser.add_argument("--google-sub", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine = make_engine(Settings().database_url.get_secret_value())
    try:
        with make_sessions(engine).begin() as db:
            target = db.scalar(
                select(GoogleAccount)
                .where(GoogleAccount.subject == args.google_sub)
                .with_for_update()
            )
            if target is None:
                raise SystemExit("Google user must sign in once before transferring ownership.")
            if db.scalar(
                select(GoogleAccount.subject).where(GoogleAccount.identity == args.legacy_owner)
            ):
                raise SystemExit(
                    "Source is already a Google identity; this tool only migrates legacy PMs."
                )
            projects = db.scalar(
                select(func.count()).select_from(Project).where(Project.owner == args.legacy_owner)
            )
            connections = db.scalar(
                select(func.count())
                .select_from(AIConnection)
                .where(AIConnection.owner == args.legacy_owner)
            )
            print(f"Source: {args.legacy_owner}; destination: {target.email} ({target.identity})")
            print(f"Projects: {projects}; AI connections: {connections}")
            if not args.apply:
                print("Dry run only. Repeat with --apply after checking the destination.")
                return
            db.execute(
                update(Project)
                .where(Project.owner == args.legacy_owner)
                .values(owner=target.identity)
            )
            db.execute(
                update(AIConnection)
                .where(AIConnection.owner == args.legacy_owner)
                .values(owner=target.identity)
            )
            db.execute(
                update(WorkItem)
                .where(WorkItem.creator == args.legacy_owner)
                .values(creator=target.identity)
            )
            print("Ownership transferred. Artifacts, approvals and run history were preserved.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
