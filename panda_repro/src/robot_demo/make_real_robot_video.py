"""Build the ABB real-footage concept demo.

This is an adaptation prototype, not a claim that the released RoboPose model
supports ABB.  It uses dense optical flow to propagate manually seeded ABB
joint landmarks and renders a RoboPose-style kinematic overlay.  The health
signals and internal fault are simulated, then classified by the trained
multimodal model from this project.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import joblib
import numpy as np

from .event_store import EventStore
from .faults import extract_features, simulate_cycle


WHITE = (244, 247, 251)
CYAN = (245, 200, 42)
GREEN = (101, 213, 104)
AMBER = (54, 177, 252)
RED = (73, 80, 245)
MUTED = (174, 184, 198)
DARK = (20, 25, 34)


def put(frame: np.ndarray, text: str, xy: tuple[int, int], scale: float = 0.55,
        color: tuple[int, int, int] = WHITE, thickness: int = 1) -> None:
    cv2.putText(frame, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color,
                thickness, cv2.LINE_AA)


def round_box(frame: np.ndarray, p1: tuple[int, int], p2: tuple[int, int],
              color: tuple[int, int, int], alpha: float = 1.0) -> None:
    overlay = frame.copy()
    cv2.rectangle(overlay, p1, p2, color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)


def load_video(path: Path, start_s: float = 0.8) -> tuple[list[np.ndarray], float]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise FileNotFoundError(f"Cannot open input video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    capture.set(cv2.CAP_PROP_POS_MSEC, start_s * 1000.0)
    frames: list[np.ndarray] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    if not frames:
        raise RuntimeError("Input video has no readable frames")
    return frames, fps


def track_joint_landmarks(frames: list[np.ndarray], initial: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Track coarse ABB landmarks with local median dense optical flow."""
    points = initial.astype(np.float32).copy()
    tracks = [points.copy()]
    motion = [0.0]
    previous = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    h, w = previous.shape
    for frame in frames[1:]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(
            previous, gray, None, 0.5, 4, 31, 3, 7, 1.5, 0,
        )
        updated = points.copy()
        local_speeds = []
        for index, (x, y) in enumerate(points):
            xi, yi = int(round(x)), int(round(y))
            radius = 24 if index < 3 else 18
            x1, x2 = max(0, xi - radius), min(w, xi + radius + 1)
            y1, y2 = max(0, yi - radius), min(h, yi + radius + 1)
            patch = flow[y1:y2, x1:x2]
            if patch.size:
                magnitude = np.linalg.norm(patch, axis=2)
                cutoff = np.percentile(magnitude, 55)
                selected = patch[magnitude >= cutoff]
                displacement = np.median(selected, axis=0) if len(selected) else np.zeros(2)
                displacement = np.clip(displacement, -14.0, 14.0)
                updated[index] += displacement
                local_speeds.append(float(np.linalg.norm(displacement)))
        # Keep the kinematic chain in the robot workcell and suppress jitter.
        updated[:, 0] = np.clip(updated[:, 0], 330, 880)
        updated[:, 1] = np.clip(updated[:, 1], 120, 670)
        points = 0.72 * points + 0.28 * updated
        tracks.append(points.copy())
        motion.append(float(np.mean(local_speeds)) if local_speeds else 0.0)
        previous = gray
    tracks_array = np.asarray(tracks)
    # Symmetric moving average makes the overlay look like a model state,
    # rather than raw optical-flow measurements.
    kernel = np.ones(7, dtype=np.float32) / 7.0
    for joint in range(tracks_array.shape[1]):
        for axis in range(2):
            padded = np.pad(tracks_array[:, joint, axis], (3, 3), mode="edge")
            tracks_array[:, joint, axis] = np.convolve(padded, kernel, mode="valid")
    return tracks_array, np.asarray(motion, dtype=np.float32)


