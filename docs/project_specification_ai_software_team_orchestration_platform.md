# PROJECT SPECIFICATION

## AI Software Team Orchestration Platform (`Squad-Live`)

**Version:** 1.0 | **Status:** MVP Architecture & Engineering Specification  
**Monorepo Root:** `Squad-Live/` (`frontend/`, `backend/`, `docs/`)

**Implemented Phase 2 contract (2026-10-22):** [04-VERTICAL-SLICE-CONTRACT.md](04-VERTICAL-SLICE-CONTRACT.md)
is the implementation addendum for this specification. Its explicit API/persistence
decisions take precedence over illustrative SQL and payload examples below: lowercase
approval decisions with attempt/gate/artifact identifiers; separate item creation/run
start; `draft` initial status; runtime bearer authentication; PostgreSQL 17 and sync
short transactions; immutable review artifacts and legacy snapshot compatibility.
The later-phase agent/sandbox/GitHub requirements below remain targets, not claims
that the deterministic vertical slice already implements them.

---

## 1. PRODUCT VISION & SCOPE BOUNDARIES

### 1.1. Product Vision
`Squad-Live` is a web-based workflow orchestration platform where a human **Project Manager (PM)** coordinates specialized AI Agents (Business Analyst, Developer, Tester) across an automated software development lifecycle (SDLC). The system connects to GitHub repositories, plans features, modifies code, runs automated test suites inside sandboxed execution environments, and opens GitHub Pull Requests (PRs).

**Core Philosophy:**
- **Human-in-the-Loop Authority:** Human PMs maintain sovereign control over critical Quality Gates (Requirements Approval, Implementation Plan Approval, and Final PR/Delivery Review).
- **Empirical Verification over Hallucination:** Code changes are validated exclusively through isolated container execution, real command exit codes, and test report artifacts—never through agent self-attestation.
- **Separation of Concerns:** Distinct agent roles, bounded context injection, and strict permission-checked tool execution.

### 1.2. In-Scope for MVP
1. Monorepo architecture with independently runnable apps (`frontend/` in Vite+React+TypeScript, `backend/` in FastAPI+SQLAlchemy+PostgreSQL).
2. GitHub repository connection with secure credential referencing.
3. Deterministic state-machine workflow engine persisting state to PostgreSQL across restarts.
4. Human approval gates pausing execution until an authorized decision is recorded.
5. Role-specific AI agents (BA, Dev, Tester) with bounded context builders and structured Pydantic outputs.
6. Isolated sandbox runner for builds, tests, and git patch application.
7. Automated Pull Request creation on GitHub upon successful test suites.
8. Interactive PM Dashboard with real-time run timelines, inspectable artifacts, and approval panels.

### 1.3. Explicit Non-Goals for MVP
- **No Automatic Merging or Deployment:** Automatic PR merging to `main` or continuous deployment to production is strictly forbidden.
- **No Untrusted Execution on Host/API Server:** Sandboxed processes must never mount the host Docker socket (`/var/run/docker.sock`).
- **No Drag-and-Drop Workflow Canvas:** Workflows are versioned, code-defined DAGs/state machines.
- **Single Git Provider:** GitHub only (no GitLab/Bitbucket in MVP).
- **No Agent Self-Approval:** Agents cannot bypass approval gates or modify backend database status directly.
- **No Heavy Distributed Middleware in Initial Slice:** Celery/Redis, complex multi-tenant billing, and enterprise IAM are deferred until core reliability metrics demand them.

---

## 2. MONOREPO SYSTEM ARCHITECTURE

```
Squad-Live/
├── frontend/             # React, Vite, TypeScript, TanStack Router & Query, shadcn/ui
├── backend/              # Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
├── docs/                 # Specifications, architecture diagrams, runbooks
├── docker-compose.yml    # Local dev orchestration (PostgreSQL + API + Sandbox)
├── .env.example          # Environment variable templates (secrets omitted)
├── .gitignore
└── README.md
```

### 2.1. System Topology & Tiers

