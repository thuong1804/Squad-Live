"""Owner-scoped encrypted BYOK connections."""

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy import select

from app.core.errors import DomainError
from app.models.entities import AIConnection


def cipher(settings):
    try:
        return Fernet(settings.connection_encryption_key.get_secret_value().encode())
    except (ValueError, TypeError):
        raise DomainError(
            503, "key_storage_unavailable", "AI key encryption is not configured"
        ) from None


def storage_ready(settings):
    try:
        cipher(settings)
        return True
    except DomainError:
        return False


def connection_for(session, connection_id, user, *, lock=False):
    query = select(AIConnection).where(AIConnection.id == connection_id, AIConnection.owner == user)
    if lock:
        query = query.with_for_update()
    connection = session.scalar(query)
    if connection is None:
        raise DomainError(404, "not_found", "AI connection not found")
    if not connection.enabled:
        raise DomainError(409, "connection_disabled", "AI connection is disabled")
    return connection


def resolve(session, user, settings, connection_id=None):
    if connection_id:
        connection = connection_for(session, connection_id, user)
        try:
            key = cipher(settings).decrypt(connection.encrypted_key.encode()).decode()
        except (InvalidToken, UnicodeError):
            raise DomainError(
                503, "key_storage_unavailable", "AI connection cannot be decrypted"
            ) from None
        return settings.model_copy(
            update={
                "llm_provider": connection.provider,
                "llm_model": connection.model,
                "openai_api_key": SecretStr(key),
            }
        )
    raise DomainError(422, "connection_required", "Choose a saved API key and model connection")
