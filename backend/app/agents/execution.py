"""Claim/execute/commit with short DB transactions and fenced, expiring leases."""

import json
import re
from dataclasses import dataclass, field
from datetime import timedelta
from time import monotonic

from sqlalchemy import select

from app.agents import browser, dev, quality
from app.agents.ba import PROMPT_VERSION, build_context
from app.agents.contracts import ProviderError, RequirementSpecification
from app.agents.providers import make_provider
from app.core.errors import DomainError
from app.models.entities import (
    AgentRun,
    Approval,
    Artifact,
    Project,
    WorkflowRun,
    WorkItem,
    new_id,
    now,
)
from app.services import ai_access
from app.services.workflows import event, fail_execution, transition

ERROR_MESSAGES = {
    "browser_unavailable": (
        "Browser checks could not run. Verify Node, Playwright and Chromium installation."
    ),
    "browser_timeout": (
        "Browser checks exceeded the time limit. Inspect generated scripts before retrying."
    ),
    "provider_service_unavailable": (
        "Nhà cung cấp AI tạm thời không sẵn sàng (HTTP 503). "
        "Hãy chờ rồi thử lại hoặc chọn kết nối với model khác. "
        "Tài liệu đã duyệt và lịch sử được giữ nguyên."
    ),
    "approved_input_missing": (
        "Thiếu tài liệu đã duyệt để Dev tiếp tục. Hãy kiểm tra lịch sử duyệt."
    ),
    "model_unavailable": (
        "Model không còn khả dụng hoặc không hỗ trợ API đang dùng. "
        "Thêm kết nối với model khác trong Cài đặt AI, rồi chọn kết nối đó để thử lại bước lỗi."
    ),
    "provider_timeout": "BA timed out. You may retry the failed step.",
    "provider_rate_limit": "LLM provider rate limit reached. Retry later.",
    "provider_unavailable": "LLM provider is unavailable. Retry later.",
    "provider_authentication": "LLM credentials or permissions need administrator attention.",
    "provider_request_rejected": "LLM model or output configuration was rejected by the provider.",
    "configuration_missing": "Live BA configuration is missing or disabled on the worker.",
    "provider_refusal": "The provider declined this request. Review the work item.",
    "incomplete_output": "AI chưa trả đủ kết quả. Kiểm tra giới hạn token rồi thử lại bước lỗi.",
    "invalid_output": "BA output did not match the requirements schema. No review was opened.",
    "context_too_large": "BA context exceeds the configured size limit. Shorten the request.",
    "worker_interrupted": "BA execution expired. Retry may incur another provider call.",
    "execution_error": "BA execution failed unexpectedly. No raw provider error was stored.",
    "connection_required": "Chọn kết nối API key trong Cài đặt AI để tiếp tục.",
    "connection_disabled": "Kết nối AI đã bị tắt. Chọn kết nối khác để tiếp tục.",
    "key_storage_unavailable": "Không đọc được API key. Kiểm tra cấu hình mã hóa trên backend.",
    "provider_quota_exhausted": "Hết quota hoặc số dư tại nhà cung cấp. Chọn kết nối khác.",
}


@dataclass(frozen=True)
class Job:
    run_id: str
    agent_id: str
    context: str
    model: str
    settings: object = field(repr=False)
    step: str = "ba_in_progress"


def redact(text: str, settings) -> str:
    # Defense in depth for accidentally pasted known credentials; never load them into context.
    secrets = [
        settings.openai_api_key.get_secret_value(),
        settings.database_url.get_secret_value(),
        settings.gemini_api_key.get_secret_value(),
        settings.deepseek_api_key.get_secret_value(),
    ]
    secrets.extend(value.get_secret_value() for value in settings.auth_tokens.values())
    for secret in secrets:
        if len(secret) >= 8:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{16,}\b", "[REDACTED]", text)
    return re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~-]{16,}", "Bearer [REDACTED]", text)


def failure(session, run, agent, code, retryable=True):
    code = code if code in ERROR_MESSAGES else "execution_error"
    agent.status = "failed"
    agent.error_code = code
    agent.ended_at = now()
    fail_execution(session, run, retryable=retryable)
    run.failure_reason = ERROR_MESSAGES[code]
    event(session, run, "agent_failed", agent_run_id=agent.id, error_code=code)


