"""Regenerate report figures from the checked-in Panda repro artifacts."""
from pathlib import Path
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
NPZ = ROOT / "panda_repro/artifacts/panda_pose_predictions.npz"
CSV = ROOT / "panda_repro/artifacts/panda_multimodal_timeseries.csv"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .18})

with np.load(NPZ, allow_pickle=False) as p:
    source_index = np.arange(len(p["q"]))
    q = np.rad2deg(p["q_calibrated"][:, :7])
    gt = np.rad2deg(p["gt_q"][:, :7])
    kp = np.linalg.norm(p["keypoints_2d_smooth"] - p["gt_keypoints_2d"], axis=2).mean(1)
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True, layout="constrained")
    for ax, j in zip(axes[:2], [3, 6]):
        ax.plot(source_index, q[:, j], color="#145c3a", lw=1.8, label="HoRoPose calibrated")
        ax.plot(source_index, gt[:, j], color="#303030", lw=1.2, ls="--", label="DREAM annotation")
        ax.set_ylabel(f"J{j+1} (deg)")
        ax.legend(loc="upper right", frameon=False)
    axes[2].plot(source_index, kp, color="#145c3a", lw=1.8)
    axes[2].set_ylabel("2D error (px)")
    axes[2].set_xlabel("Source image index")
    fig.suptitle("Checkpoint predictions on 120 DREAM RGB frames", weight="bold")
    fig.savefig(OUT / "hinh_2_pose_dream.png", dpi=160, facecolor="white")
    plt.close(fig)

with CSV.open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
ts = np.array([float(r["time_s"]) for r in rows])
fields = [("vibration_mm_s", "Vibration (mm/s)"),
          ("acoustic_dba", "Sound (dBA)"),
          ("temperature_c", "Temperature (C)"),
          ("motor_current_a", "Motor current (A)")]
fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True, layout="constrained")
for ax, (field, title) in zip(axes, fields):
    ax.plot(ts, [float(r[field]) for r in rows], color="#145c3a", lw=1.35)
    ax.axvline(238 / 30, color="#484848", ls="--", lw=1)
    ax.set_ylabel(title)
axes[-1].set_xlabel("Rendered video time (s)")
fig.suptitle("Simulated channels embedded in the 500-frame video", weight="bold")
fig.savefig(OUT / "hinh_3_cam_bien_mo_phong.png", dpi=160, facecolor="white")
plt.close(fig)
print("Generated", OUT / "hinh_2_pose_dream.png", OUT / "hinh_3_cam_bien_mo_phong.png")
