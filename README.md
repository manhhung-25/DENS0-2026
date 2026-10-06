# DENSO — demo giám sát pose và tình trạng robot Franka Panda

Đây là mã nguồn của demo ý tưởng. Video robot thật dài 16,67 giây và **pose 2D trên hình** là dữ liệu quan sát. Rung, nhiệt độ, âm thanh, độ trễ, quỹ đạo đối chứng và các sự cố đều là **dữ liệu mô phỏng**. Demo không kết nối hoặc điều khiển robot nhà máy.

## Cấu trúc

```text
<thu-muc-du-an>/
├── README.md                  # Hướng dẫn này
├── requirements.txt           # Thư viện Python của demo
├── pose_focus_demo/           # Dashboard, API, mô hình sinh/phát hiện lỗi, video, pose
└── horopose_upstream/         # Mã nghiên cứu gốc, submodule tùy chọn
```

`horopose_upstream` trỏ đến mã nghiên cứu của tác giả HoRoPose dưới dạng Git submodule; nó không cần thiết để chạy dashboard. Video và pose đã xử lý được đóng gói trong `pose_focus_demo`.

## Môi trường chạy

| Thành phần | Demo dashboard | Nghiên cứu HoRoPose (tùy chọn) |
|---|---|---|
| Hệ điều hành | Windows với PowerShell; backend FastAPI cũng có thể chạy trên Linux/macOS | Bản gốc được tác giả thử trên Ubuntu 20.04 |
| Python | 3.12, dùng môi trường ảo riêng | 3.9, dùng môi trường riêng theo README của HoRoPose |
| GPU | Không cần cho việc phát lại video và sinh dữ liệu mô phỏng | Công trình gốc dùng PyTorch 1.13, PyTorch3D 0.7.4 và CUDA 11.7 |
| Trình duyệt | Chrome, Edge hoặc trình duyệt hiện đại có hỗ trợ video MP4 H.264 và JavaScript | Không áp dụng cho dashboard |
| Lưu phản hồi | SQLite trong `%LOCALAPPDATA%\DENSO\pose_demo.sqlite3` trên Windows | Checkpoint/dataset ở thư mục riêng của HoRoPose |

`requirements.txt` ở thư mục gốc **chỉ dành cho dashboard**. Đừng cài `horopose_upstream/requirements.txt` vào cùng môi trường Python 3.12: đó là bộ thư viện nghiên cứu khác phiên bản. Không cần Docker, GPU, thiết bị robot hoặc tài khoản đám mây để xem demo.

## Dataset và tài nguyên

Demo đã có đủ dữ liệu để chạy ngay sau khi lấy mã nguồn:

| Tệp | Nội dung | Có cần tải thêm? |
|---|---|---|
| `pose_focus_demo/robot_original.mp4` | Clip Franka Panda thật đã cắt vùng hình, dài 16,67 giây, 30 fps | Không |
| `pose_focus_demo/pose_recording.json` | 500 frame và tối đa 7 mốc pose 2D/frame trích từ **nét cyan đã chú giải sẵn trên clip** | Không |
| `pose_focus_demo/poster.jpg` | Ảnh xem trước video | Không |
| CSV hoặc ZIP tải từ web | Ca cảm biến và lỗi **được tạo giả lập khi yêu cầu** | Không; dùng các nút **Xuất CSV** và **Tải 20 ca mô phỏng** |

Đây không phải dataset cảm biến/nhãn hỏng thật. Mốc `L0`…`EE` là tọa độ trong ảnh, không phải góc bảy khớp từ controller. Các giá trị rung, nhiệt, âm, độ trễ và cảnh báo là dữ liệu giả lập cùng trục thời gian với video. Không dùng bộ dữ liệu này để tuyên bố độ chính xác bảo trì tại nhà máy.

### Nếu cần tạo lại dữ liệu pose từ clip nguồn

