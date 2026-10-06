# Franka Panda: giám sát pose và phòng mô phỏng lỗi ngoại tuyến

Mở **http://127.0.0.1:8767/** sau khi chạy:

```powershell
cd D:\DENSO\pose_focus_demo
python -m uvicorn app:app --host 127.0.0.1 --port 8767
```

Dashboard phát lại **16,67 giây video robot Franka Panda** ở 30 fps. Thời gian trên video là đồng hồ chính: mọi readout, đồ thị, đường quỹ đạo, cảnh báo và xuất CSV cùng chọn bản ghi `frame = round(video.currentTime × 30)`. Bấm biểu đồ hoặc cảnh báo để tua video. Đây là demo ý tưởng, chưa có luồng camera hoặc cảm biến trực tiếp.

## Nguồn dữ liệu và giới hạn

| Dữ liệu | Nguồn | Cách diễn giải |
|---|---|---|
| Hình robot | Video ghi hình robot thật; clip gốc `D:\DENSO\panda_horopose_health_demo.mp4.crdownload` | Tệp `robot_original.mp4` được cắt vùng video, không có dữ liệu hỏng thật |
| Pose cyan | 7 mốc 2D trích từ **nét đã chú giải trên video** trong `pose_recording.json` | Mốc khuất để `null`; chưa chạy lại HoRoPose trên hình thô. `L0`…`EE` là mốc ảnh, không phải góc của bảy khớp |
| Tốc độ, thời gian đứng yên, độ phủ, khoảng cách đoạn mẫu | Tính từ pose 2D ở trên | Đơn vị pixel và giây; không suy ra vị trí 3D hoặc encoder |
| Rung, nhiệt, âm, độ trễ, trạng thái lỗi | **100% mô phỏng** | Sinh ở mỗi timestamp ảnh; đơn vị mm/s, °C, dB chỉ có ý nghĩa trong mô hình minh họa |
| Quỹ đạo đối chứng | **100% mô phỏng** | Hình chiếu 2D “nếu lỗi xảy ra”, không phải phép đo robot; pose quan sát không bị sửa |

Không có video thô chưa chú giải, hiệu chuẩn camera, checkpoint pose, log controller, cảm biến thật hoặc nhãn hỏng thật. Không được dùng độ chính xác trên dữ liệu do chính mô hình sinh để công bố hiệu quả bảo trì tại nhà máy.

## Cơ chế sinh lỗi

`engine_v2.py` giữ nguyên 500 khung pose quan sát. Mỗi mốc có đường nền phụ thuộc hoạt động 2D, tải giả định, offset môi trường và seed. Một kịch bản gồm loại lỗi, mốc, thời điểm bắt đầu, thời lượng và cường độ. Trạng thái lỗi tăng và giảm qua sườn 0,45 s. Seed quyết định biến thiên điều kiện vận hành và giúp tái lập ca thử. Có tối đa tám kịch bản trong một lần chạy.

| Lỗi giả lập | Trạng thái nguyên nhân → ảnh hưởng được sinh |
|---|---|
| Ổ bi/truyền động | Mức suy giảm × chuyển động → rung và âm đồng tăng; nhiệt tăng chậm |
| Ma sát/bôi trơn | Ma sát × chuyển động → rung, âm, trễ nhẹ; nhiệt có quán tính |
| Tản nhiệt | Giảm làm mát → nhiệt tích lũy rồi nguội dần |
| Độ rơ/sai tư thế | Độ rơ → xoay 2D quỹ đạo giả lập quanh mốc trước, mạnh hơn gần tín hiệu đảo hướng |
| Đáp ứng chậm | Độ trễ → lấy quỹ đạo giả lập từ thời điểm trước |
| Trôi cảm biến | Offset chỉ vào kênh rung; pose và các kênh khác giữ nguyên |

Tắt kịch bản đưa **tham số tác động** về 0, không hàm ý hỏng cơ khí có thể tự lành. Nhiệt còn dư giảm dần. Quỹ đạo giả lập là phép biến đổi 2D minh họa, **chưa phải digital twin động học/động lực học Franka**. Kịch bản không kết nối hay gửi lệnh đến robot. Nút “Tải 20 ca mô phỏng” xuất ZIP gồm ca bình thường và lỗi, nhiều seed/tải/cường độ, CSV và `manifest.json` ghi nhãn nguồn và cấu hình.

## Cơ chế phát hiện và vòng xác nhận

