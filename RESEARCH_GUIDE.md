# Pipeline nghiên cứu sinh dữ liệu và phát hiện bất thường v3

Tài liệu kỹ thuật cho mã nguồn; không cập nhật báo cáo đồ án.

Để học cách vận hành giao diện, đọc [hướng dẫn sử dụng web từ A–Z](HUONG_DAN_SU_DUNG_WEB.md). Tài liệu đó giải thích từng biểu đồ, quan hệ giữa các phần, mốc pose/khớp độc lập, cảnh báo, log, xuất dữ liệu và các bài thực hành.

## Chuẩn bị môi trường

Python 3.12. Chạy tại thư mục gốc repository, nơi có README và `research_pipeline/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Pipeline nghiên cứu chạy bằng CPU, không cần tải thêm checkpoint HoRoPose hoặc có GPU.
Dashboard dùng video và dự đoán đã đóng gói. Tái suy luận HoRoPose vẫn dùng môi trường riêng trong README.

## Chạy toàn bộ thí nghiệm

```powershell
.\.venv\Scripts\python.exe -m research_pipeline benchmark --seeds 19,41,73 --scarce 3 --extra 12 --output research_artifacts
.\.venv\Scripts\python.exe -m uvicorn app:app --app-dir pose_focus_demo --host 127.0.0.1 --port 8767
```

Mở http://127.0.0.1:8767 và chọn **Đánh giá AI**. Nút **Chạy benchmark 3 seed** chạy cùng pipeline bằng môi trường Python của server; có trạng thái đang chạy và lỗi. Dữ liệu benchmark có đồng hồ riêng, không phải bản ghi cảm biến kèm video.

## Chạy từng bước / tái lập

```powershell
.\.venv\Scripts\python.exe -m research_pipeline generate --seed 19 --scarce 3 --extra 12 --output research_artifacts
.\.venv\Scripts\python.exe -m research_pipeline train --seed 19 --output research_artifacts
.\.venv\Scripts\python.exe -m research_pipeline evaluate --output research_artifacts
.\.venv\Scripts\python.exe -m research_pipeline export --seed 19 --output research_artifacts
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s pose_focus_demo -p test_engine_v2.py -v
```

`train` huấn luyện, chọn ngưỡng trên validation rồi đánh giá test. `evaluate` tổng hợp các kết quả đã lưu, không huấn luyện lại. `export` xuất CSV theo chu kỳ, timestamp và khớp; mỗi hàng có nguồn `synthetic`.

Nếu chỉ đổi đặc trưng/mô hình và muốn giữ nguyên dataset đã tạo:

```powershell
.\.venv\Scripts\python.exe scripts\retrain_research.py research_artifacts
```

Thử nhiều mức thiếu dữ liệu bằng các thư mục riêng, ví dụ `--scarce 1 --output research_artifacts_low1`. Đổi nơi dashboard đọc bằng biến môi trường `DENSO_RESEARCH_DIR` trước khi chạy server.

## Cấu trúc đầu ra

```text
research_artifacts/
  benchmark.json                 # toàn bộ kết quả, seed, giới hạn kiểm chứng
  comparison.csv                 # trung bình / độ lệch chuẩn của A/B/C
  seed_19/
    dataset/manifest.json        # ID, split, seed, đơn vị, trạng thái chất lượng, SHA-256
    dataset/s19-*.npz            # đo ảo + lệnh tham chiếu + nhãn đánh giá
    models/A_original.joblib
    models/B_simple.joblib
    models/C_physics.joblib
    models/isolation.joblib
    models/metrics.json
    timeseries.csv               # khi chạy export
