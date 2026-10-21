# AI Agent Team — Implementation Plan

> **Phiên bản:** 2.0  
> **Cập nhật:** 21/10/2026  
> **Mục tiêu:** Xây dựng ứng dụng web quản lý team AI, trong đó PM là người dùng chính; các AI Agent đảm nhiệm vai trò BA, Developer và Tester. Developer Agent có thể làm việc với source code trong sandbox cô lập, chạy kiểm thử và tạo GitHub Pull Request (PR).

Tài liệu này là nguồn yêu cầu và roadmap tổng thể. Hãy triển khai theo từng phase/task nhỏ, kiểm chứng bằng lệnh chạy và test thực tế, không tự ý bỏ qua checkpoint.

---

## 1. Quyết định kiến trúc đã chốt

### 1.1. Repository và ứng dụng

- **Monorepo:** FE và BE nằm trong cùng một Git repository để dễ phát triển, review và theo dõi thay đổi.
- **Tách thành các ứng dụng/runtime độc lập:** frontend, backend API và background worker có dependency, cấu hình và lệnh chạy riêng.
- Không tạo một ứng dụng full-stack duy nhất để thay thế backend. Frontend chỉ gọi API; không truy cập PostgreSQL trực tiếp.
- Có thể triển khai FE và BE riêng biệt sau này mà không phải đổi cấu trúc repository.

### 1.2. Tech stack

**Frontend**
- React + Vite + TypeScript.
- TanStack Router: routing có type, route params và search params.
- TanStack Query: fetch/cache/refetch dữ liệu từ API.
- shadcn/ui + Tailwind CSS cho UI.
- REST API là giao thức chính; SSE để stream tiến độ workflow. Chỉ dùng WebSocket khi có nhu cầu hai chiều thực sự.
- Không cần SSR/SEO trong MVP vì sản phẩm là dashboard nội bộ. Không dùng Next.js hoặc TanStack Start trong MVP để tránh thêm lớp server khi FastAPI đã là backend chính.

**Backend và xử lý nền**
- Python 3.12+ và FastAPI.
- Pydantic Settings cho cấu hình môi trường; Pydantic cho validation và structured outputs.
- SQLAlchemy 2 + Alembic.
- PostgreSQL là nguồn dữ liệu bền vững cho workflow/task/approval/audit state.
- Redis + Celery cho background jobs khi triển khai queue. Worker là tiến trình riêng, không chạy agent hoặc shell command trực tiếp trong API request handler.
- Workflow engine là state machine do dự án quản lý trong MVP; chưa dùng workflow visual drag-and-drop builder.

**Tích hợp và vận hành**
- GitHub trước tiên, bắt đầu với repository thử nghiệm.
- LLM provider abstraction để có thể đổi provider; chỉ tích hợp provider sau khi foundation và workflow mock hoạt động.
- Docker Compose cho môi trường local; sandbox chạy code phải được cô lập khỏi API server.
- Không auto-merge PR và không deploy production trong MVP.

### 1.3. Sơ đồ logic

```text
Browser
  └── Frontend: React + Vite + TanStack Router/Query + shadcn/ui
          │ REST API + SSE
          ▼
      Backend API: FastAPI ───────────── PostgreSQL
          │ enqueue job                     └── persistent workflow state
          ▼
      Redis queue → Celery worker → Workflow engine / Agent runtime
                                      ├── LLM provider
                                      ├── Tool Executor
                                      ├── Isolated sandbox / test runner
                                      └── GitHub operations / Pull Request
```

PostgreSQL lưu trạng thái bền vững. Redis chỉ là queue/broker, không phải nguồn dữ liệu duy nhất cho trạng thái workflow.

---

## 2. Cấu trúc repository mục tiêu

Ở bước khởi tạo, chỉ tạo các thư mục và file nền tảng. Không cần sinh trước toàn bộ module nghiệp vụ.