```
+-----------------------------------------------------------------------------------+
|                              HUMAN PM INTERACTION LAYER                           |
|      (React 18+ / Vite / TanStack Router & Query / Tailwind CSS / shadcn/ui)      |
|    - Kanban & Timeline Views   - Interactive Approval Gates   - Artifact Modals   |
+-----------------------------------------------------------------------------------+
                                          ↕ REST API (HTTP 200/202) [SSE/WS later]
+-----------------------------------------------------------------------------------+
|                        FASTAPI CORE & WORKFLOW ORCHESTRATOR                       |
|  ┌───────────────────┐  ┌───────────────────────┐  ┌───────────────────────────┐  |
|  │ API Routers       │  │ State Machine Engine  │  │ Background Worker Service │  |
|  │ (Projects, Items, │  │ (Versioned DAGs,      │  │ (Async Task Runner,       │  |
|  │  Runs, Approvals) │  │  Transition Validator)│  │  Idempotent Retries)      │  |
|  └───────────────────┘  └───────────────────────┘  └───────────────────────────┘  |
|  ┌─────────────────────────────────────────────────────────────────────────────┐  |
|  │ Agent Orchestration Subsystem                                               │  |
|  │ [Agent Registry] -> [ContextBuilder] -> [LLMProvider] -> [ToolExecutor]     │  |
|  └─────────────────────────────────────────────────────────────────────────────┘  |
+-----------------------------------------------------------------------------------+
             ↕                                                ↕
+--------------------------+                     +----------------------------------+
|  PERSISTENCE STORAGE     |                     | SECURE ISOLATED EXECUTION (CI)   |
|  PostgreSQL 16 Engine    |                     | Non-privileged Container/Sandbox |
|  - Projects & Work Items |                     | - Isolated Git feature branch    |
|  - Workflow Versions     |                     | - Build & Compile execution      |
|  - Runs, Events, Audits  |                     | - Test runner & log capture      |
|  - Artifacts & Metrics   |                     | - Resource limits (CPU/RAM/Disk) |
+--------------------------+                     +----------------------------------+
```

---

## 3. AGENT ROLES, PERMISSIONS & SUBSYSTEMS

### 3.1. Role Specification Matrix

| Role | Entity Type | Responsibilities | Permitted Tools & APIs | Output Schema Contract |
| :--- | :--- | :--- | :--- | :--- |
| **PM (Product Manager)** | **Human** | Creates work items, prioritizes backlog, approves/rejects requirements, approves plans, inspects test evidence, reviews final PR. | Web Dashboard, Authenticated Approval APIs. | Manual Review Decision (`APPROVED` / `REJECTED`), Comments. |
| **BA Agent** | **AI Agent** | Analyzes feature requests, evaluates repository domain context, formulates User Stories and Gherkin Acceptance Criteria. | Repo Tree Reader, File Reader (docs/schemas), Issue Reader. | `RequirementSpecification` (User Stories, Acceptance Criteria, Edge Cases, Open Questions). |
| **Dev Agent** | **AI Agent** | Designs implementation plans, decomposes tasks, modifies codebase, runs local format/lint/compile. | File Read/Write (Sandbox only), Git Branch CLI, Terminal Command Runner (Allowlisted). | `ImplementationPlan` (Files touched, dependencies, risks) + Git Commit Patch. |
| **Tester Agent** | **AI Agent** | Designs test matrices from AC, writes unit/integration/E2E test scripts, executes test suites, analyzes logs, files bug tickets. | Test Runner CLI (`pytest`, `jest`, etc.), File Reader, App Log Reader, Bug DB Writer. | `TestExecutionReport` (Total, Passed, Failed, Exit Code, Logs) + `BugReport[]`. |

