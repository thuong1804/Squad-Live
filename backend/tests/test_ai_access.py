import json

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.agents.contracts import ProviderError
from app.agents.providers import StructuredProvider, list_models
from app.models.entities import AIConnection
from app.workers.runner import tick
from tests.conftest import OTHER_TOKEN
from tests.test_ba_agent import SPEC, Provider, live, settings
from tests.test_review_revisions import decision


def setup_connections(app, monkeypatch):
    app.state.settings.connection_encryption_key = SecretStr(Fernet.generate_key().decode())
    monkeypatch.setattr("app.api.routes.list_models", lambda *_: ["test-model"])


def create_connection(client):
    response = client.post(
        "/api/v1/ai-connections",
        json={
            "name": "My Gemini",
            "provider": "gemini",
            "model": "test-model",
            "api_key": "private-credential-for-test",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_connections_encrypted_owner_scoped_and_disable(client, app, monkeypatch):
    setup_connections(app, monkeypatch)
    connection_id = create_connection(client)
    response = client.get("/api/v1/ai-connections")
    assert "private-credential" not in response.text and "encrypted_key" not in response.text
    with app.state.sessions() as session:
        connection = session.get(AIConnection, connection_id)
        assert "private-credential" not in connection.encrypted_key
        assert (
            Fernet(app.state.settings.connection_encryption_key.get_secret_value()).decrypt(
                connection.encrypted_key.encode()
            )
            == b"private-credential-for-test"
        )
    assert (
        client.get(
            "/api/v1/ai-connections", headers={"Authorization": f"Bearer {OTHER_TOKEN}"}
        ).json()["items"]
        == []
    )
    path = f"/api/v1/ai-connections/{connection_id}/disable"
    assert client.post(path, headers={"Authorization": f"Bearer {OTHER_TOKEN}"}).status_code == 404
    assert client.post(path).json()["enabled"] is False
    with app.state.sessions() as session:
        assert session.get(AIConnection, connection_id).encrypted_key == ""


def test_disabled_connection_then_switch_preserves_history(client, app, item, monkeypatch):
    path, config = live(client, app, item)
    provider = Provider()
    tick(app.state.sessions, config, provider)
    old = decision(client, path)
    original = client.get(f"{path}/artifacts/{old['artifact_id']}").json()
    connection_id = client.get(path).json()["snapshot"]["connection_id"]
    assert client.post(f"/api/v1/ai-connections/{connection_id}/disable").status_code == 200
    assert (
        client.post(
            f"{path}/approvals", json={**old, "decision": "reject", "comment": "Add permissions"}
        ).status_code
        == 202
    )
    tick(app.state.sessions, config, provider)
    assert len(provider.contexts) == 1
    assert client.get(path).json()["status"] == "failed"
    assert client.post(f"{path}/retry").status_code == 409
    assert client.get(path).json()["attempt"] == 1
    setup_connections(app, monkeypatch)
    new_connection = create_connection(client)
    assert client.post(f"{path}/retry", json={"connection_id": new_connection}).status_code == 202
    tick(app.state.sessions, config, provider)
    assert len(provider.contexts) == 2
    assert "Add permissions" in json.dumps(provider.contexts[-1])
    assert client.get(path).json()["status"] == "requirements_approval"
    assert client.get(f"{path}/artifacts/{old['artifact_id']}").json() == original
    agents = client.get(f"{path}/agent-runs").json()["items"]
    assert agents[-1]["provider"] == "gemini" and agents[-1]["connection_id"] == new_connection
    assert agents[0]["connection_id"] == connection_id


def test_byok_required_even_with_environment_key(client, app, item):
    app.state.settings = settings().model_copy(
        update={"auth_tokens": app.state.settings.auth_tokens}
    )
    path = f"/api/v1/work-items/{item['id']}/workflow-runs"
    response = client.post(path, headers={"Idempotency-Key": "missing"}, json={"mode": "ba_live"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "connection_required"
    # Simulation still works without a key and makes no provider request.
    assert client.post(path, headers={"Idempotency-Key": "mock"}).status_code == 202


def test_own_key_without_default_provider_and_foreign_key(client, app, item, monkeypatch):
    setup_connections(app, monkeypatch)
    connection_id = create_connection(client)
    path = f"/api/v1/work-items/{item['id']}/workflow-runs"
    with app.state.sessions.begin() as session:
        connection = session.get(AIConnection, connection_id)
        connection.owner = "other"
    assert (
        client.post(
            path,
            headers={"Idempotency-Key": "own"},
            json={"mode": "ba_live", "connection_id": connection_id},
        ).status_code
        == 404
    )
    with app.state.sessions.begin() as session:
        session.get(AIConnection, connection_id).owner = "owner"
    response = client.post(
        path,
        headers={"Idempotency-Key": "own"},
        json={"mode": "ba_live", "connection_id": connection_id},
    )
    assert response.status_code == 202
    provider = Provider()
    tick(app.state.sessions, app.state.settings, provider)
    tick(app.state.sessions, app.state.settings, provider)
    assert len(provider.contexts) == 1


def test_bad_key_error_never_echoed(client, app, monkeypatch):
    setup_connections(app, monkeypatch)

    def invalid(*_):
        raise ProviderError("provider_authentication", False)

    monkeypatch.setattr("app.api.routes.list_models", invalid)
    response = client.post(
        "/api/v1/ai-connections/models",
        json={"provider": "gemini", "api_key": "private-credential-for-test"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "provider_authentication"
    assert "private-credential" not in response.text


@pytest.mark.parametrize("provider", ["gemini", "deepseek"])
def test_adapters_schema_and_usage(provider):
    config = settings().model_copy(update={"llm_provider": provider})

    def handler(request):
        payload = json.loads(request.content)
        assert "tools" not in payload
        if provider == "gemini":
            assert "key=" not in str(request.url)
            assert "x-goog-api-key" in request.headers
            assert payload["generationConfig"]["responseJsonSchema"]["type"] == "object"
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(SPEC)}]}}
                    ],
                    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
                },
            )
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(SPEC)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            },
        )

    result = StructuredProvider(config, transport=httpx.MockTransport(handler)).generate(
        "{}", "test-model"
    )
    assert result.specification.title == SPEC["title"]
    assert result.input_tokens == 10 and result.output_tokens == 20