def draw_pose(frame: np.ndarray, points: np.ndarray, fault_active: bool) -> None:
    overlay = frame.copy()
    pts = np.round(points).astype(np.int32)
    for index in range(len(pts) - 1):
        color = RED if fault_active and index in {2, 3} else CYAN
        cv2.line(overlay, tuple(pts[index]), tuple(pts[index + 1]), color, 14, cv2.LINE_AA)
        cv2.line(frame, tuple(pts[index]), tuple(pts[index + 1]), color, 3, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
    for index, point in enumerate(pts):
        color = RED if fault_active and index == 3 else CYAN
        cv2.circle(frame, tuple(point), 9, color, -1, cv2.LINE_AA)
        cv2.circle(frame, tuple(point), 4, WHITE, -1, cv2.LINE_AA)
        label = "BASE" if index == 0 else "TCP" if index == len(pts) - 1 else f"J{index}"
        put(frame, label, (int(point[0] + 11), int(point[1] - 8)), 0.43, WHITE, 1)


def trace(frame: np.ndarray, values: np.ndarray, upto: int, y: int,
          color: tuple[int, int, int], title: str, vmax: float) -> None:
    x, w, h = 892, 342, 62
    put(frame, title, (x, y - 8), 0.40, MUTED, 1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (43, 52, 65), -1)
    values = values[:max(2, upto + 1)]
    xs = np.linspace(x + 4, x + w - 4, len(values))
    ys = y + h - 8 - np.clip(values / vmax, 0, 1) * (h - 16)
    cv2.polylines(frame, [np.column_stack([xs, ys]).astype(np.int32)], False,
                  color, 2, cv2.LINE_AA)


def create_demo(input_video: Path, artifacts: Path, output: Path) -> dict:
    frames, fps = load_video(input_video)
    # Seven coarse landmarks: base, J1..J5 and TCP.  They are seeded once on
    # the first ABB frame, then propagated by dense optical flow.
    initial = np.asarray([
        [497, 600], [503, 515], [535, 405], [588, 232],
        [680, 198], [748, 274], [778, 367],
    ], dtype=np.float32)
    tracks, motion = track_joint_landmarks(frames, initial)

    fault_cycle = simulate_cycle("gearbox_backlash", faulty_joint=2,
                                 steps=len(frames), seed=20260912)
    feature_vector, _ = extract_features(fault_cycle)
    bundle = joblib.load(artifacts / "fault_model.joblib")
    predicted_fault = str(bundle["cause_model"].predict(feature_vector[None])[0])
    predicted_joint = int(bundle["joint_model"].predict(feature_vector[None])[0])
    confidence = float(np.max(bundle["cause_model"].predict_proba(feature_vector[None])[0]))

    # Fault evidence is introduced late in the observed cycle.  Values come
    # from the same physics-guided generator used to train the diagnosis model.
    vibration = np.asarray(fault_cycle["vibration"])[:, 2]
    acoustic = np.asarray(fault_cycle["acoustic"])[:, 2]
    temperature = np.asarray(fault_cycle["temperature"])[:, 2]
    fault_start = int(len(frames) * 0.54)
    vibration[:fault_start] *= 0.34
    acoustic[:fault_start] *= 0.36
    temperature[:fault_start] = temperature[0] + np.linspace(0, 0.5, fault_start)

    store = EventStore(artifacts / "events.db")
    event_id = store.add_event(
        "ABB-DEMO-001", "real-video-cycle-0001", float(fault_cycle["cycle_time"]),
        predicted_fault, predicted_joint, confidence,
        {"max_vibration": float(vibration.max()),
         "max_acoustic": float(acoustic.max()),
         "max_temperature": float(temperature.max()),
         "visual_motion_mean": float(motion.mean())},
    )
    store.add_feedback(event_id, "gearbox_backlash", 2,
                       "Demo technician confirmation", "confirmed")

    np.savez_compressed(
        artifacts / "abb_pose_tracks.npz",
        keypoints_2d=tracks,
        visual_motion=motion,
        vibration_j3=vibration,
        acoustic_j3=acoustic,
        temperature_j3=temperature,
        fps=np.asarray(fps),
        source_name=np.asarray(input_video.name),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"MJPG"),
                             fps, (1280, 720))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create {output}")

    for index, source in enumerate(frames):
        frame = cv2.resize(source, (1280, 720), interpolation=cv2.INTER_AREA)
        progress = index / max(1, len(frames) - 1)
        if progress < 0.54:
            status, status_color = "NORMAL CYCLE", GREEN
        elif progress < 0.69:
            status, status_color = "CYCLE-TIME DEVIATION", AMBER
        elif progress < 0.82:
            status, status_color = "ANOMALY DETECTED", RED
        else:
            status, status_color = "FAULT LOCALIZED", RED

        fault_active = progress >= 0.69
        draw_pose(frame, tracks[index], fault_active)

        shade = frame.copy()
        cv2.rectangle(shade, (855, 0), (1280, 720), DARK, -1)
        cv2.addWeighted(shade, 0.90, frame, 0.10, 0, frame)
        round_box(frame, (879, 20), (1254, 67), status_color, 0.96)
        put(frame, status, (902, 52), 0.67, (17, 22, 29), 2)
        put(frame, "ABB ROBOT HEALTH MONITOR", (886, 99), 0.62, WHITE, 2)
        put(frame, "RoboPose-style visual state + sensor fusion", (886, 124), 0.40, MUTED, 1)

        round_box(frame, (879, 145), (1254, 229), (37, 46, 59), 0.94)
        elapsed = progress * float(fault_cycle["cycle_time"])
        put(frame, "OBSERVED CYCLE", (897, 171), 0.40, MUTED, 1)
        put(frame, f"{elapsed:4.2f} / {float(fault_cycle['cycle_time']):4.2f} s",
            (897, 207), 0.76, WHITE, 2)
        put(frame, f"visual motion: {motion[index]:.2f} px/frame", (1080, 205), 0.36, CYAN, 1)

        trace(frame, vibration, index, 279, RED if fault_active else GREEN,
              "J3 VIBRATION", max(0.28, float(vibration.max())))
        trace(frame, acoustic, index, 379, AMBER, "J3 ACOUSTIC",
              max(0.24, float(acoustic.max())))

        round_box(frame, (879, 478), (1254, 546), (37, 46, 59), 0.94)
        put(frame, "J3 TEMPERATURE", (897, 501), 0.39, MUTED, 1)
        put(frame, f"{temperature[index]:.1f} C", (897, 532), 0.68,
            AMBER if fault_active else GREEN, 2)

        if progress >= 0.82:
            put(frame, "AI DIAGNOSIS", (886, 583), 0.42, MUTED, 1)
            put(frame, predicted_fault, (886, 616), 0.62, RED, 2)
            put(frame, f"location J{predicted_joint + 1} | confidence {confidence * 100:.1f}%",
                (886, 645), 0.46, WHITE, 1)
            put(frame, f"event #{event_id} saved + technician confirmed", (886, 679), 0.42, GREEN, 1)
        else:
            put(frame, "Monitoring pose, cycle time, sound, heat and vibration",
                (886, 608), 0.39, WHITE, 1)
            put(frame, "Baseline duration: 5.00 s", (886, 640), 0.43, GREEN, 1)

        round_box(frame, (20, 18), (412, 62), DARK, 0.76)
        put(frame, "REAL ABB FOOTAGE | PROTOTYPE POSE TRACK", (36, 47), 0.48, WHITE, 1)
        put(frame, "Concept demo: sensor/fault signals are simulated", (28, 698),
            0.42, WHITE, 1)
        writer.write(frame)
    writer.release()
    result = {
        "output": str(output), "duration_s": len(frames) / fps,
        "frames": len(frames), "fps": fps,
        "pose_backend": "manual seed + dense optical flow",
        "predicted_fault": predicted_fault,
        "predicted_joint": predicted_joint + 1,
        "confidence": confidence, "event_id": event_id,
    }
    (artifacts / "abb_real_robot_demo_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-video", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/abb_real_robot_demo_source.avi"))
    args = parser.parse_args()
    print(create_demo(args.input_video, args.artifacts, args.output))


if __name__ == "__main__":
    main()