```

Mỗi seed mặc định có 48 ca bình thường và 3 ca lỗi cho mỗi loại trong train; validation có 16 ca bình thường và 3 ca mỗi loại; test có 16 ca bình thường và 6 ca mỗi loại. Physics thêm 24 ca bình thường và 12 ca mỗi loại lỗi. B thêm đúng cùng số ca theo lớp với C. Nhãn gồm normal, bearing, friction, thermal, backlash, slow, sensor_drift, encoder_error.

## Mô hình sinh dữ liệu

`research_pipeline/physics.py` mô tả bảy servo tương đương độc lập, không phải mô hình động lực học đầy đủ hoặc thông số OEM Panda.

- Mô men điều khiển: sai số vị trí và vận tốc hồi tiếp, có giới hạn.
- Gia tốc: mô men trừ lực cản ma sát, chia quán tính tương đương có tải.
- Ma sát: phần Coulomb được làm trơn và phần nhớt. Lỗi tăng cả lực cản và nhiệt tổn hao.
- Độ rơ: deadband tại đầu ra theo chiều chuyển động; encoder phía truyền động và camera ảo được lưu riêng.
- Nhiệt: `T_next = T + dt*(P_loss - cooling*(T - ambient))/capacity`. Công suất gồm I²R và công ma sát. Sau can thiệp ảo, nhiệt còn nguội dần.
- Bearing: cùng chuỗi xung ảnh hưởng envelope rung và âm; có nhiệt bổ sung.
- Slow: giảm giới hạn mô men. Có thể khó thấy nếu tải/quỹ đạo không cần đến giới hạn đó; benchmark vẫn ghi nhận ca bỏ sót.
- Sensor drift / encoder error: thay phép đo, không thay cơ học. Nhiễu chung tạo các điều kiện bình thường khó phân biệt.
- Transient / progressive / intermittent thay lịch tác động. Kết thúc lịch được hiểu là can thiệp sửa chữa ảo, không phải robot tự lành.

Rung và âm là **envelope tổng hợp**, không phải waveform lấy mẫu cao tần. Không suy luận phổ ổ bi từ các giá trị này. Kiểm tra chất lượng chỉ kiểm tra hữu hạn, đơn vị/thời gian/kích thước, biên surrogate và tín hiệu không âm; không chứng nhận giống robot thật.

## Đặc trưng và phát hiện

`features.py` dùng cửa sổ 1,4 s, bước 0,4 s. Các đặc trưng RMS, p90, std của phép đo, sai lệch camera–encoder, sai lệch camera–lệnh và đạo hàm chuyển động; có thống kê giữa các khớp để giúp học khi ít ca lỗi. Ambient/load là ngữ cảnh đầu vào đã biết trong mô phỏng. **Không đưa nhãn, faulty_joint, severity, truth, lịch tiêm hay baseline lý tưởng vào X.** Các cửa sổ thuộc cùng chu kỳ giữ cùng split.

ExtraTrees có 120 cây, leaf tối thiểu 2, class_weight balanced. A/B/C dùng cùng cấu hình và cùng test. Ngưỡng bình thường/bất thường chọn theo binary F1 trên validation. Isolation Forest có 120 cây, học **chỉ ca bình thường train**; ngưỡng là percentile 99 của score trên validation bình thường. Cảnh báo cần hai cửa sổ liên tiếp. Đặc trưng mỗi cửa sổ không đọc mẫu ở tương lai của timestamp đó.

Test thay tải (1,15–1,65 so với 0,6–1,2 của train), tốc độ (0,22–0,32 so với 0,13–0,22 Hz), nhiễu và harmonic. Train/test vẫn chia sẻ phương trình bộ sinh. Đây là thử nghiệm tổng quát trong mô phỏng, không phải kiểm chứng sim-to-real.

## Dashboard đồng bộ video

`engine_v3.py` dùng chung các hàm envelope, thermal_step và sensor_sample. Nền cảm biến được Ridge học từ 10 ca phát lại bình thường mô phỏng ở nhiều tải/môi trường; Isolation Forest học phần dư cảm biến và sai lệch hình chiếu. Ngưỡng percentile 99,5 dùng 4 ca validation bình thường độc lập. Không dùng nền đối chứng xám làm đầu vào detector. Cần 3 frame liên tiếp để xác nhận cảnh báo. Điểm 0–100 là biến đổi score, **không phải xác suất hỏng**; ngưỡng hiển thị 50.

Các kênh what-if ở đây gắn **vùng landmark**, chưa gắn cảm biến vật lý tới J1–J7. Chọn mốc ảnh và khớp q là hai điều khiển độc lập. Không dùng nhãn DREAM hoặc lỗi keypoint GT để ra quyết định cảnh báo. Pose/checkpoint/source_sim trong video được giữ nguyên; source_sim là phần dựng sẵn, còn kịch bản what-if v3 là lớp riêng.

Vận tốc/gia tốc/jerk q tính bằng sai phân lùi bậc 1/2/3 với dt=1/FPS. Điểm nối montage bị bỏ giá trị đạo hàm. Nhãn pha và thời gian pha chỉ mô tả **bản phát lại 120 ảnh lặp/giữ frame**, chưa phải thời gian robot thực. Quỹ đạo what-if so với pose làm nền thử nghiệm; không được xem như quỹ đạo lệnh robot.

## Đọc kết quả đúng phạm vi

### Nhật ký pose và cảm biến bất thường

`pose_focus_demo/event_store.py` lưu snapshot JSON nén bằng zlib vào SQLite, kèm SHA-256 và checksum video/pose nguồn. `evidence_runs` giữ toàn ca bất biến; `anomaly_events` lập chỉ mục các sự kiện; `maintenance_audit` lưu các lần xác nhận nối tiếp. Ca mới được lưu khi tạo, ca cũ được lưu khi mở lần đầu. Các lần đọc sau không chạy lại detector. Mỗi sự kiện có một ID log riêng và không bị nhân bản khi tải lại.

Các API: `GET /api/history?run_id=...&status=all&limit=20&offset=0`, `GET /api/history/{id}`, `GET /api/history/{id}/export.json` và `/export.csv`. Cửa sổ xuất gồm khoảng cảnh báo cùng tối đa 1 giây mỗi bên, có tất cả pose/cảm biến ở từng frame. `saved_at_utc` là thời gian lưu phân tích ngoại tuyến; `t`/`t_s` là thời gian video. Không được gọi chúng là timestamp thu nhận thật tại nhà máy.

DB mặc định là `%LOCALAPPDATA%\DENSO\pose_demo.sqlite3` (hoặc biến `DENSO_DEMO_DB`). Giao diện **Lịch sử** đọc bản ghi đó, lọc/phân trang, chọn frame và xuất dữ liệu. Kết luận bảo trì có lịch sử cập nhật riêng; không thay bằng chứng ban đầu. Chưa có chính sách tự xóa/retention; cần sao lưu và quản lý dung lượng khi dùng lâu dài.

### Các chỉ số đánh giá

- Macro-F1: trung bình các lớp ở mức cửa sổ. PR-AUC: phát hiện normal/fault.
- Event recall: tỷ lệ ca lỗi có **đợt cảnh báo mới** được xác nhận sau khi lỗi bắt đầu và tại cửa sổ còn lỗi. Cảnh báo đã bật trước lúc tiêm không được tính là phát hiện. Ngắt quãng được tính một ca, không từng xung.
- Trễ: từ lúc tiêm đến cảnh báo xác nhận đầu tiên, median chỉ trên ca phát hiện được; số ca bỏ sót hiển thị riêng.
- Báo giả/giờ: số đợt cảnh báo trên **ca hoàn toàn bình thường**, chia thời gian quan sát sau warm-up. Quy đổi từ clip ngắn nên chưa đại diện ca nhà máy.
- Độ lệch chuẩn: giữa các seed, không phải khoảng tin cậy thực địa.
- Kết quả có thể không cải thiện ở từng seed. Không tự lựa chọn chỉ seed tốt.

Trọng số lỗi lịch sử trong `panda_repro/artifacts/fault_model.joblib` học bộ sinh sáu khớp cũ. Các script dựng video đọc schema legacy để giữ khả năng tái lập. Mã `faults.extract_features` mới sửa jerk bậc ba theo giây; huấn luyện lại `train_fault.py` lưu schema mới rõ ràng. Benchmark v3 dùng bộ sinh bảy khớp riêng và không dùng con số 100% lịch sử làm hiệu năng nhà máy.

Chưa thêm GAN/Diffusion, chưa có dữ liệu lỗi thật hoặc RUL. Pipeline hiện có baseline và kiểm thử để đo giá trị bổ sung khi triển khai mô hình sinh ở giai đoạn tiếp theo.

## Kết quả chạy kiểm tra ngày 07/10/2026

Đã tạo 816 ca qua ba seed 19, 41, 73, trong đó có 174 ca test. Kết quả dùng Python 3.12.10, NumPy 2.5.2, scikit-learn 1.9.1 và joblib 1.6.0; phiên bản được lưu trong `benchmark.json`.

| Nhóm | Macro-F1, trung bình ± độ lệch chuẩn |
|---|---|
| A: ít dữ liệu lỗi ban đầu | 0,167 ± 0,031 |
| B: tăng cường đơn giản | 0,169 ± 0,006 |
| C: bổ sung ca mô phỏng vật lý | 0,279 ± 0,065 |

C tăng 11,17 điểm phần trăm so với A. Recall sự kiện của C khoảng 65,9%; trung bình median trễ theo seed khoảng 0,69 s trên các ca phát hiện được. Mức báo giả quy đổi khoảng 427 đợt/giờ trên các clip bình thường ngắn khi đổi điều kiện vận hành. Các kết quả này cho thấy cần xử lý thay đổi miền và hiệu chuẩn trước khi thử tại nhà máy; không thể sử dụng trực tiếp làm hệ thống cảnh báo sản xuất. Xem `comparison.csv` và dashboard để kiểm tra cả kết quả kém và ca bỏ sót.

12 kiểm thử mới đã đạt, gồm đạo hàm jerk theo giây, tách lỗi phép đo khỏi trạng thái cơ học, checksum, chia dữ liệu theo ca, không đọc nhãn vào đặc trưng, xác nhận bảo trì và đối chiếu chính xác điểm/thời gian cảnh báo trên biểu đồ với kết quả benchmark. Biểu đồ giữ nguyên kích thước khi phát video; màn hình hẹp không làm tràn chiều ngang trang.

Checkpoint `fault_model.joblib` lịch sử được tạo bằng scikit-learn 1.8.0. Kiểm tra tương thích trên môi trường mới đã chạy được nhưng có cảnh báo khác phiên bản. Khi tái lập riêng mô hình lịch sử, dùng môi trường của gói `panda_repro` với scikit-learn 1.8.0; khi chạy nghiên cứu v3, dùng các phiên bản trong `requirements.txt` gốc và các model v3 đã huấn luyện lại.
