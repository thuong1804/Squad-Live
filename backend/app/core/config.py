from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr("postgresql+psycopg://localhost/squad_live")
    auth_tokens: dict[str, SecretStr] = Field(default_factory=dict)
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    worker_poll_seconds: float = Field(default=1, ge=0.1, le=60)

    @field_validator("auth_tokens")
    @classmethod
    def valid_tokens(cls, tokens):
        values = [token.get_secret_value() for token in tokens.values()]
        if any(not name.strip() or len(name) > 200 for name in tokens):
            raise ValueError("Identity must contain 1 to 200 characters")
        if any(len(value) < 32 for value in values) or len(set(values)) != len(values):
            raise ValueError("Tokens must be unique and at least 32 characters")
        return tokens