```text
ai-agent-team/
├── frontend/                    # React + Vite + TypeScript
│   ├── public/
│   ├── src/
│   │   ├── app/                 # App shell, providers, router setup
│   │   ├── routes/              # TanStack Router routes
│   │   ├── features/            # Feature modules theo domain
│   │   ├── components/          # Shared UI components
│   │   ├── lib/                 # API client, utilities
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── api/v1/              # API routes
│   │   ├── core/                # Settings, logging, security
│   │   ├── db/                  # Database session/base
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/            # Application/domain services
│   │   ├── workers/             # Background job entry points
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── docs/
│   ├── architecture.md
│   ├── workflow-spec.md
│   └── implementation-plan.md
├── .env.example                 # Placeholder values only; no real secrets
├── .gitignore
├── docker-compose.yml           # Local infrastructure; expand gradually
└── README.md
```

Cấu trúc này là mục tiêu định hướng. AI có thể điều chỉnh chi tiết nhỏ nếu có lý do kỹ thuật rõ ràng, nhưng không được tự ý đổi stack hoặc nhập FE và BE thành một ứng dụng.

---

## 3. Bắt đầu từ đâu? — Phase 1, Task 1

### Việc cần làm

1. Tạo Git repository `ai-agent-team`.
2. Kiểm tra môi trường Windows: Python 3.12+, Node.js LTS, npm, Git và Docker Desktop.
3. Tạo thư mục `frontend/`, `backend/`, `docs/` và các file nền tảng.
4. Khởi tạo frontend React + Vite + TypeScript; cấu hình TanStack Router, TanStack Query và shadcn/ui theo từng bước, kiểm tra app chạy được.
5. Khởi tạo backend FastAPI tối thiểu với endpoint health check.
6. Tạo `.gitignore`, `.env.example` và README hướng dẫn chạy FE/BE.
7. Chưa tích hợp LLM, chưa viết workflow engine, chưa thực thi shell/source code từ AI.

### Tiêu chí nghiệm thu

- Repository có commit đầu tiên.
- FE chạy được bằng lệnh dev server riêng.
- BE chạy được bằng lệnh riêng; `GET /api/v1/health` trả trạng thái OK.
- FE và BE có thể phát triển/build độc lập.
- Không có API key, password, token hoặc secret thật trong Git.
- README mô tả phiên bản runtime và lệnh chạy hiện tại.
- Không khai báo PostgreSQL/Redis là đã hoạt động nếu chưa chạy và kiểm tra thực tế.

---

## 4. Roadmap theo phase

### Phase 1 — Repository, FE/BE skeleton và database foundation

**Mục tiêu:** ứng dụng chạy local, FE và BE độc lập, migration database hoạt động.

- Khởi tạo monorepo và cấu hình lint/format cơ bản nếu phù hợp.
- FE: React + Vite + TypeScript; TanStack Router; TanStack Query; shadcn/ui.
- BE: FastAPI, settings qua biến môi trường, structured logging cơ bản và health endpoint.
- PostgreSQL local bằng Docker Compose.
- SQLAlchemy 2, Alembic và Pydantic Settings.
- Thêm kiểm tra kết nối DB và migration đầu tiên; chưa tạo tất cả bảng nghiệp vụ cùng lúc.

**Nghiệm thu:** FE mở được; BE health check trả OK; kết nối DB thành công; migration upgrade/downgrade được kiểm thử.

### Phase 2 — Workflow engine tối thiểu bằng mock agents

**Mục tiêu:** chứng minh state machine, approval và persistence trước khi thêm LLM.

- Định nghĩa workflow JSON có node agent, approval, condition, tool và end.
- Validate node keys, transitions và tham chiếu node hợp lệ.
- Tạo workflow run, approval và event persistence.
- Thực thi mock workflow BA → approval → Dev → Tester → Done.
- Hỗ trợ approve, reject/request changes, retry giới hạn, cancel và audit event.
- Lưu workflow version cố định vào từng run.

