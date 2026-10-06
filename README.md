# DENSO 2026 · Giám sát pose Franka Panda và mô phỏng bảo trì

Đây là hệ thống trình diễn chạy **ngoại tuyến**. Ảnh RGB của robot Franka Panda, checkpoint HoRoPose, mã suy luận, dự đoán q1–q7/pose 6D/keypoint và mã dựng video nằm trong `panda_repro/`, được giải nén từ `Panda_HoRoPose_Full_Repro.zip`. Dashboard trong `pose_focus_demo/` phát lại video và dùng trực tiếp kết quả HoRoPose đã lưu; mọi giá trị cùng bám timestamp `frame / 30`.

**Ranh giới dữ liệu:** ảnh RGB và nhãn đối chiếu thuộc tập DREAM; q1–q7 và keypoint là **dự đoán AI**, không phải encoder robot. Rung, âm thanh, nhiệt, dòng điện, trễ chu kỳ, sự cố và quỹ đạo what-if là **mô phỏng**. Chưa có camera hoặc cảm biến nối với robot nhà máy.

**Báo cáo đồ án:** [Thiết kế hệ thống giám sát tư thế robot và mô phỏng cảnh báo bảo trì đa cảm biến](BAO_CAO_DO_AN.md) trình bày cơ sở khoa học, kiến trúc, thông số, cơ chế sinh/phát hiện lỗi, kết quả kiểm chứng, giới hạn và hướng thí điểm.

## Cấu trúc

| Đường dẫn | Vai trò |
|---|---|
| `panda_repro/data/panda_realsense/` | 120 ảnh RGB 480×640 và annotation DREAM `002640..002759` |
| `panda_repro/checkpoints/horopose_panda_realsense_inference.pk` | Trọng số HoRoPose Panda, 2.308 tensor, khoảng 320 MB |
| `panda_repro/vendor/holistic_pose/` | Mã HoRoPose upstream được đóng gói |
| `panda_repro/src/robot_demo/horopose_panda.py` | Nạp checkpoint, suy luận pose, hiệu chỉnh q từ 30 nhãn đầu, ghi NPZ/metrics |
| `panda_repro/src/robot_demo/make_panda_video.py` | Dựng video 500 frame, CSV cảm biến mô phỏng và sự kiện |
| `panda_repro/artifacts/` | NPZ dự đoán, CSV thời gian, mô hình lỗi, video, metrics và SQLite mẫu |
| `pose_focus_demo/import_horopose.py` | Kiểm tra hash, ánh xạ 120 scene ID sang 500 frame, ghi `pose_recording.json` |
| `pose_focus_demo/` | FastAPI, dashboard, biểu đồ, phòng mô phỏng, cảnh báo và phản hồi bảo trì |

Thư mục `horopose_upstream/` là Git submodule tham khảo của công trình gốc; `panda_repro/vendor/holistic_pose/` giúp gói tái lập chạy ngay cả khi chưa lấy submodule.

## Chạy dashboard

Yêu cầu Windows/Linux/macOS, Python 3.12, Git LFS và trình duyệt hỗ trợ H.264. Nếu lấy từ GitHub, tải cả trọng số và video LFS trước:

```powershell
git clone https://github.com/manhhung-25/DENS0-2026.git
Set-Location DENS0-2026
git lfs install
git lfs pull
```