### 3.2. Subsystem Components (Backend Agent Architecture)
1. **`AgentRegistry`:** Manages system prompts, role boundaries, allowed tool definitions, and temperature/model configurations per role.
2. **`ContextBuilder`:** Compiles minimal, bounded token contexts per execution step. Prohibits dumping raw repositories or endless log dumps into prompts.
3. **`LLMProvider`:** Vendor-agnostic abstraction (supporting OpenAI, Anthropic, Google Gemini, Ollama) returning validated Pydantic models.
4. **`ToolExecutor`:** Centralized execution gateway. Validates tool arguments, checks strict permissions, enforces path traversal security, and executes inside sandbox containers.
5. **`UsageTracker`:** Intercepts every LLM completion to record prompt/completion tokens, duration, model identifier, and estimated cost in `usage_records`.

---

## 4. DETAILED LIFECYCLE WORKFLOW & STATE MACHINE

### 4.1. Formal State Machine Specification

The state machine is managed centrally by the backend service. Frontend actions cannot update status fields directly; all status transitions are validated transitions triggered by discrete commands.

```
                                  [draft]
                                     │
                             (PM starts run)
                                     ▼
                                  [queued]
                                     │
                             (Worker picks up)
                                     ▼
                              [ba_in_progress]
                                     │
                           (BA generates specs)
                                     ▼
                       ──► [requirements_approval] ◄──
                      │              │                │
          (PM Rejects │              │ (PM Approves)  │
           w/ comment)│              ▼                │
                       ───   [plan_in_progress]       │
                                     │                │
                           (Dev drafts tech plan)     │
                                     ▼                │
                       ──►    [plan_approval]         │
                      │              │                │
          (PM Rejects │              │ (PM Approves)  │
           w/ comment)│              ▼                │
                       ─── [implementation_in_progress]
                                     │
                           (Dev generates patch)
                                     ▼
                           [checks_in_progress]
                                     │
                     ┌───────────────┴───────────────┐
             (Checks Pass)                   (Checks Fail)
                     ▼                               ▼
               [pr_created]                [repair_in_progress]
                     │                               │
             (Tester starts QA)               (Bounded loop:
                     ▼                         Dev patches)
           [testing_in_progress]                     │
                     │                               ▼
             ┌───────┴───────┐              (Retest inside checks)
       (Tests Pass)    (Bugs Found) ─────────────────┘
             ▼
        [pm_review] ──(PM Rejects / Requests Scope Change)───┘
             │
        (PM Accepts)
             ▼
        [completed]

* Any active non-terminal state may transition to [cancelled] via human PM override,
  or to [failed] if unrecoverable infrastructure/runtime errors or retry limits are exceeded.
```

### 4.2. Step-by-Step Phase Execution

#### Phase 1: Feature Creation & Queueing (`draft` -> `queued`)
- **Actor:** Human PM.
- **Actions:** PM submits Feature Ticket (Title, Raw Description, Priority, Acceptance Criteria hints, Target Project).
- **Backend Behavior:** Creates `work_items` and `workflow_runs` records. Returns `202 Accepted` with `run_id`. Snapshots active `workflow_version`. Transitions to `queued`.

#### Phase 2: Business Analysis & Requirements Gate (`ba_in_progress` -> `requirements_approval`)
- **Actor:** BA Agent & Human PM.
- **Actions:**
  1. Worker executes BA Agent with project repository metadata and feature request.
  2. BA Agent writes structured `Requirement_Specification.md` (Stories, Gherkin ACs, Edge Cases).
  3. Orchestrator captures artifact and transitions run to `requirements_approval`.
- **Quality Gate 1 (Human PM):**
  - **Approve:** Advances state to `plan_in_progress`.
  - **Reject:** Adds comments/clarifications; state reverts to `ba_in_progress`.

#### Phase 3: Technical Planning Gate (`plan_in_progress` -> `plan_approval`)
- **Actor:** Dev Agent & Human PM.
- **Actions:**
  1. Dev Agent analyzes approved requirements against repository tree structure.
  2. Dev Agent produces `Implementation_Plan.md` (Target files, dependencies, schema changes, architectural trade-offs).
  3. Orchestrator transitions to `plan_approval`.
- **Quality Gate 2 (Human PM):**
  - **Approve:** Advances state to `implementation_in_progress`.
  - **Reject:** Dev Agent updates technical approach based on PM feedback.

