"""Offline BYOK browser fixture. Only the verification script launches this module.

API, auth, DB, encryption, workflow and worker are real. Provider I/O is replaced
with a fixture and must never be used as a production entrypoint.
"""

from app.agents.contracts import ProviderError
from app.api import auth, routes
from app.main import app as app
from app.workers import runner
from tests.test_static_site import SiteProvider


def offline_models(provider, key):
    if key != "browser-only-fake-key":
        raise ProviderError("provider_authentication", False)
    return ["test-model"]


routes.list_models = offline_models


def offline_identity(code, verifier, settings):
    if not code.startswith("fixture-"):
        raise ValueError("Only offline test identity is accepted")
    return {
        "sub": "browseruser",
        "email": "pm@example.test",
        "email_verified": True,
        "name": "Browser PM",
        "nonce": code.removeprefix("fixture-"),
    }


auth.exchange_identity = offline_identity
original_tick = runner.tick


def offline_tick(sessions, settings=None, provider=None):
    return original_tick(sessions, settings, SiteProvider())


if __name__ == "__main__":
    runner.tick = offline_tick
    runner.main()
