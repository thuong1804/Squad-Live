"""Create missing local configuration without printing secrets or overwriting files."""

import json
import secrets
from pathlib import Path
from urllib.parse import quote

from cryptography.fernet import Fernet
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[2]
root_env = root / ".env"
if not root_env.exists():
    with root_env.open("x", encoding="utf-8") as stream:
        stream.write(
            "POSTGRES_DB=squad_live\nPOSTGRES_USER=squad_live\n"
            f"POSTGRES_PASSWORD={secrets.token_hex(32)}\nPOSTGRES_PORT=55432\n"
        )
values = dotenv_values(root_env)
backend_env = root / "backend" / ".env"
if not backend_env.exists():
    password = quote(values["POSTGRES_PASSWORD"], safe="")
    user = quote(values["POSTGRES_USER"], safe="")
    database = quote(values["POSTGRES_DB"], safe="")
    port = values.get("POSTGRES_PORT", "5432")
    tokens = json.dumps({"pm-local": secrets.token_urlsafe(48)})
    with backend_env.open("x", encoding="utf-8") as stream:
        stream.write(
            f"DATABASE_URL=postgresql+psycopg://{user}:{password}@127.0.0.1:{port}/{database}\n"
            f"AUTH_TOKENS={tokens}\n"
            'CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]\n'
        )
if not dotenv_values(backend_env).get("CONNECTION_ENCRYPTION_KEY"):
    with backend_env.open("a", encoding="utf-8") as stream:
        stream.write("\nCONNECTION_ENCRYPTION_KEY=" + Fernet.generate_key().decode() + "\n")
print("Local configuration exists. Encryption key ensured; no secrets displayed.")
oauth_defaults = {
    "GOOGLE_CLIENT_ID": "",
    "GOOGLE_CLIENT_SECRET": "",
    "GOOGLE_REDIRECT_URI": "http://localhost:8000/auth/google/callback",
    "FRONTEND_URL": "http://localhost:5173",
    "LEGACY_TOKEN_AUTH_ENABLED": "false",
}
existing = dotenv_values(backend_env)
with backend_env.open("a", encoding="utf-8") as stream:
    for name, value in oauth_defaults.items():
        if name not in existing:
            stream.write(f"{name}={value}\n")
