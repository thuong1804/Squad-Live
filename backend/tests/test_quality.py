import json

import pytest
from pydantic import ValidationError

from app.agents.contracts import ProviderError
from app.agents.quality import Assessment
from app.models.entities import WorkflowRun
from app.workers.runner import tick
from tests.test_static_site import ASSESSMENT, approve, reach_plan


def reach_tester(client, app, item):
    path, config, provider = reach_plan(client, app, item)
    approve(client, path)
    for _ in range(2):
        tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "testing_in_progress"
    return path, config, provider


def test_quality_reports_are_bound_to_site_and_never_auto_approve(client, app, item):
    path, config, provider = reach_tester(client, app, item)
    tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "reviewing_in_progress"
    tester = provider.contexts[-1]
    tick(app.state.sessions, config, provider)
    reviewer = provider.contexts[-1]
    run = client.get(path).json()
    assert run["status"] == "pm_review"
    report = client.get(f"{path}/artifacts/{run['gate_artifact_id']}").json()["content"]
    assert reviewer["website_artifact_id"] == tester["website_artifact_id"]
    assert report["website_artifact_id"] == reviewer["website_artifact_id"]
    assert report["tester_report"] == ASSESSMENT == report["reviewer_report"]
    assert report["tester_artifact_id"] == reviewer["tester_artifact_id"]
    assert tick(app.state.sessions, config, provider) is False
    roles = {a["role"] for a in client.get(f"{path}/agent-runs").json()["items"]}
    assert {"TESTER", "REVIEWER"} <= roles


@pytest.mark.parametrize("step", ["testing_in_progress", "reviewing_in_progress"])
def test_quality_failure_retries_only_failed_stage(client, app, item, step):
    path, config, provider = reach_tester(client, app, item)
    if step == "reviewing_in_progress":
        tick(app.state.sessions, config, provider)
    provider.error = ProviderError("provider_service_unavailable")
    tick(app.state.sessions, config, provider)
    assert client.get(path).json()["failed_step"] == step
    assert client.post(f"{path}/retry", json={}).status_code == 202
    provider.error = None
    tick(app.state.sessions, config, provider)
    assert provider.contexts[-1]["stage"] == step
    assert len(client.get(f"{path}/websites").json()["items"]) == 1


def test_cancel_fences_quality_result(client, app, item):
    path, config, provider = reach_tester(client, app, item)
    provider.callback = lambda: client.post(f"{path}/cancel")
    tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "cancelled"
    assert not any(
        a["kind"] == "tester_report" for a in client.get(f"{path}/artifacts").json()["items"]
    )


def test_existing_v1_keeps_simulated_tester(client, app, item):
    path, config, provider = reach_tester(client, app, item)
    with app.state.sessions.begin() as db:
        run = db.get(WorkflowRun, path.rsplit("/", 1)[-1])
        snapshot = json.loads(json.dumps(run.snapshot))
        snapshot.pop("quality_prompt_version")
        snapshot["version"] = "static-site-v1"
        snapshot["automatic"]["testing_in_progress"] = "pm_review"
        run.snapshot = snapshot
    tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "pm_review"
    assert not any(a["role"] == "TESTER" for a in client.get(f"{path}/agent-runs").json()["items"])


def test_ai_cannot_claim_browser_execution_or_ignore_blocking_findings():
    with pytest.raises(ValidationError):
        Assessment.model_validate({**ASSESSMENT, "browser_tests_executed": True})
    with pytest.raises(ValidationError):
        Assessment.model_validate(
            {
                **ASSESSMENT,
                "findings": [
                    {
                        "severity": "critical",
                        "file": "script.js",
                        "evidence": "unsafe operation",
                        "recommendation": "remove it",
                    }
                ],
            }
        )
