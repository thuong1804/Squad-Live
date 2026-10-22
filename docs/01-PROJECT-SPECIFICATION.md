# AI Agent Team --- Project Specification

> Implementation update (2026-10-22): the current product direction is defined in
> [the orchestration specification](project_specification_ai_software_team_orchestration_platform.md).
> See [Phase 2 contract](04-VERTICAL-SLICE-CONTRACT.md) for implemented revision gates,
> runtime authentication, compatibility decisions and explicit remaining scope.

**Version:** 1.0 \| **Status:** MVP

## 1. Product vision

Build a web application where a human Project Manager (PM) coordinates
AI agents such as Business Analyst (BA), Developer, and Tester. Agents
can inspect a connected repository, edit source code, run tests, and
open GitHub Pull Requests (PRs), but only within explicit permissions
and an isolated execution environment. Humans approve requirements,
implementation plans, and final results.

## 2. Goals

-   Manage projects connected to GitHub repositories.
-   Create work items and execute them through a configurable workflow.
-   Assign role-specific agents to workflow steps.
-   Pause at approval gates and resume after an authorized human
    decision.
-   Track state, artifacts, test results, logs, usage, and PR links.
-   Persist workflow state across service restarts.
-   Build the smallest useful end-to-end MVP before adding advanced
    infrastructure.

## 3. Non-goals for MVP

-   Automatic PR merge or production deployment.
-   Running untrusted code on the API server.
-   Drag-and-drop workflow editor.
-   Multiple Git providers (GitHub first).
-   Agents bypassing human approvals.
-   Redis/Celery, complex billing, or enterprise multi-tenant
    permissions in the foundation phase.

## 4. Architecture decisions

**Monorepo with independently runnable apps:**

