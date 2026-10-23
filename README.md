# Squad Live

PM dashboard và workflow backend cho đội AI BA/Dev/Tester. Hiện có **BA dùng LLM**
khi kết nối API key riêng (OpenAI/Gemini/DeepSeek), yêu cầu chỉnh sửa, artifact theo phiên bản và ba gate phê duyệt.
Mặc định chạy mô phỏng. Chế độ **Tạo website tĩnh** bổ sung Dev thật để lập kế hoạch,
sinh HTML/CSS/JS, xem Preview và tải ZIP. Tester vẫn mô phỏng; chưa tạo PR, merge hoặc deploy.

## Tài liệu

- [Đặc tả sản phẩm](docs/project_specification_ai_software_team_orchestration_platform.md)
- [Hợp đồng Phase 2 và các quyết định tương thích](docs/04-VERTICAL-SLICE-CONTRACT.md)
- [Phase 3: cấu hình và demo BA dùng AI](docs/05-BA-AGENT.md)
- [Đăng nhập Google và chuyển dữ liệu PM cũ](docs/06-GOOGLE-LOGIN.md)
- [Tạo website tĩnh · BA + Dev thật](docs/07-STATIC-WEBSITE.md)
- [Kết nối repository Git local (chỉ đọc)](docs/08-LOCAL-GIT-REPOSITORY.md)
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
nhiên và không in secret. Giữ cấu hình đã có, bổ sung khóa mã hóa BYOK nếu thiếu. Cổng PostgreSQL mặc định do
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

Điền `GOOGLE_CLIENT_ID` và `GOOGLE_CLIENT_SECRET` vào `backend/.env` theo
[hướng dẫn Google OAuth](docs/06-GOOGLE-LOGIN.md), rồi restart API.
Mở http://localhost:5173 và chọn **Đăng nhập bằng Google**. Phiên cookie HttpOnly
được giữ khi tải lại trang; đăng xuất thu hồi phiên trên server. Không đưa secret vào
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
