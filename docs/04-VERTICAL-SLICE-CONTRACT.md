# Vertical slice contract — deterministic-v2

Updated 2026-10-22. This document records the implemented Phase 2 contract under
`project_specification_ai_software_team_orchestration_platform.md`. It resolves
differences between that product specification, the earlier 01/02/03 documents,
and the previous deterministic-v1 implementation. OpenAPI describes actual wire schemas.

## Scope

The delivered slice is a human-controlled **simulation** backed by PostgreSQL:
project → work item → run → requirements review → plan review → delivery review.
The browser provides bearer-token entry, project/work-item screens, a real-data
dashboard, run polling, artifacts, timeline, approval history, cancellation and retry.
No LLM, repository connection, sandbox, real test execution, GitHub PR, merge or
deployment is performed. `completed` means PM accepted the simulated workflow.

## Decisions and review concurrency

New runs snapshot `deterministic-v2`. Existing v1 snapshots are not rewritten.

| Gate | Approve | Request changes |
| --- | --- | --- |
| `requirements_approval` | `plan_in_progress` | `ba_in_progress` |
| `plan_approval` | `implementation_in_progress` | `plan_in_progress` |
| `pm_review` | `completed` | Explicit `ba_in_progress` or `plan_in_progress` |

The API uses lowercase `approve` / `reject`. For v2, `reject` means request changes,
requires a nonblank comment, and increments `revision`; it does not mark the run failed.
Final review rejection also requires `return_to`. Re-entering a review creates a new
`gate_id` and a new immutable artifact record. There is no update/delete artifact API.
Approval history stores reviewer, timestamp, revision, gate and artifact IDs.

```json
{
  "step": "requirements_approval",
  "attempt": 1,
  "gate_id": "<current gate UUID>",
  "artifact_id": "<current gate_artifact_id UUID>",
  "decision": "reject",
  "comment": "Clarify the negative case"
}
```

All identifiers must come from the current run response and the artifact actually
shown to the PM. Stale step, attempt, gate or artifact returns **409**. Missing
feedback/invalid revision target returns **422**. Changes and audit events commit
together. The UI refreshes authoritative data on conflict and does not report success.
Raw agent/Markdown content is displayed as escaped text, never executable HTML.

## Counters and retries

- `revision`: starts at 1; increments for each PM request for changes. Human review
  revisions do not consume the execution retry budget.
- `attempt`: starts at 1; increments on an authorized execution retry, max 3.
- `repair_count`: reserved for future empirical test-repair loops; remains 0 in mock mode.
- `failed_step`: records the automatic execution step that failed. Retry resumes that
  step, not the whole run. Only retryable failed runs can retry; completed/cancelled
  runs cannot. Archive and competing active-run checks still apply.

`fail_execution` is an internal service checkpoint, not a public failure-injection API.
The deterministic worker has no intentional simulated failure scenario. External
executors must add failure handling, idempotent side effects and real evidence later.
Transient database errors roll back and the worker retries with bounded backoff.

Legacy v1 runs retain reject → failed and retry → queued behavior. They do not require
new gate/artifact identifiers. The UI labels this behavior explicitly.

## API additions and conventions

- `GET /api/v1/session`: validates the runtime bearer token and returns the PM identity.
- `GET /api/v1/dashboard`: owner-scoped counts, up to 10 recent runs, 10 waiting runs,
  and 10 recent events. Counts cover all owned runs; lists are explicitly previews.
- `GET /api/v1/workflow-runs/{id}/artifacts`: paginated artifact history.
- `GET /api/v1/workflow-runs/{id}/artifacts/{artifact_id}`: exact artifact under review.
- Existing projects, items, runs, events, approvals, cancel and retry endpoints remain.
- List responses: `{items, limit, offset}`; default 25, max 100.
- Work items start as `draft`; creating an item and starting a run are separate commands.
- Priorities: `low`, `medium`, `high`, `critical`; `urgent` remains accepted for compatibility.
- UUIDs are strings; events use an increasing integer ID. UTC timestamps are serialized.
- Errors remain `{error: {code, message}}`; raw server errors and secrets are not echoed.

## Authentication and local operation

MVP authentication uses configured PM bearer tokens, not cookie sessions/OIDC.
Tokens are entered at runtime, held only in tab memory and cleared on logout/reload.
They are never put into `VITE_*` variables, localStorage or committed files.
Query caches are cleared when switching sessions. HTTPS is required outside localhost.
Bearer headers are not automatically attached by the browser as cookies are; future
cookie-based authentication must define its CSRF protection separately.

Local PostgreSQL remains version 17, matching the existing compose setup. SQLAlchemy
uses synchronous short transactions in sync FastAPI handlers and a separate worker;
an async-engine migration is not required for this slice. These are intentional
implementation choices relative to the illustrative PostgreSQL 16/async roadmap.

## Persistence and migration

Migration `0002_review_revisions` adds review metadata and artifacts without rewriting
existing snapshots/history. Downgrade refuses to collapse multiple review revisions
into a v1 approval key, preventing silent history loss. Database-owner permissions can
still modify records: this slice does not claim tamper-proof audit storage.

## Subsequent phases

Repository connections and workflow-version tables, AgentRegistry/ContextBuilder,
agent execution records, LLM usage, sandbox execution, test evidence and bounded repair
remain future work. Preserve existing snapshots and exact-artifact approval semantics.
For GitHub integration: static checks may create a **draft** PR; QA evidence must pass
before marking ready for PM review. Automatic merge/deployment remains prohibited.

Validation commands are maintained in the root and app READMEs. Browser tests use a
disposable PostgreSQL schema, separate API/worker/frontend processes and an ephemeral
token; they do not create test projects in the normal application schema.