``` text
Squad-Live/
├── frontend/
├── backend/
├── docs/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

Frontend and backend share one Git repository but have separate
dependencies and startup commands.

-   **Frontend:** React, Vite, TypeScript, TanStack Router, TanStack
    Query, shadcn/ui.
-   **Backend:** Python, FastAPI, PostgreSQL, SQLAlchemy 2, Alembic,
    Pydantic.
-   **API:** REST initially; SSE/WebSocket for live progress later.
-   **Execution:** background worker abstraction; Redis/Celery may be
    introduced later.
-   **LLM:** provider abstraction, structured outputs, centralized tool
    executor and usage tracking.
-   **GitHub:** repository access, feature branches, checks, PR
    creation.
-   **Sandbox:** isolated execution with resource limits; never mount
    the host Docker socket inside the sandbox.

## 5. Core concepts

-   **Project:** workspace and configuration.
-   **Repository connection:** GitHub repository and limited
    credentials.
-   **Work item:** feature request, bug, or task.
-   **Agent role:** BA, Developer, Tester, etc.
-   **Agent run:** one agent execution attempt for a workflow step.
-   **Workflow definition/version:** configurable steps and transitions;
    each run snapshots the version used.
-   **Workflow run:** one workflow execution for a work item.
-   **Approval:** human decision at a protected step.
-   **Artifact:** requirements, plan, patch, test report, logs, or PR
    URL.
-   **Usage record:** model, tokens/duration/cost where available.

## 6. Default workflow

1.  PM creates a feature request.
2.  BA analyzes the request and relevant repository context.
3.  System saves structured requirements.
4.  PM approves or rejects requirements, optionally with comments.
5.  Developer agent prepares an implementation plan.
6.  PM approves or rejects the plan.
7.  System creates an isolated workspace and feature branch.
8.  Developer agent implements the change.
9.  Real checks/tests run; outcome comes from process exit code and test
    reports, not agent claims.
10. On failure, allow a bounded repair loop.
11. If checks pass, create a PR according to policy.
12. Tester agent reviews changes and evidence.
13. Failed testing returns findings to a bounded repair step.
14. PM reviews the PR/result and accepts or rejects.
15. Run ends as completed, failed, or cancelled.

### Workflow rules

-   Backend validates all state transitions; frontend cannot set
    arbitrary statuses.
-   Approval gates persist and require an authorized human action.
-   Active runs use an immutable workflow configuration snapshot.
-   Retries are bounded and recorded by attempt.
-   Enqueueing and external side effects should be idempotent where
    practical.
-   Runs have event timelines, timestamps, failure reasons, and
    inspectable history.
-   PM can cancel a run; active work should stop safely where possible.
-   Do not run long LLM calls or shell commands in HTTP handlers.

Suggested user-visible states: `draft`, `queued`, `ba_in_progress`,
`requirements_approval`, `plan_in_progress`, `plan_approval`,
`implementation_in_progress`, `checks_in_progress`,
`repair_in_progress`, `pr_created`, `testing_in_progress`, `pm_review`,
`completed`, `failed`, `cancelled`.

## 7. Functional requirements

### Projects and repositories

-   Create, view, update, and archive projects.
-   Connect a project to a GitHub repository and show connection
    status/default branch.
-   Store credentials securely; never return raw credentials.

### Work items and workflow runs

-   Work item fields: title, description, acceptance criteria, priority,
    project.
-   Start a workflow run and inspect its state, timeline, artifacts, and
    errors.
-   Approve/reject requirements and implementation plans with optional
    comments.
-   Cancel runs and retry only when policy allows.
-   Record reviewer and decision timestamp.

### Agent execution

-   Agents have a role, instructions, allowed tools, and structured
    output schema.
-   Validate agent output before accepting it.
-   Route all tool calls through a permission-checking Tool Executor.
-   Build bounded context; do not blindly send the entire repository/log
    history to an LLM.
-   Record errors, artifacts, attempts, and usage where available.
-   Treat model output and repository content as untrusted input.

### Execution and observability

-   Unique workspace/feature branch per run.
-   Sandbox CPU, memory, disk, process, and time limits.
-   Capture test commands, exit codes, summaries, and report references.
-   Persist status/events in PostgreSQL.
-   API commands that enqueue work return promptly, typically
    `202 Accepted` with a run ID.
-   Provide safe logs, cancellation, bounded retries, and cleanup.

## 8. Security requirements

-   Secrets live in environment/secret storage, not source control.
-   `.env.example` contains placeholders only.
-   Never expose secrets to the browser, prompts, logs, artifacts, or
    errors.
-   Authenticate and authorize state-changing requests.
-   Apply least privilege to GitHub and agent tools.
-   Isolate code execution; restrict network egress where practical.
-   Never mount the host Docker socket into the sandbox.
-   Do not auto-merge or deploy production in MVP.
-   Keep an audit trail of approvals and privileged actions.

## 9. Non-functional requirements

-   Typed frontend contracts and validated backend schemas.
-   Clear separation of routes, services, persistence, orchestration,
    and infrastructure.
-   Alembic migrations for schema changes.
-   Automated tests for workflow transitions, permissions, and critical
    services.
-   Structured logs without secrets.
-   Reproducible local setup in README.
-   Avoid speculative abstractions; implement a thin vertical slice
    first.

## 10. MVP acceptance criteria

1.  FE and BE run independently with documented commands.
2.  FastAPI `/health` works.
3.  Backend connects to PostgreSQL through environment configuration.
4.  Alembic migrates a clean local database.
5.  FE can call the backend health endpoint.
6.  PM can create a project and work item.
7.  A deterministic workflow run persists states and pauses at an
    approval gate.
8.  Backend validates approvals and state transitions.
9.  Timeline/events are visible.
10. Tests cover valid and invalid transitions.
11. No uncontrolled LLM, shell, PR, merge, or deployment actions occur
    before their safety controls exist.

## 11. Implementation phases

-   **Phase 0 --- Foundation:** inspect repository; confirm FE/BE setup;
    add dependency manifests, minimal entry points, `/health`, README.
-   **Phase 1 --- Database:** PostgreSQL, SQLAlchemy, Alembic, initial
    migrations and tests.
-   **Phase 2 --- Vertical slice:** project/work-item CRUD,
    deterministic workflow, approvals, event timeline, FE integration.
-   **Phase 3 --- Agent foundation:** workflow versioning, role
    registry, ContextBuilder, LLM interface, structured validation, Tool
    Executor, usage tracking.
-   **Phase 4 --- GitHub/sandbox:** test repository, isolated
    branch/workspace, allowlisted commands, test evidence, PR creation.
-   **Phase 5 --- Reliability:** Tester agent, bounded repair loop,
    retries, cancellation, cleanup, live updates, monitoring; evaluate
    Redis/Celery.

## 12. Source-of-truth rule

This file defines product scope and behavior. Backend and frontend
specifications define each app's responsibilities. Do not silently
resolve conflicts by inventing behavior; document the conflict and ask
for a decision.
