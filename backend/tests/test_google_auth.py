from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import auth
from app.core.config import Settings
from app.core.errors import DomainError
from app.core.security import COOKIE_NAME, digest
from app.main import create_app
from app.models.entities import GoogleAccount, LoginAttempt, PMSession, now
from tests.conftest import TOKEN


@pytest.fixture
def google_app(engine):
    return create_app(
        Settings(
            _env_file=None,
            google_client_id="test-client",
            google_client_secret="test-secret",
            frontend_url="http://localhost:5173",
        ),
        engine,
    )


def start(client):
    response = client.get("/auth/google/start", follow_redirects=False)
    assert response.status_code == 307
    params = parse_qs(urlsplit(response.headers["location"]).query)
    assert params["scope"] == ["openid email profile"]
    assert params["code_challenge_method"] == ["S256"]
    assert "test-secret" not in response.headers["location"]
    return params


def finish(client, params):
    return client.get(
        "/auth/google/callback",
        params={"state": params["state"][0], "code": "test-code"},
        follow_redirects=False,
    )


def claims(params, **changes):
    return {
        "sub": "12345",
        "email": "pm@example.test",
        "email_verified": True,
        "name": "Example PM",
        "nonce": params["nonce"][0],
        **changes,
    }


def test_google_session_persists_rotates_and_logout_revokes(google_app, engine, monkeypatch):
    with TestClient(google_app) as client:
        params = start(client)
        monkeypatch.setattr(auth, "exchange_identity", lambda *_: claims(params))
        response = finish(client, params)
        assert response.headers["location"] == "http://localhost:5173/dashboard"
        assert (
            "HttpOnly" in response.headers["set-cookie"]
            and "SameSite=lax" in response.headers["set-cookie"]
        )
        token = client.cookies.get(COOKIE_NAME)
        info = client.get("/auth/session").json()
        assert info["identity"] == "google:12345"
        assert info["display_name"] == "Example PM"
        assert token not in str(info)
        with google_app.state.sessions() as db:
            stored = db.scalar(select(PMSession))
            assert stored.token_hash == digest(token) and stored.token_hash != token
        headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": info["csrf_token"]}
        assert (
            client.post("/api/v1/projects", json={"name": "Mine"}, headers=headers).status_code
            == 201
        )
        restarted = create_app(google_app.state.settings, engine)
        with TestClient(restarted) as restored:
            restored.cookies.update(client.cookies)
            assert restored.get("/api/v1/projects").json()["items"][0]["name"] == "Mine"
        assert client.post("/auth/logout", headers=headers).status_code == 200
        client.cookies.set(COOKIE_NAME, token)
        assert client.get("/api/v1/projects").status_code == 401
        assert client.get("/auth/session").json() == {"authenticated": False}


def test_state_browser_binding_expiry_and_replay(google_app, monkeypatch):
    calls = []
    with TestClient(google_app) as client:
        params = start(client)
        monkeypatch.setattr(auth, "exchange_identity", lambda *_: calls.append(1) or claims(params))
        with TestClient(google_app) as attacker:
            assert "invalid_session" in finish(attacker, params).headers["location"]
        assert calls == []
        assert "auth_error" not in finish(client, params).headers["location"]
        assert "invalid_session" in finish(client, params).headers["location"]
        assert calls == [1]
        params = start(client)
        with google_app.state.sessions.begin() as db:
            db.get(LoginAttempt, digest(params["state"][0])).expires_at = now() - timedelta(
                seconds=1
            )
        assert "invalid_session" in finish(client, params).headers["location"]


@pytest.mark.parametrize("changes", [{"nonce": "wrong"}, {"email_verified": False}, {"sub": ""}])
def test_invalid_claims_do_not_create_session(google_app, monkeypatch, changes):
    with TestClient(google_app) as client:
        params = start(client)
        monkeypatch.setattr(auth, "exchange_identity", lambda *_: claims(params, **changes))
        assert "login_failed" in finish(client, params).headers["location"]
        assert client.get("/auth/session").json()["authenticated"] is False


