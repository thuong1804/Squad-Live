import secrets
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import DomainError

bearer = HTTPBearer(auto_error=False)


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if credentials is not None:
        for identity, token in request.app.state.settings.auth_tokens.items():
            if secrets.compare_digest(
                credentials.credentials.encode(), token.get_secret_value().encode()
            ):
                return identity
    raise DomainError(401, "unauthorized", "A valid bearer token is required")
