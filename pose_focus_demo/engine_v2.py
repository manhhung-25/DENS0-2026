"""Causal, offline what-if generator around the observed 2D pose timeline.

The robot footage and its extracted 2D markers are immutable observations.
Every signal, latent fault state and orange what-if trajectory below is synthetic.
This is a teaching model, not a calibrated Franka mechanical digital twin.
"""
import math
import random

from engine import FPS, POSE, RECORDING, ROOT, point_distance

FAULTS = {
    "bearing": {
        "label": "Nghi suy giảm ổ bi / truyền động",
        "cause": "Ổ bi, hộp giảm tốc, gá đo hoặc nguồn âm khác",
        "checks": ["So phổ rung và âm thanh theo tốc độ, tải và pha chuyển động",
                   "Kiểm tra gá cảm biến và nguồn rung/ồn bên ngoài",
                   "Đối chiếu dòng điện, mô men và khuyến nghị OEM"],
        "mechanism": "Mức mòn ẩn làm tăng năng lượng rung và âm theo chuyển động; nhiệt tăng chậm."},
    "friction": {
        "label": "Nghi ma sát / bôi trơn",
        "cause": "Khớp, truyền động, tải hoặc bôi trơn",
        "checks": ["So cùng recipe, tải và tốc độ trước khi kết luận",
                   "Kiểm tra lịch bôi trơn theo OEM",
                   "Đối chiếu mô men/dòng điện và nhiệt đo thật"],
        "mechanism": "Ma sát ẩn tăng nhiệt có quán tính, âm và rung khi chuyển động; đáp ứng chậm nhẹ."},
    "thermal": {
        "label": "Nghi suy giảm tản nhiệt",
        "cause": "Tản nhiệt, động cơ, tải hoặc môi trường",
        "checks": ["Đo lại bằng cảm biến nhiệt thật",
                   "So tải và nhiệt môi trường với chu kỳ tương ứng",
                   "Kiểm tra thông gió và giới hạn OEM"],
        "mechanism": "Giảm hiệu quả làm mát làm nhiệt tích lũy và nguội dần sau kịch bản."},
    "backlash": {
        "label": "Nghi độ rơ / sai tư thế",
        "cause": "Truyền động, phép hiệu chuẩn camera hoặc quỹ đạo lệnh",
        "checks": ["So pose camera với encoder và lệnh cùng timestamp",
                   "Kiểm tra che khuất, rung camera và ánh sáng",
                   "Đo độ rơ khi robot dừng theo quy trình OEM"],
        "mechanism": "Độ rơ ẩn làm hình chiếu giả lập lệch quanh mốc trước, mạnh hơn gần đảo chiều."},
    "slow": {
        "label": "Nghi đáp ứng chuyển động chậm",
        "cause": "Chương trình, tải, giới hạn tốc độ hoặc truyền động",
        "checks": ["So thời gian từng pha ở cùng chương trình và tải",
                   "Đối chiếu tốc độ lệnh với encoder",
                   "Kiểm tra trạng thái controller"],
        "mechanism": "Độ trễ ẩn làm quỹ đạo giả lập lùi theo thời gian và tăng chỉ số trễ."},
    "sensor_drift": {
        "label": "Nghi trôi cảm biến rung",
        "cause": "Cảm biến, gá lắp, cáp hoặc hiệu chuẩn",
        "checks": ["Đo chéo bằng cảm biến độc lập",
                   "Kiểm tra gá lắp, cáp và nhiễu điện",
                   "Không kết luận hỏng cơ khí từ một kênh đơn lẻ"],
        "mechanism": "Chỉ phép đo rung giả lập trôi; pose và các kênh cơ khí không đổi."},
}

DEFAULT_INJECTIONS = [
    {"fault": "bearing", "landmark": 3, "start_s": 5.0, "duration_s": 3.0, "intensity": 1.0},
    {"fault": "backlash", "landmark": 5, "start_s": 10.0, "duration_s": 3.0, "intensity": 1.0},
]


