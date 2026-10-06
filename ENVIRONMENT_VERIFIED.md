# Môi trường và lệnh đã kiểm tra

## Máy Windows dùng để kiểm tra bản tích hợp

- Windows, Python 3.12.10, CPU (không cần GPU).
- PyTorch 2.13.0+cpu, torchvision 0.28.0+cpu, NumPy 2.5.2, SciPy 1.18.0, OpenCV 4.10.0, scikit-learn 1.9.1, joblib 1.6.0, imageio-ffmpeg 0.6.0.
- Dashboard: FastAPI 0.141.1 và Uvicorn, theo `requirements.txt` ở gốc.
- `panda_repro/requirements-resolved.txt` ghi môi trường gốc của gói; scikit-learn 1.8.0 trong đó là phiên bản đã tạo `fault_model.joblib`. Khi nạp bằng 1.9.1 có cảnh báo phiên bản nhưng lần kiểm tra này vẫn dự đoán đúng nhãn mô phỏng `gearbox_backlash` tại J4.

## Cài dashboard (PowerShell, tại gốc repo)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe pose_focus_demo\import_horopose.py
Set-Location pose_focus_demo
..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8767
```

Mở <http://127.0.0.1:8767/>. Lệnh import kiểm tra SHA-256 của checkpoint, MP4, NPZ và CSV đã giao; không cần chạy model mỗi lần mở web.

## Cài môi trường suy luận riêng (PowerShell, tại gốc repo)

```powershell
Set-Location panda_repro
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch==2.13.0 torchvision==0.28.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m robot_demo.horopose_panda --batch-size 4 --output artifacts\verification\panda_pose_predictions.npz
.\.venv\Scripts\python.exe -m robot_demo.make_panda_video --predictions artifacts\verification\panda_pose_predictions.npz --output artifacts\verification\reproduced.mp4 --fault-model artifacts\fault_model.joblib --events artifacts\verification\events.db
```

Kết quả mới nằm trong `artifacts/verification/` để không ghi đè bằng chứng gốc. Nếu nguồn PyTorch không còn phát hành đúng cặp phiên bản trên, dùng cặp torch/torchvision CPU tương thích Python 3.12 theo trang chính thức của PyTorch; mã đã chạy thành công với cặp ở trên.

## Kiểm tra dashboard và dữ liệu đồng bộ

```powershell
Set-Location ..\pose_focus_demo
..\.venv\Scripts\python.exe -m unittest test_engine_v2.py test_horopose_integration.py
```

Từ bộ giải nén tại `D:\DENSO\Panda_HoRoPose_Full_Repro`, tôi cũng đã chạy suy luận riêng trên 120/120 ảnh với checkpoint tại chính thư mục đó và ghi kết quả vào bản sao có quyền ghi. Hash checkpoint từ thư mục giải nén khớp `9c531ede…38026c181c3c`; video khớp `c91552e2…c21ac02e`. Thư mục `D:\DENSO` của tài khoản chạy hiện chỉ có quyền đọc; bản tích hợp được xây dựng trong clone Git có quyền ghi và đẩy lên GitHub.
