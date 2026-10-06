# Hướng dẫn sử dụng web — Franka Pose Observatory

Tài liệu này dành cho người trình diễn demo, người xem dashboard và kỹ thuật viên thử quy trình xác nhận cảnh báo. Web phát lại **16,67 giây clip Franka Panda** ở 30 khung hình/giây. Mã, checkpoint, ảnh RGB DREAM và dự đoán HoRoPose nằm trong `panda_repro/`; dashboard đọc trực tiếp keypoint và q1–q7 đã suy luận từ NPZ theo đúng frame video. Cảm biến và cảnh báo là mô phỏng ngoại tuyến. Không có kết nối đến robot hoặc cảm biến nhà máy. Xem [ghi chép nguồn gốc video](VIDEO_PROVENANCE.md).

## 1. Mở ứng dụng

Làm theo phần **Chạy trên Windows** trong [README chính](README.md), sau đó mở <http://127.0.0.1:8767/>. Giữ cửa sổ PowerShell chạy máy chủ trong lúc sử dụng web. Thanh điều hướng đầu trang đưa đến **Tổng quan**, **Biểu đồ**, **Mô phỏng** và **Bảo trì**.

Nếu được cung cấp một địa chỉ localhost khác khi trình diễn, dùng địa chỉ đó; các thao tác trên giao diện vẫn giống nhau.

## 2. Quan sát video và chọn mốc pose

Trong mục **Camera & Pose**:

- Bấm **▶ / Ⅱ** để phát hoặc tạm dừng. Kéo thanh tua để chọn thời điểm; chọn `0.5×`, `1×`, `1.5×` hoặc `2×` để đổi tốc độ phát.
- Đồng hồ **THỜI ĐIỂM VIDEO** cho biết giây và số frame đang xem. Video là đồng hồ chung: giá trị tức thời, vạch trên biểu đồ, pose và quỹ đạo giả lập cùng đổi theo frame đó.
- Dòng **x / 7 MỐC** cho biết số keypoint dự đoán nằm trong vùng video ở frame hiện tại. Mốc nằm ngoài vùng hình hiện **KHUẤT**.
- Trong **Cấu trúc cánh tay**, bấm `L0`, `L2`, `L3`, `L4`, `L6`, `L7` hoặc `EE` để chọn vùng theo dõi. Đây là tên keypoint; biểu đồ **q1–q7** là góc khớp AI dự đoán, không phải góc encoder Franka.

Khung **Tại khung hình hiện tại** cho tọa độ ảnh `X/Y`, góc khớp AI của mốc chọn, độ phủ và mã ảnh DREAM/chu kỳ. Chọn biểu đồ tốc độ để xem dịch chuyển ảnh `px/s`; giá trị này không phải tốc độ quay động cơ. Khung **Trạng thái mô phỏng** cho biết tham số lỗi và nhiệt tích lũy giả định.

## 3. Đọc các biểu đồ đồng bộ

Chọn một mốc trước khi đọc biểu đồ. Hầu hết biểu đồ thay đổi theo mốc; bấm vào vị trí trên biểu đồ thời gian để tua video đến giây tương ứng. Vạch đen chỉ frame đang xem.

| Nhóm | Biểu đồ | Cách đọc |
|---|---|---|
| AI từ ảnh DREAM | Quỹ đạo mốc, tốc độ 2D, khác biệt tư thế, độ phủ, góc khớp q và sai số keypoint | q và keypoint từ checkpoint HoRoPose đã chạy; đường nhãn DREAM dùng đối chiếu. Không có encoder thật. |
| Mô phỏng trong video nguồn | Rung, âm, nhiệt, dòng điện J4 | Giá trị CSV khớp đúng số đã vẽ vào video theo từng frame; không phải phép đo thật. |
| Cảm biến what-if giả lập | Rung RMS, nhiệt độ, âm thanh | Tạo theo kịch bản web; đường nền là trạng thái bình thường *giả lập*. Có thể khác số mô phỏng đã in trong video nguồn. |
| Tác động giả lập | Chênh pose dự kiến, trễ chuyển động | Mô tả tình huống “nếu lỗi xảy ra” so với pose quan sát. Không phải sai lệch thật đã đo. |
| Phát hiện | Điểm bất thường, vùng cảnh báo | Điểm và vùng tô được tính từ tín hiệu mô phỏng cho mốc đang chọn; `0–100` là thang minh họa, không phải xác suất hỏng. |

Trên biểu đồ quỹ đạo, đường xanh là pose HoRoPose từ ảnh nguồn; đường đứt là quỹ đạo what-if. Khi đổi mốc hoặc tua video, các biểu đồ AI và cảm biến trong video nguồn cùng nhảy tới bản ghi có cùng timestamp.

## 4. Tạo và so sánh ca lỗi trong phòng mô phỏng

Mở **Mô phỏng** và làm theo thứ tự:

1. Chọn **Nguyên nhân**: ổ bi/truyền động, ma sát/bôi trơn, suy giảm tản nhiệt, độ rơ/sai tư thế, đáp ứng chậm hoặc trôi cảm biến rung.
2. Chọn **Mốc theo dõi** và nhập **Bắt đầu (s)**, **Kéo dài (s)** trong khoảng video. Đặt **Cường độ** để thay đổi mức tác động giả lập.
3. Đặt **Seed mô phỏng** nếu cần lặp lại đúng một ca; đổi **Tải giả định** để thay đổi đường nền vận hành.
4. Bấm **+ Thêm kịch bản**. Giao diện tạo một ca mới rồi cập nhật đường tín hiệu, điểm bất thường và danh sách cảnh báo. Một ca có tối đa tám kịch bản.