**Nghiệm thu:** workflow có thể dừng ở approval, tồn tại sau khi API/worker restart và tiếp tục đúng node sau quyết định của PM.

### Phase 3 — Agent runtime và BA Agent

**Mục tiêu:** tích hợp LLM với output có cấu trúc và có thể truy vết.

- Xây LLM provider interface và một adapter đầu tiên.
- Agent registry, role prompt, ContextBuilder và output schemas.
- BA Agent nhận Feature Request và trả requirement, user stories, acceptance criteria, open questions.
- Validate output bằng Pydantic; retry lỗi schema có giới hạn.
- Ghi agent run, usage, latency, lỗi và artifact.

**Nghiệm thu:** Feature Request tạo ra BA artifact có cấu trúc; PM có thể approve hoặc request changes; các lần chạy được log.

### Phase 4 — Worker, sandbox và Dev Agent

**Mục tiêu:** cho phép AI sửa source code trong môi trường thử nghiệm có kiểm soát.

- API chỉ enqueue job và trả `202 Accepted` cùng run/task identifier; không chờ LLM, test hoặc Git operation hoàn tất.
- Worker riêng để thực thi workflow.
- Sandbox/container cô lập theo run hoặc task; không mount Docker socket vào container agent.
- Clone/checkout repository thử nghiệm và làm việc trên branch riêng.
- Dev Agent tạo patch; kiểm tra đường dẫn file và giới hạn workspace.
- Chỉ chạy lệnh được allowlist, ví dụ lint, typecheck và test.
- Lưu exit code, test report và log; kết quả kiểm thử phải dựa trên dữ liệu thực tế từ runner, không dựa vào lời agent.
- Giới hạn CPU, RAM, disk, thời gian, network egress và quyền truy cập secret.

**Nghiệm thu:** Dev Agent hoàn thành một thay đổi nhỏ trong repo demo; có diff và test report được xác minh.

### Phase 5 — GitHub integration và Tester Agent

**Mục tiêu:** tạo PR và phản hồi lỗi có thể truy vết.

- Tích hợp GitHub App hoặc credential có quyền tối thiểu.
- Tạo branch, commit, push và PR.
- Git operations phải idempotent để retry không tạo branch/commit/PR trùng.
- Tester Agent nhận acceptance criteria, diff, PR và test results.
- Báo lỗi có severity, reproduction steps, expected result và actual result.
- Giới hạn số vòng sửa lỗi; ví dụ tối đa 3 vòng trước khi chuyển sang `BLOCKED` và yêu cầu PM xử lý.

**Nghiệm thu:** một task đi từ requirement đã duyệt đến PR, kèm test report và lịch sử hoạt động.

### Phase 6 — PM workspace

**Mục tiêu:** quản lý và duyệt workflow qua UI.

- Project dashboard, task list/Kanban và task detail.
- Cấu hình agent: role, model, prompt và tool permissions.
- Workflow run timeline, artifacts, logs và trạng thái worker.
- Approval inbox: Approve hoặc Request Changes.
- SSE endpoint cập nhật trạng thái run theo thời gian thực.
- Hiển thị usage/chi phí ước tính và lỗi.
- Xử lý loading, empty, error, retry và trạng thái reconnect rõ ràng.

**Nghiệm thu:** PM có thể theo dõi và duyệt workflow từ UI mà không cần truy cập DB hoặc log server trực tiếp.

### Phase 7 — Reliability và security hardening

**Mục tiêu:** đảm bảo lỗi, retry hoặc restart không làm hỏng trạng thái và thao tác Git.

- Authentication và RBAC trên API/project.
- Kiểm thử worker crash, timeout, cancellation và retry.
- Row locking/versioning để tránh hai worker chuyển cùng một run đồng thời.
- Secret redaction; audit log; sandbox cleanup; network egress policy.
- Xử lý webhook duplicate/replay nếu dùng webhook.
- Metrics, structured logging và backup/restore database.
- Xác minh các giới hạn sandbox bằng kiểm thử thực tế.