def claim(session, run, settings) -> Job | None:
    is_browser = run.status == "checks_in_progress"
    role = {**dev.STAGES, **quality.STAGES, "checks_in_progress": "BROWSER"}[run.status]
    prompt_version = (
        browser.PROMPT_VERSION
        if is_browser
        else PROMPT_VERSION
        if role == "BA"
        else quality.PROMPT_VERSION
        if run.status in quality.STAGES
        else dev.PROMPT_VERSION
    )
    previous_attempt = session.scalar(
        select(AgentRun).where(
            AgentRun.run_id == run.id,
            AgentRun.role == role,
            AgentRun.attempt == run.attempt,
            AgentRun.revision == run.revision,
        )
    )
    if previous_attempt is not None:
        # Expired calls are never automatically replayed: the provider may already have charged.
        failure(session, run, previous_attempt, "worker_interrupted")
        return None
    agent = AgentRun(
        run_id=run.id,
        role=role,
        attempt=run.attempt,
        revision=run.revision,
        provider=run.snapshot["provider"],
        model=run.snapshot["model"],
        prompt_version=(
            run.snapshot.get("browser_checks_version")
            if is_browser
            else run.snapshot["prompt_version"]
            if role == "BA"
            else run.snapshot.get("quality_prompt_version")
            if run.status in quality.STAGES
            else run.snapshot["dev_prompt_version"]
        ),
        lease_expires_at=now()
        + timedelta(seconds=90 if is_browser else settings.llm_timeout_seconds + 30),
        connection_id=run.connection_id,
    )
    session.add(agent)
    session.flush()
    if agent.prompt_version != prompt_version:
        failure(session, run, agent, "configuration_missing", retryable=False)
        return None
    item = session.get(WorkItem, run.work_item_id)
    project = session.get(Project, item.project_id)
    try:
        selected = (
            settings
            if is_browser
            else ai_access.resolve(session, project.owner, settings, run.connection_id)
        )
        if role == "DEV_BUILD":
            selected = selected.model_copy(
                update={"llm_max_output_tokens": settings.dev_max_output_tokens}
            )
        agent.provider, agent.model = (
            ("browser", "chromium") if is_browser else (selected.llm_provider, selected.llm_model)
        )
    except DomainError as error:
        code = (
            "configuration_missing"
            if error.code in {"ba_not_configured", "not_found"}
            else error.code
        )
        failure(session, run, agent, code)
        return None
    previous = session.scalar(
        select(Artifact)
        .where(Artifact.run_id == run.id, Artifact.kind == "requirements")
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
    )
    feedback = session.scalar(
        select(Approval)
        .where(Approval.run_id == run.id, Approval.decision == "reject")
        .order_by(Approval.created_at.desc(), Approval.id.desc())
    )
    try:
        if is_browser:
            from app.services.sites import latest_site, preview

            site = latest_site(session, run)
            if site is None:
                raise ProviderError("approved_input_missing", False)
            context = json.dumps(
                {
                    "website_artifact_id": site.id,
                    "preview_html": preview(
                        dev.StaticSite.model_validate(site.content["specification"])
                    ),
                }
            )
        else:
            context = (
                build_context(
                    project,
                    item,
                    previous.content.get("specification") if previous else None,
                    feedback.comment if feedback else None,
                )
                if role == "BA"
                else quality.context(session, run)
                if run.status in quality.STAGES
                else dev.context(session, run, feedback.comment if feedback else None)
            )
        context = redact(context, selected)
    except ProviderError as error:
        failure(session, run, agent, error.code, error.retryable)
        return None
    agent.context_chars = len(context)
    event(session, run, "agent_started", agent_run_id=agent.id, role=role, model=agent.model)
    return Job(run.id, agent.id, context, agent.model, selected, run.status)


