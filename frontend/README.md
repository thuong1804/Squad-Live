# Squad Live frontend

React/Vite/TypeScript, TanStack Router/Query, Tailwind, Radix/shadcn-style UI và Zod
kiểm tra response. [Hướng dẫn chạy toàn hệ thống](../README.md) và
[hợp đồng Phase 2](../docs/04-VERTICAL-SLICE-CONTRACT.md).

Cài đặt AI cho phép nhập key một lần cho mỗi cấu hình provider/model. Key chỉ ở bộ
nhớ form khi nhập; backend lưu mã hóa và không trả lại key đã lưu. Có tài liệu BA
dễ đọc và lịch sử thực thi/model/token. Xem [Phase 3](../docs/05-BA-AGENT.md).
Chế độ **Tạo website tĩnh** có Dev thật, danh sách file, Preview desktop/mobile và
tải ZIP theo phiên bản; xem [hướng dẫn](../docs/07-STATIC-WEBSITE.md). Tester vẫn mô phỏng.

## Chạy độc lập

Node 20.19+ hoặc LTS tương thích, npm. Từ `frontend/`:

```powershell
npm.cmd ci
npm.cmd run dev
npm.cmd test
npm.cmd run build
```

Mở Vite ở http://localhost:5173. `.env.local` là tùy chọn, có thể copy từ `.env.example`.
`VITE_API_BASE_URL` mặc định `http://localhost:8000`; `VITE_HEALTH_PATH` mặc định `/health`.
Khởi động lại Vite sau khi đổi biến. Không đặt secret/token trong `VITE_*`.

Đăng nhập bằng Google theo [hướng dẫn OAuth](../docs/06-GOOGLE-LOGIN.md).
API dùng cookie HttpOnly và CSRF token trong bộ nhớ. Reload giữ phiên; logout thu hồi
phiên và xóa query cache. Backend phải cho phép CORS từ origin frontend.
Health không chứng minh DB sẵn sàng.

## Phạm vi đã triển khai

- Dashboard có số liệu thật, run chờ duyệt, run và sự kiện gần đây.
- Project list/create/detail, archive/restore; work-item create/detail.
- Khởi tạo run bằng idempotency key; giữ cùng key khi thử lại request lỗi.
- Run timeline phân trang, polling 3 giây khi nonterminal, refresh thủ công.
- Artifact theo phiên bản, quyết định gắn đúng phiên duyệt/artifact, lịch sử reviewer/time.
- Request changes quay về BA/plan, final review có chọn đích quay lại.
- Cancel có xác nhận, retry theo quyền trạng thái backend, xử lý xung đột 409 bằng refetch.
- Loading, empty, error, disabled states; keyboard focus và responsive layout.

Nội dung artifact JSON được render thành text an toàn; chưa có HTML/Markdown renderer
hoặc link do agent sinh ra. Run mô phỏng được ghi rõ, không tuyên bố đã chạy test thật.
Repository connections, agents, sandbox, GitHub, SSE và settings vẫn thuộc phase sau.

## Kiểm thử trình duyệt

```powershell
npx.cmd playwright install chromium
Set-Location ../backend
.\.venv\Scripts\python.exe scripts/verify_browser.py
```

Script dùng DB PostgreSQL local với schema test riêng, API 8001, Vite 5174, worker riêng
và token ngẫu nhiên không log. Luồng test: tạo dự án/công việc, chạy workflow, yêu cầu sửa,
chặn quyết định cũ, xử lý 409, duyệt các gate, xem lịch sử, reload, mobile, cancel và archive.
Ảnh giao diện sau đăng nhập nằm trong `test-results/` (Git ignored); trace bị tắt để tránh
ghi token. Không tự commit/push. Production static hosting cần fallback về `index.html`.
