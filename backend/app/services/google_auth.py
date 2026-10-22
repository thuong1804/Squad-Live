"""Google OIDC code exchange. Tokens remain server-side and are not persisted."""

import json
import logging

import httpx
import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.core.errors import DomainError

logger = logging.getLogger(__name__)


def exchange_identity(code, verifier, settings):
    stage = "code_exchange"
    try:
        with httpx.Client(timeout=10, trust_env=False) as client:
            with client.stream(
                "POST",
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret.get_secret_value(),
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            ) as response:
                if response.status_code != 200:
                    raise ValueError("Google exchange rejected")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 128000:
                        raise ValueError("Oversized token response")
                token = json.loads(raw)["id_token"]
        stage = "id_token_verification"
        with requests.Session() as http:
            http.trust_env = False
            transport = GoogleRequest(session=http)

            def certificates(*args, **kwargs):
                kwargs["timeout"] = 10
                return transport(*args, **kwargs)

            # Verifies signature, audience, expiry and Google issuer.
            return id_token.verify_oauth2_token(
                token, certificates, settings.google_client_id, clock_skew_in_seconds=120
            )
    except Exception as error:
        logger.warning("Google login failed: stage=%s category=%s", stage, type(error).__name__)
        # Never include token, authorization code or raw HTTP errors in API responses/logs.
        raise DomainError(401, "google_login_failed", "Google authentication failed") from None
