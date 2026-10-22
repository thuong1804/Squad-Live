"""Run PostgreSQL integration tests against a disposable, loopback-only Docker database."""

import os
import secrets
import subprocess
import sys
import time
from uuid import uuid4


def main():
    name = "squad-live-test-" + uuid4().hex[:12]
    password = secrets.token_hex(24)
    env = {**os.environ, "POSTGRES_PASSWORD": password}
    started = False
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--publish",
                "127.0.0.1::5432",
                "--env",
                "POSTGRES_PASSWORD",
                "--env",
                "POSTGRES_USER=squad_test",
                "--env",
                "POSTGRES_DB=squad_test",
                "--tmpfs",
                "/var/lib/postgresql/data",
                "postgres:17",
            ],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        started = True
        for _ in range(60):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    name,
                    "pg_isready",
                    "-U",
                    "squad_test",
                    "-d",
                    "squad_test",
                ],
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Temporary PostgreSQL did not become ready")
        binding = subprocess.check_output(
            [
                "docker",
                "port",
                name,
                "5432/tcp",
            ],
            text=True,
        ).strip()
        port = int(binding.rsplit(":", 1)[1])
        env["TEST_DATABASE_URL"] = (
            f"postgresql+psycopg://squad_test:{password}@127.0.0.1:{port}/squad_test"
        )
        return subprocess.call([sys.executable, "-m", "pytest", "-q", "-m", "postgres"], env=env)
    finally:
        if started:
            subprocess.run(["docker", "rm", "--force", name], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    raise SystemExit(main())