**Nghiệm thu:** retry không gây thao tác Git trùng; quyền và giới hạn sandbox được kiểm chứng; workflow state có thể phục hồi.

---

## 5. Database schema dự kiến

Tạo bảng theo từng phase, giữ migration nhỏ và có thể kiểm tra. Đây là danh sách định hướng, không phải yêu cầu tạo toàn bộ trong migration đầu tiên.

| Bảng | Trường chính dự kiến |
|---|---|
| `users` | `id`, `email`, `password_hash` hoặc `external_auth_id`, `role`, `created_at` |
| `projects` | `id`, `name`, `description`, `owner_user_id`, `settings` JSONB, `created_at` |
| `repositories` | `id`, `project_id`, `provider`, `owner`, `name`, `default_branch`, `credential_reference` |
| `agents` | `id`, `name`, `role`, `provider`, `model`, `system_prompt`, `tools_config` JSONB, `is_active` |
| `workflows` | `id`, `project_id`, `name`, `is_default` |
| `workflow_versions` | `id`, `workflow_id`, `version`, `definition` JSONB, `published_at` |
| `tasks` | `id`, `project_id`, `parent_task_id`, `title`, `description`, `status`, `priority`, `assignee_agent_id` |
| `workflow_runs` | `id`, `project_id`, `workflow_version_id`, `task_id`, `status`, `current_node`, `attempt_count`, `started_at`, `finished_at` |
| `agent_runs` | `id`, `workflow_run_id`, `task_id`, `agent_id`, `status`, `input` JSONB, `output` JSONB, `usage` JSONB, `error` |
| `approvals` | `id`, `workflow_run_id`, `node_key`, `status`, `decision`, `feedback`, `decided_by`, `decided_at` |
| `artifacts` | `id`, `workflow_run_id`, `task_id`, `type`, `storage_uri`, `metadata` JSONB |
| `tool_executions` | `id`, `agent_run_id`, `tool_name`, `status`, `input_summary`, `result_summary`, `started_at`, `finished_at` |
| `git_operations` | `id`, `workflow_run_id`, `branch`, `commit_sha`, `pr_url`, `status`, `idempotency_key` |
| `workflow_events` | `id`, `workflow_run_id`, `event_type`, `payload` JSONB, `created_at` |

Có thể bổ sung `task_dependencies`, `usage_records`, `webhook_events` và `project_secrets` khi có yêu cầu cụ thể. Không lưu giá trị secret trực tiếp trong bảng cấu hình hoặc JSONB; chỉ lưu reference đến secret manager/environment phù hợp.

---

## 6. API MVP dự kiến

