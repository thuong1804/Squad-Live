# Đăng nhập PM bằng Google

Frontend dùng Google OAuth Authorization Code + PKCE (S256). Backend kiểm tra
state gắn với browser, nonce, chữ ký ID token, issuer, audience và thời hạn token.
State chỉ dùng một lần trong 10 phút. Không lưu Google access/refresh/ID token.
Xác minh ID token cho phép lệch đồng hồ tối đa 120 giây. Nếu Windows chưa đồng bộ,
vào Settings → Time & language → Date & time → Sync now trước khi đăng nhập lại.

## Cấu hình Google Cloud

1. Mở [Google Cloud Console](https://console.cloud.google.com/), chọn/tạo project.
2. Vào **Google Auth Platform** (hoặc APIs & Services → OAuth consent screen).
   Khai báo app name, email hỗ trợ và contact. Chọn External nếu dùng Gmail cá nhân.
   Nếu app còn Testing, thêm email đăng nhập vào **Test users**.
3. Tạo OAuth Client loại **Web application**.
4. Authorized JavaScript origins: `http://localhost:5173`.
5. Authorized redirect URIs: `http://localhost:8000/auth/google/callback`.
6. Lưu Client ID và Client Secret vào `backend/.env`, không gửi secret trong chat
   hoặc đặt trong biến `VITE_*`.

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
FRONTEND_URL=http://localhost:5173
LEGACY_TOKEN_AUTH_ENABLED=false
SESSION_DAYS=7
```

Giữ `CONNECTION_ENCRYPTION_KEY` đã tạo cho BYOK. Chạy từ `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe scripts/setup_local.py
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Restart API sau khi đổi cấu hình. Mở **http://localhost:5173** để đăng nhập.
Frontend, API base URL và callback nên thống nhất hostname `localhost`; không
trộn với `127.0.0.1` vì cookie SameSite. Nếu đổi hostname/port, đổi cả OAuth Client,
`FRONTEND_URL`, `GOOGLE_REDIRECT_URI`, CORS và `VITE_API_BASE_URL` tương ứng.
Ngoài loopback cần HTTPS; app cookie tự bật Secure khi callback dùng HTTPS.

Chỉ xin `openid email profile`. Đăng nhập này không cấp quota Gemini, không đọc
lịch sử ChatGPT/Gemini và không thay thế API key BYOK. Khi thiếu cấu hình, trang
hiển thị hướng dẫn và khóa nút đăng nhập; không giả lập Google trong production.

## Session và quyền dữ liệu

Danh tính mặc định là `google:<sub>`; dùng Google `sub` ổn định, không dùng email
làm khóa quyền sở hữu. Email/tên chỉ dùng hiển thị. Cookie session HttpOnly,
SameSite=Lax, mặc định 7 ngày. Database chỉ giữ hash session token, có thể thu hồi.
Tải lại trang/restart server vẫn đăng nhập. Đăng xuất xóa session server và cookie.
Mọi ghi dữ liệu bằng cookie yêu cầu Origin đúng `FRONTEND_URL` và CSRF token riêng.
Frontend nhận CSRF token vào bộ nhớ, không đọc được cookie session.
Callback OAuth được loại khỏi Uvicorn access log để tránh log authorization code.
Reverse proxy triển khai thêm cũng cần bỏ query callback khỏi log.

Bearer token cũ tắt mặc định; chỉ bật `LEGACY_TOKEN_AUTH_ENABLED=true` cho migration
hoặc API automation có chủ đích. Giao diện không còn ô nhập token local.

## Dữ liệu pm-local cũ

Không tự gán dữ liệu cũ cho tài khoản Google đầu tiên. Đăng nhập Google một lần,
xem identity trong response `/auth/session` bằng DevTools (không chia sẻ cookie
hoặc csrf_token). Lấy phần `sub` sau `google:` và chạy:

```powershell
.\.venv\Scripts\python.exe scripts/link_google_owner.py --legacy-owner pm-local --google-sub YOUR_SUB
# Kiểm tra email đích và số lượng dữ liệu, rồi mới áp dụng:
.\.venv\Scripts\python.exe scripts/link_google_owner.py --legacy-owner pm-local --google-sub YOUR_SUB --apply
```

Chuyển Project owner, AI connection owner và WorkItem creator trong một transaction;
giữ artifact, approval, event và lịch sử run. Reviewer trong lịch sử giữ tên cũ.
Script mặc định dry-run, không tự chọn tài khoản đích. Sau chuyển, tải lại trang.

## Validation

Migration: `0005_google_auth`. Test offline bao gồm state/cookie binding, replay,
nonce, chữ ký/audience/issuer/expiry ID token bằng chứng chỉ RSA fixture, session
qua restart, CSRF, owner isolation và logout. Browser E2E giả lập consent/token I/O
của Google; phần callback/session/DB/quyền sở hữu là thật. Cần Client ID/Secret thật
để xác minh lần đăng nhập Google thực tế.

Tham khảo: [Google web server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server),
[xác minh ID token](https://developers.google.com/identity/sign-in/web/backend-auth).
