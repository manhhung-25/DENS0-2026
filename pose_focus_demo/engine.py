"""Precomputed HoRoPose Panda predictions aligned to the rendered 500-frame clip.

The RGB dataset, checkpoint, model adapter, and saved predictions are in
``panda_repro``. No live controller, physical sensors, or fault labels exist.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECORDING = json.loads((ROOT / "pose_recording.json").read_text(encoding="utf-8"))
FRAMES = RECORDING["frames"]
FPS = RECORDING["fps"]

FAULTS = {
    "bearing": {"label": "Nghi ổ bi / truyền động", "channels": [1.65, 2.0, 8.0],
                "cause": "Ổ bi, hộp giảm tốc hoặc gá cảm biến",
                "checks": ["So phổ rung và âm thanh ở cùng tốc độ/tải", "Kiểm tra gá cảm biến, nguồn ồn khác và lịch bôi trơn", "Đối chiếu dòng điện, mô men và hướng dẫn OEM nếu có"]},
    "friction": {"label": "Nghi ma sát / bôi trơn", "channels": [.65, 9.0, 5.0],
                 "cause": "Khớp, truyền động hoặc tải",
                 "checks": ["So nhiệt độ ở cùng tốc độ/tải và nhiệt môi trường", "Kiểm tra bôi trơn theo hướng dẫn OEM", "Đối chiếu dòng điện và mô men nếu có"]},
    "thermal": {"label": "Nghi quá nhiệt", "channels": [.25, 13.0, 1.5],
                "cause": "Động cơ, tản nhiệt hoặc môi trường",
                "checks": ["Đo lại bằng cảm biến nhiệt thật", "Kiểm tra tải, thông gió và nhiệt độ môi trường", "So với giới hạn của đúng model robot"]},
    "backlash": {"label": "Nghi sai lệch tư thế", "channels": [.65, 1.4, 2.0],
                 "cause": "Khớp, độ rơ hoặc phép hiệu chuẩn camera",
                 "checks": ["So pose camera với encoder và quỹ đạo lệnh cùng timestamp", "Kiểm tra che khuất, camera rung và hiệu chuẩn", "Chỉ kiểm tra độ rơ khi robot dừng theo quy trình OEM"]},
    "slow": {"label": "Nghi thời gian chuyển động bất thường", "channels": [.15, 1.0, .6],
             "cause": "Tải, chương trình, giới hạn tốc độ hoặc truyền động",
             "checks": ["So thời gian pha với chương trình và tải giống nhau", "Đối chiếu tốc độ lệnh với encoder", "Kiểm tra trạng thái controller và giới hạn tốc độ"]},
}

DEFAULT_INJECTIONS = [
    {"fault": "bearing", "landmark": 3, "start_s": 5.0, "duration_s": 3.0, "intensity": 1.0},
    {"fault": "backlash", "landmark": 5, "start_s": 10.0, "duration_s": 3.0, "intensity": 1.0},
]


def validate_injections(items):
    if not isinstance(items, list) or len(items) > 8:
        raise ValueError("Tối đa 8 lỗi mô phỏng")
    result = []
    for item in items:
        try:
            fault = str(item["fault"])
            landmark = int(item["landmark"])
            start = float(item["start_s"])
            duration = float(item["duration_s"])
            intensity = float(item.get("intensity", 1))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Thiếu hoặc sai tham số lỗi") from exc
        if fault not in FAULTS or not 0 <= landmark < 7 or not 0 <= start < RECORDING["duration_s"] - .5 or not .5 <= duration <= 10 or start + duration > RECORDING["duration_s"] or not .3 <= intensity <= 2:
            raise ValueError("Lỗi nằm ngoài thời lượng, mốc pose hoặc dải cường độ")
        result.append({"fault": fault, "landmark": landmark, "start_s": start,
                       "duration_s": duration, "intensity": intensity})
    return result


def point_distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def median(values):
    seq = sorted(values)
    if not seq:
        return None
    return seq[len(seq) // 2]


def make_pose_series():
    # An explicitly selected segment of this same video. It is an image reference,
    # not a programmed reference trajectory or verified healthy ground truth.
    references = [FRAMES[i] for i in range(90, 211, 6)]
    rows = []
    for i, frame in enumerate(FRAMES):
        points = frame["points"]
        speeds = []
        for j, point in enumerate(points):
            if not point or i < 3 or not FRAMES[i - 3]["points"][j]:
                speeds.append(None)
                continue
            distance = point_distance(point, FRAMES[i - 3]["points"][j])
            speeds.append(round(distance * FPS / 3, 1) if distance <= 40 else None)
        candidates = []
        for ref in references:
            # Compare configuration relative to the base marker, ignoring camera
            # translation. At least four non-base landmarks must be visible.
            if not points[0] or not ref["points"][0]:
                continue
            distances = []
            for j in range(1, 7):
                if points[j] and ref["points"][j]:
                    a = [points[j][k] - points[0][k] for k in (0, 1)]
                    b = [ref["points"][j][k] - ref["points"][0][k] for k in (0, 1)]
                    distances.append(point_distance(a, b))
            if len(distances) >= 4:
                candidates.append(median(distances))
        deviation = min(candidates) if candidates else None
        rows.append({**frame, "speed_px_s": speeds,
                     "reference_distance_px": round(deviation, 1) if deviation is not None else None})
    still = [0.0] * 7
    for i, row in enumerate(rows):
        durations = []
        for j, point in enumerate(row["points"]):
            old = rows[i - 15]["points"][j] if i >= 15 else None
            if point and old and point_distance(point, old) <= 3.0:
                still[j] += 1 / FPS
                durations.append(round(still[j], 2))
            else:
                still[j] = 0.0
                durations.append(None if not point else 0.0)
        row["still_duration_s"] = durations
    return rows


POSE = make_pose_series()


def envelope(t, start, duration):
    if not start <= t < start + duration:
        return 0.0
    return min(1.0, (t - start) / .45, (start + duration - t) / .45)


def generate(injections):
    injections = validate_injections(injections)
    rows = []
    for i, pose in enumerate(POSE):
        t = pose["t"]
        # Values and noise are entirely synthetic. They are indexed by the exact
        # video-frame timestamp and keyed to the selected pose landmark.
        signals = []
        for j in range(7):
            speed = pose["speed_px_s"][j] or 0.0
            baseline = [1.05 + .07 * j + .002 * speed + .025 * math.sin(t * 4 + j),
                        37.5 + .8 * j + .08 * t + .10 * math.sin(t + j),
                        55.5 + .55 * j + .003 * speed + .20 * math.sin(t * 3 + j)]
            values = baseline[:]
            active = []
            for item in injections:
                if item["landmark"] != j:
                    continue
                level = envelope(t, item["start_s"], item["duration_s"]) * item["intensity"]
                if level <= 0:
                    continue
                active.append(item["fault"])
                for k in range(3):
                    values[k] += level * FAULTS[item["fault"]]["channels"][k]
            z = [(values[k] - baseline[k]) / [.25, 1.6, 2.0][k] for k in range(3)]
            # Pose discrepancy is real image-derived, but its interpretation as a
            # fault is not valid without a reference command and repeated runs.
            # In a pose-fault injection, expected pose is a synthetic offset from
            # the measured marker; the measured marker itself is never changed.
            pose_gap = 0.0
            cycle_delay = 0.0
            for item in injections:
                if item["landmark"] == j:
                    level = envelope(t, item["start_s"], item["duration_s"]) * item["intensity"]
                    if item["fault"] == "backlash":
                        pose_gap += 21 * level
                    elif item["fault"] == "slow":
                        cycle_delay += .72 * level
            score = min(100, round(max(max(z) / 5, pose_gap / 18, cycle_delay / .6) * 75))
            signals.append({"landmark": j, "vibration": round(values[0], 2),
                            "temperature": round(values[1], 2), "sound": round(values[2], 2),
                            "z": [round(x, 2) for x in z], "pose_gap_px": round(pose_gap, 1),
                            "cycle_delay_s": round(cycle_delay, 2), "score": score,
                            "active": active})
        rows.append({**pose, "signals": signals, "max_score": max(x["score"] for x in signals)})
    # Detect from the resulting generated channels, not from the injection list.
    # Require three consecutive 30-fps frames.
    def detect(row, j):
        sig = row["signals"][j]
        vibration, temperature, sound = sig["z"]
        if row["points"][j] and sig["pose_gap_px"] >= 12:
            return "backlash"
        if sig["cycle_delay_s"] >= .4:
            return "slow"
        if temperature >= 4 and sound >= 2:
            return "friction"
        if vibration >= 4 and sound >= 2.5:
            return "bearing"
        if temperature >= 4:
            return "thermal"
        return None

    incidents = []
    for j in range(7):
        labels = [detect(row, j) for row in rows]
        start = 0
        while start < len(labels):
            fault = labels[start]
            if fault is None:
                start += 1
                continue
            end = start
            while end + 1 < len(labels) and labels[end + 1] == fault:
                end += 1
            if end - start + 1 >= 3:
                info = FAULTS[fault]
                peak = max(rows[start:end + 1], key=lambda r: r["signals"][j]["score"])
                incidents.append({"id": f"SIM-{len(incidents)+1}",
                                  "start_s": rows[start]["t"], "end_s": rows[end]["t"],
                                  "peak_s": peak["t"], "score": peak["signals"][j]["score"],
                                  "landmark": j, "fault": fault, "label": info["label"],
                                  "cause": info["cause"], "checks": info["checks"],
                                  "status": "Phát hiện trên tín hiệu mô phỏng — chưa xác minh"})
            start = end + 1
    incidents.sort(key=lambda x: x["start_s"])
    for n, incident in enumerate(incidents, 1):
        incident["id"] = f"SIM-{n}"
    return {"duration_s": RECORDING["duration_s"], "fps": FPS,
            "landmarks": RECORDING["landmarks"], "faults": FAULTS,
            "injections": injections, "timeline": rows, "incidents": incidents,
            "provenance": {"video": "Clip Franka Panda thật, 16,67 s; pose màu cyan đã vẽ sẵn trong nguồn",
                           "pose": "Tọa độ 2D trích bằng xử lý ảnh từ mốc màu cyan; chưa chạy checkpoint HoRoPose độc lập",
                           "reference": "Khoảng cách pose 2D so với đoạn 3–7 s cùng clip; không phải lỗi được xác thực",
                           "synthetic": "Rung, nhiệt, âm thanh, độ trễ, mục tiêu pose và lỗi đều được sinh trong demo"}}
