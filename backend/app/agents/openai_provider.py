"""Responses API adapter. Never persist/log request bodies, headers or raw errors."""

import asyncio
import json

import httpx
from pydantic import ValidationError

from app.agents.ba import SYSTEM_PROMPT
from app.agents.contracts import Generation, ProviderError, RequirementSpecification
from app.agents.retry import service_stream


class OpenAIProvider:
    def __init__(
        self,
        settings,
        *,
        transport=None,
        output_type=RequirementSpecification,
        system_prompt=SYSTEM_PROMPT,
    ):
        self.settings = settings
        self.transport = transport
        self.output_type, self.system_prompt = output_type, system_prompt

    def generate(self, context: str, model: str) -> Generation:
        return asyncio.run(self._generate(context, model))

    async def _generate(self, context: str, model: str) -> Generation:
        settings = self.settings
        key = settings.openai_api_key.get_secret_value()
        if not key or not model:
            raise ProviderError("configuration_missing", retryable=False)
        payload = {
            "model": model,
            "store": False,
            "input": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": context},
            ],
            "max_output_tokens": settings.llm_max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": self.output_type.__name__,
                    "strict": True,
                    "schema": self.output_type.model_json_schema(),
                }
            },
        }
        try:
            async with asyncio.timeout(settings.llm_timeout_seconds):
                async with httpx.AsyncClient(
                    timeout=settings.llm_timeout_seconds, trust_env=False, transport=self.transport
                ) as client:
                    async with service_stream(
                        client,
                        "POST",
                        "https://api.openai.com/v1/responses",
                        headers={"Authorization": f"Bearer {key}"},
                        json=payload,
                    ) as response:
                        if response.status_code in (401, 403):
                            raise ProviderError("provider_authentication", retryable=False)
                        if response.status_code == 404:
                            raise ProviderError("model_unavailable", retryable=False)
                        if response.status_code == 429:
                            raise ProviderError("provider_rate_limit")
                        if response.status_code == 503:
                            raise ProviderError("provider_service_unavailable")
                        if response.status_code >= 500:
                            raise ProviderError("provider_unavailable")
                        if response.status_code != 200:
                            raise ProviderError("provider_request_rejected", retryable=False)
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            raw.extend(chunk)
                            if len(raw) > 1_000_000:
                                raise ProviderError("invalid_output")
                        body = json.loads(raw)
        except (TimeoutError, httpx.TimeoutException):
            raise ProviderError("provider_timeout") from None
        except httpx.HTTPError:
            raise ProviderError("provider_unavailable") from None
        except (ValueError, TypeError):
            raise ProviderError("invalid_output") from None
        try:
            if body.get("status") != "completed":
                raise ProviderError("incomplete_output")
            parts = [
                part
                for output in body.get("output", [])
                if output.get("type") == "message"
                for part in output.get("content", [])
            ]
            if any(part.get("type") == "refusal" for part in parts):
                raise ProviderError("provider_refusal", retryable=False)
            output = "".join(part["text"] for part in parts if part.get("type") == "output_text")
            if len(output) > 200000:
                raise ProviderError("invalid_output")
            specification = self.output_type.model_validate_json(output)
            usage = body.get("usage") or {}

            def count(name):
                value = usage.get(name)
                return value if type(value) is int and value >= 0 else None

            return Generation(specification, count("input_tokens"), count("output_tokens"))
        except (ValidationError, ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError("invalid_output") from None