Prefix: `/api/v1`. Tên endpoint có thể được điều chỉnh khi viết API spec, nhưng phải thống nhất với frontend và tài liệu.

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/projects` | Tạo project |
| `GET` | `/api/v1/projects` | Liệt kê project |
| `POST` | `/api/v1/projects/{id}/repositories` | Gắn repository |
| `GET` | `/api/v1/agents` | Liệt kê agent |
| `POST` | `/api/v1/agents` | Tạo agent config |
| `POST` | `/api/v1/projects/{id}/tasks` | Tạo Feature Request/task |
| `POST` | `/api/v1/tasks/{id}/runs` | Khởi chạy workflow; trả `202 Accepted` + `run_id` |
| `GET` | `/api/v1/runs/{id}` | Xem trạng thái run |
| `GET` | `/api/v1/runs/{id}/events` | SSE theo dõi tiến độ |
| `GET` | `/api/v1/approvals?status=pending` | Approval inbox |
| `POST` | `/api/v1/approvals/{id}/decision` | Approve hoặc Request Changes |
| `GET` | `/api/v1/runs/{id}/artifacts` | Danh sách artifacts |
| `POST` | `/api/v1/runs/{id}/cancel` | Yêu cầu hủy run |

Các API nghiệp vụ phải xác thực quyền truy cập theo user/project trước khi trả dữ liệu hoặc thực hiện hành động. Không chạy LLM, shell command hoặc Git operation dài trong request handler.

---

## 7. Nguyên tắc kỹ thuật và bảo mật bắt buộc

1. API chỉ enqueue công việc dài; trả response sớm, không chờ agent/test/Git.
2. Workflow run gắn với một workflow version bất biến.
3. Approval được lưu trong PostgreSQL; không giữ trạng thái chờ chỉ trong memory.
4. Mọi tool call đi qua Tool Executor để kiểm tra permission, input và giới hạn.
5. Kết quả test được xác nhận bằng exit code/test report thực tế.
6. Sandbox có resource limits, timeout, cleanup và network policy.
7. Không mount Docker socket vào sandbox; không chạy code không tin cậy trên API server.
8. Không ghi secret thật vào prompt, database JSONB, logs hoặc artifacts.
9. Không auto-merge và không deploy production trong MVP.
10. Git operations có idempotency key hoặc kiểm tra trạng thái trước khi retry.
11. Retry phải có giới hạn; lỗi không thể phục hồi chuyển sang trạng thái rõ ràng như `BLOCKED` hoặc `FAILED`.
12. Dùng UTC trong database; frontend hiển thị theo múi giờ người dùng.
13. Có structured logging và audit events cho quyết định, tool execution và Git operation.
14. Kiểm tra concurrency để nhiều worker không cùng xử lý/chuyển trạng thái một run.
15. FE chỉ giao tiếp với backend qua API; không chứa credential truy cập database hoặc GitHub.

---

## 8. Cách làm việc theo từng checkpoint

- Mỗi phiên chỉ triển khai một phase hoặc một task nhỏ.
- Trước khi sửa code, AI phải kiểm tra cấu trúc và nội dung file hiện có; không ghi đè file không liên quan.
- AI đưa ra lệnh cụ thể phù hợp Windows PowerShell/VS Code và giải thích ngắn gọn mục đích.
- Dừng tại checkpoint để người dùng chạy lệnh và gửi output trước khi chuyển bước, trừ khi người dùng yêu cầu thực hiện trọn gói.
- Không tuyên bố đã chạy test, migration, build hoặc command nếu chưa thực sự chạy và xem kết quả.
- Khi gặp lỗi, xử lý lỗi hiện tại trước; không tiếp tục xây thêm tầng mới trên nền tảng đang lỗi.
- Sau mỗi phase, cập nhật trạng thái, quyết định đã chốt, file thay đổi, lệnh/test đã chạy và lỗi còn tồn tại trong tài liệu tiến độ.

---

## 9. Prompt cho AI khởi tạo cấu trúc repository

Sao chép prompt dưới đây vào AI coding tool tại thư mục repository `ai-agent-team`.

```text
Bạn là một senior full-stack engineer chịu trách nhiệm khởi tạo nền tảng dự án AI Agent Team. Hãy đọc toàn bộ file AI_Agent_Team_Implementation_Plan.md trước khi thực hiện.

MỤC TIÊU HIỆN TẠI
Chỉ thực hiện Phase 1, Task 1: kiểm tra repository và khởi tạo cấu trúc FE/BE tối thiểu. Không triển khai workflow engine hoặc AI agent ở task này.

KIẾN TRÚC ĐÃ CHỐT
- Monorepo: frontend/ và backend/ nằm trong cùng một Git repository nhưng là hai ứng dụng độc lập.
- Frontend: React + Vite + TypeScript, TanStack Router, TanStack Query, shadcn/ui.
- Backend: Python 3.12+ + FastAPI.
- Database mục tiêu: PostgreSQL; SQLAlchemy 2 + Alembic sẽ được thêm theo từng bước.
- Redis + Celery là thành phần xử lý nền sẽ được thêm sau khi nền tảng cơ bản ổn định.
- FE gọi BE qua REST API; không truy cập database trực tiếp.
- Không dùng Next.js hoặc TanStack Start trong MVP. Không thay đổi stack nếu chưa được người dùng chấp thuận.