def validate_injections(items):
    if not isinstance(items, list) or len(items) > 8:
        raise ValueError("Cần 0–8 kịch bản")
    clean = []
    for item in items:
        try:
            fault = str(item["fault"])
            landmark = int(item["landmark"])
            start = float(item["start_s"])
            duration = float(item["duration_s"])
            intensity = float(item.get("intensity", 1))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Kịch bản thiếu hoặc sai tham số") from exc
        if (fault not in FAULTS or not 0 <= landmark < 7 or
                not 0 <= start < RECORDING["duration_s"] - .5 or
                not .5 <= duration <= 10 or start + duration > RECORDING["duration_s"] or
                not .3 <= intensity <= 2):
            raise ValueError("Kịch bản vượt phạm vi video, mốc hoặc cường độ")
        clean.append({"fault": fault, "landmark": landmark,
                      "start_s": start, "duration_s": duration, "intensity": intensity})
    return clean


def validate_context(seed, load):
    if isinstance(seed, bool) or int(seed) != seed or not 0 <= seed <= 1000000:
        raise ValueError("Seed phải là số nguyên từ 0 đến 1.000.000")
    if not .6 <= load <= 1.4:
        raise ValueError("Mức tải mô phỏng phải từ 0,6 đến 1,4")
    return int(seed), float(load)


def envelope(t, start, duration):
    if not start <= t < start + duration:
        return 0.0
    return min(1.0, (t-start)/.45, (start+duration-t)/.45)


def activity_at(i, j):
    # Visible distal image motion is a proxy for activity, not joint angular speed.
    speeds = [POSE[i]["speed_px_s"][k] for k in range(max(2, j), 7)]
    observed = [s for s in speeds if s is not None]
    return round(min(1.3, max(.15, max(observed, default=0) / 72)), 3)


def reversal_at(i, j):
    # A 2D direction-change cue strengthens the illustrative backlash effect.
    if i < 12:
        return 0.0
    for k in range(6, max(1, j-1), -1):
        a, b, c = (POSE[q]["points"][k] for q in (i-12, i-6, i))
        if a and b and c:
            u = [b[m]-a[m] for m in (0, 1)]
            v = [c[m]-b[m] for m in (0, 1)]
            if math.hypot(*u) > 2 and math.hypot(*v) > 2:
                return 1.0 if u[0]*v[0]+u[1]*v[1] < 0 else 0.0
    return 0.0


def rotate(point, pivot, angle):
    dx, dy = point[0]-pivot[0], point[1]-pivot[1]
    co, si = math.cos(angle), math.sin(angle)
    return [round(pivot[0]+dx*co-dy*si, 1), round(pivot[1]+dx*si+dy*co, 1)]


def classify(sig):
    v, temp, sound = sig["z"]
    if sig["cycle_delay_s"] >= .4:
        return "slow"
    if sig["hysteresis_gap_px"] >= 10 and sig["pose_gap_px"] >= 10:
        return "backlash"
    if temp >= 1.5 and sound >= 1.4 and sig["cycle_delay_s"] >= .1:
        return "friction"
    if v >= 5 and sound >= 2.3:
        return "bearing"
    if temp >= 4:
        return "thermal"
    if v >= 4 and abs(sound) < 1.3 and abs(temp) < 1.3:
        return "sensor_drift"
    return None


