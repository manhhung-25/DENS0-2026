"""Import the supplied Panda reproduction's checkpoint predictions into the web replay.

This is a data conversion step, not model inference. It maps source scene IDs to
the 500-frame rendered video and keeps simulated telemetry explicitly labelled.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
REPRO = ROOT.parent / "panda_repro"
EXPECTED = {
    "checkpoints/horopose_panda_realsense_inference.pk": "9c531ede1e32fcfc1d51a92cdef63f285483786730edda35e73838026c181c3c",
    "artifacts/panda_horopose_health_demo.mp4": "c91552e2b271160257938f1bf49a37aa86f22105450dcd88d6491696c21ac02e",
    "artifacts/panda_pose_predictions.npz": "2cac72e68a9baf371a3c7dcfa9e4383502c3644023d132e33b16917b0afb6358",
    "artifacts/panda_multimodal_timeseries.csv": "a77601f8ffc8bb7ff2509afd15f71541454b896b9f08354b005a7ed03a19a938",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(repro: Path = REPRO, output: Path = ROOT / "pose_recording.json") -> dict:
    for relative, expected in EXPECTED.items():
        path = repro / relative
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"SHA-256 mismatch: {relative}: {actual}")

    with np.load(repro / "artifacts/panda_pose_predictions.npz", allow_pickle=False) as saved:
        predictions = {key: saved[key] for key in saved.files}
    with (repro / "artifacts/panda_multimodal_timeseries.csv").open(newline="", encoding="utf-8") as stream:
        timeline = list(csv.DictReader(stream))
    if len(timeline) != 500 or predictions["q"].shape != (120, 8):
        raise ValueError("Unexpected Panda source/video frame count")
    scenes = {int(scene): index for index, scene in enumerate(predictions["scene_id"])}
    names = ["L0 / đế", "L2 / vai", "L3 / khuỷu dưới", "L4 / khuỷu trên", "L6 / cẳng tay", "L7 / cổ tay", "EE / bộ kẹp"]
    frames = []
    for i, row in enumerate(timeline):
        if int(row["frame"]) != i or abs(float(row["time_s"]) - i / 30) > 1e-6:
            raise ValueError(f"Frame/timestamp mismatch at row {i}")
        scene = int(row["source_frame"])
        k = scenes[scene]
        # make_panda_video.py places 640x480 RGB at (0,66), scales it to
        # 840x630; prepare_pose.py cropped its rendered video from y=68.
        pixels = predictions["keypoints_2d_smooth"][k] * np.array([840 / 640, 630 / 480]) + [0, -2]
        points = [[round(float(x), 2), round(float(y), 2)] if 0 <= x < 840 and 0 <= y < 646 else None
                  for x, y in pixels]
        predicted_q = np.rad2deg(predictions["q_calibrated"][k, :7])
        reference_q = np.rad2deg(predictions["gt_q"][k, :7])
        for j in range(7):
            if abs(float(predicted_q[j]) - float(row[f"q{j+1}_pred_deg"])) > .01:
                raise ValueError(f"Joint/CSV mismatch at frame {i}, J{j+1}")
        frames.append({
            "frame": i, "t": round(i / 30, 4), "source_frame": scene, "cycle": int(row["cycle"]),
            "points": points, "coverage": sum(p is not None for p in points),
            "q_deg": [round(float(value), 3) for value in predicted_q],
            "q_reference_deg": [round(float(value), 3) for value in reference_q],
            "keypoint_error_px": round(float(row["kp_error_px"]), 3),
            "source_sim": {
                "vibration_mm_s": round(float(row["vibration_mm_s"]), 3),
                "sound_dba": round(float(row["acoustic_dba"]), 3),
                "temperature_c": round(float(row["temperature_c"]), 3),
                "motor_current_a": round(float(row["motor_current_a"]), 3),
                "fault_blend": round(float(row["fault_blend"]), 3),
            },
        })
    result = {
        "source": "HoRoPose checkpoint inference saved in panda_repro/artifacts/panda_pose_predictions.npz; projected joints aligned with rendered video",
        "fps": 30.0, "duration_s": 500 / 30, "frame_count": 500,
        "width": 840, "height": 646, "landmarks": names,
        "method": "120 checkpoint predictions mapped by source_frame to 500 rendered frames; q calibrated with the first 30 DREAM ground-truth frames",
        "telemetry_note": "source_sim channels are simulated values burned into the supplied MP4, not physical sensor measurements",
        "frames": frames,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"frames": len(frames), "unique_source_frames": len({f["source_frame"] for f in frames}),
            "visible_keypoints": sum(f["coverage"] for f in frames), "output": str(output)}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
