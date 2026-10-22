# Squad Live

PM dashboard và workflow backend cho đội AI BA/Dev/Tester. Hiện triển khai **Phase 2:
workflow mô phỏng bền vững**, có yêu cầu chỉnh sửa, artifact theo phiên bản và ba gate
phê duyệt. Chưa gọi LLM, chạy code/test của repository, tạo PR, merge hoặc deploy.

## Tài liệu

- [Đặc tả sản phẩm](docs/project_specification_ai_software_team_orchestration_platform.md)
- [Hợp đồng Phase 2 và các quyết định tương thích](docs/04-VERTICAL-SLICE-CONTRACT.md)
- [Frontend](frontend/README.md) · [Backend](backend/README.md)

## Khởi động local trên Windows

Cần Node 20.19+ hoặc LTS tương thích, npm, Python 3.12+, Docker Desktop đang chạy.
Từ thư mục gốc repository:

```powershell
python -m venv backend/.venv # chỉ khi chưa có virtualenv
Set-Location backend
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe scripts/setup_local.py
Set-Location ..
docker compose up -d --wait postgres
Set-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`setup_local.py` tạo `.env` gốc và `backend/.env` khi chưa có, sinh password/token ngẫu
nhiên và không in secret. Giữ nguyên file đã tồn tại. Cổng PostgreSQL mặc định do
script tạo là **55432**, để tránh xung đột với dịch vụ khác. Nếu tự cấu hình, dùng các
file `.env.example`; bảo đảm DATABASE_URL trỏ đúng database.

Terminal thứ hai, tại `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.workers.runner
```

Terminal thứ ba, tại `frontend/`:

```powershell
npm.cmd ci
npm.cmd run dev
```

Mở http://127.0.0.1:5173. Trong `backend/.env`, lấy **giá trị token** của `pm-local`
trong `AUTH_TOKENS` và nhập vào ô Token truy cập (không nhập cả JSON hoặc tiền tố Bearer).
Token chỉ tồn tại trong bộ nhớ tab; tải lại trang cần nhập lại. Không đưa token vào
`VITE_*`, commit hoặc log. `/health` kiểm tra tiến trình; `/ready` kiểm tra DB/migration.
Worker phải đang chạy thì run mới chuyển bước. CORS mặc định hỗ trợ localhost và
127.0.0.1 trên cổng 5173. Môi trường ngoài localhost phải dùng HTTPS.

## Kiểm tra

Tại `frontend/`:

```powershell
npm.cmd test
npm.cmd run build
npx.cmd playwright install chromium
```

Tại `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic scripts
.\.venv\Scripts\python.exe scripts/verify_postgres.py
.\.venv\Scripts\python.exe scripts/verify_browser.py
```

Test PostgreSQL tạo container tạm và dọn sau khi chạy. Browser E2E cần database local
đang chạy; tạo schema tạm riêng, khởi động API 8001/frontend 5174/worker, rồi dọn các
tiến trình và schema. Không ghi dữ liệu test vào schema ứng dụng. Hai cổng phải rảnh.

Để dừng database mà giữ dữ liệu: `docker compose stop postgres`. Ctrl+C dừng API,
worker và Vite trong từng terminal. Không commit `.env`, `.venv`, `node_modules`,
`dist` hay `test-results`; các đường dẫn này được ignore.
