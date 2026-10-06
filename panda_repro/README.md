# Robot Pose + Health Monitoring Demo

> Bản mới nhất: xem `PANDA_HOROPOSE_DEMO.md` và
> `artifacts/panda_horopose_health_demo.mp4`. Bản này dùng checkpoint HoRoPose
> Panda thật để dự đoán `q1...q7`, rotation 6D và translation 3D theo từng ảnh.

Prototype cho bài toán DENSO: dùng camera RGB để ước lượng trạng thái robot, đo
chu kỳ hoạt động, kết hợp dữ liệu rung/nhiệt/âm thanh/dòng điện để suy luận vị
trí và nhóm lỗi, sau đó lưu sự kiện cùng nhãn xác nhận của kỹ thuật viên.

## Điều gì được triển khai

- Bộ mô phỏng robot công nghiệp 6 khớp, camera pinhole và renderer RGB nhẹ.
- Sinh ảnh, keypoint 2D, 6 góc khớp và 6D base pose có ground truth.
- Nhánh **RoboKeyGen-inspired**: CNN phát hiện keypoint 2D, MLP nâng keypoint
  thành góc khớp và base pose.
- Nhánh **RoboPose-inspired**: tối ưu lặp trạng thái robot để hình chiếu mô hình
  khớp với keypoint quan sát (`render-and-compare refinement`).
- Sinh chu kỳ bình thường và 4 lỗi: `bearing_fault`, `gearbox_backlash`,
  `motor_overload`, `encoder_error`.
- Sensor fusion từ rung, nhiệt, âm thanh, dòng điện và sai số vị trí.
- Lưu event bất thường vào SQLite; hỗ trợ kỹ thuật viên xác nhận nhãn thật.
- Notebook chạy trên Google Colab/Kaggle GPU.

## Video ABB thật – temporal pose + đa cảm biến

`make_real_robot_video_v2.py` sửa nhược điểm overlay đứng im của bản đầu:

- CoTracker3 theo dõi dài hạn 9 pixel hỗ trợ quanh mỗi mốc BASE/J1–J5/TCP;
- median consensus loại điểm trôi sang nền;
- visibility score phát hiện che khuất; PCHIP và Savitzky–Golay sửa khoảng mất
  dấu và đưa quỹ đạo từ 6,25 fps về đủ 25 fps;
- TCP trajectory cho visual motion và chu kỳ camera;
- dashboard đồng bộ rung (`mm/s RMS`), âm thanh (`dBA`), nhiệt độ (`°C`) và
  dòng motor (`A`);
- mô hình ExtraTrees sensor fusion dự đoán `gearbox_backlash` tại J3;
- cửa sổ bất thường, dự đoán và phản hồi kỹ thuật viên được lưu vào NPZ, CSV
  và SQLite.

Trong video, RGB và quỹ đạo 2D được tính từ footage ABB thật; tín hiệu cảm biến
và fault label là mô phỏng có chủ đích. Đây chưa phải RoboPose chạy trực tiếp
trên ABB: chưa có CAD/URDF ABB, camera calibration hoặc checkpoint ABB để suy
ra góc khớp vật lý `q1..q6`. Lệnh tái tạo và ranh giới kỹ thuật nằm trong
`REAL_ROBOT_DEMO.md`.

Đây là bản tái hiện gọn theo nguyên lý của hai công trình, không phải bản sao mô
hình nghiên cứu. RoboPose gốc dùng môi trường Python 3.7/PyTorch 1.3/CUDA 10.1
và ví dụ tái huấn luyện nhiều GPU. Repo RoboKeyGen tại thời điểm kiểm tra mới
công khai dataset/checkpoint, chưa công khai training/inference code.

## Chạy nhanh trên máy local

Yêu cầu Python 3.10+.

```bash
python -m pip install -r requirements.txt
export PYTHONPATH="$PWD/src"

python -m robot_demo.simulator --output artifacts/pose_dataset.npz --samples 1800
python -m robot_demo.train_pose --data artifacts/pose_dataset.npz --epochs 12
python -m robot_demo.train_fault --output artifacts/fault_model.joblib --samples 5000
python -m robot_demo.run_demo
```

Xem event và nhập xác nhận của kỹ thuật viên:

```bash
python -m robot_demo.feedback --list
python -m robot_demo.feedback --event-id 1 --label gearbox_backlash --joint 3 \
  --action "Inspected reducer and adjusted backlash"
```

Để kiểm tra nhanh trên CPU:

```bash
export PYTHONPATH="$PWD/src"
python -m robot_demo.simulator --output artifacts/pose_dataset.npz --samples 500
python -m robot_demo.train_pose --data artifacts/pose_dataset.npz --epochs 3 --batch-size 64
python -m robot_demo.train_fault --output artifacts/fault_model.joblib --samples 1500
python -m robot_demo.run_demo
```

