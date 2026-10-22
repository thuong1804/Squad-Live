"""Fixed-host provider adapters; no arbitrary URLs or raw provider errors."""

import asyncio
import json
import re

import httpx

from app.agents.ba import SYSTEM_PROMPT
from app.agents.contracts import Generation, ProviderError, RequirementSpecification
from app.agents.openai_provider import OpenAIProvider
from app.agents.retry import service_stream

HOSTS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}


async def request_json(provider, key, path, *, body=None, timeout=10, transport=None):
    headers = (
        {"x-goog-api-key": key} if provider == "gemini" else {"Authorization": f"Bearer {key}"}
    )
    try:
        async with asyncio.timeout(timeout):
            async with httpx.AsyncClient(
                timeout=timeout, trust_env=False, transport=transport
            ) as client:
                async with service_stream(
                    client,
                    "POST" if body is not None else "GET",
                    HOSTS[provider] + path,
                    headers=headers,
                    json=body,
                ) as response:
                    code = response.status_code
                    if code in (401, 403):
                        raise ProviderError("provider_authentication", False)
                    if code == 402:
                        raise ProviderError("provider_quota_exhausted", False)
                    if code == 429:
                        raise ProviderError("provider_rate_limit")
                    if code == 404 and body is not None:
                        raise ProviderError("model_unavailable", False)
                    if code == 503:
                        raise ProviderError("provider_service_unavailable")
                    if code >= 500:
                        raise ProviderError("provider_unavailable")
                    if code != 200:
                        raise ProviderError("provider_request_rejected", False)
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 1_000_000:
                            raise ProviderError("invalid_output")
                    return json.loads(raw)
    except (TimeoutError, httpx.TimeoutException):
        raise ProviderError("provider_timeout") from None
    except httpx.HTTPError:
        raise ProviderError("provider_unavailable") from None
    except (ValueError, TypeError):
        raise ProviderError("invalid_output") from None


def valid_model(model):
    return isinstance(model, str) and bool(re.fullmatch(r"[a-zA-Z0-9._-]{1,120}", model))


def list_models(provider, key, *, transport=None):
    async def fetch():
        models = set()
        path = "/models"
        # Bound pagination. Provider listing is access discovery, not an inference guarantee.
        for _ in range(10):
            data = await request_json(provider, key, path, transport=transport)
            if provider == "gemini":
                for model in data.get("models", []):
                    name = model.get("name", "").removeprefix("models/")
                    if "generateContent" in model.get(
                        "supportedGenerationMethods", []
                    ) and valid_model(name):
                        models.add(name)
                token = data.get("nextPageToken")
                if not token:
                    break
                from urllib.parse import urlencode

                path = "/models?" + urlencode({"pageToken": token})
            else:
                for model in data.get("data", []):
                    name = model.get("id", "")
                    if valid_model(name) and (
                        provider == "deepseek" or name.startswith(("gpt-", "o1", "o3", "o4"))
                    ):
                        models.add(name)
                break
        return sorted(models)

    async def bounded_fetch():
        async with asyncio.timeout(10):
            return await fetch()

    try:
        return asyncio.run(bounded_fetch())
    except TimeoutError:
        raise ProviderError("provider_timeout") from None
    except (AttributeError, KeyError, TypeError):
        raise ProviderError("invalid_output") from None


class StructuredProvider:
    def __init__(
        self,
        settings,
        *,
        transport=None,
        output_type=RequirementSpecification,
        system_prompt=SYSTEM_PROMPT,
    ):
        self.settings, self.transport = settings, transport
        self.output_type, self.system_prompt = output_type, system_prompt

    def generate(self, context, model):
        settings = self.settings
        if not valid_model(model):
            raise ProviderError("provider_request_rejected", False)
        schema = self.output_type.model_json_schema()
        provider = settings.llm_provider
        if provider == "gemini":
            path = f"/models/{model}:generateContent"
            body = {
                "systemInstruction": {"parts": [{"text": self.system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": context}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema,
                    "maxOutputTokens": settings.llm_max_output_tokens,
                },
            }
        else:
            path = "/chat/completions"
            body = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": self.system_prompt + "\nJSON schema: " + json.dumps(schema),
                    },
                    {"role": "user", "content": context},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": settings.llm_max_output_tokens,
            }
        data = asyncio.run(
            request_json(
                provider,
                settings.openai_api_key.get_secret_value(),
                path,
                body=body,
                timeout=settings.llm_timeout_seconds,
                transport=self.transport,
            )
        )
        try:
            if provider == "gemini":
                candidates = data.get("candidates", [])
                if not candidates:
                    raise ProviderError("provider_refusal", False)
                if candidates[0].get("finishReason") != "STOP":
                    raise ProviderError("incomplete_output")
                output = "".join(part.get("text", "") for part in candidates[0]["content"]["parts"])
                usage = data.get("usageMetadata") or {}
                input_tokens, output_tokens = (
                    usage.get("promptTokenCount"),
                    usage.get("candidatesTokenCount"),
                )
            else:
                choice = data["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ProviderError("incomplete_output")
                output = choice["message"]["content"]
                usage = data.get("usage") or {}
                input_tokens, output_tokens = (
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                )
            specification = self.output_type.model_validate_json(output)

            def count(value):
                return value if type(value) is int and value >= 0 else None

            return Generation(specification, count(input_tokens), count(output_tokens))
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError("invalid_output") from None


def make_provider(settings, **kwargs):
    return (
        OpenAIProvider(settings, **kwargs)
        if settings.llm_provider == "openai"
        else StructuredProvider(settings, **kwargs)
    )