Sau đó, trên PowerShell tại thư mục chứa README:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe pose_focus_demo\import_horopose.py
Set-Location pose_focus_demo
..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8767
```

Mở <http://127.0.0.1:8767/>. Nếu chỉ muốn phát lại bản đã đóng gói, không cần chạy `import_horopose.py` mỗi lần. Dashboard vẫn mở khi không cài PyTorch: nó dùng kết quả suy luận đã lưu. Phản hồi kỹ thuật viên nằm trong SQLite ở `%LOCALAPPDATA%\DENSO\pose_demo.sqlite3` trên Windows; có thể đổi nơi lưu bằng `DENSO_DEMO_DB`.

Xem [hướng dẫn sử dụng web](HUONG_DAN_SU_DUNG_WEB.md) để phát video, chọn khớp, đọc biểu đồ, tạo ca mô phỏng và xác nhận cảnh báo.

Các phiên bản đã chạy và lệnh kiểm tra chi tiết được ghi trong [môi trường đã xác minh](ENVIRONMENT_VERIFIED.md).

## Tái lập AI → dự đoán → video

Để kiểm chứng từ checkpoint và ảnh RGB, tạo **môi trường Python riêng** cho gói nghiên cứu. Trên PowerShell:

```powershell
Set-Location panda_repro
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m robot_demo.horopose_panda --batch-size 4 --output artifacts\verification\panda_pose_predictions.npz
.\.venv\Scripts\python.exe -m robot_demo.make_panda_video --predictions artifacts\verification\panda_pose_predictions.npz --output artifacts\verification\reproduced.mp4 --fault-model artifacts\fault_model.joblib --events artifacts\verification\events.db
```

Hai lệnh cuối tạo kết quả mới trong `artifacts/verification/`, giữ nguyên các artifact đã giao để đối chiếu hash. `pose_focus_demo/import_horopose.py` nạp bản gốc đã kiểm tra hash. `make_panda_video.py` tự ánh xạ các đường dẫn ảnh tuyệt đối cũ trong NPZ sang `data/panda_realsense/` tại máy hiện tại.

Trên Linux/WSL2, thay lệnh kích hoạt Python bằng `python3 -m venv .venv`, `source .venv/bin/activate`, `export PYTHONPATH="$PWD/src"`, rồi gọi `python -m ...`. Quá trình suy luận CPU có thể chậm; GPU cần phiên bản PyTorch tương thích máy. Checkpoint được nạp với `weights_only=True` và `strict=True`.

## Bằng chứng đã kiểm tra trên máy hiện tại

| Kiểm tra | Kết quả |
|---|---:|
| ZIP video so với file `.crdownload` ban đầu | Cùng SHA-256 `c91552e2…c21ac02e` |
| Checkpoint trong gói | SHA-256 `9c531ede…38026c181c3c`; nạp 2.308 tensor, epoch 76 |
| Suy luận lại từ checkpoint + 120 ảnh | 120/120 thành công, `strict=True` |
| Sai số q1–q7 trung bình sau hiệu chỉnh 30 nhãn đầu, lần chạy lại | 5,529° trên các frame DREAM này |
| Sai số keypoint 2D sau lọc thời gian, lần chạy lại | 7,554 pixel so với nhãn DREAM |
| Video dựng lại từ suy luận mới | 500 frame, 1280×720, 30 fps; chẩn đoán mô phỏng J4 được sinh |
| Predicted keypoint trong NPZ so với mốc cyan dashboard cũ | Sai khác trung vị 0,44 pixel tại các mốc nhận được |

Số q/keypoint của lần chạy lại hơi khác file đã giao do phiên bản PyTorch/NumPy. Video mới khác hash do phiên bản FFmpeg/encoder và nội dung sự kiện; các frame so sánh giống nhau ở mức hình ảnh, sai khác pixel trung bình khoảng 4–5/255. Xem [bằng chứng và giới hạn nguồn video](VIDEO_PROVENANCE.md) cùng `panda_repro/PANDA_BUILD_MANIFEST.md`.

## Cơ chế đồng bộ và mô phỏng

1. Mỗi dòng CSV nguồn có `frame`, `time_s`, `source_frame` và `cycle`; file NPZ dùng `scene_id` để lấy q, pose và 7 keypoint đúng ảnh nguồn. `import_horopose.py` chuyển keypoint từ ảnh 640×480 sang vùng video 840×646 và ghi 500 bản ghi.
2. Video dùng 120 ảnh theo chiều xuôi/ngược qua hai chu kỳ và một đoạn giữ hình 24 frame; **500 frame không phải 500 ảnh camera độc lập**. Biểu đồ q, sai số và bốn kênh mô phỏng được vẽ sẵn trong video đều đọc cùng bản ghi theo thời gian phát.
3. Phòng mô phỏng trên web là một nhánh what-if riêng. Nó giữ nguyên video và dự đoán HoRoPose, thêm tác động giả định lên cảm biến/quỹ đạo, sau đó phát hiện từ phần dư đa kênh. Biểu đồ “cảm biến trong video nguồn” và “cảm biến giả lập what-if” được gắn nhãn khác nhau.
4. Cảnh báo chỉ là kết quả của dữ liệu mô phỏng. Kỹ thuật viên có thể xác nhận đúng/sai, nhập nguyên nhân thực tế và việc đã làm; phản hồi lưu vào SQLite theo ca chạy.

Xem [README kỹ thuật dashboard](pose_focus_demo/README.md) để biết công thức tiêm lỗi, ngưỡng và giới hạn. Mô hình chưa được kiểm định để kết luận hỏng hóc ở nhà máy.

## Kiểm tra nhanh

```powershell
Set-Location pose_focus_demo
..\.venv\Scripts\python.exe -m unittest test_engine_v2.py test_horopose_integration.py
```

Gói repro có bài kiểm tra riêng trong `panda_repro/tests/`. Mã/ảnh/trọng số đã có trong bản tích hợp cục bộ; nếu sao chép dự án sang máy khác, phải chuyển cả `panda_repro/`, kể cả checkpoint và dataset. Một số tài nguyên gốc có điều kiện sử dụng riêng; xem tài liệu nguồn của DREAM và HoRoPose trước khi phân phối thương mại.
