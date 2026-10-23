# Tạo website tĩnh với kiểm tra Chromium và đánh giá AI

Chế độ `static_site` (`static-site-v3`) dành cho website nhỏ HTML/CSS/JS.
Run mới có kiểm tra Chromium trước Tester AI và Reviewer AI. Run `static-site-v2`
giữ Tester/Reviewer chỉ đọc mã; run `static-site-v1` giữ Tester mô phỏng.
Run `mock` và `ba_live` cũ giữ nguyên hành vi và snapshot. Không tự đổi run đã hoàn tất.

## Demo

1. Đăng nhập Google và lưu kết nối AI đang dùng được trong Cài đặt AI.
2. Tạo công việc, ví dụ: “Tạo landing page tiếng Việt cho quán cà phê, có menu,
   giao diện mobile và nút đổi giao diện sáng/tối. Không dùng tài nguyên bên ngoài.”
3. Chọn **Tạo website tĩnh · BA + Dev thật**, chọn kết nối rồi **Bắt đầu tạo website**.
4. Duyệt tài liệu BA. Dev dùng AI tạo kế hoạch; đọc kế hoạch rồi phê duyệt.
5. Dev dùng AI sinh `index.html`, `styles.css`, `script.js`. Phần **Kết quả website**
   cho phép xem mã, bật Preview desktop/mobile và tải ZIP.
6. Chromium mở trang ở desktop 1440px và mobile 390px, ghi ảnh, lỗi JavaScript,
   lỗi tài nguyên/ảnh và tràn ngang. Kết quả gắn vào đúng phiên bản website.
7. Tester AI phân tích mã cùng kết quả kiểm tra, Reviewer AI đọc lại mã và báo cáo Tester.
   Cả hai trả nhận xét có bằng chứng, mức độ lỗi, đề xuất và checklist thủ công.
8. PM đọc bằng chứng và hai báo cáo, kiểm tra trang rồi duyệt cuối hoặc yêu cầu chỉnh sửa. Chọn quay về Dev để lập
   kế hoạch mới, hoặc BA nếu cần đổi yêu cầu. Mỗi bản website được giữ độc lập.

Chế độ này dùng cùng kết nối BYOK cho BA, Dev, Tester và Reviewer. Mỗi bước AI có thể tiêu tốn quota.
Dev sinh mã dùng giới hạn riêng `DEV_MAX_OUTPUT_TOKENS=16384` để có đủ chỗ cho ba
file và token suy luận; BA/kế hoạch giữ giới hạn `LLM_MAX_OUTPUT_TOKENS` hiện có.
Đổi kết nối ở bước lỗi không thay đổi model/token/metadata của các lần chạy trước.
Sau khi tải ZIP, giải nén cả ba file vào cùng thư mục rồi mở `index.html`.

## Phạm vi và cách lưu

- Workspace của mỗi run được lưu trong database dưới dạng artifact `website`
  bất biến, gồm tên và nội dung ba file. Không ghi/thi hành mã AI trên filesystem host.
- `DEV_PLAN` và `DEV_BUILD` có phiên thực thi, lease, model, token và thời gian riêng.
  Dev nhận đúng artifact đã được PM duyệt; website liên kết ID yêu cầu và kế hoạch.
- Kiểm tra cấu trúc xác minh tên file, tính duy nhất, kích thước và trang HTML đầu vào.
- `BROWSER` dùng Playwright/Chromium trong tiến trình riêng, iframe không có cùng
  origin, CSP chặn kết nối/tài nguyên ngoài, context mới không mang cookie PM,
  môi trường con không nhận API key/DB URL, giới hạn thời gian và kích thước ảnh.
  Chỉ chạy bộ kiểm tra cố định; không chạy test code do AI sinh ra. Đây là cách ly
  ở trình duyệt, không phải sandbox hệ điều hành. Cần cài Node, Playwright và Chromium.
- Báo cáo Chromium có `browser_tests_executed=true`, lưu screenshot JPEG cho mỗi
  viewport trong artifact `browser_report`. Các lỗi được ghi là quan sát thật;
  kết quả không chứng minh mọi tương tác hay tiêu chí nghiệm thu đều đúng.
- Tester và Reviewer dùng model để phân tích mã cùng báo cáo Chromium (không gửi
  ảnh vào model). Schema của AI bắt buộc `browser_tests_executed=false`: trường này
  mô tả việc chính AI không điều khiển browser, không phủ nhận bộ kiểm tra riêng.
  Hai báo cáo liên kết đúng website/yêu cầu/kế hoạch; Reviewer nhận báo cáo Tester
  của cùng website. AI không tự phê duyệt hay tự sửa code; PM quyết định cuối.
- Hai bước mới có AgentRun riêng (`TESTER`, `REVIEWER`), lease, token và retry;
  hủy run loại bỏ kết quả đến muộn. Đổi model khi retry giữ nguyên đầu vào đã duyệt.
- Khởi động lại API và worker, rồi tạo run mới để dùng luồng v3.
- Không có npm, framework, backend, tài nguyên ngoài, GitHub PR hoặc deployment.
- Không đổi schema DB; dùng bảng artifacts/agent_runs hiện có.

## Preview và quyền truy cập

Nguồn chỉ được trả qua JSON có xác thực hoặc ZIP attachment; không có endpoint
phục vụ HTML do AI sinh trực tiếp trên origin của ứng dụng. File ngoài ba tên cho phép,
đường dẫn tuyệt đối, traversal và trùng tên bị từ chối trước khi lưu.

Preview dùng `iframe sandbox="allow-scripts"`, không cấp `allow-same-origin`, popup,
form hoặc top navigation. CSS/JS đi kèm được nhúng qua data URL. CSP chặn fetch,
frame con và tài nguyên ngoài; iframe không đọc được cookie/DOM của PM. Preview
không phải sandbox hệ điều hành hay cơ chế giới hạn CPU cho JavaScript. Có thể đóng
Preview để ngừng chạy trang. File ZIP là nguồn gốc chưa sửa, nên việc mở ngoài app
không có chính sách cách ly của Preview.

Mọi endpoint sau đều kiểm tra chủ sở hữu run và artifact:

- `GET /api/v1/workflow-runs/{run_id}/websites`: danh sách phiên bản, phân trang.
- `GET /api/v1/workflow-runs/{run_id}/websites/{artifact_id}`: file, ghi chú, preview HTML.
- `GET /api/v1/workflow-runs/{run_id}/websites/{artifact_id}/download`: ZIP attachment.
- `GET /api/v1/workflow-runs/{run_id}/websites/{artifact_id}/browser-report`:
  báo cáo và ảnh của đúng website; chỉ chủ sở hữu run được xem, `no-store`.

## Kiểm tra

Backend: `python -m pytest -q tests/test_static_site.py` kiểm tra chuỗi phê duyệt,
đầu vào đã duyệt, sửa bản mới, giữ bản cũ, ZIP, phân quyền, retry, hủy, lease hết hạn
và tên file không hợp lệ. Browser: `python scripts/verify_browser.py` có luồng website
riêng, kiểm tra JavaScript/CSS trong iframe, cách ly trang cha, chặn fetch, tải xuống,
revision và reload. ZIP được giải nén vào thư mục kết quả test, mở `index.html`
độc lập để kiểm tra CSS, tương tác JavaScript, lỗi trình duyệt và chiều rộng mobile.
Browser fixture giả lập provider; API, DB, worker và session thật.

Tham khảo: [iframe srcdoc](https://developer.mozilla.org/en-US/docs/Web/API/HTMLIFrameElement/srcdoc)
và [sandbox](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/sandbox).