`pose_focus_demo/prepare_pose.py` là công cụ **tùy chọn**, không cần để chạy web. Nó phân đoạn màu trên các mốc cyan *đã có sẵn* trong video; nó không chạy mô hình HoRoPose trên ảnh thô. Công cụ cần `numpy` và `opencv-python` (đã có trong `requirements.txt`), thêm [FFmpeg](https://ffmpeg.org/download.html) trong `PATH` để cắt video và tạo poster. Clip nguồn phải đúng định dạng/bố cục mà script chờ đợi: 500 frame, 30 fps, có nét cyan. Ví dụ, khi bạn có clip nguồn tại chỗ:

```powershell
$env:DENSO_SOURCE_VIDEO = 'C:\duong-dan\video-nguon.mp4'
Set-Location .\pose_focus_demo
..\.venv\Scripts\python.exe prepare_pose.py
```

Kết quả sẽ ghi lại `pose_recording.json`, `robot_original.mp4` và `poster.jpg` trong `pose_focus_demo`. Hãy giữ bản sao ba tệp hiện có trước khi chạy lại. Clip gốc trong workspace trước đây mang đuôi `.crdownload`; bản clone từ GitHub **không cần** clip này vì video đã xử lý và JSON đã đi kèm.

### Nếu muốn thử HoRoPose thật (tùy chọn)

Mã nghiên cứu gốc: [Oliverbansk/Holistic-Robot-Pose-Estimation](https://github.com/Oliverbansk/Holistic-Robot-Pose-Estimation). Nếu clone kho dự án mà chưa lấy submodule, chạy `git submodule update --init --recursive`. Đọc [README của tác giả](https://github.com/Oliverbansk/Holistic-Robot-Pose-Estimation#installation) để tạo môi trường Ubuntu/Python 3.9 riêng. Tác giả chỉ dẫn tải [DREAM datasets](https://drive.google.com/drive/folders/1uNK2n9wU4tRE07sM_r640wDhwmOwuxx6) vào `horopose_upstream/data/dream/`, [URDF](https://drive.google.com/drive/folders/17KNhy28pypheYfDCxgOjJf4IyUnOI3gW?) vào `horopose_upstream/data/deps/`, [HRNet backbone](https://drive.google.com/file/d/1eqIftq1T_oIGhmCfkVYSM245Wj5xZaUo/view?) vào `horopose_upstream/models/` và [segmentation weights](https://drive.google.com/drive/folders/1PpXe3p5dJt9EOM-fwvJ9TNStTWTQFDNK?) vào `horopose_upstream/models/panda_segmentation/`.

Các dataset/checkpoint/URDF này **không nằm trong gói demo** và không cần để mở dashboard. Kết quả HoRoPose cũng chưa được nối vào `pose_recording.json`; muốn thay pose trích từ nét cyan bằng dự đoán từ video thô phải có clip chưa chú giải, checkpoint, hiệu chuẩn camera và bước ánh xạ mốc được kiểm thử riêng.

## Chạy trên Windows

Yêu cầu Python 3.12. Tại PowerShell, đứng ở thư mục chứa README này:

Nếu chưa có mã nguồn, lấy từ GitHub bằng `git clone https://github.com/manhhung-25/DENS0-2026.git`, rồi `Set-Location .\DENS0-2026`. Dashboard chạy được khi chưa tải submodule.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location .\pose_focus_demo
..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8767
```

Mở <http://127.0.0.1:8767/>. Nếu không dùng môi trường ảo, chạy `python -m pip install -r requirements.txt`, vào `pose_focus_demo` và chạy `python -m uvicorn app:app --host 127.0.0.1 --port 8767`.

Nếu lệnh `python` không trỏ đến Python 3.12, thay bằng `py -3.12` khi tạo `.venv`. Sau khi tạo xong, tiếp tục dùng `..\.venv\Scripts\python.exe` như trên. Muốn đổi nơi lưu SQLite, đặt `DENSO_DEMO_DB` thành đường dẫn tệp trước khi khởi động máy chủ.

## Sử dụng web nhanh

1. Ở **Tổng quan**, bấm **▶** để phát video Franka Panda; kéo thanh thời gian hoặc chọn tốc độ `0.5×`–`2×`. Đồng hồ video điều khiển các giá trị và biểu đồ cùng lúc.
2. Chọn một mốc ở **Cấu trúc cánh tay** (`L0`…`EE`) để xem pose, quỹ đạo và tín hiệu của vùng tay đó. Chữ **KHUẤT** nghĩa là mốc không quan sát được tại khung hình đang xem.
3. Ở **Biểu đồ**, bấm một vị trí bất kỳ trên đồ thị để tua video đến thời điểm đó. Phân biệt phần **TỪ VIDEO** với các phần **Cảm biến giả lập** và **WHAT-IF**.
4. Ở **Mô phỏng**, chọn nguyên nhân, mốc, thời điểm bắt đầu, thời lượng, cường độ, seed và tải; bấm **+ Thêm kịch bản**. Có thể **Xóa lỗi** để xem ca nền hoặc **Về kịch bản mẫu** để khôi phục hai lỗi minh họa.
5. Ở **Bảo trì**, chọn cảnh báo để nhảy đến thời điểm đỉnh và xem bằng chứng. Chọn dự đoán đúng/sai, nhập tên kỹ thuật viên và việc đã làm; nếu dự đoán sai, nhập cả nguyên nhân thực tế, rồi bấm **Lưu xác nhận**.
6. Bấm **Xuất CSV** để tải dữ liệu của ca đang xem, hoặc **Tải 20 ca mô phỏng** để lấy bộ ZIP phục vụ thử nghiệm ngoại tuyến.

Đọc [hướng dẫn sử dụng web chi tiết](HUONG_DAN_SU_DUNG_WEB.md) để biết ý nghĩa từng biểu đồ, quy trình trình diễn và cách xử lý lỗi thường gặp. Giao diện đang **phát lại clip ghi sẵn**, chưa giám sát robot theo thời gian thực.

## Mã nguồn chính

| Tệp | Chức năng |
|---|---|
| `pose_focus_demo/app.py` | API FastAPI, phục vụ giao diện/video, xuất dữ liệu và lưu phản hồi kỹ thuật viên vào SQLite |
| `pose_focus_demo/engine.py` | Đọc chuỗi pose quan sát và đặc trưng ảnh |
| `pose_focus_demo/engine_v2.py` | Sinh tín hiệu giả lập, tiêm lỗi ngoại tuyến, phát hiện và tạo cảnh báo |
| `pose_focus_demo/index_v3.html`, `styles_v4.css`, `app_v2.js` | Dashboard hiện hành; mọi biểu đồ và cảnh báo bám thời gian video |
| `pose_focus_demo/pose_recording.json`, `robot_original.mp4`, `poster.jpg` | Pose 2D, video robot thật và ảnh poster đi kèm |
| `pose_focus_demo/prepare_pose.py` | Tiện ích tạo lại pose/video từ clip nguồn; cần FFmpeg trong PATH và clip nguồn phù hợp |
| `pose_focus_demo/test_engine_v2.py` | Kiểm tra luồng sinh dữ liệu và phát hiện |

Các tệp `index.html`, `index_v2.html`, `styles.css`, `styles_v2.css`, `styles_v3.css`, `app.js` là các phiên bản giao diện cũ được giữ lại để tham khảo. SQLite `pose_demo.sqlite3` được tạo tự động trong `%LOCALAPPDATA%\DENSO` trên Windows, nên ứng dụng vẫn chạy khi thư mục mã nguồn chỉ có quyền đọc. Có thể chọn nơi lưu bằng biến môi trường `DENSO_DEMO_DB`. Tệp cơ sở dữ liệu không có trong gói mã nguồn.

## Kiểm tra

```powershell
Set-Location .\pose_focus_demo
..\.venv\Scripts\python.exe -m unittest test_engine_v2.py
```

Xem [tài liệu kỹ thuật](pose_focus_demo/README.md) để hiểu nguồn dữ liệu, cơ chế sinh lỗi, phát hiện lỗi, đồng bộ thời gian, giới hạn và hướng tích hợp vào nhà máy. Các ngưỡng hiện tại chỉ để trình diễn, chưa phải ngưỡng vận hành hay kết quả kiểm định trên robot thật.
