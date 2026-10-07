# Hướng dẫn sử dụng hệ thống web từ A–Z

## Franka Pose Observatory — Giám sát pose, mô phỏng bất thường và đánh giá AI

**Áp dụng cho phiên bản dashboard v3 có lịch sử SQLite.** Tài liệu dành cho người mới sử dụng, người trình diễn, kỹ thuật viên thử nghiệm và người chạy thí nghiệm nghiên cứu.

> Hệ thống hiện tại là demo phân tích và phát lại ngoại tuyến. Ảnh robot lấy từ DREAM; pose và góc khớp là dự đoán HoRoPose đã lưu. Các cảm biến, tình huống lỗi và cảnh báo là mô phỏng. Web chưa thu nhận camera/cảm biến trực tiếp, chưa điều khiển Franka và chưa được kiểm chứng bằng dữ liệu lỗi tại nhà máy.

## Mục lục

1. [Hệ thống làm gì và nguồn dữ liệu là gì?](#1-hệ-thống-làm-gì-và-nguồn-dữ-liệu-là-gì)
2. [Chuẩn bị môi trường và khởi động](#2-chuẩn-bị-môi-trường-và-khởi-động)
3. [Bản đồ giao diện và mối liên hệ giữa các phần](#3-bản-đồ-giao-diện-và-mối-liên-hệ-giữa-các-phần)
4. [Hiểu thời gian, mốc pose và khớp robot](#4-hiểu-thời-gian-mốc-pose-và-khớp-robot)
5. [Camera, pose và trạng thái tức thời](#5-camera-pose-và-trạng-thái-tức-thời)
6. [Cách đọc biểu đồ nói chung](#6-cách-đọc-biểu-đồ-nói-chung)
7. [Giải thích từng biểu đồ trên dashboard](#7-giải-thích-từng-biểu-đồ-trên-dashboard)
8. [Phòng mô phỏng: các tham số và thao tác](#8-phòng-mô-phỏng-các-tham-số-và-thao-tác)
9. [Cơ chế sinh dữ liệu bất thường](#9-cơ-chế-sinh-dữ-liệu-bất-thường)
10. [Cơ chế phát hiện và cách hiểu cảnh báo](#10-cơ-chế-phát-hiện-và-cách-hiểu-cảnh-báo)
11. [Xem bằng chứng và xác nhận bảo trì](#11-xem-bằng-chứng-và-xác-nhận-bảo-trì)
12. [Log lịch sử pose và cảm biến](#12-log-lịch-sử-pose-và-cảm-biến)
13. [Đánh giá AI và so sánh trước–sau tăng cường](#13-đánh-giá-ai-và-so-sánh-trướcsau-tăng-cường)
14. [Xuất dữ liệu và đọc các tệp](#14-xuất-dữ-liệu-và-đọc-các-tệp)
15. [Bài thực hành vận hành từ đầu đến cuối](#15-bài-thực-hành-vận-hành-từ-đầu-đến-cuối)
16. [Quản lý ca chạy, sao lưu và tắt hệ thống](#16-quản-lý-ca-chạy-sao-lưu-và-tắt-hệ-thống)
17. [Xử lý sự cố và câu hỏi thường gặp](#17-xử-lý-sự-cố-và-câu-hỏi-thường-gặp)
18. [Thuật ngữ và tài liệu liên quan](#18-thuật-ngữ-và-tài-liệu-liên-quan)

## 1. Hệ thống làm gì và nguồn dữ liệu là gì?

Hệ thống cho phép quan sát cánh tay Franka Panda, tạo tình huống giả định, xem tín hiệu đa nguồn, phát hiện bất thường, giữ bằng chứng và ghi kết luận kỹ thuật viên. Phần nghiên cứu riêng cho phép so sánh mô hình học với ít dữ liệu lỗi trước và sau khi tăng cường dữ liệu.

### 1.1. Bốn lớp dữ liệu cần phân biệt

| Lớp dữ liệu | Nguồn | Có thay đổi khi thêm lỗi trên web? | Dùng để làm gì? |
|---|---|---|---|
| Ảnh RGB robot | 120 ảnh DREAM được dựng thành clip 500 frame | Không | Hiển thị robot và đối chiếu dự đoán |
| Pose, keypoint, góc q1–q7 | Kết quả HoRoPose đã suy luận, đóng gói trong dự án | Không | Quan sát tọa độ, góc và chuyển động trong bản phát lại |
| Cảm biến in sẵn trong video nguồn | CSV mô phỏng của gói tái lập, gồm rung/âm/nhiệt/dòng J4 | Không | Đối chiếu đúng những con số đã dựng vào video |
| Cảm biến và pose what-if trên web | Bộ sinh tình huống theo seed, tải, môi trường và lỗi người dùng chọn | Có | Thử cơ chế sinh lỗi, phát hiện, log và phản hồi |

**What-if** nghĩa là “nếu lỗi này xảy ra thì tín hiệu có thể thay đổi thế nào”. Pose what-if là bản giả định riêng; nó không sửa pose HoRoPose gốc.

### 1.2. Những việc có thể thực hiện

- Phát, dừng, tua và xem dữ liệu tại từng frame.
- Chọn vùng landmark để theo dõi cảm biến/quỹ đạo.
- Chọn khớp J1–J7 độc lập để xem góc và các đạo hàm.
- Thêm, bỏ và kết hợp tối đa 8 kịch bản lỗi trong một ca.
- Xem cảnh báo, biểu đồ bằng chứng và giả thuyết kiểm tra.
- Lưu đúng/sai, nguyên nhân thực tế, người xác nhận và việc đã làm.
- Mở lại log bất thường cũ, xem pose/cảm biến và xuất JSON/CSV.
- Chạy benchmark A/B/C, xem confusion matrix và các ca kiểm thử.

**Chưa có:** thu nhận trực tiếp tại nhà máy, gửi lệnh tới robot, thông báo SMS/email, dự báo tuổi thọ còn lại (RUL), GAN/Diffusion, tự huấn luyện lại từ kết luận kỹ thuật viên. Bấm “Phát” là phát bản ghi; không khởi động robot.

## 2. Chuẩn bị môi trường và khởi động

### 2.1. Xác định đúng thư mục

Các lệnh bên dưới chạy tại **thư mục gốc dự án**, nơi có:

~~~text
README.md
requirements.txt
HUONG_DAN_SU_DUNG_WEB.md
RESEARCH_GUIDE.md
pose_focus_demo/
research_pipeline/
panda_repro/
~~~

Trên máy đã dùng để kiểm tra, bản tích hợp đang chạy nằm tại:

~~~text
C:\Users\ManhHung\DENSO_robot_health_demo\github_DENS0_2026
~~~

Thay đường dẫn bằng nơi bạn đặt bản tích hợp nếu dùng máy khác. Không chạy lệnh ở thư mục con panda_repro hoặc pose_focus_demo khi dùng cú pháp --app-dir bên dưới.

### 2.2. Cài đặt lần đầu trên Windows

Chuẩn bị Python 3.12 và trình duyệt phát được video H.264. Dashboard và pipeline nghiên cứu chạy bằng CPU; không cần GPU hoặc cài PyTorch để xem các dự đoán đã đóng gói.

Nếu lấy dự án từ GitHub, dùng Git và Git LFS để tải đúng các tệp lớn:

~~~powershell
git clone https://github.com/manhhung-25/DENS0-2026.git
Set-Location DENS0-2026
git lfs install
git lfs pull
~~~

Nếu đã có thư mục dự án đầy đủ, bỏ qua bước clone. Tạo môi trường tại thư mục gốc:

~~~powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
~~~

Kiểm tra có pose_focus_demo/robot_original.mp4 và pose_focus_demo/pose_recording.json. Nếu tệp video chỉ chứa vài dòng văn bản bắt đầu bằng “version https://git-lfs...”, đó là con trỏ LFS; cần git lfs pull.

Để nhập lại dữ liệu từ tài nguyên đã đóng gói, xem README và chạy:

~~~powershell
.\.venv\Scripts\python.exe pose_focus_demo\import_horopose.py
~~~

Không cần chạy lệnh nhập lại mỗi lần mở web nếu video và pose_recording.json đã có. Hướng dẫn tái suy luận từ ảnh và checkpoint nằm trong [README](README.md); đó là quy trình khác, dùng môi trường riêng của panda_repro.

### 2.3. Mở web mỗi lần sử dụng

Tại thư mục gốc dự án:

~~~powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --app-dir pose_focus_demo --host 127.0.0.1 --port 8767
~~~

Mở trình duyệt tại **http://127.0.0.1:8767/**.

Giữ PowerShell đang chạy. Lần đầu phân tích ca có thể cần chờ mô hình bình thường được chuẩn bị. Nếu bạn đã thấy trang và server đang chạy thì không mở thêm server cùng cổng.

Đường dẫn nhanh trên máy hiện tại:

~~~powershell
Set-Location C:\Users\ManhHung\DENSO_robot_health_demo\github_DENS0_2026
.\.venv\Scripts\python.exe -m uvicorn app:app --app-dir pose_focus_demo --host 127.0.0.1 --port 8767
~~~

### 2.4. Chuẩn bị phần Đánh giá AI

Nếu chưa có kết quả benchmark, có hai cách:

- Mở web → **Đánh giá AI → Chạy benchmark 3 seed**.
- Hoặc chạy ở PowerShell tại thư mục gốc:

~~~powershell
.\.venv\Scripts\python.exe -m research_pipeline benchmark --seeds 19,41,73 --scarce 3 --extra 12 --output research_artifacts
~~~

Đợi lệnh hoàn thành rồi mở/làm mới web. Nếu server đã chạy, dùng cửa sổ PowerShell thứ hai để chạy lệnh. Không chạy hai benchmark đồng thời vào cùng thư mục đầu ra.

## 3. Bản đồ giao diện và mối liên hệ giữa các phần

### 3.1. Các khu vực

| Khu vực | Nội dung chính | Liên quan đến phần nào? |
|---|---|---|
| Tổng quan | Video, tọa độ, mốc chọn, trạng thái mô phỏng | Cấp thời điểm video và vùng theo dõi cho dashboard |
| Biểu đồ | Pose, cảm biến nguồn, cảm biến what-if, điểm AI | Hiển thị dữ liệu ca hiện tại theo thời gian video |
| Mô phỏng | Tham số và danh sách lỗi | Sinh ca mới, cập nhật cảm biến/what-if/cảnh báo |
| Bảo trì | Cảnh báo, 6 biểu đồ bằng chứng, form kết luận | Đọc kết quả phát hiện của ca hiện tại; ghi phản hồi |
| Lịch sử | Các sự kiện đã lưu và dữ liệu trước–trong–sau | Đọc bằng chứng cố định của cả ca cũ lẫn ca hiện tại |
| Chuyển động và bằng chứng AI | Khớp q, vận tốc, gia tốc, jerk, dòng, điểm AI/luật, chất lượng | Dùng đồng hồ video; chọn khớp độc lập với landmark |
| Đánh giá AI | A/B/C, bảng chỉ số, confusion matrix, ablation, ca test | Dữ liệu nghiên cứu riêng; không tua theo video chính |
| Xuất CSV ở đầu trang | Timeline toàn ca hiện tại | Không phải chỉ một cảnh báo và không phải benchmark |

### 3.2. Sơ đồ luồng sử dụng

~~~mermaid
flowchart TD
    A[Video và pose HoRoPose đã lưu] --> B[Đồng hồ video và lựa chọn landmark]
    B --> C[Biểu đồ quan sát]
    B --> D[Bộ sinh what-if]
    E[Seed, tải, môi trường, lịch lỗi] --> D
    D --> F[Cảm biến và quỹ đạo giả lập]
    F --> G[Mô hình phát hiện đa nguồn]
    G --> H[Cảnh báo và giả thuyết]
    H --> I[Xem bằng chứng và xác nhận bảo trì]
    H --> J[Snapshot và log SQLite]
    I --> J
    J --> K[Xem lịch sử, xuất JSON và CSV]
    L[Bộ sinh nghiên cứu bảy servo] --> M[Dataset train, validation, test]
    M --> N[Benchmark A/B/C]
    N --> O[Đánh giá AI trên đồng hồ mô phỏng riêng]
~~~

Nếu trình đọc Markdown không hỗ trợ Mermaid, đọc theo thứ tự: **video/pose + cấu hình lỗi → tín hiệu what-if → phát hiện → cảnh báo → bằng chứng → xác nhận → lịch sử**. Benchmark là một nhánh thí nghiệm riêng.

### 3.3. Khi thao tác thì phần nào đổi?

| Thao tác | Thay đổi | Giữ nguyên |
|---|---|---|
| Phát/dừng/tua video | Frame hiện tại, các giá trị tức thời và vạch thời gian dashboard | Cấu hình lỗi, snapshot và kết quả toàn ca |
| Chọn landmark | Tọa độ, quỹ đạo, tốc độ mốc, cảm biến vùng, điểm AI vùng; ô mốc trong phòng mô phỏng cũng đổi | Khớp J đang chọn; dữ liệu video và danh sách lỗi đã thêm |
| Chọn Khớp cơ khí | Góc q, vận tốc, gia tốc, jerk và góc trong khung tức thời | Landmark và cảm biến vùng |
| Thêm/bỏ lỗi; đổi seed/tải/môi trường | Tạo ID ca mới, tính tín hiệu/cảnh báo mới, lưu snapshot mới | Ảnh và pose HoRoPose gốc, cảm biến đã in trong video, log cũ |
| Lưu xác nhận | Kết luận mới nhất và lịch sử các lần cập nhật | Pose/cảm biến/điểm AI đã lưu |
| Tua Khung hình trong log | Pose, bảng, biểu đồ của log đang mở | Video và ca đang xem trên dashboard |
| Chọn ca test/khớp/tín hiệu nghiên cứu | Biểu đồ ca test | Video, ca what-if và log bảo trì |
| Đổi Nhóm ở confusion matrix | Ma trận và mô hình dùng để vẽ điểm lỗi của ca test | Ca test và ca video |
| Đổi Seed ở confusion matrix | Ma trận và bảng ablation của seed đó | Ca test đang chọn có ID/seed riêng |

## 4. Hiểu thời gian, mốc pose và khớp robot

### 4.1. Ba cách đọc thời gian

| Thời gian | Xuất hiện ở đâu? | Ý nghĩa |
|---|---|---|
| Giây video, khoảng 0–16,67 s | Dashboard, cảnh báo, timeline lịch sử | Vị trí trong clip; dữ liệu lấy theo frame/30 |
| Ngày giờ lưu UTC/UTC+7 | Log và phản hồi | Khi server lưu dữ liệu hoặc người dùng xác nhận; không phải thời gian robot được quay |
| Giây mô phỏng nghiên cứu | Biểu đồ ca test trong Đánh giá AI | Đồng hồ của ca servo ảo độc lập |

Clip có **500 frame ở 30 fps nhưng chỉ 120 ảnh RGB nguồn**, có lặp, đảo chiều và giữ hình. Vì thế, thời gian chuyển động trong clip không phải bản ghi liên tục của robot thật. Góc/vận tốc/jerk của bản phát lại cũng không phải phép đo encoder.

Thanh **Khung hình trong log** là con trỏ riêng trên cùng hệ giây video của ca cũ. Nó không điều khiển video chính.

### 4.2. Landmark L0–EE

| Mốc ảnh | Nhãn trên web |
|---|---|
| L0 | Đế |
| L2 | Vai |
| L3 | Khuỷu dưới |
| L4 | Khuỷu trên |
| L6 | Cẳng tay |
| L7 | Cổ tay |
| EE | Bộ kẹp |

Các số không liên tục vì giữ quy ước mốc của nguồn pose. Đây là **tọa độ 2D trên ảnh**, không phải tên cảm biến được lắp thực tế.

### 4.3. Khớp J1–J7

J1–J7 là danh sách góc q1–q7 của mô hình. Chọn **Khớp cơ khí** ở phần Chuyển động và bằng chứng AI để đổi góc/vận tốc/gia tốc/jerk.

**Chọn L4 không tự chuyển sang J4.** Ví dụ bạn có thể xem cảm biến giả lập vùng L4 và góc J7 cùng lúc. Chưa có ánh xạ một cảm biến vật lý tại mỗi landmark tới khớp có cùng số.

Trong log cũng có hai lựa chọn riêng: **Vùng cảm biến** và **Khớp góc độc lập**.

## 5. Camera, pose và trạng thái tức thời

### 5.1. Camera & Pose

- **▶ / Ⅱ:** phát hoặc tạm dừng. Khi clip đã hết, bấm phát để chạy lại từ đầu.
- **Thanh tua:** chọn thời điểm video.
- **0.5× / 1× / 1.5× / 2×:** đổi tốc độ phát trên trình duyệt. Không đổi cường độ lỗi, thời gian lỗi hay bộ dữ liệu.
- **THỜI ĐIỂM VIDEO:** phút:giây và số frame hiện tại.
- **x / 7 MỐC:** số mốc dự đoán đang được biểu diễn trong vùng ảnh.

Màu trong video:

| Dấu hiển thị | Ý nghĩa |
|---|---|
| Nét cyan đã có trong video | Keypoint/pose HoRoPose dự đoán được vẽ khi dựng video; không phải dấu vật lý nhà sản xuất dán lên robot |
| Vòng xanh sáng quanh một mốc | Landmark bạn đang chọn trên web |
| Đường trắng đứt | Pose what-if giả lập khi sai khác đủ lớn để hiển thị |

Không thấy đường trắng đứt có thể vì sai khác nhỏ hoặc mốc bị khuất; không đồng nghĩa không có lỗi cảm biến.

### 5.2. Tại khung hình hiện tại

| Trường | Cách đọc |
|---|---|
| TỌA ĐỘ ẢNH | X/Y của landmark đang chọn, đơn vị pixel trong vùng hiển thị |
| GÓC KHỚP AI | Góc của J đang chọn độc lập, đơn vị độ |
| ĐỘ PHỦ POSE | Số mốc được biểu diễn trên tổng 7 |
| ẢNH NGUỒN / CHU KỲ | ID ảnh DREAM và lượt phát lại; giúp truy ngược tài nguyên |

Giá trị “—”, “KHUẤT” hoặc “Bị che khuất” là thiếu giá trị hợp lệ, không phải bằng 0.

### 5.3. Trạng thái mô phỏng

Hiển thị chỉ báo hoạt động ảnh, nhiệt tích lũy giả lập, chênh pose và các tham số lỗi đang tác động ở vùng chọn. Dùng khung này để kiểm tra “lỗi đã bắt đầu chưa” khi tua video.

Tham số lỗi là thông tin của bộ sinh, không phải bằng chứng AI tự đo được. Bộ phát hiện dùng tín hiệu quan sát giả lập và phần dư, không dùng nhãn lỗi tiêm để quyết định cảnh báo.

## 6. Cách đọc biểu đồ nói chung

### 6.1. Trục và giá trị

- **Trục ngang:** giây video đối với dashboard; giây ca mô phỏng đối với benchmark.
- **Trục dọc:** đơn vị ghi trên biểu đồ như mm/s, °C, dB, A, px, ° hoặc điểm AI.
- **Số ở góc biểu đồ dashboard:** giá trị tại frame video đang xem, không phải giá trị lớn nhất của toàn đường.
- **Vạch đen dọc:** frame đang chọn. Đây không phải ngưỡng.
- **Trục dọc tự chọn khoảng phù hợp:** hai biểu đồ khác nhau có thể dùng thang khác nhau. Đọc số trục trước khi so độ cao; dao động nhiệt nhỏ có thể trông rất lớn khi trục chỉ trải khoảng 0,5 °C.

### 6.2. Đường nền, đường tham chiếu và ngưỡng

| Dấu | Cách hiểu đúng |
|---|---|
| Xám đứt trong cảm biến what-if/log | Nền đối chứng mô phỏng cùng điều kiện; không phải giới hạn kỹ thuật hay ngưỡng cảnh báo |
| Xám đứt trong Góc khớp | Nhãn DREAM để đối chiếu dự đoán; không phải đường nền cảm biến |
| Đen đứt trong quỹ đạo | Quỹ đạo giả lập “nếu có lỗi” |
| Đen đứt trong AI và luật đối chiếu | Điểm của luật đối chiếu; không phải pose |
| Nâu đứt ngang ở biểu đồ điểm AI của cảnh báo/log | Ngưỡng 50/100 |
| Nâu đứt dọc trong cảnh báo/log | Thời điểm mô hình xác nhận đủ 3 frame vượt ngưỡng |
| Khoảng trống trên đường | Thiếu dữ liệu hợp lệ; không nối suy diễn thành tín hiệu thật |

Không phải mọi biểu đồ điểm AI đều vẽ đường ngưỡng ngang. Ngưỡng dashboard vẫn là 50; cảnh báo chi tiết và log thể hiện đường này.

### 6.3. Vùng tô có ý nghĩa khác nhau theo vị trí

| Biểu đồ | Vùng tô biểu diễn |
|---|---|
| Điểm bất thường ở nhóm C | Các khoảng cảnh báo đã phát hiện tại landmark đang chọn |
| Sáu biểu đồ trong một cảnh báo | Khoảng của riêng cảnh báo đang mở |
| Biểu đồ trong Lịch sử | Khoảng của riêng sự kiện log đang mở |
| AI và luật đối chiếu | Khoảng lỗi được người dùng tiêm tại landmark đang chọn |
| Tín hiệu/điểm lỗi ca nghiên cứu | Khoảng tiêm lỗi biết trước để đánh giá |

**Không được hiểu mọi vùng tô là AI đã phát hiện.** Vùng tiêm lỗi là nhãn thí nghiệm; vùng cảnh báo là kết quả mô hình. Hai vùng có thể lệch nhau, không trùng hoặc không có cảnh báo.

### 6.4. Tua bằng biểu đồ

Nhấn biểu đồ thời gian trên dashboard để tua video. Nếu video còn đang phát thì nó tiếp tục chạy sau khi tua; hãy tạm dừng trước khi so sánh số.

Trong biểu đồ cảnh báo: dùng chuột hoặc Tab để chọn canvas rồi dùng ←/→ một frame, Home/End đến đầu/cuối đoạn. Mở cảnh báo tự tạm dừng video.

Trong log: chuột hoặc ←/→, Home/End chỉ đổi frame log. Biểu đồ nghiên cứu dùng các ô lựa chọn; chưa có chức năng nhấn để tua video chính. Biểu đồ quỹ đạo X–Y không phải biểu đồ thời gian.

## 7. Giải thích từng biểu đồ trên dashboard

### 7.1. Quỹ đạo và tốc độ mốc

| Biểu đồ | Phụ thuộc lựa chọn nào? | Đọc như thế nào? | Có thể kết luận gì? |
|---|---|---|---|
| Quỹ đạo mốc đã chọn | Landmark | Hình đường đi trong mặt phẳng ảnh; xanh là pose nguồn, đen đứt là what-if, chấm tròn là vị trí hiện tại | Thấy sự khác biệt đường đi giả định; chưa biết sai lệch theo mm hoặc trong 3D |
| Tốc độ mốc 2D | Landmark | Mức dịch chuyển pixel mỗi giây | Thấy nhanh/chậm trên ảnh; không phải tốc độ quay khớp |

### 7.2. Nhóm A — Hình ảnh quan sát

| Biểu đồ | Đơn vị / phạm vi | Ý nghĩa và cách xem |
|---|---|---|
| Khác biệt với đoạn mẫu | px; tổng hợp cấu hình cánh tay | So cấu hình hiện tại với các mẫu ảnh đoạn 3–7 s, tương đối với mốc đế. Cao nghĩa là tư thế ảnh khác mẫu; mẫu chưa được xác nhận là quỹ đạo lệnh hoặc trạng thái cơ khí tốt |
| Độ phủ mốc | 0–7; toàn cánh tay | Mức hiện diện của các mốc. Giảm có thể do khuất/ra ngoài khung ảnh; không phải điểm sức khỏe robot |
| Thời gian ít dịch chuyển | s; landmark chọn | Thời gian tích lũy khi mốc ít thay đổi vị trí. Có thể là đoạn giữ hình hoặc dừng theo chương trình; không đủ để kết luận đáp ứng chậm |
| Góc khớp q1–q7 | °; J chọn | Xanh: dự đoán đã hiệu chỉnh bằng 30 nhãn đầu; xám: nhãn DREAM. Khoảng cách hai đường là sai khác dự đoán trong dữ liệu này |
| Sai số keypoint 2D | px; tổng hợp so nhãn DREAM | Đánh giá chất lượng keypoint. Cao là AI pose sai khác nhãn, không phải robot lệch cơ khí |

**Khác biệt với đoạn mẫu, độ phủ và sai số keypoint là chỉ số toàn cánh tay**, không đổi chỉ vì chọn landmark khác. Góc q đổi bằng lựa chọn J; tốc độ mốc và thời gian ít dịch chuyển đổi theo landmark.

### 7.3. Nhóm A+ — Cảm biến được vẽ trong video nguồn

Bốn biểu đồ **Rung (mm/s), Âm thanh (dBA), Nhiệt độ (°C), Dòng động cơ (A)** đọc bản ghi mô phỏng J4 đã dùng để dựng video.

- Tua tới một frame để đối chiếu với số trong video.
- Các kênh này không đổi khi thêm lỗi trong phòng mô phỏng.
- Chọn landmark khác cũng không biến chúng thành cảm biến của vùng mới: chúng vẫn là J4 trong nguồn video.
- Âm trong nguồn được gắn nhãn dBA; âm what-if được gắn dB. Không dùng hai đường để kết luận hiệu chuẩn âm thanh thực tế.

### 7.4. Nhóm B — Cảm biến giả lập what-if

| Biểu đồ | Đơn vị | Cách đọc |
|---|---|---|
| Rung RMS | mm/s | Đường liền là kênh giả lập của ca, xám đứt là nền. Xung tăng có thể do ổ bi/độ rơ; lệch kênh riêng có thể do trôi cảm biến |
| Nhiệt độ | °C | Tích lũy do tổn hao/tản nhiệt giả định; có thể tăng chậm, còn cao sau khi lịch lỗi kết thúc và nguội dần |
| Âm thanh | dB | Mức âm tổng hợp theo hoạt động, tải và lỗi. Đối chiếu rung và dòng để xem nhiều kênh có cùng thay đổi không |

Ba biểu đồ đều theo landmark chọn. Nhãn RMS/envelope không có nghĩa hệ thống đã thu waveform gia tốc cao tần: đây là tín hiệu tổng hợp mức bao. Chưa có FFT, phổ ổ bi hoặc audio thật.

### 7.5. Nhóm C — Tác động mô phỏng và phát hiện

| Biểu đồ | Đơn vị | Cách đọc |
|---|---|---|
| Chênh pose dự kiến | px | Sai khác giữa pose nguồn và what-if, tổng hợp các mốc còn so sánh được từ vùng chọn về phía cuối tay. Nền có nhiễu nhỏ nên không nhất thiết bằng 0 |
| Trễ chuyển động | s | Ước lượng bằng so hình chiếu what-if với các pose quá khứ. Không phải thời gian trễ đo từ controller/encoder |
| Điểm bất thường | 0–100 | Điểm Isolation Forest đã biến đổi; càng cao thường càng khác trạng thái bình thường mô hình học. Không phải % xác suất hỏng. Vùng tô là cảnh báo của vùng chọn |

Chênh pose cao có thể do lỗi cơ khí giả định hoặc phép đo vị trí giả định; bản thân chỉ số này không xác định được nguyên nhân.

### 7.6. Chuyển động và bằng chứng AI

| Biểu đồ | Lựa chọn | Ý nghĩa |
|---|---|---|
| Vận tốc góc dự đoán | J | Đạo hàm góc theo thời gian clip, °/s; dấu âm/dương biểu diễn hướng |
| Gia tốc góc dự đoán | J | Mức thay đổi vận tốc, °/s²; tăng/giảm tốc |
| Jerk | J | Mức thay đổi gia tốc, °/s³; rất nhạy với nhiễu dự đoán và việc dựng clip |
| Dòng giả lập tại vùng chọn | Landmark | Dòng ca what-if và đường nền, A; liên quan mô men giả định |
| AI và luật đối chiếu | Landmark | Xanh liền: AI; đen đứt: luật. Có thể khác nhau vì cách tính khác nhau; luật chỉ để đối chiếu |
| Chất lượng phép quan sát | Landmark và pose toàn tay | Xanh: độ phủ pose toàn tay; đen đứt: độ phủ so sánh what-if từ vùng chọn. Trục 0–1, số tức thời what-if được hiển thị theo % |

Đạo hàm dùng sai phân theo giây của bản phát lại. Điểm nối/đảo ảnh được bỏ giá trị để hạn chế đỉnh giả; thấy “—” tại các đoạn này là chủ động đánh dấu thiếu dữ liệu.

Dòng **chuyển động / dừng / không quan sát** và thời gian pha mô tả clip hiện tại, chưa phải chu kỳ thao tác do PLC/controller ghi nhận.

## 8. Phòng mô phỏng: các tham số và thao tác

### 8.1. Các ô nhập

| Tham số | Phạm vi | Ý nghĩa |
|---|---|---|
| Nguyên nhân | 7 loại ở mục 9 | Chọn tác động giả định |
| Mốc theo dõi | L0, L2, L3, L4, L6, L7, EE | Vùng áp dụng kịch bản; chưa phải địa chỉ cảm biến thật |
| Bắt đầu | Giây trong clip | Mốc lịch tiêm; cần đủ thời gian cho lỗi |
| Kéo dài | 0,5–10 s | Thời gian lịch tác động; bắt đầu + kéo dài không vượt 16,67 s |
| Cường độ | 0,3–2,0× | Hệ số tương đối của lỗi; 2× không có nghĩa hư hỏng 200% |
| Seed mô phỏng | Số nguyên 0–1.000.000 | Điều khiển ngẫu nhiên để tái lập với cùng cấu hình và phiên bản |
| Tải giả định | 0,6–1,4× | Thay điều kiện nền, mô men/dòng/nhiệt giả định |
| Tiến triển lỗi | Nhất thời, tăng dần, ngắt quãng | Dạng tác động theo thời gian |
| Môi trường nền | Danh định, rung/ồn, nóng, che khuất what-if | Thử độ bền của phát hiện và chất lượng quan sát |

Giao diện giới hạn ô Bắt đầu tới 15,5 s. Server kiểm tra cả khoảng tác động; ví dụ bắt đầu 15 s, kéo dài 3 s không hợp lệ.

### 8.2. Các nút

| Nút | Hành vi |
|---|---|
| + Thêm kịch bản | Lấy các ô lỗi đang nhập, thêm vào danh sách hiện có và tạo ca mới |
| × ở một kịch bản | Bỏ riêng kịch bản đó; tạo ca mới với các kịch bản còn lại |
| Xóa lỗi | Tạo ca không có lịch tiêm lỗi; không xóa lịch sử, không xóa database |
| Về kịch bản mẫu | Thay danh sách bằng ổ bi L4 từ 5–8 s và độ rơ L7 từ 10–13 s; dùng seed/tải/môi trường hiện tại |
| Tải 20 ca mô phỏng | Tải ZIP các ca minh họa riêng; không đưa thêm 20 ca vào danh sách hiện tại |
| Giải thích chi tiết cách sinh và phát hiện lỗi | Mở mô tả cơ chế trên giao diện |

Đổi **seed, tải hoặc môi trường** sẽ tạo ca mới với danh sách lỗi đã có. Đổi loại lỗi/mốc/bắt đầu/kéo dài/cường độ/tiến triển chỉ chuẩn bị ô nhập cho lần **Thêm kịch bản** tiếp theo; không sửa ngược kịch bản đã thêm.

Khi đang lưu, đợi nút hoạt động trở lại. Thêm trùng một lỗi vào cùng vùng/cùng thời gian khiến các tác động cộng lại; nếu muốn thử một lỗi riêng, bấm Xóa lỗi trước.

### 8.3. Thứ tự thao tác nên dùng

1. Tạm dừng video.
2. Ghi lại hoặc sao chép URL ca hiện tại nếu cần giữ để so sánh.
3. Chọn seed, tải và môi trường.
4. Bấm Xóa lỗi để có ca nền dưới điều kiện đó.
5. Chọn loại lỗi, vùng, thời gian, cường độ, tiến triển.
6. Bấm + Thêm kịch bản.
7. Chọn đúng landmark trên dashboard và tua vào khoảng tác động.
8. Quan sát nhiều kênh, điểm AI, chất lượng và cảnh báo.
9. Mở log/xuất dữ liệu để giữ bằng chứng.

## 9. Cơ chế sinh dữ liệu bất thường

### 9.1. Luồng sinh trên web

1. Đọc pose nguồn theo frame.
2. Từ hoạt động ảnh và tải giả định, xây dựng mô men, dòng và tổn hao nền.
3. Lịch lỗi tạo cường độ tác động theo thời gian.
4. Cùng tác động đó làm đổi các kênh liên quan và/hoặc pose what-if.
5. Thêm nhiễu có seed; lưu tín hiệu cùng timestamp.
6. Mô hình phát hiện đọc tín hiệu đã sinh; không được đặt cảnh báo chỉ vì có một kịch bản trong danh sách.

Các loại lỗi không được tạo bằng cách tùy ý nâng mọi đường cùng lúc. Ví dụ lỗi tản nhiệt đổi tích nhiệt; trôi cảm biến rung đổi phép đo rung; độ rơ chủ yếu đổi hình chiếu và đáp ứng tại đảo chiều.

### 9.2. Tác động của từng loại

| Loại | Tác động trong demo | Kênh nên xem | Giới hạn khi diễn giải |
|---|---|---|---|
| Ổ bi / truyền động | Tạo thành phần xung chung cho rung/âm; tăng tổn hao và mô men giả định | Rung, âm, dòng, nhiệt, điểm AI | Không chứng minh chính xác lỗi ổ bi nếu không có phép đo thật và phổ |
| Ma sát / bôi trơn | Tăng lực cản/mô men và nhiệt tổn hao, có đáp ứng trễ giả định | Dòng, nhiệt, rung/âm, chênh pose, trễ | Không định lượng được lượng mỡ hay mức mòn thực |
| Suy giảm tản nhiệt | Giảm hệ số làm nguội, nhiệt tích lũy | Nhiệt, đường nền, điểm AI | Clip ngắn có thể chưa đủ để tạo chênh nhiệt lớn |
| Độ rơ / sai tư thế | Xoay quỹ đạo what-if quanh mốc lân cận; tăng tác động khi đảo chiều | Chênh pose, quỹ đạo, rung/âm | Là surrogate hình chiếu, không phải mô hình hộp số đầy đủ |
| Đáp ứng chậm | Dùng pose tham chiếu quá khứ để tạo quỹ đạo trễ | Trễ, chênh pose, quỹ đạo | Chỉ rõ khi có chuyển động đủ để phân biệt |
| Trôi cảm biến rung | Tăng lệch kênh rung, không gây lỗi cơ học tương ứng | Rung đối chiếu âm/dòng/nhiệt | Cần phân biệt lỗi cảm biến với lỗi máy |
| Sai lệch phép đo vị trí | Làm lệch vị trí what-if, giữ trạng thái cơ học và các kênh điều kiện khác | Chênh pose và các kênh không đổi | Có thể giống sai tư thế; chẩn đoán nguyên nhân còn mơ hồ |

### 9.3. Dạng tiến triển và môi trường

- **Nhất thời / can thiệp ảo:** tác động tăng rồi giảm ở đầu/cuối lịch. Khi kết thúc được hiểu là can thiệp sửa chữa ảo, không phải robot tự lành.
- **Tăng dần:** cường độ phát triển theo tuổi lỗi trước khi kết thúc lịch.
- **Ngắt quãng:** tác động bật/tắt theo thời gian; có thể tạo nhiều đợt cảnh báo.
- **Rung / ồn bên ngoài:** thêm nhiễu nền để thử báo động giả.
- **Nhiệt môi trường cao:** thay nền nhiệt, không đồng nghĩa tiêm lỗi tản nhiệt.
- **Che khuất camera what-if:** làm thiếu mốc what-if trong một đoạn mô phỏng; ảnh video gốc vẫn giữ nguyên.

**Nhiệt có quán tính:** kết thúc lịch lỗi không bắt buộc nhiệt quay ngay về nền.

### 9.4. Khác với bộ sinh của benchmark

Web dùng hoạt động pose của bản phát lại để tạo cảm biến theo vùng landmark. Benchmark dùng **bảy servo tương đương độc lập**, có lệnh tham chiếu, ma sát, giới hạn mô men, encoder/camera ảo và trạng thái nhiệt. Hai nhánh chia sẻ một số hàm sinh tín hiệu nhưng không phải cùng dataset hay cùng đồng hồ.

Bộ sinh chưa mô tả toàn bộ động lực học liên kết Franka, chưa hiệu chuẩn theo thông số OEM và chưa tạo video lỗi thật.

## 10. Cơ chế phát hiện và cách hiểu cảnh báo

### 10.1. Bộ phát hiện của dashboard

1. **Ridge** học mức cảm biến bình thường dự kiến từ 10 ca mô phỏng bình thường có tải/môi trường khác nhau.
2. Với mỗi frame/vùng, tính phần dư giữa rung/nhiệt/âm/dòng và mức dự kiến, chuẩn hóa theo độ dao động khi học.
3. **Isolation Forest** đánh giá tổ hợp phần dư cùng chênh pose và trễ.
4. Ngưỡng được hiệu chuẩn ở percentile 99,5 trên 4 ca validation bình thường độc lập.
5. Điểm thô được biến đổi thành thang 0–100; mức ngưỡng hiển thị tương ứng khoảng 50.
6. Độ phủ so sánh what-if phải ít nhất 60%; cần **3 frame liên tiếp** đáp ứng điều kiện để ghi nhận sự kiện.

Ở 30 fps, frame đầu và frame thứ ba cách nhau khoảng 0,067 s. Đây là điều kiện duy trì của demo, không phải độ trễ thu nhận/tính toán đo tại nhà máy.

Đường nền xám là đối chứng mô phỏng để người xem so sánh; mô hình dùng nền bình thường **đã học**, không lấy đường xám làm ngưỡng. Nhãn DREAM và nhãn lỗi tiêm không được dùng để quyết định cảnh báo.

### 10.2. Vì sao chưa đến đỉnh cao nhất đã cảnh báo?

Ví dụ minh họa từ một ca đã lưu:

| Tại khoảng 5,73 s | Giá trị giả lập | Mức bình thường mô hình dự kiến |
|---|---:|---:|
| Rung | 1,65 mm/s | 1,06 mm/s |
| Âm | 59,09 dB | 56,76 dB |
| Dòng | 1,66 A | 1,59 A |

Dù rung chưa đạt 4 mm/s, tổ hợp đa kênh đã khác trạng thái bình thường đủ để điểm AI vượt ngưỡng. Các số trên chỉ giải thích ca đó; không phải giới hạn an toàn của Franka hay ngưỡng công nghiệp.

Một đỉnh lớn đơn lẻ có thể chưa tạo sự kiện nếu không đủ 3 frame liên tiếp hoặc thiếu chất lượng. Ngược lại, nhiều kênh lệch vừa phải cùng lúc có thể tạo cảnh báo. Điểm Isolation Forest không tăng tuyến tính theo riêng biên độ rung.

### 10.3. Điểm vượt ngưỡng, sự kiện và nguyên nhân là ba việc khác nhau

| Khái niệm | Nghĩa |
|---|---|
| Điểm/frame vượt ngưỡng | Tổ hợp tín hiệu tại frame đủ khác nền học được |
| Sự kiện cảnh báo | Đủ duy trì 3 frame và điều kiện chất lượng |
| “Nghi ổ bi”, “Nghi ma sát”… | Giả thuyết từ mẫu bằng chứng đa nguồn, cần kiểm tra |

Một frame xuống dưới ngưỡng hiện có thể kết thúc sự kiện; lần vượt đủ 3 frame tiếp theo tạo sự kiện mới. Do chưa có cơ chế gộp đợt bằng khoảng chờ, một lỗi tiêm có thể tạo nhiều log ngắn. Không đồng nhất “số log” với “số bộ phận hỏng”.

**Đỉnh bất thường trong cảnh báo là frame có điểm AI cao nhất của sự kiện**, không nhất thiết là frame có rung cao nhất.

### 10.4. Phân biệt hai kiểu “xác nhận”

- **Xác nhận tại 5,73 s:** mô hình đã có đủ frame để xác nhận cảnh báo trên thời gian video.
- **ĐÃ XÁC NHẬN / Dự đoán đúng / Dự đoán sai:** kỹ thuật viên đã lưu kết luận.

Chữ “xác nhận” của mô hình không có nghĩa kỹ thuật viên đã kiểm tra xong hoặc đã chứng minh máy hỏng.

## 11. Xem bằng chứng và xác nhận bảo trì

### 11.1. Mở một cảnh báo

1. Đến **Bảo trì → Vòng phản hồi bảo trì**.
2. Bấm tên cảnh báo.
3. Web chọn landmark của cảnh báo, tạm dừng video và tua tới đỉnh điểm AI.
4. Xem thông tin bắt đầu–kết thúc, thời điểm xác nhận mô hình, giả thuyết và các bước kiểm tra.
5. Xem **Biểu đồ bằng chứng** ngay trong cảnh báo, không cần tìm ở trang khác.

Sáu biểu đồ: **rung, nhiệt, âm, chênh pose, trễ, điểm AI**. Chúng phóng khoảng cảnh báo và tối đa 1 giây ngữ cảnh mỗi bên.

- **Xem lúc phát hiện:** tới thời điểm xác nhận đủ frame.
- **Xem đỉnh bất thường:** tới đỉnh điểm AI của sự kiện.
- Nhấn biểu đồ để kiểm tra từng thời điểm.
- Vùng xanh chỉ là sự kiện đang mở. Đoạn ngoài vùng xanh có thể chứa một sự kiện khác, không mặc nhiên là bình thường.

Nếu muốn xem dòng điện hoặc toàn bộ mốc/khớp tại cùng thời điểm, mở **Xem log pose & cảm biến đã lưu**.

### 11.2. Đọc bằng chứng z / σ

Ví dụ “rung +6,3σ” nghĩa là phần dư rung cao hơn mức dự kiến theo thang chuẩn hóa của dữ liệu bình thường mô phỏng. Đây không phải “cao gấp 6,3 lần mm/s”, không phải xác suất hỏng và không phải tiêu chuẩn OEM.

Xem bằng chứng này cùng đơn vị gốc, chất lượng, tải, môi trường, pose và các kênh còn lại.

### 11.3. Ghi kết luận

1. Chọn **Dự đoán đúng** hoặc **Dự đoán sai**.
2. Nhập **Kỹ thuật viên**.
3. Nhập **Việc đã làm**.
4. Nếu dự đoán sai, bắt buộc ghi **Nguyên nhân thực tế**.
5. Bấm **Lưu xác nhận**, kiểm tra trạng thái đã lưu.

Ví dụ phản hồi thử nghiệm:

~~~text
Kết luận: Dự đoán sai
Kỹ thuật viên: Demo - người kiểm tra
Nguyên nhân thực tế: Nhiễu rung bên ngoài, chưa thấy bằng chứng lỗi ổ bi
Việc đã làm: Đối chiếu âm/dòng/nhiệt, kiểm tra nguồn nhiễu và yêu cầu đo lại
~~~

Chỉ ghi đúng/sai khi có cơ sở. Trong demo, ghi rõ đây là xác nhận thử nghiệm; không trình bày như kết quả bảo trì thiết bị thật.

Có thể cập nhật kết luận. Hệ thống giữ kết luận mới nhất và lưu nối tiếp các lần cập nhật trong lịch sử. Việc lưu **không sửa tín hiệu cũ, không tự giảm điểm AI và không tự huấn luyện lại mô hình**.

## 12. Log lịch sử pose và cảm biến

### 12.1. Cách mở

Chọn **Lịch sử** trên thanh điều hướng hoặc link **Xem log pose & cảm biến đã lưu** dưới cảnh báo.

Bảng lịch sử gồm ID sự kiện/ca, giả thuyết, landmark, khoảng cảnh báo, thời điểm xác nhận mô hình, điểm đỉnh, ngày giờ lưu và trạng thái kỹ thuật viên.

- **Ca chạy:** tất cả ca hoặc ca đang xem.
- **Xác nhận bảo trì:** tất cả/chưa xác nhận/đã xác nhận.
- **Trang trước / Trang sau:** mỗi trang tối đa 20 sự kiện.
- **Làm mới lịch sử:** tải lại danh sách đã lưu.

Ca không có cảnh báo vẫn có snapshot, nhưng không có dòng sự kiện bất thường trong bảng. Ca cũ chưa được lưu bằng cơ chế mới được tạo snapshot khi mở lại lần đầu.

### 12.2. Xem từng frame trong log

1. Bấm **Xem log** ở sự kiện cần xem.
2. Kiểm tra ID ca, thời điểm lưu, số frame, cửa sổ thời gian và SHA-256.
3. Chọn **Vùng cảm biến** để xem kênh của vùng đó.
4. Chọn **Khớp góc độc lập** để xem q và đạo hàm của J cần kiểm tra.
5. Chọn **Tín hiệu**: rung/nhiệt/âm/dòng/chênh pose/trễ.
6. Kéo **Khung hình trong log** hoặc nhấn hai biểu đồ.
7. Đọc pose, giá trị tức thời, bảng 7 mốc và bảng J1–J7 tại cùng timestamp.
8. Mở **Kết luận kỹ thuật viên và các lần cập nhật** để xem lịch sử phản hồi.

Pose xanh là dữ liệu HoRoPose đã lưu, pose đen đứt là what-if. Hình ở đây là **sơ đồ nối tọa độ 2D đã lưu**, không phải camera mới, không phải mô hình 3D hay một lần suy luận AI mới.

### 12.3. Phạm vi log và tính cố định

- Snapshot giữ **toàn bộ ca**: pose, q, các đạo hàm, cảm biến 7 vùng, điểm AI/luật, chất lượng, cấu hình và nguồn dữ liệu.
- Màn hình/xuất theo sự kiện lấy khoảng cảnh báo cộng tối đa **1 giây trước và 1 giây sau**, cắt tại giới hạn clip.
- Xem log không đổi video hay kịch bản đang chạy.
- Snapshot ghi lần đầu và đọc lại nguyên bản. Đổi mã/mô hình không tự thay bằng chứng cũ.
- SHA-256 giúp kiểm tra bản chụp dữ liệu nhất quán; không chứng nhận dữ liệu đo thật hoặc chẩn đoán đúng.
- Ngày giờ lưu là thời gian phân tích/lưu ngoại tuyến. Toàn bộ clip đã có trước, nên dữ liệu sau cảnh báo có sẵn ngay; chưa phải vòng đệm trực tiếp.

### 12.4. Quay lại xác nhận một ca cũ

Bấm **Mở ca để xác nhận** trong log. Web mở tab mới tại đúng ID ca và khu vực Bảo trì. Chọn cảnh báo tương ứng rồi ghi kết luận. Quay lại Lịch sử và bấm Làm mới nếu cần.

Tải lại URL có ?run=... sẽ mở đúng ca trên **cùng database/máy chủ**. URL không chứa toàn bộ dataset và không chuyển lịch sử sang máy khác.

## 13. Đánh giá AI và so sánh trước–sau tăng cường

### 13.1. Mục đích

Phần này trả lời: với ít dữ liệu lỗi, bổ sung ca mô phỏng có cải thiện dự đoán trên tập test hay không? Kết quả không phải thống kê cảnh báo của clip đang phát.

| Nhóm | Dữ liệu huấn luyện |
|---|---|
| A — Dữ liệu gốc | Ca bình thường và số ít ca lỗi ban đầu |
| B — Tăng cường đơn giản | A cùng các ca tăng cường đơn giản, số lượng theo lớp bằng C |
| C — Mô phỏng vật lý | A cùng các ca mới sinh từ surrogate vật lý |

A/B/C dùng cùng cấu hình ExtraTrees và cùng tập test trong từng seed. Ngưỡng chọn trên validation. Dataset chia theo ca để các cửa sổ cùng ca không rơi vào cả train và test.

### 13.2. Chạy và xem kết quả

1. Đến **Đánh giá AI**.
2. Nếu chưa có kết quả, bấm **Chạy benchmark 3 seed**.
3. Đọc trạng thái đang chạy/hoàn tất/lỗi; kết quả cũ có thể vẫn hiển thị trong khi chạy.
4. Khi xong, đọc biểu đồ cột và bảng trung bình ± độ lệch chuẩn.
5. Đổi seed/nhóm để kiểm tra ma trận, không chỉ nhìn con số trung bình.
6. Chọn ca test để xem tín hiệu và các thời điểm cảnh báo.
7. Tải CSV so sánh hoặc ZIP dataset/manifest để đối chiếu.

Không cần bấm chạy benchmark mỗi lần mở trang.

### 13.3. Ý nghĩa các chỉ số

| Chỉ số | Cách hiểu | Chiều mong muốn |
|---|---|---|
| Macro-F1 | Trung bình F1 của các lớp normal/lỗi ở mức cửa sổ; giảm việc lớp lớn lấn át lớp hiếm | Cao hơn |
| PR-AUC | Khả năng phân biệt bình thường/bất thường trên nhiều ngưỡng; phụ thuộc tỷ lệ lớp của test | Cao hơn |
| Recall sự kiện | Tỷ lệ ca lỗi có một đợt cảnh báo mới được xác nhận sau lúc bắt đầu và khi cửa sổ còn lỗi | Cao hơn |
| Trễ (s) | Median độ trễ trong các ca phát hiện được; không tính ca bỏ sót là trễ 0 | Thấp hơn, đọc cùng recall |
| Báo giả/giờ | Số đợt cảnh báo trên ca hoàn toàn bình thường, quy đổi theo thời gian quan sát | Thấp hơn |
| Bỏ sót ca | Số ca lỗi không được phát hiện theo tiêu chí | Thấp hơn |
| ± độ lệch chuẩn | Độ biến động giữa các seed | Đọc để biết tính ổn định; không phải khoảng tin cậy thực địa |

Biểu đồ cột: cột đậm là Macro-F1, cột nhạt là PR-AUC; vạch nhỏ biểu diễn độ lệch chuẩn giữa seed. Tăng 0,10 F1 tương đương 10 điểm phần trăm, không đồng nghĩa tăng 10% tương đối.

Test hiện thay tải/tốc độ/nhiễu nhưng vẫn dùng cùng phương trình bộ sinh. Chỉ số cải thiện chưa chứng minh hiệu quả trên robot thật. Khi mô hình có recall cao nhưng báo giả lớn, vẫn cần cải tiến/hiệu chuẩn; không chọn mô hình chỉ dựa vào một chỉ số.

### 13.4. Confusion matrix

- **Hàng:** nhãn thật của bộ sinh.
- **Cột:** lớp mô hình dự đoán.
- **Ô đường chéo:** dự đoán đúng.
- **Ô ngoài đường chéo:** nhầm lớp.
- Hàng “Bình thường” rơi vào cột lỗi là báo động giả.
- Hàng lỗi rơi vào cột “Bình thường” là bỏ sót.

Các ô đếm **cửa sổ**, không đếm robot hỏng hoặc số sự kiện. Đổi Seed để xem fold khác, đổi Nhóm để xem A/B/C trên fold đang chọn.

### 13.5. So sánh nguồn dữ liệu — ablation

Bảng **Ảnh hưởng của nguồn dữ liệu và mô hình học bình thường** gồm chỉ rung, rung + chuyển động, đa nguồn và Isolation Forest học bình thường.

Bảng theo seed đang chọn ở ma trận. Dùng để đánh giá nguồn bổ sung có giúp hay không. Chỉ số “—” của Macro-F1 đối với Isolation Forest không phải 0: mô hình đó phát hiện bất thường, không phân loại đầy đủ từng chế độ lỗi như ExtraTrees.

### 13.6. Biểu đồ ca nghiên cứu

1. Chọn **Ca kiểm thử**, đọc ID, loại lỗi, tải/tốc độ, kiểu tiến triển và khớp tiêm.
2. Chọn **Khớp**; khi đổi ca, web mặc định chọn khớp tiêm hoặc J1 nếu bình thường.
3. Chọn **Tín hiệu**: rung, âm, nhiệt, dòng, camera ảo, encoder ảo, jerk.
4. Camera/encoder được so với đường lệnh tham chiếu đen đứt; các phép đo vị trí này dùng rad, không phải pixel.
5. Biểu đồ điểm lỗi dùng **Nhóm A/B/C đang chọn tại confusion matrix**.
6. Đọc đường ngưỡng và các tam giác xác nhận. Ngưỡng này được học riêng cho từng mô hình, không mặc định là 50/100 như dashboard.
7. Vùng tô là khoảng tiêm lỗi. Không có tam giác trong vùng có thể là bỏ sót; tam giác trên ca normal là báo giả.

Đổi seed ma trận không tự chọn ca test của seed đó. Kiểm tra tiền tố s19/s41/s73 trong ID ca nếu muốn so cùng seed. Hai biểu đồ có thể dùng trục thời gian/cách lấy mẫu khác nhau vì điểm được tính theo cửa sổ.

“Kiểm tra số học: đạt” nghĩa dữ liệu qua các kiểm tra hữu hạn/kích thước/biên surrogate, không chứng nhận giống dữ liệu nhà máy.

## 14. Xuất dữ liệu và đọc các tệp

### 14.1. Chọn đúng loại tải

| Nút/link | Dữ liệu tải | Khi nên dùng |
|---|---|---|
| Xuất CSV đầu trang | Toàn timeline ca video hiện tại; 7 hàng mỗi frame | So biểu đồ với giá trị cụ thể hoặc lưu toàn ca |
| Tải JSON trong log | Bằng chứng sự kiện, timeline cửa sổ, metadata, checksum, cấu hình, lịch sử bảo trì | Giữ dữ liệu có cấu trúc đầy đủ |
| Tải CSV trong log | Cửa sổ sự kiện, 7 hàng mỗi frame, thêm ID/giờ lưu/checksum/pha before-during-after | Phân tích bảng theo thời gian/vùng |
| Tải 20 ca mô phỏng | ZIP các ca web minh họa và manifest | Thử nhiều tình huống ngoại tuyến; không phải dataset benchmark A/B/C |
| Tải bảng so sánh CSV | Chỉ số tổng hợp A/B/C | So sánh trước–sau tăng cường |
| Tải dataset và manifest | Dataset nghiên cứu và thông tin nguồn/split | Kiểm tra hoặc tái lập nghiên cứu; không chứa model. Model nằm ở research_artifacts/seed_<seed>/models/ |

### 14.2. Cột quan trọng trong CSV ca/log

| Cột / nhóm cột | Ý nghĩa |
|---|---|
| t_s | Giây video |
| landmark | Vùng hình ảnh |
| source_frame, cycle | Ảnh DREAM và lượt phát lại |
| q_joint_id, q_pred_deg | ID J và góc HoRoPose; đọc theo q_joint_id |
| q_reference_deg | Nhãn DREAM đối chiếu, không phải encoder đang chạy |
| pose_x_px_pred, pose_y_px_pred | Tọa độ pose nguồn |
| twin_x_px_synthetic, twin_y_px_synthetic | Tọa độ what-if |
| vibration_sim_mm_s, temperature_sim_c, sound_sim_db | Cảm biến what-if |
| regional_current_sim_a | Dòng what-if |
| *_baseline_sim_* | Nền mô phỏng đối chứng |
| video_*_sim_* | Cảm biến đã dựng trong video nguồn |
| score_sim, ai_raw_score, rule_score | Điểm hiển thị, điểm AI thô và điểm luật |
| q_velocity_pred_deg_s, q_acceleration_pred_deg_s2, q_jerk_pred_deg_s3 | Đạo hàm của q trong bản phát lại |
| fault_truth_sim | Nhãn tiêm để đánh giá; không phải chẩn đoán đo được |
| pose_source, sensor_source | Dấu nguồn dự đoán/mô phỏng |
| replay_discontinuity | Điểm gián đoạn bản phát lại |
| event_id, run_id | ID sự kiện và ca; có ở CSV log |
| saved_at_utc, snapshot_sha256 | Thời gian lưu và checksum; có ở CSV log |
| event_phase | before/during/after đối với cảnh báo đang xuất |

Một hàng CSV có một landmark và một J được xuất cạnh nhau theo thứ tự mảng. **Không coi đây là ánh xạ vật lý cảm biến–khớp.** Dùng landmark để lọc cảm biến, dùng q_joint_id để lọc góc.

### 14.3. Xem CSV bằng Excel

1. Mở Excel → Data → From Text/CSV.
2. Chọn UTF-8, dấu phân cách comma nếu Excel không tự nhận.
3. Giữ các ID/checksum ở kiểu Text.
4. Lọc landmark hoặc q_joint_id cần xem.
5. Dùng t_s làm trục X.
6. Ô trống nghĩa thiếu giá trị; không tự thay bằng 0 khi tính đạo hàm/thống kê.

Các CSV xuất có BOM UTF-8 để hỗ trợ tiếng Việt. Giờ lưu UTC cần cộng 7 giờ khi đối chiếu với bảng lịch sử hiển thị UTC+7.

## 15. Bài thực hành vận hành từ đầu đến cuối

### 15.1. Ca nền → lỗi ổ bi → cảnh báo → log → phản hồi

1. Mở web và tạm dừng video.
2. Trong Mô phỏng, chọn seed 0, tải 1,00×, môi trường Danh định.
3. Bấm **Xóa lỗi**. Sao chép URL và tải CSV nền để đối chiếu.
4. Chọn **Ổ bi / truyền động**, **L4**, bắt đầu **5 s**, kéo dài **3 s**, cường độ **1×**, tiến triển **Nhất thời**.
5. Bấm **+ Thêm kịch bản**.
6. Chọn L4 trong Cấu trúc cánh tay; tua từ 4 s qua 8 s.
7. Xem rung/âm cùng đổi, dòng/nhiệt và điểm AI; không yêu cầu mọi kênh đạt đỉnh cùng lúc.
8. Đến Bảo trì, mở cảnh báo nếu xuất hiện. Nếu không có, ghi nhận ca chưa phát hiện; xem chất lượng, tải và thời gian.
9. Bấm Xem lúc phát hiện rồi Xem đỉnh bất thường để so sánh.
10. Mở log, kéo frame trước–trong–sau và kiểm tra bảng 7 vùng.
11. Tải JSON và CSV log.
12. Ghi một kết luận thử nghiệm trong Bảo trì và mở lại lịch sử cập nhật.
13. Tải lại trang: ca, log và kết luận phải còn trong cùng database.

Đây là cấu hình thực hành, không bảo đảm mọi phiên bản/cấu hình đều tạo đúng số cảnh báo giống nhau.

### 15.2. Thử sai tư thế và trễ

Làm mỗi loại thành một ca riêng:

| Loại | Cấu hình gợi ý | Quan sát chính |
|---|---|---|
| Độ rơ / sai tư thế | Xóa lỗi → L7, 10–13 s, 1× | Pose trắng đứt/what-if, quỹ đạo, chênh pose |
| Đáp ứng chậm | Xóa lỗi → L4, 5–8 s, 1× | Trễ và chênh pose lúc có chuyển động |
| Suy giảm tản nhiệt | Xóa lỗi → L4, 5–8 s, 1× | Nhiệt thay đổi chậm; sau lịch có thể chưa quay về nền |
| Trôi cảm biến rung | Xóa lỗi → L4, 5–8 s, 1× | Rung lệch nhưng âm/dòng/nhiệt không tăng theo cùng cơ chế lỗi cơ khí |

Giữ nguyên seed/tải/môi trường khi so các loại. Khi so nhiều mức cường độ, lưu URL/CSV từng ca; không thêm chồng lỗi nếu mục tiêu là so một lỗi riêng.

### 15.3. Kiểm tra báo động giả và thiếu quan sát

1. Tạo ca không tiêm lỗi với môi trường Rung/ồn bên ngoài.
2. Xem có cảnh báo không. Nếu có, đó là ca báo giả trong thí nghiệm, không được giấu đi.
3. Đổi sang Che khuất camera what-if và xem chất lượng giảm.
4. Nếu cảnh báo không xuất hiện vì chất lượng thiếu, ghi nhận thiếu quan sát; không kết luận trạng thái máy an toàn.

### 15.4. Trình diễn trong khoảng 5 phút

1. Giới thiệu ảnh robot/pose là dự đoán đã lưu, cảm biến là giả lập.
2. Phát/tua video để thấy các giá trị cùng timestamp.
3. Chọn L4 và J7 để chứng minh hai hệ lựa chọn độc lập.
4. Tạo một lỗi và chỉ ra những kênh thay đổi liên quan.
5. Mở cảnh báo; giải thích ngưỡng đa nguồn và vùng tô.
6. Mở log, tua từng frame, tải JSON/CSV và thử xác nhận.
7. Sang Đánh giá AI, trình bày A/B/C cùng recall/báo giả, nêu đúng phạm vi mô phỏng.

## 16. Quản lý ca chạy, sao lưu và tắt hệ thống

### 16.1. Giữ và mở lại ca

Mỗi thay đổi cấu hình tạo ID ca mới. Sao chép URL có dạng:

~~~text
http://127.0.0.1:8767/?run=<ID_CA>
~~~

Đây là mẫu; thay <ID_CA> bằng ID thực. Có thể lấy ID từ bảng Lịch sử hoặc URL đang mở. Ca cũ và kết luận cũ không tự chuyển sang ca mới dù cấu hình giống nhau.

Nếu nâng cấp mô hình, ca đã có snapshot vẫn giữ kết quả cũ. Tạo ca mới với cùng cấu hình để kiểm tra phiên bản mới; không sửa snapshot cũ để “cập nhật” bằng chứng.

### 16.2. Nơi lưu dữ liệu

Trên Windows mặc định:

~~~text
%LOCALAPPDATA%\DENSO\pose_demo.sqlite3
~~~

Trên máy đã kiểm tra:

~~~text
C:\Users\ManhHung\AppData\Local\DENSO\pose_demo.sqlite3
~~~

Có thể đổi nơi lưu trước khi chạy server:

~~~powershell
$env:DENSO_DEMO_DB = 'C:\DENSO_Data\pose_demo.sqlite3'
.\.venv\Scripts\python.exe -m uvicorn app:app --app-dir pose_focus_demo --host 127.0.0.1 --port 8767
~~~

Dùng thư mục có quyền ghi. Đổi biến này sang database mới làm danh sách lịch sử khác đi; không có nghĩa log cũ đã bị xóa.

Kết quả nghiên cứu nằm ở research_artifacts/, riêng với SQLite. Có thể đổi nơi đọc nghiên cứu bằng DENSO_RESEARCH_DIR theo [RESEARCH_GUIDE](RESEARCH_GUIDE.md).

### 16.3. Sao lưu

Cách đơn giản cho người sử dụng:

1. Dừng benchmark nếu đã hoàn tất, tắt server bằng Ctrl+C.
2. Sao chép pose_demo.sqlite3 sang thư mục sao lưu với tên/ngày riêng.
3. Giữ cả tài nguyên nguồn video/pose nếu muốn mở lại bằng chứng và ca.
4. Sao lưu research_artifacts nếu cần giữ kết quả/dataset/model nghiên cứu.
5. Khởi động lại server.

Khi server còn hoạt động, dùng SQLite backup API thay vì sao chép tệp đang được ghi. Database chứa kết luận kỹ thuật viên; không ghi đè database cũ khi nâng cấp mã.

Chưa có chính sách tự xóa lịch sử hoặc giao diện xóa log. Dữ liệu có thể tăng khi tạo nhiều ca; theo dõi dung lượng và sao lưu.

### 16.4. Tắt và mở lại

- Bấm dừng video nếu muốn dừng xem.
- Đóng tab không nhất thiết dừng server.
- Ctrl+C ở PowerShell đang chạy Uvicorn để tắt server.
- Muốn mở lại, chạy lệnh Uvicorn ở mục 2.3.
- Nếu đổi cổng, dùng địa chỉ mới tương ứng; URL cũ cần sửa cổng.

## 17. Xử lý sự cố và câu hỏi thường gặp

| Hiện tượng / câu hỏi | Cách kiểm tra hoặc giải thích |
|---|---|
| Không mở được localhost | Server phải còn chạy. Kiểm tra dòng Uvicorn và cổng 8767; không mở index_v3.html trực tiếp bằng file:// |
| PowerShell báo không tìm thấy .venv hoặc app | Kiểm tra đang ở thư mục gốc và đã tạo môi trường; dùng --app-dir pose_focus_demo |
| Cổng đang được sử dụng | Có thể server đã chạy. Thử mở web trước; nếu cần dùng cổng khác, chạy --port 8768 và mở localhost:8768 |
| Trang cũ, thiếu Lịch sử/biểu đồ mới | Ctrl+F5, kiểm tra server chạy từ đúng bản tích hợp |
| Video không phát | Kiểm tra MP4 đầy đủ, Git LFS và trình duyệt H.264; kiểm tra tài nguyên không phải con trỏ văn bản |
| Web báo không có ca | URL đang chỉ ID không thuộc database hiện tại. Mở trang gốc hoặc khôi phục đúng database |
| Lỗi quyền ghi/SQLite | Kiểm tra DENSO_DEMO_DB và quyền ghi thư mục lưu; không đặt DB trong thư mục nguồn chỉ đọc |
| Thêm lỗi bị từ chối | Tối đa 8 kịch bản; đúng mốc/loại, cường độ, seed; bắt đầu + kéo dài phải trong clip |
| Đổi cường độ nhưng kịch bản cũ không đổi | Thanh cường độ chuẩn bị lỗi mới. Bỏ lỗi cũ rồi thêm lại nếu muốn thay |
| Cảm biến in trong video không đổi khi tiêm lỗi | Đó là dữ liệu nguồn đã dựng sẵn. Xem nhóm B/C what-if để thấy kịch bản web |
| Có đỉnh rung nhưng không có cảnh báo | Cần tổ hợp điểm đa nguồn, 3 frame liên tiếp và đủ chất lượng; không có ngưỡng mm/s cố định trong demo |
| Rung thấp hơn đỉnh lớn nhưng đã cảnh báo | So với nền học và các kênh khác; xem mục 10 |
| Ngoài vùng xanh vẫn có đỉnh cao | Log/cảnh báo chỉ tô sự kiện đang chọn; đoạn ngữ cảnh có thể chứa sự kiện khác |
| Xóa lỗi rồi vẫn có cảnh báo | “Không tiêm lỗi” khác “mô hình chắc chắn không báo”. Nhiễu/thay đổi môi trường có thể gây báo giả |
| Một lỗi có nhiều log | Detector hiện tách đợt khi điểm/quality xuống điều kiện; chưa gộp bằng khoảng chờ |
| Số góc không đổi khi chọn L4 | J là lựa chọn độc lập. Đổi Khớp cơ khí để xem góc khác |
| Có “—”, KHUẤT hoặc đường bị ngắt | Thiếu mốc/giá trị hoặc đoạn nối montage không hợp lệ; không tự coi là 0 |
| Thấy chênh nhiệt rất lớn bằng mắt | Đọc trục °C; biểu đồ có thể chỉ trải một khoảng nhỏ |
| Bấm Xem log không tua video | Đây là hành vi đúng: con trỏ lịch sử độc lập |
| Lịch sử rỗng | Kiểm tra bộ lọc, database và ca có cảnh báo; mở ca cũ để tạo snapshot nếu chưa có |
| Không lưu được xác nhận | Cần kỹ thuật viên và việc đã làm; dự đoán sai cần nguyên nhân thực tế |
| Xác nhận đúng rồi AI vẫn cao | Kết luận không sửa bằng chứng cũ hoặc tự huấn luyện lại |
| Benchmark chưa có biểu đồ | Chạy benchmark, đợi xong, kiểm tra trạng thái lỗi và research_artifacts |
| Ca test khác seed ma trận | Ca test có ID riêng. Chọn s19/s41/s73 tương ứng nếu muốn so cùng seed |
| Recall tốt nhưng báo giả cao | Mô hình còn hạn chế khi đổi điều kiện; cần đọc đầy đủ chỉ số, không tuyên bố sẵn sàng nhà máy |
| Chạy web có huấn luyện lại pose không? | Không. Web đọc dự đoán pose đã đóng gói. Tái suy luận HoRoPose là quy trình riêng |
| Lưu phản hồi có làm AI tự học không? | Không. Dữ liệu phản hồi được giữ để dùng trong quy trình cải tiến/huấn luyện sau này |

## 18. Thuật ngữ và tài liệu liên quan

| Thuật ngữ | Ý nghĩa trong hệ thống |
|---|---|
| Pose | Tư thế robot; dashboard thể hiện keypoint 2D và góc dự đoán |
| Landmark / keypoint | Mốc hình ảnh theo quy ước L0…EE |
| q1–q7 | Góc của 7 khớp mô hình |
| HoRoPose | Mô hình dự đoán pose robot; kết quả đã được suy luận trước |
| DREAM | Nguồn ảnh RGB và nhãn đối chiếu của robot |
| What-if | Tình huống giả định nếu lỗi xảy ra |
| Baseline / đường nền | Dữ liệu đối chứng bình thường mô phỏng |
| Residual / phần dư | Sai khác phép đo với mức bình thường mô hình dự kiến |
| Seed | Tham số tái lập ngẫu nhiên |
| Run / ca chạy | Một cấu hình với timeline, cảnh báo và snapshot riêng |
| Incident / sự kiện | Một đợt cảnh báo được detector ghi nhận |
| Snapshot | Bản chụp cố định toàn bộ dữ liệu ca |
| Ground truth | Nhãn đối chiếu; trong benchmark là nhãn của bộ sinh, không phải xác nhận thực địa |
| Jerk | Đạo hàm bậc ba của vị trí/góc theo thời gian |
| Ablation | Thử bỏ/bổ sung nguồn dữ liệu để so ảnh hưởng |
| Sim-to-real | Chuyển từ mô phỏng sang thực tế; chưa được kiểm chứng trong demo |

Tài liệu liên quan:

- [README](README.md): cấu trúc, cài đặt tài nguyên và tái lập checkpoint → pose → video.
- [RESEARCH_GUIDE](RESEARCH_GUIDE.md): lệnh sinh/huấn luyện/đánh giá, mô hình và phạm vi benchmark.
- [VIDEO_PROVENANCE](VIDEO_PROVENANCE.md): nguồn gốc video và bằng chứng tái lập.
- [ENVIRONMENT_VERIFIED](ENVIRONMENT_VERIFIED.md): môi trường đã kiểm tra.
- [README dashboard](pose_focus_demo/README.md): tài liệu kỹ thuật của dashboard; với detector v3 và log, đối chiếu thêm RESEARCH_GUIDE.
- Mã lưu log: pose_focus_demo/event_store.py.
- Mã phát hiện dashboard hiện tại: pose_focus_demo/engine_v3.py.
- Bộ sinh nghiên cứu: research_pipeline/physics.py.

**Nguyên tắc khi trình bày:** luôn nói rõ nguồn nào là ảnh/dự đoán, nguồn nào mô phỏng; phân biệt bất thường tín hiệu với hỏng hóc đã xác nhận; đọc cả báo giả/bỏ sót và giữ bằng chứng theo ca.
