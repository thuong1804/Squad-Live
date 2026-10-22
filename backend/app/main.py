import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.auth import router as auth_router
from app.api.routes import router
from app.core.config import Settings
from app.core.errors import DomainError
from app.db.session import make_engine, make_sessions

logger = logging.getLogger(__name__)


class HideOAuthCallback(logging.Filter):
    def filter(self, record):
        return "/auth/google/callback" not in record.getMessage()


# OAuth codes are query parameters; never write callback URLs to access logs.
logging.getLogger("uvicorn.access").addFilter(HideOAuthCallback())


def error_response(status, code, message):
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(
        status_code=status, headers=headers, content={"error": {"code": code, "message": message}}
    )


def create_app(settings: Settings | None = None, engine=None):
    settings = settings or Settings()
    owns_engine = engine is None
    engine = engine if engine is not None else make_engine(settings.database_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(_app):
        yield
        if owns_engine:
            engine.dispose()

    api = FastAPI(title="Squad Live API", version="0.1.0", lifespan=lifespan)
    api.state.settings = settings
    api.state.sessions = make_sessions(engine)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-CSRF-Token"],
    )

    @api.exception_handler(DomainError)
    async def domain_error(_request, exc):
        return error_response(exc.status, exc.code, exc.message)

    @api.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        # Do not echo untrusted request values, tokens, or Pydantic exception contexts.
        return error_response(422, "validation_error", "Request does not match the API schema")

    @api.exception_handler(HTTPException)
    async def http_error(_request, exc):
        return error_response(exc.status_code, "http_error", "Request could not be handled")

    @api.exception_handler(IntegrityError)
    async def integrity_error(_request, _exc):
        return error_response(409, "conflict", "Concurrent change conflicts with this request")

    @api.exception_handler(SQLAlchemyError)
    async def database_error(_request, _exc):
        logger.error('{"event":"database_unavailable"}')
        return error_response(503, "database_unavailable", "Database is unavailable")

    @api.exception_handler(Exception)
    async def unexpected_error(_request: Request, _exc: Exception):
        logger.error('{"event":"unexpected_error"}')
        return error_response(500, "internal_error", "An internal error occurred")

    @api.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    @api.get("/ready", tags=["health"])
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                version = connection.scalar(text("SELECT version_num FROM alembic_version"))
                if version != "0005_google_auth":
                    return error_response(503, "not_ready", "Database migrations are required")
        except SQLAlchemyError:
            return error_response(503, "not_ready", "Database is unavailable or not migrated")
        return {"status": "ready"}

    api.include_router(router)
    api.include_router(auth_router)
    return api


app = create_app()
