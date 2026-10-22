import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from pydantic import ValidationError

from app.agents.contracts import Generation, ProviderError
from app.agents.dev import SitePlan, StaticSite
from app.agents.quality import Assessment
from app.agents.execution import claim, execute
from app.models.entities import AgentRun, WorkflowRun
from app.workers.runner import tick
from tests.conftest import OTHER_TOKEN
from tests.test_ba_agent import Provider, seed_connection, settings
from tests.test_review_revisions import decision

PLAN = {
    "title": "Todo page",
    "summary": "A small static website",
    "steps": ["Create a button"],
    "acceptance_checks": ["Click increments counter"],
    "limitations": ["No backend"],
}
ASSESSMENT = {
    "summary": "Source assessment only",
    "verdict": "ready_for_pm",
    "browser_tests_executed": False,
    "findings": [],
    "manual_checks": ["Click Count: the displayed number should increase."],
    "limitations": ["No browser executed"],
}
SITE = {
    "title": "Todo page",
    "summary": "Interactive static page",
    "notes": [],
    "files": [
        {
            "path": "index.html",
            "content": (
                '<!doctype html><html><head><link rel="stylesheet" href="./styles.css">'
                '<script src="./script.js" defer></script></head><body>'
                '<h1>Static website</h1><button id="count">Count 0</button></body></html>'
            ),
        },
        {
            "path": "styles.css",
            "content": "body { background: #f3f6fa; font-family: sans-serif; padding: 24px; }",
        },
        {
            "path": "script.js",
            "content": (
                "let n=0; document.querySelector('#count').addEventListener('click', e => { "
                "e.target.textContent = 'Count ' + (++n); });"
            ),
        },
    ],
}


class SiteProvider(Provider):
    def generate(self, context, model):
        data = json.loads(context)
        if "stage" not in data:
            return super().generate(context, model)
        self.contexts.append(data)
        if self.error:
            raise self.error
        if self.callback:
            self.callback()
        result = (
            Assessment.model_validate(ASSESSMENT)
            if data["stage"] in {"testing_in_progress", "reviewing_in_progress"}
            else SitePlan.model_validate(PLAN)
            if data["stage"] == "plan_in_progress"
            else StaticSite.model_validate(SITE)
        )
        return Generation(result, 20, 100)


def start_site(client, app, item):
    config = settings()
    config.auth_tokens = app.state.settings.auth_tokens
    app.state.settings = config
    connection = seed_connection(app.state.sessions, config)
    response = client.post(
        f"/api/v1/work-items/{item['id']}/workflow-runs",
        headers={"Idempotency-Key": "site"},
        json={"mode": "static_site", "connection_id": connection},
    )
    assert response.status_code == 202, response.text
    return f"/api/v1/workflow-runs/{response.json()['id']}", config


def approve(client, path):
    response = client.post(
        f"{path}/approvals", json={**decision(client, path), "decision": "approve"}
    )
    assert response.status_code == 202, response.text


def reach_plan(client, app, item):
    path, config = start_site(client, app, item)
    provider = SiteProvider()
    for _ in range(2):
        tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "requirements_approval"
    assert tick(app.state.sessions, config, provider) is False
    approve(client, path)
    tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "plan_approval"
    assert client.get(f"{path}/websites").json()["items"] == []
    return path, config, provider


def test_full_site_approved_inputs_download_owner_isolation_and_revisions(client, app, item):
    path, config, provider = reach_plan(client, app, item)
    approved_plan = decision(client, path)["artifact_id"]
    approve(client, path)
    for _ in range(4):
        tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "pm_review"
    version = client.get(f"{path}/websites").json()["items"][0]
    url = f"{path}/websites/{version['id']}"
    site = client.get(url).json()
    assert len(site["files"]) == 3
    assert "Content-Security-Policy" in site["preview_html"]
    assert "data:text/javascript;base64," in site["preview_html"]
    assert provider.contexts[-1]["plan_artifact_id"] == approved_plan
    assert provider.contexts[-1]["approved_plan"]["specification"] == PLAN
    download = client.get(url + "/download")
    assert download.headers["content-type"] == "application/zip"
    assert download.headers["content-disposition"].startswith("attachment;")
    with ZipFile(BytesIO(download.content)) as archive:
        assert set(archive.namelist()) == {"index.html", "styles.css", "script.js"}
        assert archive.read("script.js").decode() == SITE["files"][2]["content"]
    for suffix in [
        "/websites",
        f"/websites/{version['id']}",
        f"/websites/{version['id']}/download",
    ]:
        assert (
            client.get(
                path + suffix, headers={"Authorization": f"Bearer {OTHER_TOKEN}"}
            ).status_code
            == 404
        )
    old_gate = decision(client, path)
    assert (
        client.post(
            f"{path}/approvals",
            json={
                **old_gate,
                "decision": "reject",
                "return_to": "plan_in_progress",
                "comment": "Add a footer",
            },
        ).status_code
        == 202
    )
    tick(app.state.sessions, config, provider)
    assert provider.contexts[-1]["pm_feedback"] == "Add a footer"
    assert provider.contexts[-1]["previous_website"] == SITE
    approve(client, path)
    for _ in range(4):
        tick(app.state.sessions, config, provider)
    assert client.get(url).json() == site
    assert len(client.get(f"{path}/websites").json()["items"]) == 2
    assert (
        client.post(f"{path}/approvals", json={**old_gate, "decision": "approve"}).status_code
        == 409
    )
    approve(client, path)
    assert client.get(path).json()["status"] == "completed"
    agents = client.get(f"{path}/agent-runs").json()["items"]
    assert [a["role"] for a in agents].count("DEV_BUILD") == 2


def test_cancel_during_dev_fences_output(client, app, item):
    path, config, provider = reach_plan(client, app, item)
    approve(client, path)
    provider.callback = lambda: client.post(f"{path}/cancel")
    tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "cancelled"
    assert client.get(f"{path}/websites").json()["items"] == []


def test_dev_failure_can_retry_with_new_connection_and_preserves_approved_plan(client, app, item):
    path, config, provider = reach_plan(client, app, item)
    approve(client, path)
    provider.error = ProviderError("model_unavailable", False)
    tick(app.state.sessions, config, provider)
    assert client.get(path).json()["failed_step"] == "implementation_in_progress"
    connection = seed_connection(app.state.sessions, config)
    assert client.post(f"{path}/retry", json={"connection_id": connection}).status_code == 202
    provider.error = None
    tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "checks_in_progress"
    assert client.get(f"{path}/websites").json()["items"][0]["attempt"] == 2


def test_expired_dev_lease_discards_late_result(client, app, item):
    from datetime import timedelta

    from app.models.entities import now

    path, config, provider = reach_plan(client, app, item)
    approve(client, path)
    with app.state.sessions.begin() as db:
        run = db.get(WorkflowRun, path.rsplit("/", 1)[-1])
        job = claim(db, run, config)
    with app.state.sessions.begin() as db:
        db.get(AgentRun, job.agent_id).lease_expires_at = now() - timedelta(seconds=1)
    execute(app.state.sessions, job, config, provider)
    assert client.get(path).json()["status"] == "failed"
    assert client.get(f"{path}/websites").json()["items"] == []


@pytest.mark.parametrize("bad_path", ["../index.html", "/etc/passwd", "C:\\test.html", "script.js"])
def test_site_rejects_traversal_and_duplicate_files(bad_path):
    value = json.loads(json.dumps(SITE))
    value["files"][0]["path"] = bad_path
    with pytest.raises(ValidationError):
        StaticSite.model_validate(value)