Kết quả nằm trong `artifacts/`:

- `pose_model.pt`: checkpoint camera-pose/joint-angle model.
- `demo_pose_dataset.npz`: tập ảnh nhỏ để chạy ngay inference demo.
- `pose_metrics.json`: sai số keypoint, góc khớp, base pose và residual của
  bước refinement.
- `pose_example.png`: ảnh so sánh ground truth, dự đoán và refinement.
- `fault_model.joblib`: mô hình sensor fusion.
- `fault_metrics.json`: accuracy/confusion matrix.
- `events.db`: sự kiện bất thường và feedback kỹ thuật viên.
- `demo_summary.json`, `demo_result.png`: kết quả end-to-end.
- `abb_real_robot_demo.mp4`: video concept với footage ABB thật.
- `abb_real_robot_demo_v1.mp4`: bản optical-flow cũ để so sánh.
- `abb_cotracker_tracks.npz`: support tracks, visibility, landmark 2D và sensor.
- `abb_multimodal_timeseries.csv`: mỗi frame một dòng dữ liệu đồng bộ.
- `abb_real_robot_demo_summary.json`: cấu hình và kết quả chẩn đoán của video.

Accuracy trong `fault_metrics.json` chỉ là **synthetic sanity check**: nó xác
nhận pipeline học đúng các quy luật đã lập trình vào simulator, không phải bằng
chứng accuracy trên robot thật. Báo cáo thực tế phải dùng tập lỗi đã được kỹ
thuật viên xác nhận và tuyệt đối không trộn các chu kỳ cùng phiên giữa train/test.

## Chạy trên Colab hoặc Kaggle

Mở `colab_demo.ipynb`, upload thư mục dự án hoặc file ZIP, rồi chạy lần lượt các
cell. Notebook tự kiểm tra CUDA và chọn số lượng mẫu/epoch phù hợp.

## Luồng xử lý

1. Sinh ảnh RGB từ cấu trúc động học robot và camera đã hiệu chuẩn.
2. CNN dự đoán keypoint của các khớp.
3. Mạng lifting dự đoán góc khớp và base pose.
4. Differentiable kinematics chiếu mô hình robot trở lại ảnh và tối ưu trạng thái.
5. Pose theo thời gian tạo quỹ đạo và cycle time.
6. Khi cycle time/pose/sensor score bất thường, sensor-fusion model dự đoán
   `fault_type` và `faulty_joint`.
7. Event được lưu cùng cửa sổ dữ liệu; kỹ thuật viên bổ sung nhãn xác nhận.

## Chuyển sang ABB hoặc Nachi

Thay ba thành phần:

1. `LINK_OFFSETS`, `JOINT_AXES`, `JOINT_LIMITS` trong `geometry.py` bằng thông
   số từ URDF/CAD/manual.
2. Renderer mô phỏng bằng CAD thật của robot để ảnh giống thực tế.
3. Hiệu chỉnh mô hình trên một tập ảnh thật có nhãn nhỏ.

Không dùng dữ liệu mô phỏng đơn lẻ để khẳng định lỗi thật. Quy trình triển khai
đúng là: synthetic pretraining → real-normal calibration → technician-confirmed
fault labels → periodic retraining.

Lưu ý: refinement tối ưu độ khớp với keypoint quan sát, không được bảo đảm luôn
giảm sai số so với ground truth khi detector keypoint còn nhiễu. File metrics
báo cáo riêng residual theo quan sát và sai số theo ground truth để tránh đánh
đồng hai đại lượng.

## Thuật ngữ

- **Render-and-compare**: render robot từ trạng thái dự đoán rồi chỉnh trạng thái
  để hình chiếu khớp quan sát.
- **Keypoint lifting**: chuyển keypoint 2D thành cấu hình 3D/góc khớp.
- **Forward kinematics**: tính vị trí các link từ góc khớp.
- **Sim-to-real gap**: khác biệt giữa ảnh/tín hiệu mô phỏng và nhà máy thật.
- **Human-in-the-loop**: kỹ thuật viên xác nhận nhãn trước khi hệ thống học lại.
- **Point tracking**: bám cùng một điểm ảnh qua nhiều frame video.
- **Long-term tracking**: theo dõi xuyên suốt đoạn dài, kể cả khi vật đổi hướng.
- **Visibility / occlusion**: độ tin cậy điểm còn nhìn thấy / bị che khuất.
- **Sensor fusion**: kết hợp nhiều nguồn đo để suy luận một trạng thái chung.
- **Temporal pose**: quỹ đạo pose theo thời gian, không phải một ảnh độc lập.