@pytest.mark.parametrize("provider", ["gemini", "deepseek"])
def test_unavailable_model_is_actionable_and_does_not_expose_provider_body(provider):
    config = settings().model_copy(update={"llm_provider": provider})

    def handler(request):
        return httpx.Response(
            404, json={"error": {"message": "Retired model; private-provider-diagnostic"}}
        )

    with pytest.raises(ProviderError) as caught:
        StructuredProvider(config, transport=httpx.MockTransport(handler)).generate(
            "{}", "retired-model"
        )
    assert caught.value.code == "model_unavailable"
    assert caught.value.retryable is False
    assert "private-provider-diagnostic" not in str(caught.value)


@pytest.mark.parametrize("provider", ["gemini", "deepseek", "openai"])
def test_503_retries_are_bounded_and_errors_are_redacted(provider, monkeypatch):
    from app.agents.openai_provider import OpenAIProvider

    config = settings().model_copy(update={"llm_provider": provider})
    calls = []

    async def no_wait(delay):
        pass

    monkeypatch.setattr("app.agents.retry.asyncio.sleep", no_wait)

    def handler(request):
        calls.append(request.method)
        return httpx.Response(503, json={"error": {"message": "private-provider-detail"}})

    adapter = OpenAIProvider if provider == "openai" else StructuredProvider
    with pytest.raises(ProviderError) as caught:
        adapter(config, transport=httpx.MockTransport(handler)).generate("{}", "test-model")
    assert caught.value.code == "provider_service_unavailable"
    assert caught.value.retryable is True
    assert "private-provider-detail" not in str(caught.value)
    assert calls == ["POST", "POST", "POST"]


def test_model_discovery_filters_and_paginates():
    def handler(request):
        if not request.url.query:
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-test",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {"name": "models/embedding"},
                    ],
                    "nextPageToken": "next",
                },
            )
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-test-2",
                        "supportedGenerationMethods": ["generateContent"],
                    }
                ]
            },
        )

    assert list_models("gemini", "test", transport=httpx.MockTransport(handler)) == [
        "gemini-test",
        "gemini-test-2",
    ]