def execute(sessions, job: Job, settings, provider=None) -> None:
    settings = job.settings
    started = monotonic()
    result, error = None, None
    output_type = {
        "checks_in_progress": browser.BrowserReport,
        "ba_in_progress": RequirementSpecification,
        "plan_in_progress": dev.SitePlan,
        "implementation_in_progress": dev.StaticSite,
        "testing_in_progress": quality.Assessment,
        "reviewing_in_progress": quality.Assessment,
    }[job.step]
    options = (
        {}
        if job.step == "ba_in_progress"
        else {
            "output_type": output_type,
            "system_prompt": dev.PLAN_PROMPT
            if job.step == "plan_in_progress"
            else quality.TEST_PROMPT
            if job.step == "testing_in_progress"
            else quality.REVIEW_PROMPT
            if job.step == "reviewing_in_progress"
            else dev.BUILD_PROMPT,
        }
    )
    try:
        result = (
            browser.generate(job.context)
            if job.step == "checks_in_progress"
            else (provider or make_provider(settings, **options)).generate(job.context, job.model)
        )
        # Validate even injected providers; redact known credentials before persistence.
        specification = output_type.model_validate_json(
            redact(result.specification.model_dump_json(), settings)
        )
    except ProviderError as exc:
        error = exc
    except Exception:
        error = ProviderError("execution_error")
    elapsed = int((monotonic() - started) * 1000)
    with sessions.begin() as session:
        run = session.scalar(
            select(WorkflowRun).where(WorkflowRun.id == job.run_id).with_for_update()
        )
        agent = session.get(AgentRun, job.agent_id)
        agent.duration_ms = elapsed
        if result:
            agent.input_tokens = result.input_tokens
            agent.output_tokens = result.output_tokens
        if (
            agent.status != "running"
            or run.status != job.step
            or run.attempt != agent.attempt
            or run.revision != agent.revision
        ):
            # Cancellation, expired lease, or a later attempt fences this late result.
            if agent.status == "running":
                agent.status, agent.ended_at = "discarded", now()
            return
        # Compare in DB so SQLite test timezone handling cannot weaken production fencing.
        expired = session.scalar(
            select(AgentRun.id).where(AgentRun.id == agent.id, AgentRun.lease_expires_at <= now())
        )
        if expired:
            failure(session, run, agent, "worker_interrupted")
        elif error:
            failure(session, run, agent, error.code, error.retryable)
        else:
            content = {
                "simulated": False,
                "source": "llm",
                "provider": agent.provider,
                "model": agent.model,
                "prompt_version": agent.prompt_version,
                "agent_run_id": agent.id,
                "connection_id": agent.connection_id,
                "specification": specification.model_dump(),
                "usage": {
                    "input_tokens": agent.input_tokens,
                    "output_tokens": agent.output_tokens,
                    "duration_ms": elapsed,
                },
                "notice": (
                    "AI-generated output for human review. No code or tests executed on the server."
                ),
            }
            if job.step == "checks_in_progress":
                content["source"] = "browser"
                content["notice"] = "Executed fixed Chromium checks; not full acceptance tests."
                content["website_artifact_id"] = json.loads(job.context)["website_artifact_id"]
                report = Artifact(
                    id=new_id(),
                    run_id=run.id,
                    gate_id=new_id(),
                    kind="browser_report",
                    revision=run.revision,
                    attempt=run.attempt,
                    content=content,
                )
                session.add(report)
                session.flush()
                artifact_id = report.id
                transition(session, run, "testing_in_progress")
            elif job.step in quality.STAGES:
                inputs = json.loads(job.context)
                for name in ("website_artifact_id", "requirements_artifact_id", "plan_artifact_id"):
                    content[name] = inputs[name]
                if "browser_artifact_id" in inputs:
                    content["browser_artifact_id"] = inputs["browser_artifact_id"]
                    content["browser_report"] = inputs["browser_report"]
                if job.step == "testing_in_progress":
                    report = Artifact(
                        id=new_id(),
                        run_id=run.id,
                        gate_id=new_id(),
                        kind="tester_report",
                        revision=run.revision,
                        attempt=run.attempt,
                        content=content,
                    )
                    session.add(report)
                    session.flush()
                    artifact_id = report.id
                    transition(session, run, "reviewing_in_progress")
                else:
                    content["tester_artifact_id"] = inputs["tester_artifact_id"]
                    content["tester_report"] = inputs["tester_report"]
                    content["reviewer_report"] = specification.model_dump()
                    transition(session, run, "pm_review", review_content=content)
                    artifact_id = run.gate_artifact_id
            elif job.step == "implementation_in_progress":
                inputs = json.loads(job.context)
                content["requirements_artifact_id"] = inputs["requirements_artifact_id"]
                content["plan_artifact_id"] = inputs["plan_artifact_id"]
                site = Artifact(
                    id=new_id(),
                    run_id=run.id,
                    gate_id=new_id(),
                    kind="website",
                    revision=run.revision,
                    attempt=run.attempt,
                    content=content,
                )
                session.add(site)
                session.flush()
                artifact_id = site.id
                transition(session, run, "checks_in_progress")
            else:
                target = (
                    "requirements_approval" if job.step == "ba_in_progress" else "plan_approval"
                )
                if job.step == "plan_in_progress":
                    content["requirements_artifact_id"] = json.loads(job.context)[
                        "requirements_artifact_id"
                    ]
                transition(session, run, target, review_content=content)
                artifact_id = run.gate_artifact_id
            agent.status, agent.ended_at, agent.artifact_id = (
                "succeeded",
                now(),
                artifact_id,
            )
            event(
                session,
                run,
                "agent_completed",
                agent_run_id=agent.id,
                artifact_id=agent.artifact_id,
            )
