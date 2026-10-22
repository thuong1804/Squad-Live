"""Verify the documented Uvicorn entrypoint over a real loopback HTTP connection."""

import os
import socket
import subprocess
import sys
import time

import httpx


def test_uvicorn_health_docs_and_readiness_without_db():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {
        **os.environ,
        "DATABASE_URL": "postgresql+psycopg://127.0.0.1:1/unavailable",
        "AUTH_TOKENS": "{}",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            for _ in range(100):
                assert process.poll() is None, "Uvicorn exited before becoming ready"
                try:
                    response = client.get("/health", timeout=0.5)
                    break
                except httpx.TransportError:
                    time.sleep(0.1)
            else:
                raise AssertionError("Uvicorn did not start in time")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            assert client.get("/docs").status_code == 200
            # Allow the configured 5-second DB connect timeout plus HTTP overhead.
            assert client.get("/ready", timeout=10).status_code == 503
            assert client.get("/api/v1/projects").status_code == 401
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
