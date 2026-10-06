# Ghi chép nguồn gốc video demo

## Những gì xác minh được

- Trước khi dựng dashboard, workspace đã có tệp `D:\DENSO\panda_horopose_health_demo.mp4.crdownload`. Tệp có 3.667.451 byte; SHA-256: `C91552E2B271160257938F1BF49A37AA86F22105450DCD88D6491696C21AC02E`.
- Nội dung là MP4/H.264, 1280 × 720, 30 fps, dài 16,67 giây dù tên có đuôi `.crdownload`. Metadata chứa `encoder=Lavf61.1.100`; thông tin này chỉ cho biết tệp từng được mã hóa/đóng gói bằng FFmpeg, không cho biết tác giả hay URL nguồn.
- Hình video có cánh tay Franka Panda, đường/mốc cyan và một bảng chỉ số. Trên hình có chữ “HoRoPose ECCV 2024 checkpoint” và ghi chú cảm biến/lỗi/độ trễ được mô phỏng cho demo. Đây là **chữ nằm trong video**, chưa phải bằng chứng checkpoint HoRoPose đã chạy.
- `pose_focus_demo/prepare_pose.py` cắt vùng hình robot từ tệp trên thành `robot_original.mp4` (840 × 646), tạo `poster.jpg`, dùng OpenCV tìm những dấu cyan **đã có sẵn** và lưu tối đa 7 tọa độ 2D/frame vào `pose_recording.json`. Dashboard không chạy HoRoPose inference trên video thô.

## Những gì chưa xác minh được

- Chưa tìm thấy URL tải, trang xuất bản, tên tác giả, giấy phép sử dụng hoặc video camera chưa có chú giải. Tệp không có Windows `Zone.Identifier` chứa nguồn tải; lịch sử tải Chrome trên máy không có bản ghi khớp tên tệp. Tìm kiếm công khai theo tên tệp và các dòng chữ đặc trưng không tìm thấy bản gốc có thể đối chiếu.
- Không thể kết luận dấu cyan do nhà sản xuất robot, một dataset, HoRoPose hay người biên tập video tạo ra. Không thể dùng clip này để chứng minh độ chính xác nhận diện khớp từ ảnh RGB thô.

Tệp `.crdownload` là **tệp đầu vào sớm nhất hiện tìm thấy trong workspace**, không phải “footage gốc” theo nghĩa đã rõ nơi quay và chuỗi xử lý. Nó không được đưa vào repo vì dashboard đã có bản cắt `robot_original.mp4`. Muốn xây dựng demo pose AI có thể kiểm chứng, cần clip RGB không chèn pose, quyền sử dụng rõ ràng, checkpoint/phiên bản mô hình, cấu hình camera và kết quả inference có thể tái lập.
