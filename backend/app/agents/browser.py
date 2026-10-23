"""Bounded browser checks, isolated from worker secrets and database transactions."""

import json
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field

from app.agents.contracts import Generation, ProviderError, Structured

PROMPT_VERSION = "browser-checks-v1"


class ViewportResult(Structured):
    viewport: Literal["desktop", "mobile"]
    width: int
    height: int
    loaded: bool
    horizontal_overflow: bool
    broken_images: int = Field(ge=0)
    javascript_errors: list[str] = Field(max_length=20)
    resource_errors: list[str] = Field(max_length=20)
    screenshot_base64: str = Field(max_length=1000000, pattern=r"^[A-Za-z0-9+/=]+$")


class BrowserReport(Structured):
    browser_tests_executed: Literal[True]
    engine: Literal["chromium"]
    viewports: list[ViewportResult] = Field(min_length=2, max_length=2)
    scope: str


def summary(report):
    return {
        **report,
        "viewports": [
            {key: value for key, value in viewport.items() if key != "screenshot_base64"}
            for viewport in report["viewports"]
        ],
    }


def generate(context):
    data = json.loads(context)
    root = Path(__file__).resolve().parents[3]
    module = root / "frontend" / "node_modules" / "playwright"
    node = shutil.which("node")
    if not node or not module.exists():
        raise ProviderError("browser_unavailable", False)
    # The child gets no API credentials, DB URL, auth tokens or worker environment.
    env = {
        name: value
        for name, value in os.environ.items()
        if name.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LOCALAPPDATA", "HOME", "PATH"}
    }
    with tempfile.TemporaryDirectory(prefix="squad-browser-") as directory:
        with subprocess.Popen(
            [node, str(Path(__file__).with_name("browser_runner.cjs")), str(module)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=directory,
            env=env,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ) as process:
            try:
                output, _ = process.communicate(
                    json.dumps({"html": data["preview_html"]}).encode(), timeout=45
                )
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=10,
                    )
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                if process.poll() is None:
                    process.kill()
                process.communicate()
                raise ProviderError("browser_timeout") from None
            if process.returncode or len(output) > 2500000:
                raise ProviderError("browser_unavailable")
    try:
        return Generation(BrowserReport.model_validate_json(output))
    except ValueError:
        raise ProviderError("invalid_output") from None
