"""Render the ABB real-footage multimodal health-monitoring demo (v2).

Video pose is measured by CoTracker3 long-term point tracking.  Internal fault
and sensor signals are physics-guided simulations because the stock footage has
no synchronized accelerometer, microphone, thermal or controller telemetry.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import joblib
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from .cotracker_pose import DEFAULT_LANDMARKS, run_cotracker
from .event_store import EventStore
from .faults import extract_features, simulate_cycle
from .make_real_robot_video import load_video


WHITE = (244, 247, 251)
CYAN = (245, 200, 42)
GREEN = (101, 213, 104)
AMBER = (54, 177, 252)
RED = (73, 80, 245)
MUTED = (174, 184, 198)
DARK = (18, 23, 32)
CARD = (38, 47, 60)


def put(frame: np.ndarray, text: str, xy: tuple[int, int], scale: float = 0.5,
        color: tuple[int, int, int] = WHITE, thickness: int = 1) -> None:
    cv2.putText(frame, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color,
                thickness, cv2.LINE_AA)


def box(frame: np.ndarray, p1: tuple[int, int], p2: tuple[int, int],
        color: tuple[int, int, int], alpha: float = 0.94) -> None:
    overlay = frame.copy()
    cv2.rectangle(overlay, p1, p2, color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)


def draw_dashed_line(frame: np.ndarray, p1: np.ndarray, p2: np.ndarray,
                     color: tuple[int, int, int], thickness: int = 2) -> None:
    distance = float(np.linalg.norm(p2 - p1))
    segments = max(1, int(distance / 12))
    for index in range(0, segments, 2):
        a = p1 + (p2 - p1) * (index / segments)
        b = p1 + (p2 - p1) * (min(index + 1, segments) / segments)
        cv2.line(frame, tuple(np.round(a).astype(int)),
                 tuple(np.round(b).astype(int)), color, thickness, cv2.LINE_AA)


def draw_pose(frame: np.ndarray, points: np.ndarray, confidence: np.ndarray,
              fault_active: bool) -> None:
    pts = np.asarray(points, dtype=np.float32)
    glow = frame.copy()
    for index in range(len(pts) - 1):
        segment_confidence = float(min(confidence[index], confidence[index + 1]))
        color = RED if fault_active and index in {2, 3} else CYAN
        if segment_confidence >= 0.35:
            cv2.line(glow, tuple(np.round(pts[index]).astype(int)),
                     tuple(np.round(pts[index + 1]).astype(int)), color, 13,
                     cv2.LINE_AA)
            cv2.line(frame, tuple(np.round(pts[index]).astype(int)),
                     tuple(np.round(pts[index + 1]).astype(int)), color, 3,
                     cv2.LINE_AA)
        else:
            draw_dashed_line(frame, pts[index], pts[index + 1], MUTED, 2)
    cv2.addWeighted(glow, 0.15, frame, 0.85, 0, frame)

    for index, point in enumerate(np.round(pts).astype(int)):
        color = RED if fault_active and index == 3 else CYAN
        if confidence[index] < 0.35:
            color = MUTED
        cv2.circle(frame, tuple(point), 9, color, -1, cv2.LINE_AA)
        cv2.circle(frame, tuple(point), 3, WHITE, -1, cv2.LINE_AA)
        label = "BASE" if index == 0 else "TCP" if index == 6 else f"J{index}"
        put(frame, label, (int(point[0] + 11), int(point[1] - 7)), 0.40, WHITE)

    # Show the proposed physical sensor placement around the reducer at J3.
    anchor = np.round(pts[3]).astype(int)
    cv2.line(frame, tuple(anchor), (int(anchor[0] - 55), int(anchor[1] + 58)),
             WHITE, 1, cv2.LINE_AA)
    x, y = int(anchor[0] - 115), int(anchor[1] + 58)
    for offset, label, color in [(0, "ACC", RED), (38, "MIC", AMBER),
                                 (78, "TEMP", CYAN)]:
        box(frame, (x + offset, y - 17), (x + offset + 34, y + 4), color, 0.96)
        put(frame, label, (x + offset + 3, y - 3), 0.28, (17, 22, 29), 1)


def resample(values: np.ndarray, length: int) -> np.ndarray:
    old_axis = np.linspace(0.0, 1.0, len(values))
    return np.interp(np.linspace(0.0, 1.0, length), old_axis, values)


def build_sensor_streams(length: int, faulty_joint: int = 2) -> tuple[dict, dict]:
    normal = simulate_cycle("normal", steps=96, seed=310)
    fault = simulate_cycle("gearbox_backlash", faulty_joint=faulty_joint,
                           steps=96, seed=20260912)
    start = int(length * 0.57)
    blend = np.zeros(length, dtype=np.float32)
    blend[start:] = np.clip(np.linspace(0.0, 1.0, length - start) * 2.2, 0, 1)

    raw = {}
    for modality in ["vibration", "acoustic", "temperature", "current"]:
        normal_values = resample(np.asarray(normal[modality])[:, faulty_joint], length)
        fault_values = resample(np.asarray(fault[modality])[:, faulty_joint], length)
        raw[modality] = normal_values * (1.0 - blend) + fault_values * blend

    # Convert simulator values to plausible display units.  The source footage
    # has no real sensor stream; these values remain explicitly marked simulated.
    streams = {
        "vibration_mm_s": 1.7 + raw["vibration"] * 27.0,
        "acoustic_dba": 59.5 + raw["acoustic"] * 48.0,
        "temperature_c": raw["temperature"] + blend * 0.8,
        "motor_current_a": raw["current"],
        "fault_blend": blend,
    }
    return streams, fault


def detected_cycle_times(tracks: np.ndarray, fps: float) -> tuple[np.ndarray, float]:
    signal = tracks[:, 6, 0]
    peaks, _ = find_peaks(signal, prominence=max(8.0, float(np.std(signal) * 0.32)),
                          distance=max(20, int(fps * 1.7)))
    times = np.diff(peaks) / fps
    # Remove slow camera/zoom drift, then estimate the dominant repetition lag.
    detrended = signal - gaussian_filter1d(signal, max(3.0, fps * 0.6))
    autocorrelation = np.correlate(detrended, detrended, mode="full")[len(signal) - 1:]
    minimum_lag = max(2, int(fps * 1.7))
    maximum_lag = min(len(autocorrelation), int(fps * 3.5))
    if maximum_lag > minimum_lag:
        dominant_lag = minimum_lag + int(np.argmax(
            autocorrelation[minimum_lag:maximum_lag]
        ))
        baseline = dominant_lag / fps
    else:
        baseline = float(np.median(times[:3])) if len(times) else 2.56
    return times.astype(np.float32), baseline


def draw_trace(frame: np.ndarray, values: np.ndarray, index: int, y: int,
               title: str, unit: str, color: tuple[int, int, int],
               threshold: float, window: int = 90) -> None:
    x, width, height = 872, 376, 66
    current = float(values[index])
    alert = current >= threshold
    box(frame, (x, y), (x + width, y + height), CARD)
    put(frame, title, (x + 11, y + 20), 0.36, MUTED)
    put(frame, f"{current:5.1f} {unit}", (x + 235, y + 22), 0.46,
        RED if alert else GREEN, 2)
    left = max(0, index - window)
    history = values[left:index + 1]
    minimum = float(min(np.min(values), threshold * 0.72))
    maximum = float(max(np.max(values), threshold * 1.18))
    xs = np.linspace(x + 10, x + width - 10, max(2, len(history)))
    normalized = np.clip((history - minimum) / max(1e-6, maximum - minimum), 0, 1)
    ys = y + height - 8 - normalized * 31
    if len(history) == 1:
        history = np.r_[history, history]
        ys = np.r_[ys, ys]
    cv2.polylines(frame, [np.column_stack([xs, ys]).astype(np.int32)], False,
                  RED if alert else color, 2, cv2.LINE_AA)
    threshold_y = int(y + height - 8 - np.clip(
        (threshold - minimum) / max(1e-6, maximum - minimum), 0, 1
    ) * 31)
    cv2.line(frame, (x + 10, threshold_y), (x + width - 10, threshold_y),
             (92, 101, 113), 1, cv2.LINE_AA)


def save_timeseries(path: Path, fps: float, tracks: np.ndarray,
                    confidence: np.ndarray, motion: np.ndarray,
                    sensors: dict[str, np.ndarray]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        fields = ["frame", "time_s", "visual_motion_px_frame", "tracking_confidence"]
        fields += ["vibration_mm_s", "acoustic_dba", "temperature_c",
                   "motor_current_a", "fault_blend"]
        for joint in range(7):
            fields += [f"landmark_{joint}_x", f"landmark_{joint}_y"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(len(tracks)):
            row = {
                "frame": index,
                "time_s": index / fps,
                "visual_motion_px_frame": float(motion[index]),
                "tracking_confidence": float(np.mean(confidence[index])),
                **{name: float(values[index]) for name, values in sensors.items()},
            }
            for joint in range(7):
                row[f"landmark_{joint}_x"] = float(tracks[index, joint, 0])
                row[f"landmark_{joint}_y"] = float(tracks[index, joint, 1])
            writer.writerow(row)


def create_demo(input_video: Path, artifacts: Path, output: Path,
                cotracker_repo: Path, checkpoint: Path,
                force_track: bool = False, tracking_stride: int = 4) -> dict:
    frames, fps = load_video(input_video)
    cache = artifacts / "abb_cotracker_tracks.npz"
    if cache.exists() and not force_track:
        stored = np.load(cache, allow_pickle=False)
        tracked = {name: stored[name] for name in stored.files}
    else:
        tracked = run_cotracker(frames, cotracker_repo, checkpoint,
                                DEFAULT_LANDMARKS, tracking_stride=tracking_stride)

    tracks = np.asarray(tracked["keypoints_2d"], dtype=np.float32)
    confidence_track = np.asarray(tracked["joint_confidence"], dtype=np.float32)
    motion = np.asarray(tracked["visual_motion"], dtype=np.float32)
    sensors, fault_cycle = build_sensor_streams(len(frames), faulty_joint=2)
    cycle_times, baseline_cycle = detected_cycle_times(tracks, fps)

    bundle = joblib.load(artifacts / "fault_model.joblib")
    feature_vector, _ = extract_features(fault_cycle)
    predicted_fault = str(bundle["cause_model"].predict(feature_vector[None])[0])
    predicted_joint_zero = int(bundle["joint_model"].predict(feature_vector[None])[0])
    diagnosis_confidence = float(np.max(
        bundle["cause_model"].predict_proba(feature_vector[None])[0]
    ))

    event_cycle_time = baseline_cycle * 1.23
    store = EventStore(artifacts / "events.db")
    event_id = store.add_event(
        "ABB-REAL-DEMO-CT3", "cycle-anomaly-0001", event_cycle_time,
        predicted_fault, predicted_joint_zero, diagnosis_confidence,
        {
            "signals_are_simulated": True,
            "max_vibration_mm_s": float(np.max(sensors["vibration_mm_s"])),
            "max_acoustic_dba": float(np.max(sensors["acoustic_dba"])),
            "max_temperature_c": float(np.max(sensors["temperature_c"])),
            "max_motor_current_a": float(np.max(sensors["motor_current_a"])),
            "mean_tracking_confidence": float(np.mean(confidence_track)),
            "camera_cycle_baseline_s": baseline_cycle,
        },
    )
    store.add_feedback(event_id, "gearbox_backlash", 2,
                       "Demo: reducer backlash inspected and confirmed", "confirmed")

    generated_sensor_keys = {
        "vibration_mm_s", "acoustic_dba", "temperature_c",
        "motor_current_a", "fault_blend", "fps", "source_name", "tracker_name",
    }
    np.savez_compressed(
        cache,
        **{name: value for name, value in tracked.items()
           if isinstance(value, (np.ndarray, np.generic, int, float))
           and name not in generated_sensor_keys},
        vibration_mm_s=sensors["vibration_mm_s"],
        acoustic_dba=sensors["acoustic_dba"],
        temperature_c=sensors["temperature_c"],
        motor_current_a=sensors["motor_current_a"],
        fault_blend=sensors["fault_blend"],
        fps=np.asarray(fps),
        source_name=np.asarray(input_video.name),
        tracker_name=np.asarray("CoTracker3 scaled offline"),
    )
    save_timeseries(artifacts / "abb_multimodal_timeseries.csv", fps, tracks,
                    confidence_track, motion, sensors)

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"MJPG"),
                             fps, (1280, 720))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create {output}")

    for index, source in enumerate(frames):
        frame = cv2.resize(source, (1280, 720), interpolation=cv2.INTER_AREA)
        progress = index / max(1, len(frames) - 1)
        blend = float(sensors["fault_blend"][index])
        if progress < 0.57:
            status, status_color = "NORMAL / BINH THUONG", GREEN
        elif progress < 0.70:
            status, status_color = "CYCLE TIME DEVIATION", AMBER
        elif progress < 0.84:
            status, status_color = "MULTIMODAL ANOMALY", RED
        else:
            status, status_color = "FAULT LOCALIZED: J3", RED

        draw_pose(frame, tracks[index], confidence_track[index], progress >= 0.70)

        shade = frame.copy()
        cv2.rectangle(shade, (850, 0), (1280, 720), DARK, -1)
        cv2.addWeighted(shade, 0.94, frame, 0.06, 0, frame)
        box(frame, (868, 15), (1260, 62), status_color, 0.98)
        put(frame, status, (884, 47), 0.58, (17, 22, 29), 2)
        put(frame, "ABB MULTIMODAL HEALTH MONITOR", (871, 88), 0.54, WHITE, 2)
        put(frame, "CoTracker3 2D landmarks + cycle timing", (871, 108),
            0.34, MUTED)

        box(frame, (868, 119), (1260, 181), CARD)
        observed_cycle = baseline_cycle * (1.0 + 0.23 * blend)
        put(frame, "CAMERA / POSE", (880, 141), 0.34, MUTED)
        put(frame, f"cycle {observed_cycle:.2f}s  ref {baseline_cycle:.2f}s",
            (880, 166), 0.48, AMBER if blend > 0.25 else GREEN, 2)
        put(frame, f"motion {motion[index]:.2f}px/f", (1080, 141), 0.31, CYAN)
        put(frame, f"track {np.mean(confidence_track[index]) * 100:.0f}%",
            (1110, 166), 0.31, WHITE)

        draw_trace(frame, sensors["vibration_mm_s"], index, 194,
                   "VIBRATION / RUNG (J3)", "mm/s RMS", CYAN, 4.5)
        draw_trace(frame, sensors["acoustic_dba"], index, 268,
                   "ACOUSTIC / AM THANH (J3)", "dBA", AMBER, 66.0)
        draw_trace(frame, sensors["temperature_c"], index, 342,
                   "TEMPERATURE / NHIET (J3)", "C", AMBER, 48.0)
        draw_trace(frame, sensors["motor_current_a"], index, 416,
                   "MOTOR CURRENT / DONG (J3)", "A", CYAN, 3.0)

        box(frame, (868, 502), (1260, 694), CARD)
        put(frame, "AI SENSOR-FUSION DIAGNOSIS", (881, 528), 0.39, MUTED)
        if progress < 0.70:
            put(frame, "No internal fault evidence", (881, 561), 0.54, GREEN, 2)
            put(frame, "Monitoring RGB + ACC + MIC + TEMP", (881, 591),
                0.38, WHITE)
        elif progress < 0.84:
            put(frame, "Evidence window captured", (881, 561), 0.54, AMBER, 2)
            put(frame, "Cross-checking vibration and sound...", (881, 591),
                0.38, WHITE)
        else:
            put(frame, predicted_fault, (881, 560), 0.58, RED, 2)
            put(frame, f"likely joint J{predicted_joint_zero + 1}",
                (881, 589), 0.48, WHITE, 2)
            put(frame, f"confidence {diagnosis_confidence * 100:.1f}%",
                (1070, 589), 0.39, WHITE)
            put(frame, f"event #{event_id} saved", (881, 622), 0.41, CYAN, 1)
            feedback = "technician label: PENDING"
            feedback_color = AMBER
            if progress >= 0.94:
                feedback = "technician: CONFIRMED BACKLASH"
                feedback_color = GREEN
            put(frame, feedback, (881, 653), 0.40, feedback_color, 1)
        put(frame, "Signals simulated | Replace with synchronized sensors",
            (881, 682), 0.31, MUTED)

        box(frame, (18, 17), (440, 61), DARK, 0.78)
        put(frame, "REAL ABB FOOTAGE | COTRACKER3 TEMPORAL POSE",
            (31, 46), 0.43, WHITE, 1)
        put(frame, "2D tracked landmarks - not calibrated ABB joint angles",
            (20, 701), 0.37, WHITE, 1)
        writer.write(frame)
    writer.release()

    result = {
        "output": str(output),
        "duration_s": len(frames) / fps,
        "frames": len(frames),
        "fps": fps,
        "pose_backend": "CoTracker3 scaled offline; 9 support points per landmark",
        "tracking_stride": int(np.asarray(tracked.get("tracking_stride", 2))),
        "mean_joint_visibility": float(np.mean(confidence_track)),
        "camera_cycle_times_s": cycle_times.tolist(),
        "camera_cycle_baseline_s": baseline_cycle,
        "predicted_fault": predicted_fault,
        "predicted_joint": predicted_joint_zero + 1,
        "diagnosis_confidence": diagnosis_confidence,
        "event_id": event_id,
        "sensor_truth": "simulated",
    }
    (artifacts / "abb_real_robot_demo_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-video", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/abb_real_robot_demo_source_v2.avi"))
    parser.add_argument("--cotracker-repo", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--force-track", action="store_true")
    parser.add_argument("--tracking-stride", type=int, default=4,
                        help="Track every Nth frame; 4 is CPU/RAM friendly, 2 suits GPU")
    args = parser.parse_args()
    print(json.dumps(create_demo(
        args.input_video, args.artifacts, args.output, args.cotracker_repo,
        args.checkpoint, args.force_track, args.tracking_stride,
    ), indent=2))


if __name__ == "__main__":
    main()
