# Model card

## Intended use

Proof-of-concept cho giám sát chu kỳ robot công nghiệp bằng một camera RGB cố
định. Mô hình phát hiện bảy keypoint, suy ra sáu góc khớp và sai lệch base pose,
sau đó dùng mô hình động học để refinement. Một classifier độc lập hợp nhất các
đặc trưng rung, nhiệt, âm thanh, dòng điện và position error để tạo nhãn lỗi mô
phỏng.

## Quan hệ với nghiên cứu gốc

- [RoboPose](https://www.di.ens.fr/willow/research/robopose/): prototype dùng ý
  tưởng cập nhật lặp trạng thái sao cho hình chiếu mô hình khớp quan sát. Bản
  này tối ưu keypoint reprojection bằng differentiable forward kinematics; nó
  không sao chép neural refiner và renderer CAD của RoboPose.
- [RoboKeyGen](https://nimolty.github.io/Robokeygen/): prototype dùng pipeline
  2D keypoints → state lifting → kinematic fitting. Bản này dùng MLP point
  estimate; chưa dùng diffusion distribution vì code training/inference chính
  thức chưa được công khai trong repo kiểm tra.

## Kết quả lần chạy tham chiếu

Thiết lập: 3.000 ảnh tổng hợp, 2.460 train, 540 test, 20 epoch, CPU.

| Metric | Kết quả |
| --- | ---: |
| Keypoint RMSE | 1,79 pixel |
| Mean joint-angle error | 2,59° |
| Base translation MAE | 9,55 mm |
| Base rotation MAE | 1,40° |

Các số trên chỉ đo trên renderer tổng hợp và họ quỹ đạo pick-and-place đã định
nghĩa. Chúng không phải kết quả trên ABB/Nachi thật.

Classifier lỗi đạt 100% trên tập synthetic split vì simulator tạo các lớp theo
quy luật tách biệt có chủ ý. Đây chỉ là sanity check. Trước khi công bố accuracy,
cần thêm nhiễu miền, chia train/test theo phiên vận hành, và đánh giá trên lỗi
được kỹ thuật viên xác nhận.

## Hạn chế

- Một ảnh RGB có mơ hồ độ sâu; kết quả phụ thuộc camera cố định và motion prior.
- Render-and-compare có thể giảm residual theo keypoint quan sát nhưng tăng sai
  số ground truth nếu detector keypoint bị lệch.
- Sensor simulator chỉ tạo tín hiệu proxy, không mô phỏng chính xác phổ rung,
  truyền nhiệt hoặc âm học của gearbox thật.
- Không sử dụng để ra quyết định dừng máy hoặc đảm bảo an toàn.
- Không dùng nhãn kỹ thuật viên chưa xác nhận để tự động retrain.

## Điều kiện chuyển sang robot thật

1. CAD/URDF và giới hạn khớp đúng model ABB/Nachi.
2. Camera calibration và khoảng 300–1.000 ảnh thật có keypoint/pose reference.
3. Timestamp đồng bộ giữa camera và cảm biến.
4. Dữ liệu normal ở nhiều tải/tốc độ.
5. Tập holdout gồm event bảo trì đã xác nhận.

