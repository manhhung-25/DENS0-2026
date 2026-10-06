"""Run the complete pose -> fault diagnosis -> event feedback workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import joblib
import matplotlib.pyplot as plt
import numpy as np
import torch

from .event_store import EventStore
from .faults import extract_features, simulate_cycle
from .geometry import Camera
from .models import PosePipeline
from .simulator import render_state
from .train_pose import refine_state


def run(artifacts: Path, fault: str = "gearbox_backlash", joint: int = 2) -> dict:
    pose_ckpt = torch.load(artifacts / "pose_model.pt", map_location="cpu", weights_only=False)
    model = PosePipeline()
    model.load_state_dict(pose_ckpt["model"])
    model.eval()
    demo_data = artifacts / "demo_pose_dataset.npz"
    data = np.load(demo_data if demo_data.exists() else artifacts / "pose_dataset.npz")
    extents = data["keypoints"].max(axis=1) - data["keypoints"].min(axis=1)
    sample_idx = int(np.argmax(extents[:, 0] * extents[:, 1]))
    image = data["images"][sample_idx]
    image_tensor = torch.from_numpy(image.copy()).permute(2, 0, 1).float()[None] / 255.0
    with torch.no_grad():
        kp_norm, state_norm = model(image_tensor)
    mean, std = pose_ckpt["state_mean"], pose_ckpt["state_std"]
    initial_state = state_norm[0].numpy() * std + mean
    camera = Camera(width=image.shape[1], height=image.shape[0], focal=image.shape[1] * 0.9765625)
    refined_state = refine_state(initial_state, kp_norm[0].numpy(), camera)
    _, initial_kp = render_state(initial_state, camera, domain_randomization=False)
    _, refined_kp = render_state(refined_state, camera, domain_randomization=False)
    gt_kp = data["keypoints"][sample_idx]

    bundle = joblib.load(artifacts / "fault_model.joblib")
    cycle = simulate_cycle(fault, joint, seed=20260912)
    x, names = extract_features(cycle)
    cause_model, joint_model = bundle["cause_model"], bundle["joint_model"]
    predicted_fault = str(cause_model.predict(x[None])[0])
    predicted_joint = int(joint_model.predict(x[None])[0])
    probabilities = cause_model.predict_proba(x[None])[0]
    confidence = float(np.max(probabilities))
    anomaly_gate = bool(float(cycle["cycle_time"]) > 5.25 or predicted_fault != "normal")
    summary = {
        "max_vibration": float(np.max(cycle["vibration"])),
        "max_temperature": float(np.max(cycle["temperature"])),
        "max_acoustic": float(np.max(cycle["acoustic"])),
        "max_position_error": float(np.max(np.abs(cycle["position_error"]))),
    }
    store = EventStore(artifacts / "events.db")
    event_id = store.add_event(
        "SIM-KUKA-001", "cycle-0001", float(cycle["cycle_time"]), predicted_fault,
        predicted_joint, confidence, summary,
    )
    # Demo the feedback loop. In production this comes from a technician form.
    store.add_feedback(event_id, fault, joint, "Simulated inspection record", "confirmed")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.3))
    overlay = image.copy()
    for pts, color in [(gt_kp, (30, 220, 30)), (initial_kp, (230, 60, 45)), (refined_kp, (35, 120, 245))]:
        for p in pts:
            cv2.circle(overlay, tuple(np.round(p).astype(int)), 3, color, -1, cv2.LINE_AA)
    axes[0].imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    axes[0].set_title("Pose: GT / initial / refined")
    axes[0].axis("off")
    t = np.linspace(0, float(cycle["cycle_time"]), len(cycle["vibration"]))
    axes[1].plot(t, np.asarray(cycle["vibration"])[:, joint], label="vibration")
    acoustic_scaled = np.asarray(cycle["acoustic"])[:, joint]
    axes[1].plot(t, acoustic_scaled, label="acoustic")
    axes[1].set_title(f"{predicted_fault}, predicted J{predicted_joint + 1}")
    axes[1].set_xlabel("time (s)")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(artifacts / "demo_result.png", dpi=150)
    plt.close(fig)

    result = {
        "anomaly_gate": anomaly_gate,
        "cycle_time": float(cycle["cycle_time"]),
        "true_fault": fault,
        "predicted_fault": predicted_fault,
        "true_joint": joint + 1,
        "predicted_joint": predicted_joint + 1,
        "confidence": confidence,
        "event_id": event_id,
        "event": store.get_event(event_id),
        "pose_initial_rmse_px": float(np.sqrt(np.mean((initial_kp - gt_kp) ** 2))),
        "pose_refined_rmse_px": float(np.sqrt(np.mean((refined_kp - gt_kp) ** 2))),
    }
    (artifacts / "demo_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--fault", choices=["bearing_fault", "gearbox_backlash", "motor_overload", "encoder_error"], default="gearbox_backlash")
    parser.add_argument("--joint", type=int, default=3, help="1-based joint number")
    args = parser.parse_args()
    run(args.artifacts, args.fault, args.joint - 1)


if __name__ == "__main__":
    main()
