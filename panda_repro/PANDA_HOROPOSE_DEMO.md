# Demo Franka Panda: pose thật từ checkpoint + giám sát đa cảm biến

## Kết quả đã chạy

Video dùng 120 ảnh RGB liên tiếp của robot Franka Emika Panda thật trong tập
`DREAM panda-3cam_realsense`. Mỗi ảnh đều đi qua checkpoint Panda–RealSense
công khai của **HoRoPose / Real-time Holistic Robot Pose Estimation with Unknown
States (ECCV 2024)**. Đây không phải keypoint đặt bằng tay hoặc optical flow.

Checkpoint xuất trực tiếp:

- `q1...q7` và độ mở ngón kẹp;
- rotation 6D của root `L4`;
- translation XYZ của root `L4`;
- 7 keypoint 3D, sau đó chiếu về ảnh bằng camera intrinsics.

Kiểm tra thực tế của lần chạy này:

| Thuộc tính | Kết quả |
|---|---:|
| Frame inference độc lập | 120/120 |
| Tensor checkpoint được load | 2.308 |
| Strict state-dict load | `true` |
| Epoch ghi trong checkpoint | 76 |
| ADD/AUC ghi trong checkpoint | 0,7522 |
| Sai số keypoint sau lọc thời gian | 7,55 px |
| MAE 7 góc khớp, raw | 12,66° |
| MAE sau hiệu chuẩn chu kỳ chuẩn | 5,54° |

Hiệu chuẩn dùng median offset của 30 frame đầu có annotation. Trong nhà máy,
annotation này phải được thay bằng telemetry controller hoặc quỹ đạo chuẩn của
nhà sản xuất. Không dùng ground truth để làm mượt quỹ đạo keypoint.

## Video tốt hơn bản ABB ở đâu

| Bản ABB trước | Bản Panda này |
|---|---|
| CoTracker theo điểm 2D | Checkpoint robot-pose chuyên biệt |
| Không có góc khớp vật lý | Có `q1...q7` theo từng frame |
| Không có pose camera–robot | Có rotation 6D + translation 3D |
| Không có ground truth kiểm thử | Có annotation, báo sai số 7,55 px |
| Overlay điểm ảnh | Overlay động học 3D chiếu về RGB + temporal filter |

Q7 gần như không chuyển động trong đoạn dữ liệu chọn, nên sai số riêng của q7
còn cao. Video vẫn giữ dấu tham chiếu màu xanh để điểm yếu này nhìn thấy được.

## Phần thật và phần giả lập

- **Thật:** ảnh RGB Panda, checkpoint, `q`, pose 6D, keypoint 3D/2D.
- **Giả lập có ghi nhãn rõ:** thời gian dừng thêm 0,8 s ở chu kỳ 2; tín hiệu
  rung, âm thanh, nhiệt độ, dòng motor; nhãn `gearbox_backlash` tại J4.
- Mô hình ExtraTrees sensor fusion dự đoán lại `gearbox_backlash`, J4 với
  confidence 96,15%. Event và phản hồi kỹ thuật viên được lưu trong SQLite.

Các tín hiệu giả lập chỉ chứng minh pipeline dữ liệu. Chúng không chứng minh
robot thật đang hỏng.

## Chạy lại

```bash
python -m pip install -r requirements.txt
export PYTHONPATH="$PWD/src"

python -m robot_demo.horopose_panda --batch-size 4
python -m robot_demo.make_panda_video
```

Nếu nhận checkpoint dưới dạng bốn phần, đặt chúng trong `checkpoint_parts/`
rồi chạy `bash assemble_panda_checkpoint.sh`. Hash tệp ghép phải khớp giá trị
trong `CHECKPOINT_PARTS_SHA256.txt`.

Các tệp chính:

- `src/robot_demo/horopose_panda.py`: adapter inference CPU và đánh giá.
- `src/robot_demo/make_panda_video.py`: temporal pose, cycle time, sensor fusion.
- `vendor/holistic_pose/`: mã nguồn upstream đúng commit
  `77cd316a36ff8de0c736a66c692ca9276fdc2eae`.
- `checkpoints/horopose_panda_realsense_inference.pk`: checkpoint inference 306 MB,
  giữ nguyên toàn bộ 2.308 tensor model; SHA-256
  `9c531ede1e32fcfc1d51a92cdef63f285483786730edda35e73838026c181c3c`.
- Checkpoint phát hành đầy đủ 958 MB (có thêm optimizer để tiếp tục training)
  được lấy lại bằng `download_panda_assets.sh`; SHA-256
  `8611ff23183d1ada861627f728b19f3318f755a95c6d7d75a0944b5dd5b8614c`.
- `artifacts/panda_pose_predictions.npz`: raw/smoothed/calibrated predictions.
- `artifacts/panda_multimodal_timeseries.csv`: toàn bộ timeline đồng bộ.
- `artifacts/events.db`: event và nhãn kỹ thuật viên.

## Thuật ngữ / keywords

- **Unknown robot states:** trạng thái/góc khớp không được cấp trước cho model.
- **6D pose:** rotation 3D và translation 3D của robot so với camera.
- **Root pose:** pose của link được chọn làm gốc; demo này dùng `L4`.
- **Joint angle estimation:** ước lượng các biến khớp `q1...q7` từ RGB.
- **Temporal smoothing:** lọc theo thời gian để giảm rung/jitter giữa các frame.
- **Normal-cycle calibration:** lấy chu kỳ máy khỏe làm mốc bù sai lệch cố định.
- **Cycle-time deviation:** thời gian chu kỳ lệch khỏi mốc bình thường.
- **Sensor fusion:** kết hợp camera, rung, âm thanh, nhiệt độ và dòng điện.
- **Evidence window:** đoạn dữ liệu đa cảm biến quanh thời điểm bất thường.
- **Human-in-the-loop:** kỹ thuật viên xác nhận/sửa nhãn để tái huấn luyện sau.

## Nguồn chính thức

- HoRoPose: <https://github.com/Oliverbansk/Holistic-Robot-Pose-Estimation>
- RoboPose: <https://github.com/yannlabb/robopose>
- DREAM Panda real dataset và model zoo: các Google Drive ID nằm trong
  `download_panda_assets.sh` và README upstream.

Repository HoRoPose không kèm tệp LICENSE ở commit đã dùng; cần liên hệ tác giả
trước khi dùng thương mại. DREAM/Franka assets cũng phải được rà soát license
riêng khi chuyển từ nghiên cứu sang triển khai nhà máy.