#### Phase 4: Implementation & Local Checks (`implementation_in_progress` -> `checks_in_progress`)
- **Actor:** Dev Agent & Sandbox Runner.
- **Actions:**
  1. System creates an isolated feature branch (`feature/<work-item-id>-<slug>`) and workspace directory.
  2. Dev Agent writes code changes using authorized tool calls.
  3. System triggers static checks (linting, syntax validation, typecheck, build compilation) in `checks_in_progress`.
  4. If checks fail: Transitions to `repair_in_progress` (bounded attempt limit, e.g., max 3 attempts).
  5. If checks pass: System commits changes, pushes branch to GitHub, opens a GitHub Pull Request with draft labels, and transitions to `pr_created`.

#### Phase 5: Testing & Empirical Regression Loop (`testing_in_progress` -> `pm_review`)
- **Actor:** Tester Agent & Sandbox Runner.
- **Actions:**
  1. Tester Agent writes executable automated test cases reflecting the approved Gherkin ACs.
  2. Test suites run inside the isolated sandbox. Exit codes, stdout/stderr, and report files are recorded in `test_runs`.
  3. **Evaluation:**
     - **Failures Detected:** Tester Agent writes structured `bug_reports`. Run enters `repair_in_progress` where Dev Agent receives error logs and patches code. Tester Agent runs regression checks.
     - **100% AC Verified:** Generates `Test_Execution_Summary.md`. Transitions to `pm_review`.

#### Phase 6: PM Review & Acceptance (`pm_review` -> `completed`)
- **Actor:** Human PM.
- **Actions:**
  1. PM reviews the Unified Delivery Dashboard: PR link, code diff, requirements checklist, test execution evidence, and preview environment URL.
  2. **Decision:**
     - **Accept:** Run transitions to `completed`. Work item marked completed. (PR ready for human manual merge).
     - **Reject:** PM specifies defect or requirement deviation; task routes back to `plan_in_progress` or `ba_in_progress`.

---

## 5. DATABASE ARCHITECTURE & DATA SCHEMAS

### 5.1. Entity Relationship Overview

```
[projects] 1 ──── 0..* [repository_connections]
    │
    1
    └─── 0..* [work_items] 1 ──── 0..* [workflow_runs]
                                            │
                                            ├── 0..* [approvals]
                                            ├── 0..* [workflow_events]
                                            ├── 0..* [agent_runs] ── 0..* [artifacts]
                                            ├── 0..* [test_runs]
                                            └── 0..* [usage_records]
```

### 5.2. Core Database Tables (SQLAlchemy 2 / PostgreSQL)

```sql
-- Projects & Repositories
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE TABLE repository_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL DEFAULT 'github',
    repo_identifier VARCHAR(255) NOT NULL, -- e.g. "org/repo"
    default_branch VARCHAR(100) NOT NULL DEFAULT 'main',
    secret_ref VARCHAR(255) NOT NULL,      -- reference pointer to KMS/vault/env
    status VARCHAR(50) NOT NULL DEFAULT 'connected',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Work Items
CREATE TABLE work_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    acceptance_criteria TEXT,
    priority VARCHAR(50) NOT NULL DEFAULT 'medium', -- low, medium, high, critical
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Workflow Definitions & Runs
CREATE TABLE workflow_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE
);

CREATE TABLE workflow_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_definition_id UUID NOT NULL REFERENCES workflow_definitions(id),
    version_number INT NOT NULL,
    steps_config JSONB NOT NULL, -- Immutable JSON representation of DAG/steps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    UNIQUE(workflow_definition_id, version_number)
);

CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    workflow_version_id UUID NOT NULL REFERENCES workflow_versions(id),
    status VARCHAR(50) NOT NULL, -- queued, ba_in_progress, requirements_approval, etc.
    current_step VARCHAR(100) NOT NULL,
    retry_count INT DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    ended_at TIMESTAMP WITH TIME ZONE,
    failure_reason TEXT
);

-- Human Approvals
CREATE TABLE approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step VARCHAR(100) NOT NULL,
    decision VARCHAR(50) NOT NULL, -- APPROVED, REJECTED
    reviewer VARCHAR(100) NOT NULL,
    comment TEXT,
    decided_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Execution Events & Audit Trail
CREATE TABLE workflow_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Agent & Tool Executions
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- BA, DEV, TESTER
    step VARCHAR(100) NOT NULL,
    attempt INT NOT NULL DEFAULT 1,
    status VARCHAR(50) NOT NULL,
    provider_model VARCHAR(100),
    duration_ms INT,
    error_summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    artifact_type VARCHAR(100) NOT NULL, -- SPEC, PLAN, PATCH, TEST_REPORT, PR_URL
    storage_ref TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE TABLE test_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    command TEXT NOT NULL,
    exit_code INT NOT NULL,
    summary JSONB NOT NULL,
    report_url TEXT,
    duration_ms INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);
```

