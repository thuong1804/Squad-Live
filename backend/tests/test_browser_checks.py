import json

from app.agents.browser import generate
from app.agents.dev import StaticSite
from app.services.sites import preview
from tests.test_static_site import SITE


def test_browser_observes_script_error_overflow_and_blocked_resource():
    site = json.loads(json.dumps(SITE))
    site["files"][0]["content"] = site["files"][0]["content"].replace(
        "</body>", '<img src="https://example.invalid/track.png"></body>'
    )
    site["files"][1]["content"] += " body { width: 1800px; }"
    site["files"][2]["content"] += "; throw new Error('observed-test-error')"
    report = generate(json.dumps({"preview_html": preview(StaticSite.model_validate(site))}))
    views = report.specification.viewports
    assert [view.viewport for view in views] == ["desktop", "mobile"]
    assert all(view.loaded and view.horizontal_overflow for view in views)
    assert all(
        any("observed-test-error" in error for error in view.javascript_errors) for view in views
    )
    assert all(view.broken_images > 0 or view.resource_errors for view in views)
    assert all(view.screenshot_base64 for view in views)