def test_csrf_owner_isolation_and_legacy_disabled(google_app, monkeypatch):
    with TestClient(google_app) as client:
        params = start(client)
        monkeypatch.setattr(auth, "exchange_identity", lambda *_: claims(params))
        finish(client, params)
        csrf = client.get("/auth/session").json()["csrf_token"]
        for headers in (
            {},
            {"Origin": "http://evil.test", "X-CSRF-Token": csrf},
            {"Origin": "http://localhost:5173", "X-CSRF-Token": "wrong"},
        ):
            assert (
                client.post("/api/v1/projects", json={"name": "No"}, headers=headers).status_code
                == 403
            )
        headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf}
        project = client.post("/api/v1/projects", json={"name": "Private"}, headers=headers).json()
        assert (
            client.get("/api/v1/projects", headers={"Authorization": f"Bearer {TOKEN}"}).status_code
            == 401
        )
        params = start(client)
        monkeypatch.setattr(auth, "exchange_identity", lambda *_: claims(params, sub="67890"))
        finish(client, params)
        assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404
        with google_app.state.sessions() as db:
            assert len(db.scalars(select(GoogleAccount)).all()) == 2


def test_google_error_and_cancel_are_safe(google_app, monkeypatch):
    with TestClient(google_app) as client:
        params = start(client)

        def failure(*_):
            raise DomainError(401, "google_login_failed", "private-google-message")

        monkeypatch.setattr(auth, "exchange_identity", failure)
        response = finish(client, params)
        assert "private-google-message" not in str(response.headers)
        assert "login_failed" in response.headers["location"]
        params = start(client)
        response = client.get(
            "/auth/google/callback",
            params={"state": params["state"][0], "error": "access_denied"},
            follow_redirects=False,
        )
        assert "cancelled" in response.headers["location"]


@pytest.mark.parametrize(
    "invalid", [None, "audience", "issuer", "expired", "signature", "small_skew", "future"]
)
def test_real_google_token_verification_with_offline_certificate(monkeypatch, invalid):
    import json
    import time
    from datetime import UTC, datetime

    import httpx
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from google.auth import crypt, jwt

    from app.services import google_auth

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Offline Google test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private.public_key())
        .serial_number(1)
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .sign(private, hashes.SHA256())
    )
    payload = {
        "iss": "https://accounts.google.com",
        "aud": "client",
        "sub": "123",
        "iat": int(time.time()) - 10,
        "exp": int(time.time()) + 600,
        "nonce": "nonce",
        "email_verified": True,
    }
    if invalid == "audience":
        payload["aud"] = "other-client"
    if invalid == "issuer":
        payload["iss"] = "https://attacker.example"
    if invalid == "expired":
        payload["exp"] = int(time.time()) - 121
    if invalid == "small_skew":
        payload["iat"] = int(time.time()) + 113
    if invalid == "future":
        payload["iat"] = int(time.time()) + 180
    signed = jwt.encode(crypt.RSASigner.from_string(pem, key_id="test"), payload).decode()
    if invalid == "signature":
        parts = signed.split(".")
        parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
        signed = ".".join(parts)
    original_client = httpx.Client

    def endpoint(request):
        assert str(request.url) == "https://oauth2.googleapis.com/token"
        assert b"code_verifier=verifier" in request.content
        return httpx.Response(200, json={"id_token": signed})

    monkeypatch.setattr(
        google_auth.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(endpoint), **kwargs),
    )

    class CertResponse:
        status = 200
        data = json.dumps({"test": cert.public_bytes(serialization.Encoding.PEM).decode()}).encode()

    monkeypatch.setattr(
        google_auth, "GoogleRequest", lambda **_: lambda *args, **kwargs: CertResponse()
    )
    config = Settings(_env_file=None, google_client_id="client", google_client_secret="secret")
    if invalid and invalid != "small_skew":
        with pytest.raises(DomainError, match="Google authentication failed"):
            google_auth.exchange_identity("code", "verifier", config)
    else:
        assert google_auth.exchange_identity("code", "verifier", config)["sub"] == "123"
