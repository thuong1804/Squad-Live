import os
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr("postgresql+psycopg://localhost/squad_live")
    auth_tokens: dict[str, SecretStr] = Field(default_factory=dict)
    legacy_token_auth_enabled: bool = False
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    frontend_url: str = "http://localhost:5173"
    session_days: int = Field(default=7, ge=1, le=30)
    workspace_root: Path = Field(
        default_factory=lambda: Path(os.environ.get("LOCALAPPDATA", Path.home()))
        / "SquadLive"
        / "worktrees"
    )

    @field_validator("workspace_root")
    @classmethod
    def valid_workspace_root(cls, value: Path):
        if not value.is_absolute():
            raise ValueError("Workspace root must be an absolute path")
        return value

    @property
    def google_ready(self):
        return bool(self.google_client_id and self.google_client_secret.get_secret_value())

    @field_validator("frontend_url", "google_redirect_uri")
    @classmethod
    def valid_auth_url(cls, value, info):
        url = urlsplit(value)
        if url.username or url.password or url.query or url.fragment or not url.hostname:
            raise ValueError("Auth URLs must not contain credentials, queries or fragments")
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1"}
        ):
            raise ValueError("Auth requires HTTPS except on loopback")
        if info.field_name == "frontend_url" and url.path not in {"", "/"}:
            raise ValueError("Frontend URL must be an origin")
        return value.rstrip("/")

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    worker_poll_seconds: float = Field(default=1, ge=0.1, le=60)
    llm_provider: str = "openai"
    llm_model: str = Field(default="", max_length=120, pattern=r"^[a-zA-Z0-9._:/-]*$")
    openai_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    deepseek_api_key: SecretStr = SecretStr("")
    connection_encryption_key: SecretStr = SecretStr("")
    llm_timeout_seconds: int = Field(default=90, ge=5, le=180)
    llm_max_output_tokens: int = Field(default=4096, ge=512, le=8192)
    dev_max_output_tokens: int = Field(default=16384, ge=2048, le=32768)

    @field_validator("auth_tokens")
    @classmethod
    def valid_tokens(cls, tokens):
        values = [token.get_secret_value() for token in tokens.values()]
        if any(not name.strip() or len(name) > 200 for name in tokens):
            raise ValueError("Identity must contain 1 to 200 characters")
        if any(len(value) < 32 for value in values) or len(set(values)) != len(values):
            raise ValueError("Tokens must be unique and at least 32 characters")
        return tokens
