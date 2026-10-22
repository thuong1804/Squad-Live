import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import delete, select

from app.core.errors import DomainError
from app.core.security import COOKIE_NAME, current_user, digest
from app.models.entities import GoogleAccount, LoginAttempt, PMSession, now
from app.services.google_auth import exchange_identity

router = APIRouter(prefix="/auth", tags=["authentication"])
FLOW_COOKIE = "squad_google_login"


def cookie_options(settings):
    return {
        "httponly": True,
        "secure": settings.google_redirect_uri.startswith("https://"),
        "samesite": "lax",
    }


def login_result(settings, error=None):
    target = settings.frontend_url + "/dashboard"
    if error:
        target += "?" + urlencode({"auth_error": error})
    response = RedirectResponse(target, status_code=303)
    response.delete_cookie(FLOW_COOKIE, path="/auth/google", **cookie_options(settings))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/config")
def auth_config(request: Request):
    return JSONResponse(
        {"google_enabled": request.app.state.settings.google_ready},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/google/start")
def google_start(request: Request):
    settings = request.app.state.settings
    if not settings.google_ready:
        return login_result(settings, "not_configured")
    state, browser, nonce, verifier = [secrets.token_urlsafe(32) for _ in range(4)]
    with request.app.state.sessions.begin() as db:
        db.execute(delete(LoginAttempt).where(LoginAttempt.expires_at <= now()))
        db.execute(delete(PMSession).where(PMSession.expires_at <= now()))
        db.add(
            LoginAttempt(
                state_hash=digest(state),
                browser_hash=digest(browser),
                nonce=nonce,
                verifier=verifier,
                expires_at=now() + timedelta(minutes=10),
            )
        )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))
    response.set_cookie(
        FLOW_COOKIE, browser, max_age=600, path="/auth/google", **cookie_options(settings)
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/google/callback")
def google_callback(
    request: Request,
    state: str = Query(default="", max_length=256),
    code: str = Query(default="", max_length=4096),
    error: str = Query(default="", max_length=256),
):
    settings = request.app.state.settings
    if not settings.google_ready:
        return login_result(settings, "not_configured")
    browser = request.cookies.get(FLOW_COOKIE, "")
    with request.app.state.sessions.begin() as db:
        # Atomic single-use consumption across multiple API processes.
        attempt = db.execute(
            delete(LoginAttempt)
            .where(
                LoginAttempt.state_hash == digest(state),
                LoginAttempt.browser_hash == digest(browser),
                LoginAttempt.expires_at > now(),
            )
            .returning(LoginAttempt.nonce, LoginAttempt.verifier)
        ).first()
    if not state or not browser or attempt is None:
        return login_result(settings, "invalid_session")
    if error or not code:
        return login_result(settings, "cancelled")
    try:
        claims = exchange_identity(code, attempt.verifier, settings)
        nonce = claims.get("nonce")
        subject, email = claims.get("sub"), claims.get("email")
        if (
            not isinstance(nonce, str)
            or not secrets.compare_digest(nonce.encode(), attempt.nonce.encode())
            or not isinstance(subject, str)
            or not subject.isascii()
            or not subject.isalnum()
            or len(subject) > 100
            or not subject
            or not isinstance(email, str)
            or len(email) > 320
            or claims.get("email_verified") is not True
        ):
            raise DomainError(401, "google_login_failed", "Google identity is invalid")
    except DomainError:
        return login_result(settings, "login_failed")
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    with request.app.state.sessions.begin() as db:
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        values = {
            "subject": subject,
            "identity": "google:" + subject,
            "email": email,
            "display_name": str(claims.get("name") or email)[:200],
            "created_at": now(),
        }
        db.execute(
            insert(GoogleAccount)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["subject"],
                set_={"email": email, "display_name": values["display_name"]},
            )
        )
        # Rotate any previous local session instead of keeping both valid.
        db.execute(
            delete(PMSession).where(
                PMSession.token_hash == digest(request.cookies.get(COOKIE_NAME, ""))
            )
        )
        db.add(
            PMSession(
                token_hash=digest(token),
                subject=subject,
                csrf_token=csrf,
                expires_at=now() + timedelta(days=settings.session_days),
            )
        )
    response = login_result(settings)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        path="/",
        **cookie_options(settings),
    )
    return response


@router.get("/session")
def browser_session(request: Request):
    if not request.cookies.get(COOKIE_NAME):
        return JSONResponse({"authenticated": False}, headers={"Cache-Control": "no-store"})
    with request.app.state.sessions() as db:
        result = db.execute(
            select(PMSession, GoogleAccount)
            .join(GoogleAccount)
            .where(
                PMSession.token_hash == digest(request.cookies.get(COOKIE_NAME, "")),
                PMSession.expires_at > now(),
            )
        ).first()
        if result is None:
            return JSONResponse({"authenticated": False}, headers={"Cache-Control": "no-store"})
        session, account = result
        return JSONResponse(
            {
                "authenticated": True,
                "identity": account.identity,
                "display_name": account.display_name,
                "email": account.email,
                "csrf_token": session.csrf_token,
            },
            headers={"Cache-Control": "no-store"},
        )


@router.post("/logout")
def logout(request: Request, user: str = Depends(current_user)):
    with request.app.state.sessions.begin() as db:
        db.execute(
            delete(PMSession).where(
                PMSession.token_hash == digest(request.cookies.get(COOKIE_NAME, ""))
            )
        )
    response = JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
    response.delete_cookie(COOKIE_NAME, path="/", **cookie_options(request.app.state.settings))
    return response
