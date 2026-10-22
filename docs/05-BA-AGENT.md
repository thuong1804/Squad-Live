# Phase 3: BA thật với BYOK

Bổ sung cho [hợp đồng Phase 2](04-VERTICAL-SLICE-CONTRACT.md).
Run `mock` mô phỏng toàn bộ. Run `ba_live` gọi AI cho BA; Dev/Tester chưa thực thi
code/test hoặc tạo PR. Không có gói dùng thử hay credit nền tảng.

## Cấu hình local

Từ `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe scripts/setup_local.py
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Terminal khác, cũng từ backend:
.\.venv\Scripts\python.exe -m app.workers.runner
```

Setup tạo `CONNECTION_ENCRYPTION_KEY` nếu thiếu, giữ nguyên giá trị đã có và không
in secret. API và worker phải dùng cùng key mã hóa. Sao lưu database **và** key này;
đổi/mất key mã hóa khiến các kết nối đã lưu không đọc được. File `.env` không commit.
Nếu chuyển máy, cần chuyển cả hai bằng kênh riêng. App mặc định bind loopback.

`LLM_TIMEOUT_SECONDS=90`, `LLM_MAX_OUTPUT_TOKENS=4096` là giới hạn chung.
Không dùng `OPENAI_API_KEY`, `BA_LIVE_ENABLED` hoặc `LLM_MODEL` trong `.env` làm
nguồn mặc định: mọi run thật phải chọn kết nối BYOK của PM.

## Thao tác người dùng

1. Đăng nhập PM bằng Google theo [hướng dẫn OAuth](06-GOOGLE-LOGIN.md).
2. Mở **Cài đặt AI** → nhập tên kết nối, nhà cung cấp và API key.
3. Chọn **Kiểm tra key và lấy model**, chọn model rồi **Lưu kết nối**.
4. Mở công việc → chọn **BA dùng AI thật** → chọn **Nguồn AI** đã lưu → bắt đầu.
5. Đọc tài liệu BA, phê duyệt hoặc nhập phản hồi để tạo bản sửa mới.

Một kết nối gắn với một provider/model/key. Nhập key một lần cho cấu hình đó;
backend lưu mã hóa để dùng lại sau khi tải trang, đăng xuất hoặc khởi động lại.
Có thể dùng cùng key để tạo cấu hình cho model khác nếu nhà cung cấp cho phép.
Nhập thêm kết nối mới khi đổi key/model; cấu hình cũ giữ metadata cho lịch sử.
Tắt kết nối xóa ciphertext đã lưu và chặn lần gọi mới. Request đã bắt đầu
có thể vẫn hoàn tất và tính phí.

Khi lỗi xác thực/quota, thêm hoặc chọn kết nối khác trên trang workflow rồi
**Thử lại bước lỗi**. Giữ yêu cầu, tài liệu BA trước và phản hồi PM. Lịch sử mỗi
lần gọi ghi provider/model/connection ID riêng; snapshot ban đầu không bị sửa.
Tối đa 3 attempts cho một run. Hết số lần thử cần tạo run mới; tài liệu run cũ
vẫn xem được nhưng không tự nhập vào context của run mới.

PM account là danh tính trong Squad Live, không phải đăng nhập Google/DeepSeek.
Ứng dụng không lấy lịch sử chat hay quyền subscription từ các sản phẩm đó.
Chi phí và quota thuộc tài khoản API của người dùng.

## Provider và model

- OpenAI: Responses API với strict JSON Schema.
- Gemini: Generate Content với `responseMimeType` và `responseJsonSchema`.
- DeepSeek: Chat Completions với JSON mode; kiểm tra schema bằng Pydantic.

Discovery gọi endpoint model chính thức với key user, không gọi inference.
Danh sách là quyền truy cập được provider trả về, không bảo đảm mọi model đều
hỗ trợ schema/output budget. Nếu provider từ chối, run báo lỗi; chọn model khác.
Có giới hạn timeout/kích thước response. Không có base URL tùy ý.

Nguồn: [OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs),
[Gemini](https://ai.google.dev/gemini-api/docs/generate-content/structured-output),
[DeepSeek](https://api-docs.deepseek.com/guides/json_mode/).

## API và lưu trữ

- `GET /api/v1/capabilities`: khả năng BYOK và mã hóa; không chứa key.
- `POST /api/v1/ai-connections/models`: `{provider, api_key}` → danh sách model.
- `POST /api/v1/ai-connections`: `{name, provider, api_key, model}` → metadata.
- `GET /api/v1/ai-connections`: metadata phân trang, chỉ owner.
- `POST /api/v1/ai-connections/{id}/disable`: tắt và xóa key đã mã hóa.
- Start run: `{mode:"ba_live", connection_id:"..."}` với `Idempotency-Key`.
  Thiếu connection trả 422; connection của PM khác trả 404; bị tắt trả 409.
  Cùng idempotency key khác mode/kết nối trả 409.
- Retry run: body tùy chọn `{connection_id:"..."}` để đổi kết nối ở bước BA lỗi.
- `GET /api/v1/workflow-runs/{id}/agent-runs`: lần thực thi, model/token/thời gian.

Migration `0004_ai_connections` thêm kết nối và liên kết đến run/agent.
Lịch sử cũ giữ nguyên. Run BA cũ thiếu kết nối phải chọn BYOK trước khi thử lại.
Không có endpoint trả API key hoặc ciphertext. Key mã hóa bằng Fernet; frontend
chỉ giữ tạm trong form, không lưu localStorage/sessionStorage. PM đăng nhập Google
qua cookie HttpOnly; API key model được quản lý riêng với tài khoản đăng nhập.

## Bảo đảm thực thi

Claim bằng PostgreSQL row lock/lease; gọi AI ngoài transaction. Kết quả chỉ lưu
nếu run/attempt/revision/lease còn hợp lệ. Hủy run bỏ kết quả đến muộn, không bảo đảm
hủy phí provider. Lease hết hạn không tự gọi lại. Không tự đổi key hoặc provider.

Pydantic kiểm tra ID story/AC, liên kết và kích thước tài liệu trước khi mở gate.
Artifact bất biến; duyệt phải khớp attempt/gate/artifact. Không cấp tool cho LLM.
Context tối đa 50.000 ký tự, tài liệu tối đa 24.000; trường bị cắt có ghi chú trong
context. Redaction chỉ là phòng vệ bổ sung, không bảo đảm loại mọi loại secret.
Không lưu raw lỗi provider. Thiếu usage hiển thị `—`, không giả định bằng 0.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic scripts
.\.venv\Scripts\python.exe scripts/verify_postgres.py
.\.venv\Scripts\python.exe scripts/verify_browser.py
```

Browser verification dùng `tests.browser_services`: API/auth/DB/mã hóa/workflow/
worker thật, chỉ I/O provider thay bằng fixture offline. Không dùng entrypoint
này để chạy ứng dụng. Production vẫn là `app.main:app` và `app.workers.runner`.
Test adapters dùng MockTransport, không cần key và không phát sinh phí.
Chưa xác minh live với OpenAI/Gemini/DeepSeek vì chưa có credential thật.