---

## 6. BACKEND API SPECIFICATION (FASTAPI)

### 6.1. General Conventions
- All state-changing routes require authenticated sessions.
- Asynchronous tasks return `202 Accepted` alongside the execution entity ID.
- Standard error envelope:
```json
{
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "Cannot trigger approvals while run is in status 'implementation_in_progress'",
    "details": {}
  }
}
```

### 6.2. Endpoint Contract Reference

#### System Health & Diagnostics
- `GET /health`: Process health status.
- `GET /ready`: Readiness check verifying live PostgreSQL connection pool.
- `GET /docs`: OpenAPI Swagger documentation.

#### Projects Management
- `POST /api/v1/projects`: Create project.
- `GET /api/v1/projects`: List active projects (paginated).
- `GET /api/v1/projects/{project_id}`: Get project details + repository connection metadata.
- `PATCH /api/v1/projects/{project_id}`: Update project details or archive flag.

#### Work Items
- `POST /api/v1/projects/{project_id}/work-items`: Create feature or bug ticket.
- `GET /api/v1/projects/{project_id}/work-items`: Filterable backlog list.
- `GET /api/v1/work-items/{work_item_id}`: Work item detail view.

#### Workflow Runs & Orchestration
- `POST /api/v1/work-items/{work_item_id}/workflow-runs`: Start new run (`202 Accepted`).
- `GET /api/v1/workflow-runs/{run_id}`: Real-time execution status, current step, and metadata.
- `GET /api/v1/workflow-runs/{run_id}/events`: Event stream history and timestamps.
- `GET /api/v1/workflow-runs/{run_id}/artifacts`: List generated specifications, plans, diffs, and test runs.
- `POST /api/v1/workflow-runs/{run_id}/approvals`: Submit gate decision:
  ```json
  {
    "step": "requirements_approval",
    "decision": "APPROVED",
    "comment": "Proceed with implementation"
  }
  ```
- `POST /api/v1/workflow-runs/{run_id}/cancel`: Signal graceful stop of active execution.
- `POST /api/v1/workflow-runs/{run_id}/retry`: Retry from last failed step (if allowable by retry policy).

---

## 7. FRONTEND ARCHITECTURE & UX DESIGN

### 7.1. Technology Stack
- **Framework & Build:** React 18+, Vite, TypeScript (strict mode).
- **Routing:** TanStack Router (type-safe path routing).
- **Server State & Caching:** TanStack Query (invalidation after mutations, short-interval polling on active runs).
- **UI Components:** `shadcn/ui` (accessible Radix primitives with Tailwind CSS).
- **HTTP Client:** Centralized typed API client (`lib/api-client.ts`). Secrets never included in client bundles.

### 7.2. Route Hierarchy
```
/
├── dashboard                           # Overview: active runs, gates pending PM review
├── projects
│   ├── new                             # Connect repo & initialize project
│   ├── :projectId                      # Project detail, backlog, repo status
│   └── :projectId/work-items/new       # Feature ticket creation form
├── work-items
│   └── :workItemId                     # Work item details, history of runs
└── workflow-runs
    └── :runId                          # Main PM Command Console (Timeline, Gates, Artifacts)
```

