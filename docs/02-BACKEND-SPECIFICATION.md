# AI Agent Team --- Backend Specification

> Implementation update (2026-10-22): [Phase 2 contract](04-VERTICAL-SLICE-CONTRACT.md)
> defines exact v2 approval payloads, versioned artifacts, revision/retry behavior and
> legacy v1 compatibility. Use OpenAPI for current request/response schemas.

**Version:** 1.0 \| **Application:** `backend/`

## 1. Mission

Backend owns business rules, persistence, authorization, workflow
transitions, agent orchestration, GitHub integration, and secure
execution coordination. The frontend must never be trusted to enforce
policy or set arbitrary workflow states.

## 2. Technology

-   Python + FastAPI.
-   PostgreSQL as durable source of truth.
-   SQLAlchemy 2 for ORM/data access.
-   Alembic for all schema changes.
-   Pydantic for request/response validation.
-   Environment-based settings and `.env.example` placeholders.
-   REST first; live event transport later.
-   A background execution abstraction; Redis/Celery only in a later
    phase if needed.

## 3. Suggested structure

Adapt existing directories; inspect files before creating or replacing
anything.

``` text
backend/
├── app/
│   ├── main.py
│   ├── api/          # routers and routes
│   ├── core/         # settings, logging, security, errors
│   ├── db/           # engine, sessions, base
│   ├── models/       # SQLAlchemy models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # business logic and state machine
│   └── workers/      # background tasks
├── alembic/
├── tests/
├── alembic.ini
├── pyproject.toml    # or requirements.txt; choose one canonical method
└── .env.example
```

## 4. Design rules

-   Keep API routers thin; put business logic in services.
-   Centralize workflow transitions in one state-machine/service layer.
-   Use explicit transaction boundaries; do not hold DB transactions
    open during LLM/shell execution.
-   Long-running work must not run inside HTTP request handlers.
-   Commands that enqueue work should return `202 Accepted` and a
    run/task ID.
-   Use UTC timestamps and consistent error response shapes.
-   Do not expose stack traces or secrets.
-   Add pagination for potentially large collections.
-   Protect state-changing endpoints with authentication/authorization;
    do not leave privileged operations open by default.
-   Add idempotency protection for retried commands with external side
    effects.

## 5. Initial endpoints

Implement incrementally; do not build everything before the first
vertical slice.

### Foundation

-   `GET /health` --- process health.
-   `GET /ready` --- readiness, including database connectivity once
    configured.
-   `GET /docs` --- FastAPI OpenAPI docs.

### Projects

-   `POST /api/v1/projects`
-   `GET /api/v1/projects`
-   `GET /api/v1/projects/{project_id}`
-   `PATCH /api/v1/projects/{project_id}`
-   Archive endpoint or documented archive-field update.

### Work items

-   `POST /api/v1/projects/{project_id}/work-items`
-   `GET /api/v1/projects/{project_id}/work-items`
-   `GET /api/v1/work-items/{work_item_id}`

### Workflow runs

-   `POST /api/v1/work-items/{work_item_id}/workflow-runs`
-   `GET /api/v1/workflow-runs/{run_id}`
-   `GET /api/v1/workflow-runs/{run_id}/events`
-   `POST /api/v1/workflow-runs/{run_id}/approvals`
-   `POST /api/v1/workflow-runs/{run_id}/cancel`
-   `POST /api/v1/workflow-runs/{run_id}/retry` only when policy
    permits.

Later: artifacts and agent-run endpoints.

## 6. Core data model

Introduce tables incrementally, only when needed: - `projects`: name,
description, owner, status, timestamps. - `repository_connections`:
project, provider, repository identifier, default branch, secret
reference/status; never return token. - `work_items`: project, title,
description, acceptance criteria, priority, status, creator,
timestamps. - `workflow_definitions` and immutable
`workflow_versions`. - `workflow_runs`: work item, workflow
snapshot/version, status, current step, start/end, cancellation/failure
details. - `approvals`: run, step, decision, reviewer, comment,
timestamp. - `workflow_events`: run, event type, safe structured
payload, timestamp. - `agent_runs`: role, step, attempt, status,
provider/model, duration, error summary. - `artifacts`: type, run/agent
run, structured content or safe storage reference, metadata. -
`test_runs`: command, exit code, summary, report reference, duration. -
`usage_records`: provider/model, token counts/cost/duration where
available. - `users` only as required by the selected MVP authentication
model.

