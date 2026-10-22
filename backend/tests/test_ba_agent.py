import json
from datetime import timedelta

import httpx
import pytest
from cryptography.fernet import Fernet

from app.agents.contracts import Generation, ProviderError, RequirementSpecification
from app.agents.execution import claim, execute
from app.agents.openai_provider import OpenAIProvider
from app.core.config import Settings
from app.models.entities import AgentRun, AIConnection, WorkflowRun, now
from app.workers.runner import tick
from tests.conftest import OTHER_TOKEN
from tests.test_review_revisions import decision

SPEC = {
    "title": "Example requirements",
    "summary": "A reviewable request",
    "user_stories": [
        {"id": "US1", "role": "PM", "goal": "Review a request", "benefit": "Control scope"}
    ],
    "acceptance_criteria": [
        {
            "id": "AC1",
            "story_id": "US1",
            "given": "A request exists",
            "when": "PM reviews",
            "then": "A decision is recorded",
        }
    ],
    "edge_cases": [],
    "non_functional_requirements": [],
    "open_questions": ["Who may review?"],
    "assumptions": [],
}


def settings():
    return Settings(
        _env_file=None,
        legacy_token_auth_enabled=True,
        ba_live_enabled=True,
        llm_model="test-model",
        openai_api_key="test-provider-key-not-real",
        connection_encryption_key=Fernet.generate_key().decode(),
    )


class Provider:
    def __init__(self, callback=None, error=None):
        self.contexts = []
        self.callback = callback
        self.error = error

    def generate(self, context, model):
        self.contexts.append(json.loads(context))
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return Generation(RequirementSpecification.model_validate(SPEC), 123, 45)


def seed_connection(sessions, config):
    from app.services.ai_access import cipher

    with sessions.begin() as session:
        connection = AIConnection(
            owner="owner",
            name="Test",
            provider="openai",
            model="test-model",
            encrypted_key=cipher(config).encrypt(b"test-provider-key-not-real").decode(),
        )
        session.add(connection)
        session.flush()
        return connection.id


def live(client, app, item):
    config = settings()
    config.auth_tokens = app.state.settings.auth_tokens
    app.state.settings = config
    connection_id = seed_connection(app.state.sessions, config)
    response = client.post(
        f"/api/v1/work-items/{item['id']}/workflow-runs",
        headers={"Idempotency-Key": "live"},
        json={"mode": "ba_live", "connection_id": connection_id},
    )
    assert response.status_code == 202, response.text
    tick(app.state.sessions, config)
    return f"/api/v1/workflow-runs/{response.json()['id']}", config


def test_disabled_and_capabilities(client, item):
    assert client.get("/api/v1/capabilities").json()["ba_live_available"] is False
    response = client.post(
        f"/api/v1/work-items/{item['id']}/workflow-runs",
        headers={"Idempotency-Key": "live"},
        json={"mode": "ba_live"},
    )
    assert response.status_code == 422


def test_live_revision_and_immutable_artifact(client, app, item):
    path, config = live(client, app, item)
    provider = Provider()
    tick(app.state.sessions, config, provider)
    old = decision(client, path)
    original = client.get(f"{path}/artifacts/{old['artifact_id']}").json()
    assert original["content"]["simulated"] is False
    assert original["content"]["specification"] == SPEC
    assert (
        client.post(
            f"{path}/approvals", json={**old, "decision": "reject", "comment": "Clarify roles"}
        ).status_code
        == 202
    )
    tick(app.state.sessions, config, provider)
    assert "Clarify roles" in json.dumps(provider.contexts[-1])
    assert SPEC["title"] in json.dumps(provider.contexts[-1])
    assert client.get(path).json()["revision"] == 2
    assert client.post(f"{path}/approvals", json=old).status_code == 409
    assert client.get(f"{path}/artifacts/{old['artifact_id']}").json() == original
    agents = client.get(f"{path}/agent-runs").json()["items"]
    assert len(agents) == 2 and all(a["status"] == "succeeded" for a in agents)
    assert agents[0]["input_tokens"] == 123
    assert config.openai_api_key.get_secret_value() not in json.dumps(agents)
    assert (
        client.get(
            f"{path}/agent-runs", headers={"Authorization": f"Bearer {OTHER_TOKEN}"}
        ).status_code
        == 404
    )
    assert client.post(f"{path}/approvals", json=decision(client, path)).status_code == 202
    tick(app.state.sessions, config, provider)
    plan = client.get(path).json()
    assert plan["status"] == "plan_approval"
    assert (
        client.get(f"{path}/artifacts/{plan['gate_artifact_id']}").json()["content"]["simulated"]
        is True
    )