Bộ phát hiện chỉ đọc các **tín hiệu đã sinh**, không đọc danh sách lỗi tiêm làm đáp án. Nó trừ đường nền giả lập và tính phần dư theo thang tham chiếu: rung 0,25 mm/s, nhiệt 1,6 °C, âm 2 dB. Các quy tắc kết hợp rung + âm, nhiệt + âm + trễ, nhiệt riêng, chênh pose + dấu đảo hướng, trễ lớn hoặc trôi rung đơn kênh. Một trạng thái phải kéo dài ít nhất 3 frame; khoảng mất tín hiệu ngắn tối đa 12 frame được nối. Ngưỡng nằm trong `classify()` và chỉ để thử luồng cảnh báo. Nếu robot dừng giữa một kịch bản, tín hiệu gắn chuyển động có thể mất rồi tái xuất hiện ở lần chạy kế tiếp.

Mỗi cảnh báo dẫn đến frame đỉnh, mốc theo dõi, bằng chứng và danh sách kiểm tra. Kỹ thuật viên xác nhận dự đoán đúng/sai, ghi tên, việc đã làm; nếu sai phải nhập nguyên nhân thực tế. Bản ghi lưu SQLite theo `run_id` và `incident_id` tại `%LOCALAPPDATA%\DENSO\pose_demo.sqlite3` trên Windows (có thể đổi bằng `DENSO_DEMO_DB`). Với hệ thống thật, cần thêm work order, ghi nhận trước/sau sửa, kiểm tra chất lượng nhãn rồi mới dùng làm dữ liệu huấn luyện.

## Kiểm tra và API

```powershell
python -m unittest test_engine_v2.py
```

`POST /api/run` nhận `{ "injections": [...], "seed": 41, "load": 1.0 }`. `GET /api/run/{id}` trả toàn bộ timeline và cảnh báo. `GET /api/run/{id}/export.csv` có cột quan sát và mô phỏng tách riêng. `GET /api/ensemble.zip?count=20&seed=41` tạo tối đa 40 ca ngoại tuyến. Giao diện chính gồm `index_v3.html`, `styles_v4.css`, `app_v2.js`; `engine.py` giữ các đặc trưng pose gốc và `engine_v2.py` sinh giả lập.

Thiết kế dashboard nhóm biểu đồ thành ba phần: pose quan sát, cảm biến giả lập, tác động và phát hiện. Giao diện dùng xanh lá đậm, đen, trắng và font Times New Roman theo phong cách trang trọng. Mọi đồ thị có giá trị tại frame đang xem, chú giải nguồn và cùng vạch thời gian; đồ thị điểm bất thường tô vùng các cảnh báo của mốc được chọn. Thanh tua có thể điều khiển bằng bàn phím. Kích thước biểu đồ được cố định để không phóng to khi phát video; giao diện đã được kiểm tra ở chiều rộng 375 px và desktop.

## Hướng đưa vào nhà máy

1. Thu nhiều chu kỳ bình thường của **từng recipe, tải, tốc độ và điều kiện môi trường**. Gắn timestamp tại thiết bị cho camera, controller, cảm biến; đo lệch đồng hồ. Ghi chất lượng pose và trường hợp mốc che khuất.
2. Dùng dữ liệu bình thường để học đường nền theo ngữ cảnh. Tách cảnh báo hỏng cơ khí khỏi lỗi cảm biến, camera và thay đổi chương trình. Đặt chế độ chỉ quan sát, đo tỷ lệ báo sai trên nhiều ca chạy trước khi dùng cho bảo trì.
3. Khi có model robot, URDF, controller, camera calibration và cảm biến đo thật, chuyển sang mô phỏng ngoại tuyến có tham số được hiệu chuẩn. Thử độ nhạy với tải, ma sát, backlash, nhiễu và sai thời gian. Kiểm chứng với log bảo trì thật hoặc bệ phụ, không cố ý phá robot sản xuất.
4. Kết nối work order và phản hồi kỹ thuật viên; đánh giá riêng trên robot/ca chạy/thời gian chưa dùng để chỉnh mô hình. Dữ liệu mô phỏng dùng để thử bao phủ và robustness, không thay thế kiểm định thực địa.

Hướng này phù hợp với [FANUC ZDT](https://www.fanucamerica.com/products/software/robot/zero-down-time-zdt), [KUKA iiQoT](https://www.kuka.com/en-gb/products/robotics-systems/software/cloud-software/iiqot-robot-condition-monitoring) và [ABB Connected Services](https://www.abb.com/global/en/areas/robotics/services/data-driven-services/connected-services) ở việc theo dõi trạng thái vận hành. [ABB RobotStudio](https://new.abb.com/products/robotics/nl/software-and-digital/robotstudio) và [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim/) là hướng mô phỏng ngoại tuyến chuyên sâu hơn. [MathWorks](https://www.mathworks.com/help/predmaint/ug/data-ensembles-for-condition-monitoring-and-predictive-maintenance.html) mô tả bộ dữ liệu nhiều ca mô phỏng; [Siemens Senseye](https://developer.siemens.com/senseye/workorders/structure.html) minh họa cấu trúc work order. Các nguồn này gợi ý kiến trúc, không chứng nhận mô hình v2 có độ chính xác thực địa.