def generate(injections, seed=0, load=1.0):
    injections = validate_injections(injections)
    seed, load = validate_context(seed, load)
    rng = random.Random(seed)
    ambient = rng.uniform(-1.1, 1.1)
    vib_gain = rng.uniform(.92, 1.08)
    sound_floor = rng.uniform(-1.5, 1.5)
    temp_state = [0.0]*7
    phase = [0.0]*7
    rows = []
    for i, observed in enumerate(POSE):
        t = observed["t"]
        components = []
        signals = []
        for j in range(7):
            active = {name: 0.0 for name in FAULTS}
            truth = []
            for inj in injections:
                if inj["landmark"] == j:
                    level = envelope(t, inj["start_s"], inj["duration_s"]) * inj["intensity"]
                    if level > 0:
                        active[inj["fault"]] += level
                        truth.append(inj["fault"])
            motion = activity_at(i, j)
            reverse = reversal_at(i, j)
            phase[j] += 2*math.pi*(1.6+2.2*motion)/FPS
            impact = .82 + .18*math.sin(phase[j])**2
            # Thermal inertia: heat continues to dissipate after the fault ends.
            heat_in = (4.5*active["friction"]*motion +
                       1.1*active["bearing"]*motion +
                       5.5*active["thermal"]*(.45+.55*motion))
            cooling = .32/(1+.7*active["thermal"])
            temp_state[j] += (heat_in-cooling*temp_state[j])/FPS
            baseline = {
                "vibration": round(vib_gain*(.88+.065*j+.19*load*motion)+.018*math.sin(3.3*t+j), 3),
                "temperature": round(37+.72*j+ambient+.06*t+.32*load*motion+.07*math.sin(.8*t+j), 3),
                "sound": round(54.5+.55*j+sound_floor+1.7*load*motion+.13*math.sin(2.7*t+j), 3),
            }
            vibration = (baseline["vibration"] +
                         1.85*active["bearing"]*motion*impact +
                         .65*active["friction"]*motion +
                         .48*active["backlash"]*reverse +
                         1.75*active["sensor_drift"])
            temperature = baseline["temperature"] + temp_state[j]
            sound = (baseline["sound"] +
                     7.3*active["bearing"]*motion*(.92+.08*impact) +
                     4.7*active["friction"]*motion +
                     1.4*active["backlash"]*reverse)
            delay = min(.9, .66*active["slow"]+.16*active["friction"]*motion)
            z = [(vibration-baseline["vibration"])/.25,
                 (temperature-baseline["temperature"])/1.6,
                 (sound-baseline["sound"])/2.0]
            sig = {"landmark": j, "vibration": round(vibration, 2),
                   "temperature": round(temperature, 2), "sound": round(sound, 2),
                   "baseline": baseline, "z": [round(v, 2) for v in z],
                   "cycle_delay_s": round(delay, 2), "pose_gap_px": 0.0,
                   "hysteresis_gap_px": 0.0, "score": 0,
                   "activity": motion, "reversal": reverse,
                   "thermal_state_c": round(temp_state[j], 2),
                   "truth": truth,
                   "latent": {name: round(value, 2) for name, value in active.items() if value > 0}}
            signals.append(sig)
            components.append(active)

        # Projected 2D what-if trajectory. It is separate from the observed pose.
        twin = [p[:] if p else None for p in observed["points"]]
        for j, active in enumerate(components):
            if not any(active.values()):
                continue
            delay = signals[j]["cycle_delay_s"]
            if delay >= .05:
                old = POSE[max(0, i-round(delay*FPS))]["points"]
                for k in range(j, 7):
                    if twin[k] and old[k]:
                        twin[k] = old[k][:]
            if active["backlash"] > 0:
                pivot_index = max(0, j-1)
                pivot = observed["points"][pivot_index]
                if pivot:
                    angle = min(.29, .23*active["backlash"]*(.88+.12*signals[j]["reversal"]))
                    for k in range(max(1, j), 7):
                        if twin[k]:
                            before = twin[k]
                            twin[k] = rotate(before, pivot, angle)
                            signals[j]["hysteresis_gap_px"] = max(
                                signals[j]["hysteresis_gap_px"], point_distance(before, twin[k]))
        twin = [[round(v, 1) for v in p] if p else None for p in twin]
        for j, sig in enumerate(signals):
            if sig["latent"].get("backlash") or sig["latent"].get("slow") or sig["latent"].get("friction"):
                gaps = [point_distance(observed["points"][k], twin[k])
                        for k in range(j, 7) if observed["points"][k] and twin[k]]
                sig["pose_gap_px"] = round(max(gaps, default=0), 1)
            sig["hysteresis_gap_px"] = round(sig["hysteresis_gap_px"], 1)
            evidence = max(sig["z"][0]/5, sig["z"][1]/4,
                           sig["z"][2]/2.3, sig["pose_gap_px"]/10,
                           sig["cycle_delay_s"]/.4)
            sig["score"] = round(100*(1-math.exp(-.65*max(0, evidence))))
        rows.append({**observed, "twin_points": twin, "signals": signals,
                     "max_score": max(s["score"] for s in signals)})

    incidents = []
    for j in range(7):
        labels = []
        friction_cooling = False
        for row in rows:
            label = classify(row["signals"][j])
            if label == "friction":
                friction_cooling = True
            elif label == "thermal" and friction_cooling:
                label = "friction"  # same heating episode during cooling
            elif row["signals"][j]["z"][1] < 2:
                friction_cooling = False
            labels.append(label)
        # Bridge short dips in the activity proxy or detection confidence.
        k = 0
        while k < len(labels):
            if labels[k] is not None:
                k += 1
                continue
            end = k
            while end < len(labels) and labels[end] is None:
                end += 1
            if k > 0 and end < len(labels) and end-k <= 12 and labels[k-1] == labels[end]:
                labels[k:end] = [labels[end]]*(end-k)
            k = end
        i = 0
        while i < len(labels):
            fault = labels[i]
            if fault is None:
                i += 1
                continue
            end = i
            while end+1 < len(labels) and labels[end+1] == fault:
                end += 1
            if end-i+1 >= 3:
                peak = max(rows[i:end+1], key=lambda row: row["signals"][j]["score"])
                info = FAULTS[fault]
                evidence = peak["signals"][j]
                incidents.append({"id": "", "start_s": rows[i]["t"],
                                  "end_s": rows[end]["t"], "peak_s": peak["t"],
                                  "landmark": j, "fault": fault, "label": info["label"],
                                  "cause": info["cause"], "checks": info["checks"],
                                  "score": evidence["score"],
                                  "evidence": {"z": evidence["z"],
                                               "pose_gap_px": evidence["pose_gap_px"],
                                               "cycle_delay_s": evidence["cycle_delay_s"]},
                                  "status": "Tín hiệu mô phỏng — chưa xác minh"})
            i = end+1
    incidents.sort(key=lambda x: (x["start_s"], x["landmark"]))
    for n, incident in enumerate(incidents, 1):
        incident["id"] = f"SIM-{n}"
    return {"duration_s": RECORDING["duration_s"], "fps": FPS,
            "landmarks": RECORDING["landmarks"], "faults": FAULTS,
            "injections": injections, "seed": seed, "load": load,
            "context": {"ambient_offset_c": round(ambient, 2),
                        "vibration_gain": round(vib_gain, 3),
                        "sound_floor_offset_db": round(sound_floor, 2)},
            "timeline": rows, "incidents": incidents,
            "method": {"name": "causal what-if v2", "version": "2.0",
                       "motion_proxy": "2D image speed, not motor speed",
                       "thermal": "first-order heating and cooling state",
                       "bearing": "motion-linked vibration and acoustic energy",
                       "backlash": "projected 2D downstream rotation with reversal cue",
                       "slow": "time-lagged projected trajectory",
                       "detector": "residual and cross-channel rules, at least 3 consecutive frames"},
            "provenance": {"video": "Recorded Franka Panda footage, 16.67 s, 500 frames",
                           "pose": "Observed 2D marker coordinates extracted from pre-annotated video; no new HoRoPose inference",
                           "twin_points": "Synthetic projected what-if positions, not measurements",
                           "signals": "All vibration, temperature, sound, delay and fault state are synthetic",
                           "validation": "Not calibrated to a physical robot; no real fault labels"}}