def test_cancellation_during_call_fences_result(client, app, item):
    path, config = live(client, app, item)

    def cancel():
        # A separate request writes while generate runs: no long DB transaction/lock.
        assert client.post(f"{path}/cancel", json={"reason": "Stop"}).status_code == 202

    tick(app.state.sessions, config, Provider(callback=cancel))
    assert client.get(path).json()["status"] == "cancelled"
    assert client.get(f"{path}/artifacts").json()["items"] == []
    assert client.get(f"{path}/agent-runs").json()["items"][0]["status"] == "discarded"


def test_expired_lease_no_automatic_replay_and_late_result(client, app, item):
    path, config = live(client, app, item)
    with app.state.sessions.begin() as session:
        job = claim(session, session.get(WorkflowRun, path.rsplit("/", 1)[-1]), config)
    provider = Provider()
    assert tick(app.state.sessions, config, provider) is False
    with app.state.sessions.begin() as session:
        session.get(AgentRun, job.agent_id).lease_expires_at = now() - timedelta(seconds=1)
    tick(app.state.sessions, config, provider)
    assert provider.contexts == []
    assert client.get(path).json()["status"] == "failed"
    execute(app.state.sessions, job, config, provider)
    assert client.get(f"{path}/artifacts").json()["items"] == []
    assert client.post(f"{path}/retry").status_code == 202
    tick(app.state.sessions, config, provider)
    assert client.get(path).json()["status"] == "requirements_approval"


def test_failure_bounded_retry_and_no_secret(client, app, item):
    path, config = live(client, app, item)
    provider = Provider(error=ProviderError("provider_timeout"))
    for attempt in range(1, 4):
        tick(app.state.sessions, config, provider)
        run = client.get(path).json()
        assert run["status"] == "failed" and run["attempt"] == attempt
        assert client.post(f"{path}/retry").status_code == (202 if attempt < 3 else 409)
    assert client.get(f"{path}/artifacts").json()["items"] == []


def response_body(spec=SPEC):
    return {
        "status": "completed",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(spec)}]}
        ],
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


def test_openai_wire_contract():
    def handler(request):
        body = json.loads(request.content)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert body["store"] is False and "tools" not in body
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        return httpx.Response(200, json=response_body())

    result = OpenAIProvider(settings(), transport=httpx.MockTransport(handler)).generate(
        "{}", "test-model"
    )
    assert result.specification.title == SPEC["title"] and result.output_tokens == 50


@pytest.mark.parametrize(
    "status,body,code,retryable",
    [
        (401, {}, "provider_authentication", False),
        (429, {}, "provider_rate_limit", True),
        (500, {}, "provider_unavailable", True),
        (400, {}, "provider_request_rejected", False),
        (200, {"status": "incomplete"}, "incomplete_output", True),
        (200, response_body({}), "invalid_output", True),
        (
            200,
            {
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "refusal"}]}],
            },
            "provider_refusal",
            False,
        ),
    ],
)
def test_provider_errors(status, body, code, retryable):
    provider = OpenAIProvider(
        settings(), transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body))
    )
    with pytest.raises(ProviderError) as error:
        provider.generate("{}", "test-model")
    assert error.value.code == code and error.value.retryable is retryable


def test_timeout_and_invalid_references():
    def timeout(_):
        raise httpx.ReadTimeout("secret details must never escape")

    with pytest.raises(ProviderError, match="^provider_timeout$"):
        OpenAIProvider(settings(), transport=httpx.MockTransport(timeout)).generate(
            "{}", "test-model"
        )
    with pytest.raises(ValueError, match="unknown story"):
        RequirementSpecification.model_validate(
            {**SPEC, "user_stories": [{**SPEC["user_stories"][0], "id": "US2"}]}
        )
