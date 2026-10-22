# AI Agent Team --- Frontend Specification

> Implementation update (2026-10-22): project/work-item/run screens now use backend
> data and runtime PM bearer authentication. See [Phase 2 contract](04-VERTICAL-SLICE-CONTRACT.md)
> for review-session identifiers, artifact binding, conflicts and simulation limits.

**Version:** 1.0 \| **Application:** `frontend/`

## 1. Mission

Build a PM dashboard to manage projects, submit work items, monitor
AI-agent runs, review artifacts, approve/reject gated steps, and inspect
failures. The frontend displays state and submits commands; backend owns
business rules and workflow transitions.

## 2. Technology

-   React + Vite + TypeScript.
-   TanStack Router for routing.
-   TanStack Query for server state, caching, mutations, and
    invalidation.
-   shadcn/ui for accessible UI primitives.
-   Centralized typed API client.
-   `VITE_API_BASE_URL` for API base URL; never put secrets in `VITE_*`.
-   REST initially; SSE/WebSocket or polling for progress after basic
    integration works.

This is an authenticated operational dashboard; the selected
architecture is React/Vite, not Next.js for SEO.

## 3. UX principles

-   Make current state and next action obvious.
-   Clearly distinguish active work, approval required, completed,
    failed, and cancelled.
-   Show safe error summaries and recovery options, not raw stack
    traces.
-   Preserve a visible timeline and artifacts.
-   Confirm cancellation and other high-impact actions.
-   Provide loading, empty, success, error, and disabled states.
-   Use accessible forms, labels, keyboard navigation, focus, and
    contrast.
-   Do not show success until backend confirms the operation.
-   Backend is authoritative if UI state is stale.

## 4. Suggested routes

``` text
/dashboard
/projects
/projects/new
/projects/:projectId
/projects/:projectId/work-items/new
/work-items/:workItemId
/workflow-runs/:runId
/settings/workflows       # later
/settings/agents          # later
```

Implement only routes supported by the current backend.

## 5. MVP screens

### Dashboard

-   Active runs, runs waiting for approval, completed/failed runs,
    recent activity.
-   Links to projects and workflow runs.

### Projects list/detail

-   Name, repository, status, last activity.
-   Create project, view details, repository connection status.
-   Project work items and create-work-item action.
-   Clear empty and connection-error states.

### Create work item

Fields: project, title (required), description (required), acceptance
criteria, priority. Validate client-side for usability while treating
backend validation as authoritative. Navigate to detail after successful
creation.

### Work item detail

-   Request description, acceptance criteria, status, related workflow
    runs, artifacts.
-   Start workflow only when supported and valid.
-   Handle `409 Conflict` if state changes after the page loads.

### Workflow run detail --- highest priority

-   Work item title, run ID, overall status, current step.
-   Timeline of steps, status, start/end time, and attempt count.
-   Approval panel when a decision is required.
-   Requirements and implementation plan artifacts.
-   Test commands, exit codes, summaries, and report links when
    available.
-   PR link after creation.
-   Safe error summary and allowed retry/cancel actions.
-   Refresh/live updates without losing context.

Approval panel must show the artifact, Approve/Reject controls, optional
comment, and confirmed reviewer/time after the backend responds.

### Workflow and agent settings (later)

-   Simple configuration for ordered steps, role, approval gate, retry
    limit, and enabled state.
-   No drag-and-drop editor in MVP.
-   Do not expose secrets or controls the backend cannot persist.

## 6. Suggested folder layout

Adapt the current project; inspect before replacing files.

``` text
frontend/
├── src/
│   ├── app/                 # providers and route setup
│   ├── routes/
│   ├── features/
│   │   ├── dashboard/
│   │   ├── projects/
│   │   ├── work-items/
│   │   ├── workflow-runs/
│   │   └── settings/
│   ├── components/
│   │   ├── ui/              # shadcn/ui
│   │   └── shared/
│   ├── lib/
│   │   ├── api-client.ts
│   │   ├── query-client.ts
│   │   └── utils.ts
│   ├── types/
│   └── main.tsx
├── .env.example
├── package.json
└── vite.config.ts
```

## 7. API integration

-   Centralize request construction, response parsing, and error
    handling.
-   Use types matching backend schemas.
-   Do not scatter raw `fetch()` calls across components.
-   Use TanStack Query for queries/mutations and invalidate relevant
    data after success.
-   Handle `401`, `403`, `404`, `409`, `422`, and `5xx` meaningfully.
-   Avoid optimistic updates for approval/workflow transitions unless
    rollback and conflict handling exist.
-   Paginate growing lists when supported.
-   Do not silently present hardcoded mock data as live data.

## 8. Status presentation

Keep one centralized mapping from backend status to labels and visual
variants: - `queued`: Queued - `ba_in_progress`: BA analyzing -
`requirements_approval`: Waiting for requirements approval -
`plan_in_progress`: Preparing implementation plan - `plan_approval`:
Waiting for plan approval - `implementation_in_progress`: Implementing -
`checks_in_progress`: Running checks - `repair_in_progress`: Fixing
issues - `pr_created`: PR created - `testing_in_progress`: Testing
changes - `pm_review`: Waiting for PM review - `completed`: Completed -
`failed`: Failed - `cancelled`: Cancelled

The backend enum is authoritative. Update this mapping when the API
contract changes.

## 9. Progress updates

Initial version: poll run detail at a reasonable interval only while
active, if supported, and stop when terminal; provide manual refresh.
Later: SSE/WebSocket, safe reconnect, event deduplication, and
connection status. REST remains the source of current state.

## 10. Security and accessibility

-   Never put LLM/GitHub credentials or private API keys in frontend
    environment variables.
-   Treat agent output, logs, repository content, and backend text as
    untrusted.
-   Render generated Markdown safely; sanitize before rendering HTML.
-   Validate agent-provided links/actions before making them
    interactive.
-   Do not expose secret-bearing logs or environment values.
-   Use semantic HTML, keyboard navigation, visible focus, accessible
    labels, and status text that does not rely only on color.

## 11. Testing

-   Unit tests for status mapping and reusable logic.
-   Component tests for forms, approval controls, and error states.
-   Test loading, empty, failure, and disabled states.
-   Test `409 Conflict` handling and actions invalid for current status.
-   Critical E2E path: create project → create work item → start
    workflow → view approval gate → approve/reject → view updated
    timeline.

## 12. Implementation order

1.  Inspect existing files, package manager, and lockfile.
2.  Confirm Vite app starts independently.
3.  Set up TanStack Router and app shell/navigation.
4.  Configure API base URL and typed API client.
5.  Verify backend health connectivity.
6.  Implement project list/create/detail using real API data.
7.  Implement work-item creation/detail.
8.  Implement workflow run timeline and approval controls.
9.  Add query invalidation, error handling, and active-run polling.
10. Add tests, responsive behavior, and accessibility refinements.
11. Add live updates and settings only when backend endpoints exist.

## 13. First-slice acceptance criteria

-   Frontend starts using the repository's documented package manager.
-   Frontend can call the health endpoint.
-   API base URL changes without code edits.
-   Project/work-item views use backend data.
-   Workflow state and timeline are visible.
-   Approval actions reflect backend-confirmed results.
-   API errors, including state conflicts, are explained.
-   Key screens have loading, empty, and failure states.
-   No secrets are bundled in browser code.
