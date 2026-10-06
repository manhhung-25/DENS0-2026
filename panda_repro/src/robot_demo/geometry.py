"""Differentiable kinematics and camera projection for a 6-DoF demo robot."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import torch


JOINT_AXES = np.asarray(
    [[0, 0, 1], [0, 1, 0], [0, 1, 0], [1, 0, 0], [0, 1, 0], [1, 0, 0]],
    dtype=np.float32,
)
LINK_OFFSETS = np.asarray(
    [[0.0, 0.0, 0.30], [0.32, 0.0, 0.0], [0.28, 0.0, 0.0],
     [0.20, 0.0, 0.0], [0.16, 0.0, 0.0], [0.12, 0.0, 0.0]],
    dtype=np.float32,
)
JOINT_LOW = np.asarray([-math.pi, -1.35, -1.35, -math.pi, -1.35, -math.pi], dtype=np.float32)
JOINT_HIGH = np.asarray([math.pi, 1.35, 1.35, math.pi, 1.35, math.pi], dtype=np.float32)

# [tx, ty, tz, roll, pitch, yaw] sampling limits.
BASE_LOW = np.asarray([-0.16, -0.12, -0.02, -0.12, -0.12, -0.45], dtype=np.float32)
BASE_HIGH = np.asarray([0.16, 0.12, 0.08, 0.12, 0.12, 0.45], dtype=np.float32)


@dataclass(frozen=True)
class Camera:
    width: int = 128
    height: int = 128
    focal: float = 125.0
    eye: tuple[float, float, float] = (1.65, -1.65, 1.25)
    target: tuple[float, float, float] = (0.25, 0.0, 0.48)
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)

    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        eye = np.asarray(self.eye, dtype=np.float32)
        target = np.asarray(self.target, dtype=np.float32)
        up = np.asarray(self.up, dtype=np.float32)
        forward = target - eye
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, up)
        right /= np.linalg.norm(right)
        true_up = np.cross(right, forward)
        return right, true_up, forward


def _rot_np(axis: np.ndarray, angle: float) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    c, s = math.cos(float(angle)), math.sin(float(angle))
    C = 1.0 - c
    return np.asarray([
        [c + x*x*C, x*y*C - z*s, x*z*C + y*s],
        [y*x*C + z*s, c + y*y*C, y*z*C - x*s],
        [z*x*C - y*s, z*y*C + x*s, c + z*z*C],
    ], dtype=np.float32)


def rpy_np(rpy: np.ndarray) -> np.ndarray:
    rx, ry, rz = rpy
    return _rot_np(np.asarray([0, 0, 1], np.float32), rz) @ _rot_np(
        np.asarray([0, 1, 0], np.float32), ry
    ) @ _rot_np(np.asarray([1, 0, 0], np.float32), rx)


def forward_kinematics_np(state: np.ndarray) -> np.ndarray:
    """Return 7 keypoints (base + six link ends) in world coordinates."""
    q, base = np.asarray(state[:6]), np.asarray(state[6:12])
    R = rpy_np(base[3:6])
    t = base[:3].astype(np.float32).copy()
    points = [t.copy()]
    for axis, offset, angle in zip(JOINT_AXES, LINK_OFFSETS, q):
        R = R @ _rot_np(axis, float(angle))
        t = t + R @ offset
        points.append(t.copy())
    return np.asarray(points, dtype=np.float32)


def project_np(points: np.ndarray, camera: Camera = Camera()) -> tuple[np.ndarray, np.ndarray]:
    right, up, forward = camera.basis()
    eye = np.asarray(camera.eye, dtype=np.float32)
    rel = points - eye[None]
    cam = np.stack([rel @ right, rel @ up, rel @ forward], axis=-1)
    depth = np.maximum(cam[:, 2], 1e-4)
    u = camera.width / 2 + camera.focal * cam[:, 0] / depth
    v = camera.height / 2 - camera.focal * cam[:, 1] / depth
    return np.stack([u, v], axis=-1).astype(np.float32), cam[:, 2]


def _skew_torch(axis: torch.Tensor) -> torch.Tensor:
    x, y, z = axis.unbind(-1)
    zero = torch.zeros_like(x)
    return torch.stack([zero, -z, y, z, zero, -x, -y, x, zero], dim=-1).reshape(*axis.shape[:-1], 3, 3)


def _rot_torch(axis: torch.Tensor, angle: torch.Tensor) -> torch.Tensor:
    axis = axis / torch.linalg.vector_norm(axis)
    K = _skew_torch(axis)
    eye = torch.eye(3, dtype=angle.dtype, device=angle.device)
    return eye + torch.sin(angle) * K + (1.0 - torch.cos(angle)) * (K @ K)


def rpy_torch(rpy: torch.Tensor) -> torch.Tensor:
    axes = torch.eye(3, dtype=rpy.dtype, device=rpy.device)
    return _rot_torch(axes[2], rpy[2]) @ _rot_torch(axes[1], rpy[1]) @ _rot_torch(axes[0], rpy[0])


def forward_kinematics_torch(state: torch.Tensor) -> torch.Tensor:
    """Differentiable FK for one 12-value state tensor."""
    q, base = state[:6], state[6:12]
    axes = torch.as_tensor(JOINT_AXES, dtype=state.dtype, device=state.device)
    offsets = torch.as_tensor(LINK_OFFSETS, dtype=state.dtype, device=state.device)
    R = rpy_torch(base[3:6])
    t = base[:3]
    points = [t]
    for idx in range(6):
        R = R @ _rot_torch(axes[idx], q[idx])
        t = t + R @ offsets[idx]
        points.append(t)
    return torch.stack(points)


def project_torch(points: torch.Tensor, camera: Camera = Camera()) -> torch.Tensor:
    right, up, forward = camera.basis()
    eye = torch.as_tensor(camera.eye, dtype=points.dtype, device=points.device)
    right_t = torch.as_tensor(right, dtype=points.dtype, device=points.device)
    up_t = torch.as_tensor(up, dtype=points.dtype, device=points.device)
    forward_t = torch.as_tensor(forward, dtype=points.dtype, device=points.device)
    rel = points - eye
    x, y, z = rel @ right_t, rel @ up_t, rel @ forward_t
    z = torch.clamp(z, min=1e-4)
    u = camera.width / 2 + camera.focal * x / z
    v = camera.height / 2 - camera.focal * y / z
    return torch.stack([u, v], dim=-1)


def sample_state(rng: np.random.Generator) -> np.ndarray:
    q = rng.uniform(JOINT_LOW * 0.72, JOINT_HIGH * 0.72)
    base = rng.uniform(BASE_LOW, BASE_HIGH)
    return np.concatenate([q, base]).astype(np.float32)


def sample_cycle_state(rng: np.random.Generator) -> np.ndarray:
    """Sample from a realistic repetitive pick-and-place motion manifold.

    Industrial monitoring observes a small family of programmed trajectories,
    not arbitrary independent configurations of every joint. This prior also
    reduces the monocular depth ambiguity of 2D-to-joint lifting.
    """
    phase = float(rng.uniform(0, 2 * math.pi))
    center = np.asarray([0.0, -0.38, 0.48, 0.0, 0.28, 0.0], dtype=np.float32)
    amplitude = np.asarray([1.05, 0.48, 0.58, 0.70, 0.42, 0.82], dtype=np.float32)
    phase_offset = np.asarray([0.0, 0.8, 1.45, 0.35, 1.9, 0.95], dtype=np.float32)
    harmonic = np.asarray([0.08, 0.04, 0.05, 0.07, 0.04, 0.06], dtype=np.float32)
    q = center + amplitude * np.sin(phase + phase_offset)
    q += harmonic * np.sin(2 * phase + phase_offset * 0.7)
    q += rng.normal(0, 0.025, 6)
    q = np.clip(q, JOINT_LOW, JOINT_HIGH)
    base_center = np.asarray([0.0, 0.0, 0.02, 0.0, 0.0, 0.0], dtype=np.float32)
    base_span = (BASE_HIGH - BASE_LOW) * 0.12
    base = base_center + rng.uniform(-base_span, base_span)
    return np.concatenate([q, base]).astype(np.float32)
