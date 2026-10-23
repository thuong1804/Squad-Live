# Kết nối repository Git local

Sau khi chạy `alembic upgrade head` và khởi động lại API, mở trang dự án và chọn
**Chọn thư mục Git**. Hộp thoại của hệ điều hành mở trên máy chạy backend. Chọn
**thư mục gốc** của một Git working tree có commit. Nếu backend không có desktop
để mở hộp thoại, có thể mở **Nhập đường dẫn thủ công**.
Trang dự án hiển thị nhánh, commit HEAD, trạng thái thay đổi của các file tracked,
cho tìm file và xem nội dung UTF-8. Ngắt kết nối chỉ bỏ đường dẫn trong database;
không xóa hay sửa repository trên máy. Mỗi project có một kết nối, chỉ PM sở hữu
project được truy cập qua API.

Đây là bước **chỉ đọc**. Dev AI và Tester AI vẫn dùng workflow/artifact hiện tại;
chúng chưa nhận mã nguồn repository làm ngữ cảnh, chưa ghi file hay chạy lệnh test
trong repository. Kết nối Git không tự chuyển các workflow đã có sang chế độ sửa code.

Chỉ các file tracked được liệt kê, tối đa 2.000 file. API chặn `.env*`, private-key
extensions, thư mục build/dependency, đường dẫn ra ngoài repository, symlink trỏ
ra ngoài, binary và file trên 256 KiB. Các giới hạn này giảm rủi ro khi xem mã nguồn,
không phải cơ chế phát hiện mọi secret. Trước khi cho agent sửa code/chạy test,
cần worktree riêng cho từng run, diff để PM duyệt và môi trường thực thi giới hạn quyền.

Backend được hướng dẫn chạy trên `127.0.0.1`; không mở các endpoint truy cập
filesystem local ra mạng công cộng.