First migration should include only the minimum for projects, work
items, runs, approvals, and events.

## 7. Workflow engine

-   Validate transitions centrally; invalid transitions return a
    conflict response.
-   Store a workflow version snapshot for every run.
-   Store approval decision, reviewer, and timestamp.
-   Write state changes and events transactionally.
-   Support bounded retries, cancellation, failure reasons, and
    resumable state.
-   Record each attempt and meaningful transition.
-   Test valid and invalid transitions.
-   Begin with deterministic/mock steps before connecting real agents.

## 8. Later agent architecture

-   `AgentRegistry`: role definitions, instructions, allowed tools.
-   `ContextBuilder`: selects relevant context with limits.
-   `LLMProvider`: vendor-neutral interface.
-   Structured output validation with Pydantic.
-   `ToolExecutor`: validates arguments and enforces permissions.
-   `UsageTracker`: provider/model, tokens, duration, cost where
    available.
-   Orchestrator calls the correct agent for the current workflow step.
    Agents must not bypass the state machine or write arbitrary database
    state.

## 9. Background work and reliability

-   Begin with a small task/worker abstraction and deterministic mock
    execution.
-   Add Redis/Celery only after queue durability and concurrency needs
    are clear.
-   PostgreSQL remains the source of truth, not the queue.
-   Use bounded retry/backoff for transient failures.
-   Make duplicate deliveries safe and side effects idempotent.
-   Check cancellation between safe steps.
-   Capture timeout, exit code, logs, and failure summary.

## 10. GitHub and sandbox safety (later phase)

-   Least-privilege GitHub credentials and secure secret storage.
-   Unique workspace and feature branch per run.
-   Run repository code in an isolated sandbox, never in the FastAPI
    process.
-   Never mount host Docker socket inside sandbox.
-   Apply CPU, memory, disk, process, and wall-clock limits.
-   Restrict network egress where practical and clean workspaces.
-   Validate tool arguments and command allowlists.
-   PR creation only after required checks and workflow policy permit
    it.
-   No auto-merge or production deployment in MVP.
-   Treat repository files and agent output as untrusted.

## 11. Testing

-   Unit tests for transitions and validation.
-   API tests for schemas, status codes, and errors.
-   DB integration tests for persistence and migrations.
-   Authorization tests for protected actions.
-   Approval, cancellation, retry-limit, and invalid-transition tests.
-   Mock LLM/GitHub in unit tests.
-   Determine test success from actual exit codes/reports, not agent
    claims.

## 12. Implementation order

1.  Inspect existing files; do not overwrite them.
2.  Add dependency manifest and settings.
3.  Add minimal `app/main.py` and `GET /health`.
4.  Run FastAPI and verify `/docs`.
5.  Configure PostgreSQL and SQLAlchemy session.
6.  Configure Alembic and test migrations on a clean database.
7.  Add minimum models/migrations.
8.  Implement project and work-item CRUD.
9.  Implement deterministic workflow, approvals, and event history.
10. Add tests and connect FE.
11. Add background worker abstraction.
12. Add LLM, GitHub, sandbox, and live updates in separate phases.

## 13. First-slice acceptance criteria

-   Documented command starts FastAPI in the virtual environment.
-   `/health` works.
-   DB settings come from environment variables.
-   Alembic migrates schema.
-   Project/work-item CRUD works.
-   Workflow state and events persist.
-   Approvals are accepted only at the correct step.
-   Invalid transitions are rejected and tested.
-   Long-running work is not executed in HTTP handlers.
-   No credentials are committed or returned.
