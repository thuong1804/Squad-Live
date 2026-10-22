"""Immutable per-run website workspace stored in artifacts, never executed on the host."""

import base64
from html import escape
from html.parser import HTMLParser
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select

from app.agents.dev import StaticSite
from app.core.errors import DomainError
from app.models.entities import Artifact
from app.services.workflows import event, fail_execution, transition


def latest_site(db, run):
    return db.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == run.id, Artifact.kind == "website", Artifact.revision == run.revision
        )
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    )


def site_for(db, run, artifact_id):
    artifact = db.get(Artifact, artifact_id)
    if artifact is None or artifact.run_id != run.id or artifact.kind != "website":
        raise DomainError(404, "not_found", "Website artifact not found")
    return artifact, StaticSite.model_validate(artifact.content["specification"])


def advance_site(db, run):
    if run.status == "queued":
        transition(db, run, "ba_in_progress")
        return
    artifact = latest_site(db, run)
    if artifact is None:
        fail_execution(db, run, retryable=False)
        run.failure_reason = "Thiếu phiên bản website để kiểm tra hoặc duyệt."
        return
    # This validates the file bundle, not browser behavior or acceptance criteria.
    StaticSite.model_validate(artifact.content["specification"])
    if run.status == "checks_in_progress":
        event(
            db,
            run,
            "site_bundle_checked",
            artifact_id=artifact.id,
            checks=["three_unique_allowed_files", "size_budget", "html_entrypoint"],
            browser_tests_executed=False,
        )
        transition(db, run, "testing_in_progress")
    elif run.status == "testing_in_progress":
        event(
            db,
            run,
            "mock_evidence",
            simulated=True,
            executed=False,
            summary="Tester is simulated. PM must inspect the website preview.",
        )
        transition(
            db,
            run,
            "pm_review",
            review_content={
                "simulated": False,
                "source": "static_site",
                "website_artifact_id": artifact.id,
                "title": "Website sẵn sàng để PM xem trước",
                "checks": ["Đủ ba file hợp lệ", "Đúng giới hạn kích thước", "Có trang index.html"],
                "tester_simulated": True,
                "notice": (
                    "Mã nguồn đã được tạo. Chưa chạy kiểm thử trình duyệt tự động cho website này."
                ),
            },
        )


def archive(site):
    data = BytesIO()
    with ZipFile(data, "w", ZIP_DEFLATED) as bundle:
        for file in site.files:
            bundle.writestr(file.path, file.content.encode("utf-8"))
    return data.getvalue()


class PreviewHTML(HTMLParser):
    def __init__(self, files):
        super().__init__(convert_charrefs=False)
        self.files, self.parts = files, []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        path = (values.get("src") if tag == "script" else values.get("href")) or ""
        path = path.removeprefix("./")
        if (tag == "script" and path == "script.js") or (
            tag == "link" and path == "styles.css" and values.get("rel") == "stylesheet"
        ):
            mime = "text/javascript" if tag == "script" else "text/css"
            source = base64.b64encode(self.files[path].encode()).decode()
            attr = "src" if tag == "script" else "href"
            attrs = [
                (key, value)
                for key, value in attrs
                if key not in {attr, "integrity", "crossorigin"}
            ]
            attrs.append((attr, f"data:{mime};base64,{source}"))
            self.parts.append(
                "<"
                + tag
                + "".join(f' {key}="{escape(value or "", quote=True)}"' for key, value in attrs)
                + ">"
            )
        else:
            self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_comment(self, data):
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.parts.append(f"<!{decl}>")


def preview(site):
    parser = PreviewHTML({file.path: file.content for file in site.files})
    parser.feed(parser.files["index.html"])
    parser.close()
    # First policy is enforced even if generated HTML adds its own, more permissive policy.
    # Paired with iframe sandbox=allow-scripts (never allow-same-origin).
    policy = (
        "default-src 'none'; script-src 'unsafe-inline' data:; style-src 'unsafe-inline' data:; "
        "img-src data:; font-src data:; connect-src 'none'; frame-src 'none'; "
        "object-src 'none'; base-uri 'none'; form-action 'none'"
    )
    return (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
        f'content="{escape(policy, quote=True)}">' + "".join(parser.parts)
    )
