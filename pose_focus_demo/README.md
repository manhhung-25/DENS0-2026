# Dashboard kỹ thuật · HoRoPose Panda

## Dữ liệu và đồng hồ chung

`robot_original.mp4` là vùng robot cắt từ `panda_repro/artifacts/panda_horopose_health_demo.mp4`, dài 16,67 giây ở 30 fps. `import_horopose.py` kiểm tra SHA-256 của checkpoint, video, NPZ và CSV trước khi nhập. Mỗi bản ghi trong `pose_recording.json` có `frame`, `t`, `source_frame`, `cycle`, 7 keypoint 2D, q1–q7 dự đoán, q đối chiếu từ DREAM, sai số keypoint và bốn kênh cảm biến **mô phỏng đã vẽ trong video**. Tọa độ keypoint được biến đổi đúng tỷ lệ và vị trí cắt video.

120 ảnh RGB nguồn tạo 500 frame phát lại bằng chuỗi xuôi/ngược và đoạn giữ hình 24 frame. `app_v2.js` lấy `frame = round(video.currentTime × 30)` để đọc mọi biểu đồ và readout. Bấm biểu đồ hoặc cảnh báo đưa video về cùng frame. Đây là đồng bộ phát lại một timeline, **không phải đồng bộ thiết bị thời gian thực**.

Các mốc `L0`, `L2`, `L3`, `L4`, `L6`, `L7`, `EE` là vị trí keypoint trên robot; q1–q7 là góc khớp AI dự đoán, không phải dữ liệu encoder. HoRoPose dùng bounding box từ nhãn DREAM để tạo crop đầu vào và 30 góc nhãn đầu để hiệu chỉnh offset. Các con số đánh giá chỉ áp dụng cho đoạn DREAM này.

| Nguồn | Có trong hệ thống? | Cách hiển thị |
|---|---|---|
| RGB Panda, nhãn DREAM, checkpoint, dự đoán pose/q | Có, trong `panda_repro/` | Video, khớp, góc q, sai số so với nhãn |
| Rung/âm/nhiệt/dòng điện **trong video nguồn** | Có, nhưng toàn bộ mô phỏng | Bốn biểu đồ gắn đúng CSV từng frame |
| Cảm biến/quỹ đạo/cảnh báo **what-if** do web sinh | Có, toàn bộ mô phỏng | Nhóm biểu đồ và phòng mô phỏng riêng |
| Camera/controller/cảm biến vật lý/nhãn hỏng nhà máy | Chưa có | Chưa hiển thị như dữ liệu thật |

## Sinh lỗi what-if

`engine_v2.py` giữ nguyên pose AI và video, rồi tạo một bản số giả định theo `seed`, tải và 0–8 kịch bản. `start_s`, `duration_s`, `intensity` điều khiển đường tác động tăng/giảm trong thời gian video. Bộ sinh dùng tốc độ ảnh làm **proxy** hoạt động; nó không biết mô men hoặc tốc độ encoder.

- **Ổ bi/truyền động:** tăng rung và âm theo proxy chuyển động, có nhấn mạnh theo pha; thêm nhiệt chậm.
- **Ma sát/bôi trơn:** tăng âm/rung khi hoạt động, tích nhiệt có quán tính và trễ nhẹ.
- **Suy giảm tản nhiệt:** thay hệ số làm mát, khiến nhiệt tích lũy rồi nguội dần.
- **Độ rơ/sai tư thế:** xoay quỹ đạo what-if của các mốc phía sau quanh mốc trước; tác động mạnh hơn gần đảo hướng.
- **Đáp ứng chậm:** lấy quỹ đạo what-if tại thời điểm trước đó và tăng chỉ số trễ.
- **Trôi cảm biến:** chỉ đổi kênh rung, giữ nguyên pose và các kênh khác.

Khi tắt kịch bản, tác động số về 0; điều này không mô tả cơ khí tự hồi phục. Nhiệt dư tiếp tục suy giảm theo phương trình bậc một. Các kênh cảm biến mô phỏng trong **video đã render** giữ nguyên; người dùng chỉnh kịch bản chỉ tác động tới nhánh what-if trên web. Chúng được tách thành hai nhóm biểu đồ để tránh coi như một phép đo.

## Phát hiện và xác nhận

Bộ phát hiện đọc tín hiệu **sau khi đã sinh**, không lấy danh sách lỗi tiêm làm đáp án. Nó so rung, nhiệt, âm với nền cùng seed/tải; tính phần dư theo thang 0,25 mm/s, 1,6°C và 2 dB; kết hợp dấu pose và trễ; yêu cầu ít nhất 3 frame liên tiếp và nối khoảng hụt tối đa 12 frame. `classify()` trong `engine_v2.py` chứa các ngưỡng minh họa. Score 0–100 chỉ là thứ tự cảnh báo của demo, không phải xác suất hỏng được hiệu chuẩn.

Trong mục **Bảo trì**, người dùng chọn cảnh báo, xem frame đỉnh, giả thuyết và bước kiểm tra rồi nhập kỹ thuật viên, việc đã làm, kết luận đúng/sai và nguyên nhân thật nếu dự đoán sai. API lưu phản hồi theo `run_id` và `incident_id` trong SQLite. Không tự dùng phản hồi chưa thẩm định để huấn luyện lại.

## Tái lập và giới hạn

Xem [README gốc](../README.md) để cài đặt, chạy checkpoint, dựng video và kiểm tra hash. `test_engine_v2.py` kiểm tra tính bất biến của pose và sáu lỗi; `test_horopose_integration.py` kiểm tra ánh xạ NPZ/CSV/JSON cùng timestamp. Các mô hình lỗi và ngưỡng hiện tại chỉ kiểm tra luồng phần mềm. Để áp dụng ở nhà máy, cần camera đã hiệu chuẩn, đồng hồ chung với controller/cảm biến, recipe và tải đúng, baseline vận hành thật cùng dữ liệu bảo trì được kỹ thuật viên xác nhận.
