# Kết nối repository Git local

Sau khi chạy `alembic upgrade head` và khởi động lại API, mở trang dự án và chọn
**Chọn thư mục Git**. Hộp thoại của hệ điều hành mở trên máy chạy backend. Chọn
**thư mục gốc** của một Git working tree có commit. Nếu backend không có desktop
để mở hộp thoại, có thể mở **Nhập đường dẫn thủ công**.
Trang dự án hiển thị nhánh, commit HEAD, trạng thái thay đổi của các file tracked,
cho tìm file và xem nội dung UTF-8. Ngắt kết nối chỉ bỏ đường dẫn trong database;
không xóa hay sửa repository trên máy. Mỗi project có một kết nối, chỉ PM sở hữu
project được truy cập qua API.

Trang repository của dự án vẫn **chỉ đọc**. Khi dự án đã kết nối Git và có workflow run,
trang chi tiết run cho phép PM chọn **Tạo workspace riêng**. Backend tạo một Git worktree
detached cho run, ghim commit HEAD tại thời điểm tạo và lưu đường dẫn trong database.
Repository nguồn phải sạch; mỗi run chỉ có một workspace và thao tác tạo lặp lại trả về
workspace cũ. PM có thể tìm trong cây thư mục file thay đổi, chọn từng file để xem diff
so với commit gốc ngay trên trang run; file mới, đã sửa và đã xóa có trạng thái riêng.
Các file mới chưa tracked cũng được hiển thị nếu là văn bản UTF-8 nhỏ; diff bị giới hạn
512 KiB và tối đa 100 file để tránh phản hồi quá lớn. Workspace mặc định nằm trong thư mục
`%LOCALAPPDATA%\SquadLive\worktrees` trên Windows; có thể đổi bằng `WORKSPACE_ROOT`.

Worktree hiện là nền tảng cách ly và đối chiếu. Dev AI và Tester AI vẫn dùng workflow/artifact
hiện tại. Trong trang run, PM có thể chọn một model BYOK và bấm **Cho Dev AI sửa code**.
Đây là hành động riêng, có lịch sử trong run: PM có thể chọn tối đa 12 file nguồn hoặc
để hệ thống tự chọn. Các file UTF-8 (mỗi file tối đa 8 KiB, tổng tối đa 64 KiB),
tài liệu đã duyệt nếu có và yêu cầu công việc được
gửi tới model; hệ thống nhận tối đa 5 file hoàn chỉnh,
kiểm tra đường dẫn và ghi vào worktree. File hiện có chỉ được sửa nếu đã nằm trong ngữ cảnh
gửi đi; file mới phải nằm dưới thư mục đã có. Nếu workspace thay đổi trong lúc model chạy,
hệ thống không áp dụng kết quả cũ. Mỗi lần bấm có thể tiêu tốn quota API, kể cả khi model
trả kết quả không hợp lệ. Hành động này không tự duyệt, không commit, không merge và không
chạy build/test. PM cần xem diff sau khi AI sửa. Luồng Tester AI hiện chưa đọc worktree.
Kết nối Git không tự chuyển các workflow đã có sang chế độ sửa code tự động.

Chỉ các file tracked được liệt kê, tối đa 2.000 file. API chặn `.env*`, private-key
extensions, thư mục build/dependency, đường dẫn ra ngoài repository, symlink trỏ
ra ngoài, binary và file trên 256 KiB. Các giới hạn này giảm rủi ro khi xem mã nguồn,
không phải cơ chế phát hiện mọi secret. Trước khi cho agent sửa code/chạy test,
cần nối workflow với worktree và môi trường thực thi giới hạn quyền.

Backend được hướng dẫn chạy trên `127.0.0.1`; không mở các endpoint truy cập
filesystem local ra mạng công cộng.
