# Nguồn gốc video demo Panda

## Bằng chứng đã kiểm tra

- `D:\DENSO\Panda_HoRoPose_Full_Repro.zip` chứa `artifacts/panda_horopose_health_demo.mp4`. Video trong ZIP có 3.667.451 byte, SHA-256 `C91552E2B271160257938F1BF49A37AA86F22105450DCD88D6491696C21AC02E`, trùng chính xác với `D:\DENSO\panda_horopose_health_demo.mp4.crdownload`. Đuôi `.crdownload` không phản ánh định dạng bên trong: đây là MP4/H.264, 1280 × 720, 30 fps, dài 16,67 giây.
- ZIP chứa 120 ảnh RGB và nhãn JSON của bộ DREAM `panda-3cam_realsense`, checkpoint HoRoPose Panda khoảng 320 MB, `artifacts/panda_pose_predictions.npz` (góc khớp, pose, tọa độ khớp 2D/3D và nhãn đối chiếu), cùng mã nguồn dựng video.
- `src/robot_demo/horopose_panda.py` nạp checkpoint với `load_state_dict(..., strict=True)` rồi suy luận trên 120 ảnh RGB. Pipeline dùng bounding box từ nhãn DREAM làm đầu vào và dùng góc khớp thật của 30 frame đầu để hiệu chỉnh offset; vì vậy đây chưa phải quy trình suy luận độc lập từ luồng camera chưa gắn nhãn.
- `src/robot_demo/make_panda_video.py` vẽ đường và chấm cyan từ `keypoints_2d_smooth`; chấm xanh lam là dự đoán thô và chấm xanh lá là nhãn dữ liệu. Biểu đồ cảm biến, lỗi và độ trễ trong video được tạo mô phỏng. Vùng robot ở frame đầu khớp với ảnh RGB đầu tiên sau khi đổi kích thước (sai khác tuyệt đối trung vị 2 mức màu); các chỉ số trong JSON cũng khớp khi tính lại từ NPZ.
- Dashboard mới dùng `pose_focus_demo/import_horopose.py` để lấy trực tiếp keypoint/q từ NPZ, ánh xạ theo `source_frame` sang 500 frame video. `prepare_pose.py` chỉ còn là công cụ kiểm tra lớp cyan cũ. Tại các mốc có thể đối chiếu, tọa độ NPZ và marker cyan cũ lệch trung vị khoảng 0,44 pixel.

## Giới hạn tái lập

- Đã chạy lại toàn bộ suy luận trên 120/120 ảnh bằng checkpoint trong ZIP: `strict=True`, 2.308 tensor, epoch 76. Lần chạy lại đạt MAE góc khớp sau hiệu chỉnh 5,529° và sai số keypoint 7,554 px trên tập DREAM này. Mã adapter hiện nạp checkpoint bằng `weights_only=True`.
- Đã dựng lại video từ dự đoán mới: 500 frame, 1280 × 720, 30 fps, chẩn đoán mô phỏng J4. Hash video khác bản giao vì phiên bản mã hóa và sự kiện; ở sáu frame lấy mẫu, sai khác pixel trung bình khoảng 4–5/255. Dự đoán keypoint mới so với NPZ gốc lệch trung bình khoảng 0,005 pixel; góc q thô lệch trung bình khoảng 0,0005 rad.
- `image_path` lưu trong NPZ là đường dẫn tuyệt đối `/workspace/scratch/...` của môi trường tạo gói. `make_panda_video.py` đã được sửa để ánh xạ tên ảnh sang `data/panda_realsense/` tại máy hiện tại.
- Video 500 frame được dựng bằng cách dùng lại 120 ảnh nguồn theo chiều xuôi và ngược, cùng đoạn giữ hình để mô phỏng chậm chuyển động. Đây không phải 500 frame camera độc lập hay telemetry cảm biến thực.
- Checkpoint có sẵn trong ZIP; dashboard phát lại dự đoán đã lưu, không huấn luyện hoặc suy luận trong mỗi lần phát video. `checkpoint_sha256` ghi trong NPZ là hash của checkpoint công khai đầy đủ lúc tạo bản gốc (`8611…`); checkpoint đóng gói đã bỏ optimizer nên hash khác (`9c53…`) dù vẫn nạp strict đủ tensor. Nguồn phát hành và giấy phép riêng của footage/dataset/checkpoint vẫn cần đối chiếu với tài liệu gốc của từng tài nguyên trước khi dùng ngoài demo.
