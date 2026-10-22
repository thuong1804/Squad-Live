"""Real browser/API/worker E2E with a disposable PostgreSQL schema and ephemeral token."""

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import Settings
from app.db.session import make_engine


def main():
    root = Path(__file__).resolve().parents[2]
    backend, frontend = root / "backend", root / "frontend"
    settings = Settings()
    url = settings.database_url.get_secret_value()
    engine = make_engine(url)
    schema = "browser_test_" + uuid4().hex
    processes = []
    test_engine = None
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        scoped_url = (
            make_url(url)
            .update_query_dict({"options": f"-csearch_path={schema}"})
            .render_as_string(hide_password=False)
        )
        test_engine = make_engine(scoped_url)
        config = Config(str(backend / "alembic.ini"))
        with test_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        token = secrets.token_urlsafe(48)
        env = {
            **os.environ,
            "DATABASE_URL": scoped_url,
            "AUTH_TOKENS": json.dumps({"google:browseruser": token}),
            "LEGACY_TOKEN_AUTH_ENABLED": "true",
            "GOOGLE_CLIENT_ID": "offline-test-client",
            "GOOGLE_CLIENT_SECRET": "offline-test-secret",
            "GOOGLE_REDIRECT_URI": "http://127.0.0.1:8001/auth/google/callback",
            "FRONTEND_URL": "http://127.0.0.1:5174",
            "CORS_ORIGINS": '["http://127.0.0.1:5174"]',
            "WORKER_POLL_SECONDS": "0.2",
            "VITE_API_BASE_URL": "http://127.0.0.1:8001",
            "E2E_TOKEN": token,
            "CONNECTION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        }
        commands = [
            (
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "tests.browser_services:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8001",
                ],
                backend,
            ),
            ([sys.executable, "-m", "tests.browser_services"], backend),
            (
                [
                    "node",
                    "node_modules/vite/bin/vite.js",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5174",
                    "--strictPort",
                ],
                frontend,
            ),
        ]
        for args, cwd in commands:
            processes.append(
                subprocess.Popen(
                    args,
                    cwd=cwd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
            )
        with httpx.Client(trust_env=False) as client:
            for _ in range(100):
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError("E2E service exited; verify ports 8001 and 5174 are free")
                try:
                    if (
                        client.get("http://127.0.0.1:8001/ready").status_code == 200
                        and client.get("http://127.0.0.1:5174").status_code == 200
                    ):
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.2)
            else:
                raise RuntimeError("E2E services not ready")
        return subprocess.call(
            ["node", "node_modules/@playwright/test/cli.js", "test"], cwd=frontend, env=env
        )
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if test_engine:
            test_engine.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
