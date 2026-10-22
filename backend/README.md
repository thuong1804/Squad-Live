# Squad Live backend

FastAPI + SQLAlchemy 2 + PostgreSQL + Alembic. Worker riêng xử lý workflow mô phỏng,
không thực thi tác vụ dài trong HTTP handler. Hướng dẫn thiết lập đầy đủ ở
[README gốc](../README.md); [hợp đồng Phase 2](../docs/04-VERTICAL-SLICE-CONTRACT.md)
là nguồn mô tả hành vi hiện tại.

## Lệnh chạy từ `backend/`

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe scripts/setup_local.py
docker compose --project-directory .. up -d --wait postgres
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Terminal khác:
.\.venv\Scripts\python.exe -m app.workers.runner
```

Settings đọc `.env` từ working directory. `AUTH_TOKENS` ánh xạ identity sang token
ngẫu nhiên tối thiểu 32 ký tự; `{}` mặc định từ chối API nghiệp vụ. Token được gửi
qua `Authorization: Bearer ...`; không có cookie session/login/OIDC. Người dùng chỉ
truy cập tài nguyên mình sở hữu; tài nguyên người khác trả 404. Không in token/DB URL.

## API

`/health`, `/ready`, `/docs`, `/openapi.json` công khai. API nghiệp vụ dưới `/api/v1`:

| Endpoint | Thao tác |
| --- | --- |
| `/session` | GET identity của token |
| `/dashboard` | GET số lượng và tối đa 10 bản ghi mỗi danh sách gần đây/chờ duyệt |
| `/projects` | GET danh sách phân trang, POST tạo |
| `/projects/{id}` | GET, PATCH thông tin/status active hoặc archived |
| `/projects/{id}/work-items` | GET phân trang, POST tạo |
| `/work-items/{id}` | GET chi tiết |
| `/work-items/{id}/workflow-runs` | GET phân trang, POST bắt đầu với `Idempotency-Key` |
| `/workflow-runs/{id}` | GET trạng thái/snapshot/phiên duyệt |
| `/workflow-runs/{id}/events` | GET lịch sử phân trang |
| `/workflow-runs/{id}/artifacts` | GET lịch sử artifact phân trang |
| `/workflow-runs/{id}/artifacts/{artifact_id}` | GET artifact chính xác |
| `/workflow-runs/{id}/approvals` | GET lịch sử; POST quyết định |
| `/workflow-runs/{id}/cancel` | POST hủy, reason tùy chọn |
| `/workflow-runs/{id}/retry` | POST thử lại bước lỗi nếu hợp lệ |

Danh sách `{items,limit,offset}`, mặc định 25, tối đa 100. Timestamp UTC. Các trường
request ngoài schema bị từ chối. Errors `{error:{code,message}}`: 401 thiếu/sai token,
404 không tồn tại/không có quyền, 409 trạng thái cũ, 422 dữ liệu sai, 503 DB chưa sẵn sàng.

## Workflow và tương thích

Run mới snapshot `deterministic-v2`, bắt đầu queued, worker dừng ở requirements,
plan và PM review. Approve chuyển bước; reject có comment quay về BA/plan và tăng
revision. Final reject phải chọn `return_to`. Approval bắt buộc gửi đúng `step`,
`attempt`, `gate_id`, `artifact_id`; xem ví dụ trong hợp đồng Phase 2.

Mỗi phiên duyệt có artifact JSON riêng; không có endpoint sửa/xóa artifact. Nội dung
được đánh dấu simulated, executed=false. `completed` không phải bằng chứng test thật.
Các run v1 giữ nguyên reject→failed và retry→queued. Run v2 retry từ `failed_step`,
tối đa 3 attempts; chỉnh sửa của PM không tiêu tốn retry. Repair thực chưa triển khai.

Worker dùng transaction ngắn và `FOR UPDATE SKIP LOCKED` trên PostgreSQL. Restart
tiếp tục từ trạng thái đã commit. DB lỗi được backoff tối đa 5 lần rồi worker thoát;
khởi động lại sau khi DB phục hồi. Không có API tự ý sửa trạng thái/failure injection.
SQLite chỉ dùng cho unit/API tests, không thay thế kiểm thử concurrency PostgreSQL.

Migration hiện tại: `0002_review_revisions`. Không sửa snapshot v1. Downgrade bị chặn
nếu nhiều revision không thể biểu diễn bằng schema v1 mà không mất lịch sử.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic scripts
.\.venv\Scripts\python.exe -m ruff format --check app tests alembic scripts
.\.venv\Scripts\python.exe scripts/verify_postgres.py
.\.venv\Scripts\python.exe scripts/verify_browser.py
```

PostgreSQL tests được skip trong pytest thường nếu thiếu `TEST_DATABASE_URL`.
`verify_postgres.py` tự tạo container tạm. Browser tests cần cài dependencies frontend
và `npx playwright install chromium`; dùng schema tạm trong DB cấu hình local.
