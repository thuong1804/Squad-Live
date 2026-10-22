import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.errors import DomainError
from app.models.entities import GoogleAccount, PMSession, now

COOKIE_NAME = "squad_pm_session"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


bearer = HTTPBearer(auto_error=False)


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    settings = request.app.state.settings
    if credentials is not None and settings.legacy_token_auth_enabled:
        for identity, token in request.app.state.settings.auth_tokens.items():
            if secrets.compare_digest(
                credentials.credentials.encode(), token.get_secret_value().encode()
            ):
                return identity
    if credentials is not None:
        raise DomainError(401, "unauthorized", "Google sign-in is required")
    if not request.cookies.get(COOKIE_NAME):
        raise DomainError(401, "unauthorized", "Google sign-in is required")
    with request.app.state.sessions() as db:
        result = db.execute(
            select(PMSession, GoogleAccount.identity)
            .join(GoogleAccount)
            .where(
                PMSession.token_hash == digest(request.cookies.get(COOKIE_NAME, "")),
                PMSession.expires_at > now(),
            )
        ).first()
        if result:
            session, identity = result
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                if request.headers.get(
                    "origin"
                ) != settings.frontend_url or not secrets.compare_digest(
                    request.headers.get("X-CSRF-Token", "").encode(), session.csrf_token.encode()
                ):
                    raise DomainError(
                        403, "csrf_invalid", "Session validation failed; reload the page"
                    )
            return identity
    raise DomainError(401, "unauthorized", "Google sign-in is required")