### 7.3. PM Command Console Design (`/workflow-runs/:runId`)
1. **Header & Status Banner:**
   - Work item title, current lifecycle status badge (color-coded, accessible), run ID, total elapsed time, active PR link.
2. **Interactive Quality Gate Panel (Conditional Render):**
   - Appears prominently whenever `status` is `requirements_approval`, `plan_approval`, or `pm_review`.
   - Embeds Markdown preview of the document under review (Spec or Implementation Plan) or Git Diff viewer.
   - Action controls: `Approve` button (primary green), `Request Changes` button (outline destructive), with structured feedback textarea.
3. **Execution Timeline & Audit Rail:**
   - Vertical timeline displaying chronological steps, agent role involved, attempt number, start/end timestamps, and exit codes.
4. **Artifacts & Evidence Tab:**
   - Tabbed view: `Requirements (SRS)`, `Technical Plan`, `Git Diff`, `Test Suite Output (Terminal/Logs)`, `LLM Token & Cost Usage`.

---

## 8. EXECUTION SANDBOX & SECURITY MODEL

### 8.1. Sandbox Isolation Rules
- **No Direct Host Execution:** Dev Agent code and test suites run inside ephemeral, unprivileged Docker containers or isolated runtimes.
- **Socket Protection:** The host Docker socket (`/var/run/docker.sock`) is **never** mounted inside sandbox environments.
- **Resource Constraints:**
  - Max CPU: 2 Cores.
  - Max RAM: 2048 MB.
  - Disk Quota: 4 GB ephemeral scratchpad.
  - Command Timeout: 300 seconds maximum per shell execution.
- **Network Policy:** Restricted network egress. Sandbox cannot access local network RFC1918 subnets or the backend database container.

### 8.2. Secrets & Credential Management
- GitHub Personal Access Tokens or App Private Keys are stored in environment-configured secure key stores, referenced only by identifier (`secret_ref`).
- Raw tokens are never returned across the REST API, never surfaced in frontend bundles, and scrubbed from execution logs/prompts before persistence.

---

## 9. PHASED IMPLEMENTATION ROADMAP

### Phase 0: Foundation Setup
- Configure monorepo structure (`frontend/`, `backend/`, `docs/`, `docker-compose.yml`).
- Implement FastAPI application entrypoint with `GET /health` and Pydantic configuration.
- Implement React Vite frontend shell with health check integration.

### Phase 1: Database & Core Persistence
- Set up PostgreSQL 16 container, SQLAlchemy 2 async engine, and Alembic migrations.
- Create initial migrations for `projects`, `repository_connections`, `work_items`, `workflow_runs`, `approvals`, and `workflow_events`.
- Write automated tests for database session lifecycle and model relationships.

### Phase 2: Vertical Slice (Deterministic Orchestrator)
- Implement project and work-item CRUD endpoints.
- Build the deterministic State Machine engine executing mock steps.
- Implement PM approval gating (`POST .../approvals`) and verify transitions.
- Build the frontend PM Dashboard showing active runs, timeline events, and approval actions.

### Phase 3: Agent Infrastructure & Context Engine
- Implement `AgentRegistry`, `ContextBuilder`, and `LLMProvider` abstractions.
- Build Pydantic structured output parsers for BA Agent (`RequirementSpecification`).
- Introduce `usage_records` table tracking token consumption and cost.

### Phase 4: Isolated Execution & GitHub Integration
- Implement sandbox execution runner with resource constraints.
- Integrate GitHub API client: clone repository, branch creation, commit patch application, PR generation.
- Integrate Dev Agent implementation and automated compilation checks.

### Phase 5: Testing Agent & Bounded Repair Loop
- Integrate Tester Agent generating test scripts against Acceptance Criteria.
- Wire test execution sandbox capturing real command exit codes.
- Implement the automated `repair_in_progress` feedback loop (max 3 repair iterations).
- Complete the end-to-end PM review and sign-off workflow.
