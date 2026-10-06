"""Lightweight RGB simulator with automatic pose/keypoint labels."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import cv2
import numpy as np

from .geometry import Camera, forward_kinematics_np, project_np, sample_cycle_state, sample_state


LINK_COLORS = [
    (222, 108, 65), (75, 160, 235), (105, 196, 123),
    (188, 111, 213), (238, 186, 73), (80, 203, 210),
]


def render_state(state: np.ndarray, camera: Camera = Camera(), seed: int = 0,
                 domain_randomization: bool = True) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    h, w = camera.height, camera.width
    if domain_randomization:
        base_color = rng.integers(168, 236, size=3, dtype=np.uint8)
    else:
        base_color = np.asarray([220, 224, 230], dtype=np.uint8)
    image = np.broadcast_to(base_color, (h, w, 3)).copy()

    # Factory-like floor/grid and mild texture.
    for x in range(0, w, 16):
        cv2.line(image, (x, 0), (x, h - 1), tuple(int(v * 0.92) for v in base_color), 1)
    for y in range(0, h, 16):
        cv2.line(image, (0, y), (w - 1, y), tuple(int(v * 0.92) for v in base_color), 1)
    noise = rng.normal(0, 3.0 if domain_randomization else 0.5, image.shape)
    image = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    points_3d = forward_kinematics_np(state)
    points_2d, depth = project_np(points_3d, camera)
    order = np.argsort(depth[:-1])[::-1]
    for idx in order:
        p0 = tuple(np.round(points_2d[idx]).astype(int))
        p1 = tuple(np.round(points_2d[idx + 1]).astype(int))
        color = LINK_COLORS[idx]
        cv2.line(image, p0, p1, color, 9, cv2.LINE_AA)
        cv2.line(image, p0, p1, tuple(max(c - 45, 0) for c in color), 2, cv2.LINE_AA)
    for idx, p in enumerate(points_2d):
        center = tuple(np.round(p).astype(int))
        cv2.circle(image, center, 6 if idx else 8, (35, 38, 44), -1, cv2.LINE_AA)
        cv2.circle(image, center, 3, (242, 242, 242), -1, cv2.LINE_AA)

    if domain_randomization:
        image = cv2.GaussianBlur(image, (3, 3), sigmaX=float(rng.uniform(0.0, 0.7)))
        image = np.clip(image.astype(np.float32) * rng.uniform(0.86, 1.13), 0, 255).astype(np.uint8)
    return image, points_2d


def generate_dataset(output: Path, samples: int = 1500, image_size: int = 128,
                     seed: int = 7, motion_mode: str = "cycle") -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    camera = Camera(width=image_size, height=image_size, focal=image_size * 0.9765625)
    rng = np.random.default_rng(seed)
    images, keypoints, states = [], [], []
    attempts = 0
    while len(images) < samples:
        attempts += 1
        if attempts > samples * 20:
            raise RuntimeError("Could not sample enough visible robot states")
        state = sample_cycle_state(rng) if motion_mode == "cycle" else sample_state(rng)
        image, kp = render_state(state, camera, seed=int(rng.integers(2**31 - 1)))
        margin = 5
        visible = np.logical_and.reduce([
            kp[:, 0] >= margin, kp[:, 0] < image_size - margin,
            kp[:, 1] >= margin, kp[:, 1] < image_size - margin,
        ])
        if not bool(visible.all()):
            continue
        images.append(image)
        keypoints.append(kp)
        states.append(state)
    # Write atomically so a stopped Colab/Kaggle cell never leaves a dataset
    # that looks valid by name but has a missing ZIP central directory.
    temp = output.with_name(output.name + ".tmp")
    with temp.open("wb") as handle:
        np.savez_compressed(
            handle,
            images=np.asarray(images, dtype=np.uint8),
            keypoints=np.asarray(keypoints, dtype=np.float32),
            states=np.asarray(states, dtype=np.float32),
            camera=np.asarray([camera.width, camera.height, camera.focal, *camera.eye, *camera.target], dtype=np.float32),
            motion_mode=np.asarray(motion_mode),
        )
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/pose_dataset.npz"))
    parser.add_argument("--samples", type=int, default=1500)
    parser.add_argument("--image-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--motion-mode", choices=["cycle", "random"], default="cycle")
    args = parser.parse_args()
    path = generate_dataset(args.output, args.samples, args.image_size, args.seed, args.motion_mode)
    print(f"saved {args.samples} synthetic RGB samples to {path}")


if __name__ == "__main__":
    main()