Danh sách ngay dưới các nút cho biết lỗi, mốc và khoảng thời gian đã thêm; bấm dấu **×** của một mục để bỏ riêng kịch bản đó. **Xóa lỗi** tạo ca nền giả lập không tiêm lỗi. **Về kịch bản mẫu** tạo lại hai lỗi minh họa: ổ bi/truyền động và độ rơ/sai tư thế. Đổi seed hoặc tải sau khi nhập sẽ tạo ca mới với cùng danh sách lỗi.

Tất cả thao tác này chỉ biến đổi **bản ghi what-if**; video, dự đoán HoRoPose và cảm biến đã vẽ trong video nguồn giữ nguyên. Nút **Giải thích chi tiết cách sinh và phát hiện lỗi** mô tả quy tắc của từng loại lỗi. Lỗi quá nhẹ hoặc diễn ra khi mốc ít chuyển động có thể không tạo cảnh báo.

## 5. Xem cảnh báo và ghi kết luận bảo trì

Ở mục **Bảo trì**, bấm tên một cảnh báo. Web sẽ chọn mốc liên quan, tua video đến thời điểm tín hiệu đạt đỉnh và mở phần chi tiết gồm bằng chứng, giả thuyết nguyên nhân, các bước nên kiểm tra. Nhãn **SIM** nhắc rằng đây là cảnh báo từ dữ liệu mô phỏng.

Để thử vòng phản hồi:

1. Chọn **Dự đoán đúng** hoặc **Dự đoán sai**.
2. Nhập **Kỹ thuật viên** và **Việc đã làm**; đây là hai trường bắt buộc.
3. Nếu chọn **Dự đoán sai**, nhập thêm **Nguyên nhân thực tế**.
4. Bấm **Lưu xác nhận**. Trạng thái đổi thành **ĐÃ XÁC NHẬN** và hiện thời gian lưu. Có thể mở lại để sửa kết luận cho cùng cảnh báo.

Phản hồi được lưu trong SQLite theo **ca chạy + cảnh báo**. Khi tạo một ca mô phỏng mới, kết luận ở ca trước không tự chuyển sang ca mới. Để bảo trì robot thật, kỹ thuật viên vẫn cần kiểm tra theo quy trình nhà máy và tài liệu của đúng model robot.

## 6. Tải dữ liệu

- **Xuất CSV** ở góc trên tải timeline của **ca đang xem**, gồm mã ảnh nguồn, chu kỳ, góc q AI, nhãn DREAM đối chiếu, các kênh mô phỏng đã in trong video và kênh what-if. Tên cột phân biệt `pred`, `reference` và `sim`.
- **Tải 20 ca mô phỏng** tải ZIP chứa 20 CSV và `manifest.json`. Các ca khác nhau về seed, tải, loại lỗi và cường độ; có cả ca nền. Tệp này dùng để thử luồng phần mềm ngoại tuyến, không phải tập lỗi thật và không dùng để báo cáo độ chính xác tại nhà máy.

## 7. Quy trình trình diễn trong 3 phút

1. Mở web, phát video, chọn mốc `L4`; chỉ ra pose quan sát và đồng hồ chung.
2. Bấm biểu đồ rung tại khoảng giây thứ 6; chỉ ra video tua cùng biểu đồ, rồi mở cảnh báo ổ bi/truyền động.
3. Xem bằng chứng rung + âm, giả thuyết và các bước kiểm tra. Giải thích rằng các kênh này đang mô phỏng.
4. Chọn **Xóa lỗi**, quan sát ca nền; sau đó chọn **Về kịch bản mẫu** hoặc thêm một lỗi **Đáp ứng chậm** để so sánh.
5. Lưu một kết luận thử nghiệm, rồi **Xuất CSV** để xem dấu nguồn của từng cột.

## 8. Khi web không hoạt động như mong đợi

| Hiện tượng | Kiểm tra |
|---|---|
| Trang không mở | Kiểm tra lệnh Uvicorn còn chạy và dùng đúng địa chỉ/cổng được in trong PowerShell. |
| Có trang nhưng video không hiện | Kiểm tra `pose_focus_demo/robot_original.mp4` còn trong thư mục và tải lại trang. |
| Báo lỗi `unable to open database file` | Bản `app.py` cũ đang cố ghi SQLite trong thư mục mã nguồn chỉ đọc. Cập nhật bằng gói mới; bản mới lưu dữ liệu tại `%LOCALAPPDATA%\DENSO`. |
| Một mốc hiện **KHUẤT** hoặc giá trị **—** | Mốc không quan sát được ở frame đó hoặc đặc trưng chưa xác định; tua sang đoạn khác. |
| Không xuất hiện cảnh báo | Kiểm tra đã thêm lỗi, chọn đúng mốc và thử thời điểm/cường độ khác. Không có cảnh báo không chứng minh robot thật an toàn. |

Tài liệu về cơ chế sinh và phát hiện lỗi nằm trong [README kỹ thuật](pose_focus_demo/README.md). Demo chưa có dữ liệu cảm biến/controller trực tiếp, đồng bộ đồng hồ thiết bị hay mô hình bảo trì đã được kiểm chứng trên robot nhà máy.