PHẠM VI TASK NÀY
1. Kiểm tra các file/thư mục hiện có và phiên bản công cụ có thể kiểm tra an toàn. Không xóa hoặc ghi đè file hiện có nếu chưa kiểm tra.
2. Nếu repository chưa có cấu trúc, tạo frontend/, backend/, docs/ và các file nền tảng cần thiết.
3. Khởi tạo frontend tối thiểu bằng Vite + React + TypeScript. Cấu hình TanStack Router và TanStack Query ở mức đơn giản, dễ hiểu. Chuẩn bị để tích hợp shadcn/ui; không tạo dashboard nghiệp vụ phức tạp.
4. Khởi tạo FastAPI tối thiểu với GET /api/v1/health trả JSON thể hiện trạng thái OK.
5. Tạo .gitignore phù hợp Windows, Python, Node, virtual environment, node_modules, build artifacts và .env.
6. Tạo .env.example chỉ chứa tên biến và placeholder, tuyệt đối không có secret thật.
7. Viết README.md mô tả kiến trúc, yêu cầu môi trường và lệnh chạy FE/BE.
8. Tạo docs/architecture.md và giữ docs/implementation-plan.md đồng bộ với kế hoạch này nếu chưa có.
9. Không tích hợp LLM, không tạo schema nghiệp vụ đầy đủ, không chạy shell/source code do AI sinh ra, không tạo GitHub PR, không triển khai production. Chưa cần thêm Redis/Celery nếu việc đó không cần thiết cho skeleton.
10. Chỉ tạo docker-compose.yml khi cần cho hạ tầng local; không khẳng định database/Redis hoạt động nếu chưa chạy và kiểm tra được.

QUY TẮC THỰC HIỆN
- Ưu tiên các bước nhỏ, dễ kiểm tra, phù hợp Windows và VS Code.
- Trước khi chạy lệnh có khả năng thay đổi/xóa dữ liệu, giải thích tác động và chờ xác nhận.
- Không xóa file người dùng, không ghi secret vào file hoặc terminal log.
- Không tự nhận đã chạy build/test nếu chưa thực thi và đọc kết quả.
- Nếu thiếu công cụ hoặc lệnh thất bại, dừng tại đó, báo chính xác lỗi và đưa hướng xử lý; không giả định thành công.
- Sau khi tạo file, chạy các kiểm tra phù hợp: frontend install/build, backend import/start hoặc test health endpoint nếu môi trường cho phép.
- Báo cáo cuối cùng gồm: cấu trúc đã tạo, file quan trọng, lệnh đã chạy và kết quả thật, việc còn thiếu, và bước kế tiếp được đề xuất.

CHECKPOINT
Nếu môi trường chưa rõ hoặc chưa có repository, trước tiên chỉ đưa ra các lệnh kiểm tra môi trường và chờ người dùng gửi kết quả. Nếu AI coding tool có quyền thao tác trực tiếp trên repository và môi trường đã sẵn sàng, có thể thực hiện các thay đổi không phá hủy trong phạm vi task này rồi báo cáo kết quả.
```

---

## 10. Timeline tham khảo

Roadmap 7 phase có thể mất khoảng 8 tuần cho một MVP có phạm vi kiểm soát, nhưng đây không phải cam kết thời gian. Ưu tiên tiêu chí nghiệm thu và độ an toàn hơn lịch tuần. Nếu làm một mình, hãy hoàn thành từng phase, ghi rõ backlog và tránh tích hợp LLM trước khi workflow mock, persistence và kiểm thử nền tảng ổn định.
