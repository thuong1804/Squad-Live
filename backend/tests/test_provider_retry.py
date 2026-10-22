import asyncio

import httpx
import pytest

from app.agents.contracts import ProviderError
from app.agents.providers import request_json


@pytest.mark.parametrize("statuses", [[503, 200], [503, 503, 200]])
def test_recovers_from_service_rejection(monkeypatch, statuses):
    calls, waits, responses = [], [], []

    async def sleep(delay):
        waits.append(delay)

    def respond(request):
        calls.append(request)
        response = httpx.Response(statuses[len(calls) - 1], json={"ok": True})
        responses.append(response)
        return response

    monkeypatch.setattr("app.agents.retry.asyncio.sleep", sleep)
    result = asyncio.run(request_json("gemini", "secret", "/test", body={},
                                     transport=httpx.MockTransport(respond)))
    assert result == {"ok": True}
    assert len(calls) == len(statuses)
    assert 2 <= waits[0] <= 3
    if len(waits) == 2:
        assert 4 <= waits[1] <= 5
    assert all(response.is_closed for response in responses)


@pytest.mark.parametrize("status,code,count", [
    (503, "provider_service_unavailable", 3),
    (429, "provider_rate_limit", 1),
    (401, "provider_authentication", 1),
    (400, "provider_request_rejected", 1),
])
def test_bounded_retries_and_nontransient_failures(monkeypatch, status, code, count):
    calls = []

    async def sleep(delay):
        pass

    def respond(request):
        calls.append(request)
        return httpx.Response(status)

    monkeypatch.setattr("app.agents.retry.asyncio.sleep", sleep)
    with pytest.raises(ProviderError) as error:
        asyncio.run(request_json("gemini", "secret", "/test", body={},
                                 transport=httpx.MockTransport(respond)))
    assert error.value.code == code
    assert len(calls) == count


def test_retries_share_the_total_deadline():
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(503)

    with pytest.raises(ProviderError) as error:
        asyncio.run(request_json("gemini", "secret", "/test", body={}, timeout=0.02,
                                 transport=httpx.MockTransport(respond)))
    assert error.value.code == "provider_timeout"
    assert len(calls) == 1


def test_network_timeout_is_not_replayed():
    calls = []

    def respond(request):
        calls.append(request)
        raise httpx.ReadTimeout("unknown completion", request=request)

    with pytest.raises(ProviderError) as error:
        asyncio.run(request_json("gemini", "secret", "/test", body={},
                                 transport=httpx.MockTransport(respond)))
    assert error.value.code == "provider_timeout"
    assert len(calls) == 1
