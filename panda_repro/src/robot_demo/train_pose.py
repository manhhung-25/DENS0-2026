"""Train/evaluate the synthetic RGB pose pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.utils.data import DataLoader

from .geometry import BASE_HIGH, BASE_LOW, Camera, JOINT_HIGH, JOINT_LOW, forward_kinematics_torch, project_torch
from .models import PoseDataset, PosePipeline
from .simulator import render_state


def denormalize_state(value: torch.Tensor, mean: np.ndarray, std: np.ndarray) -> torch.Tensor:
    return value * torch.as_tensor(std, dtype=value.dtype, device=value.device) + torch.as_tensor(
        mean, dtype=value.dtype, device=value.device
    )


def refine_state(initial: np.ndarray, target_kp_norm: np.ndarray, camera: Camera,
                 steps: int = 100, lr: float = 0.035) -> np.ndarray:
    """RoboPose-style differentiable render-and-compare refinement."""
    state = torch.tensor(initial, dtype=torch.float32, requires_grad=True)
    target = torch.tensor(target_kp_norm, dtype=torch.float32)
    prior = torch.tensor(initial, dtype=torch.float32)
    optimizer = torch.optim.Adam([state], lr=lr)
    for _ in range(steps):
        projected = project_torch(forward_kinematics_torch(state), camera)
        projected_norm = projected.clone()
        projected_norm[:, 0] = projected_norm[:, 0] / (camera.width - 1) * 2 - 1
        projected_norm[:, 1] = projected_norm[:, 1] / (camera.height - 1) * 2 - 1
        loss = ((projected_norm - target) ** 2).mean() + 0.001 * ((state - prior) ** 2).mean()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            state[:6].clamp_(torch.as_tensor(JOINT_LOW), torch.as_tensor(JOINT_HIGH))
            state[6:12].clamp_(torch.as_tensor(BASE_LOW), torch.as_tensor(BASE_HIGH))
    return state.detach().cpu().numpy()


def draw_keypoints(image: np.ndarray, kp: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    out = image.copy()
    for p in kp:
        cv2.circle(out, tuple(np.round(p).astype(int)), 3, color, -1, cv2.LINE_AA)
    return out


def train(data_path: Path, output_dir: Path, epochs: int, batch_size: int,
          seed: int = 11) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = np.load(data_path)
    n = len(raw["images"])
    indices = np.random.default_rng(seed).permutation(n)
    split = int(n * 0.82)
    train_idx, test_idx = indices[:split], indices[split:]
    mean = raw["states"][train_idx].mean(axis=0)
    std = raw["states"][train_idx].std(axis=0) + 1e-6
    train_ds = PoseDataset(str(data_path), train_idx, mean, std)
    test_ds = PoseDataset(str(data_path), test_idx, mean, std)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = PosePipeline().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    history = []
    for epoch in range(epochs):
        model.train()
        running = 0.0
        for image, kp, state in train_loader:
            image, kp, state = image.to(device), kp.to(device), state.to(device)
            pred_kp, pred_state = model(image)
            # Teacher-forced lifting stabilizes the 2D->state stage. The
            # end-to-end term still teaches it to tolerate detector errors.
            teacher_state = model.lifter(kp + torch.randn_like(kp) * 0.012)
            kp_loss = torch.nn.functional.smooth_l1_loss(pred_kp, kp)
            state_loss = torch.nn.functional.smooth_l1_loss(teacher_state, state)
            e2e_loss = torch.nn.functional.smooth_l1_loss(pred_state, state)
            loss = 3.5 * kp_loss + state_loss + 0.25 * e2e_loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            running += float(loss.detach()) * len(image)
        history.append(running / len(train_ds))
        print(f"epoch {epoch + 1:02d}/{epochs}: loss={history[-1]:.5f}")

    model.eval()
    all_kp, all_state, all_gt_kp, all_gt_state = [], [], [], []
    with torch.no_grad():
        for image, kp, state in test_loader:
            pred_kp, pred_state = model(image.to(device))
            all_kp.append(pred_kp.cpu())
            all_state.append(pred_state.cpu())
            all_gt_kp.append(kp)
            all_gt_state.append(state)
    pred_kp = torch.cat(all_kp).numpy()
    pred_state_n = torch.cat(all_state).numpy()
    gt_kp = torch.cat(all_gt_kp).numpy()
    gt_state_n = torch.cat(all_gt_state).numpy()
    pred_state = pred_state_n * std + mean
    gt_state = gt_state_n * std + mean
    image_size = raw["images"].shape[1]
    kp_rmse_px = float(np.sqrt(np.mean((pred_kp - gt_kp) ** 2)) * (image_size - 1) / 2)
    joint_mae_deg = float(np.rad2deg(np.abs(pred_state[:, :6] - gt_state[:, :6])).mean())
    base_translation_mae_m = float(np.abs(pred_state[:, 6:9] - gt_state[:, 6:9]).mean())
    base_rotation_mae_deg = float(np.rad2deg(np.abs(pred_state[:, 9:12] - gt_state[:, 9:12])).mean())

    checkpoint = {
        "model": model.cpu().state_dict(), "state_mean": mean, "state_std": std,
        "image_size": image_size, "history": history,
    }
    torch.save(checkpoint, output_dir / "pose_model.pt")

    # One visible qualitative example and geometric refinement.
    # Pick a well-spread pose for the qualitative panel; quantitative metrics
    # above still use the full held-out split.
    candidate_kp = raw["keypoints"][test_idx[: min(120, len(test_idx))]]
    extent = candidate_kp.max(axis=1) - candidate_kp.min(axis=1)
    sample_pos = int(np.argmax(extent[:, 0] * extent[:, 1]))
    sample_global = int(test_idx[sample_pos])
    image = raw["images"][sample_global]
    target_kp_norm = pred_kp[sample_pos]
    camera = Camera(width=image_size, height=image_size, focal=image_size * 0.9765625)
    refined = refine_state(pred_state[sample_pos], target_kp_norm, camera)
    _, initial_px = render_state(pred_state[sample_pos], camera, seed=0, domain_randomization=False)
    _, refined_px = render_state(refined, camera, seed=0, domain_randomization=False)
    gt_px = raw["keypoints"][sample_global]
    observed_px = target_kp_norm.copy()
    observed_px[:, 0] = (observed_px[:, 0] + 1) * (image_size - 1) / 2
    observed_px[:, 1] = (observed_px[:, 1] + 1) * (image_size - 1) / 2
    overlay = draw_keypoints(image, gt_px, (30, 220, 30))
    overlay = draw_keypoints(overlay, initial_px, (230, 60, 45))
    overlay = draw_keypoints(overlay, refined_px, (35, 120, 245))
    plt.figure(figsize=(5.2, 5.2))
    plt.imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    plt.title("Green=GT, Red=initial, Blue=render-and-compare")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_dir / "pose_example.png", dpi=150)
    plt.close()

    init_reproj = float(np.sqrt(np.mean((initial_px - gt_px) ** 2)))
    refined_reproj = float(np.sqrt(np.mean((refined_px - gt_px) ** 2)))
    initial_observation_residual = float(np.sqrt(np.mean((initial_px - observed_px) ** 2)))
    refined_observation_residual = float(np.sqrt(np.mean((refined_px - observed_px) ** 2)))
    metrics = {
        "device": str(device), "train_samples": len(train_ds), "test_samples": len(test_ds),
        "epochs": epochs, "keypoint_rmse_px": kp_rmse_px,
        "joint_mae_deg": joint_mae_deg,
        "base_translation_mae_m": base_translation_mae_m,
        "base_rotation_mae_deg": base_rotation_mae_deg,
        "example_initial_to_ground_truth_rmse_px": init_reproj,
        "example_refined_to_ground_truth_rmse_px": refined_reproj,
        "example_initial_to_observation_rmse_px": initial_observation_residual,
        "example_refined_to_observation_rmse_px": refined_observation_residual,
    }
    (output_dir / "pose_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("artifacts/pose_dataset.npz"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    train(args.data, args.output_dir, args.epochs, args.batch_size)


if __name__ == "__main__":
    main()
