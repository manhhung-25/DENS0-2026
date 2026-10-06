# Panda/HoRoPose: trọn bộ tạo video

Gói này đã có mã nguồn, checkpoint đã ghép sẵn, 120 ảnh RGB và annotation DREAM, dự đoán từng frame, mô hình chẩn đoán cảm biến, cơ sở dữ liệu sự kiện và video mẫu. Không cần tải hay ghép thêm bốn phần checkpoint. Video mẫu trong gói khớp SHA-256 với `D:\DENSO\panda_horopose_health_demo.mp4.crdownload`; ảnh RGB nguồn nằm ở `data/panda_realsense/`.

## Chạy trên Ubuntu hoặc WSL2

Mở terminal **trong thư mục này**:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export PYTHONPATH="$PWD/src"
python -m robot_demo.horopose_panda --batch-size 4 --output artifacts/verification/panda_pose_predictions.npz
python -m robot_demo.make_panda_video --predictions artifacts/verification/panda_pose_predictions.npz --output artifacts/verification/reproduced.mp4 --fault-model artifacts/fault_model.joblib --events artifacts/verification/events.db
```

Kết quả mới ở `artifacts/verification/`; video và dự đoán gốc giữ nguyên để so hash. Nếu chỉ cần dựng lại từ kết quả AI đã lưu, dùng `--predictions artifacts/panda_pose_predictions.npz` và một đường `--output` mới. Mã render tự ánh xạ `image_path` tuyệt đối cũ sang ảnh trong thư mục `data/panda_realsense/`.

Trên PowerShell: kích hoạt `.venv\Scripts\Activate.ps1` và đặt `$env:PYTHONPATH = (Resolve-Path src).Path` trước hai lệnh `python -m ...`.

## Mã nào làm việc gì

- `vendor/holistic_pose/`: mã HoRoPose chính thức ở commit `77cd316a36ff8de0c736a66c692ca9276fdc2eae`.
- `checkpoints/horopose_panda_realsense_inference.pk`: checkpoint Panda–RealSense; model tensors giữ nguyên, optimizer đã bỏ. SHA-256: `9c531ede1e32fcfc1d51a92cdef63f285483786730edda35e73838026c181c3c`.
- `src/robot_demo/horopose_panda.py`: nạp checkpoint strict, inference 120 frame, tính `q`, rotation 6D, translation và keypoint; lọc thời gian; hiệu chuẩn góc khớp từ 30 annotation đầu.
- `src/robot_demo/make_panda_video.py`: 500 frame, 1280×720, 30 FPS; overlay robot, dashboard chu kỳ, tín hiệu cảm biến, kết luận và xuất H.264.
- `src/robot_demo/faults.py`, `train_fault.py`, `event_store.py`: dữ liệu lỗi giả lập, mô hình ExtraTrees và lưu sự kiện.
- `data/panda_realsense/`: ảnh và nhãn DREAM `002640..002759`.
- `artifacts/panda_pose_predictions.npz`: kết quả inference đã lưu, để render lại nhanh.
- `artifacts/fault_model.joblib`: mô hình chẩn đoán dùng cho dashboard.
- `artifacts/panda_horopose_health_demo.mp4`: video kết quả mẫu; SHA-256 `c91552e2b271160257938f1bf49a37aa86f22105450dcd88d6491696c21ac02e`.
- `PANDA_RUN_LOG.md` và `PANDA_HOROPOSE_DEMO.md`: lệnh đã chạy, kết quả và giải thích chi tiết.

## Giới hạn cần biết

Phần camera/pose là dự đoán từ checkpoint công khai. Offset `q` được tính từ ground truth 30 frame đầu; các chấm xanh lá và vạch xanh lá là ground truth dùng để đánh giá. Chu kỳ thứ hai được kéo dài giả lập; rung, âm thanh, nhiệt độ, dòng điện và nhãn lỗi J4 cũng là giả lập. Dựng lại MP4 có thể khác hash vì phiên bản bộ mã hóa, cơ sở dữ liệu sự kiện và thư viện khác nhau, dù pipeline và hình ảnh tương ứng.

Trong bản tích hợp DENSO hiện tại, suy luận đã chạy lại trên 120/120 ảnh bằng checkpoint đóng gói (`strict=True`, 2.308 tensor), rồi dựng lại video 500 frame, 1280×720, 30 fps. Lần chạy lại đạt sai số q sau hiệu chỉnh 5,529° và keypoint 7,554 px trên đoạn DREAM. Video mới khác hash do phiên bản mã hóa/môi trường nhưng khớp cấu trúc và hình ảnh gần sát bản giao.
