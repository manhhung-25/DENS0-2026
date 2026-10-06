"""Long-term 2D robot landmark tracking with CoTracker3.

The public RoboPose checkpoints do not contain an ABB model.  This module is
therefore the temporal observation layer for the ABB concept demo: CoTracker3
follows several pixels around each manually initialized joint, and a robust
consensus turns those support tracks into one J1--J6/TCP trajectory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter


DEFAULT_LANDMARKS = np.asarray(
    [
        [497, 600],  # robot base
        [503, 515],  # J1/base rotation housing
        [535, 405],  # J2/shoulder
        [588, 232],  # J3/elbow
        [680, 198],  # J4/forearm roll
        [748, 274],  # J5/wrist bend
        [778, 367],  # TCP/tool centre point
    ],
    dtype=np.float32,
)


def support_points(centres: np.ndarray, radius: float = 8.0) -> np.ndarray:
    """Create a compact 3x3 point group around every initialized landmark."""
    offsets = np.asarray(
        [
            [0, 0], [-radius, 0], [radius, 0], [0, -radius], [0, radius],
            [-radius, -radius], [radius, -radius], [-radius, radius],
            [radius, radius],
        ],
        dtype=np.float32,
    )
    return centres[:, None, :] + offsets[None, :, :]


def aggregate_support_tracks(
    tracks: np.ndarray,
    visibility: np.ndarray,
    initial_support: np.ndarray,
    initial_centres: np.ndarray,
    minimum_visible: int = 2,
) -> tuple[np.ndarray, np.ndarray]:
    """Fuse support tracks into robust landmark centres.

    Parameters use shapes ``[T, J, K, 2]`` and ``[T, J, K]``.  Median motion
    rejects individual pixels that drift to the background.  Missing intervals
    remain NaN here and are repaired by :func:`repair_and_resample_tracks`.
    """
    if tracks.shape[:-1] != visibility.shape:
        raise ValueError("tracks and visibility shapes do not match")
    if tracks.shape[1:3] != initial_support.shape[:2]:
        raise ValueError("support-point layout does not match track layout")

    steps, joints, _, _ = tracks.shape
    centres = np.full((steps, joints, 2), np.nan, dtype=np.float32)
    confidence = visibility.mean(axis=2).astype(np.float32)
    initial_displacement_origin = initial_support.astype(np.float32)

    for step in range(steps):
        for joint in range(joints):
            valid = visibility[step, joint]
            if int(valid.sum()) < minimum_visible:
                continue
            displacement = (
                tracks[step, joint, valid]
                - initial_displacement_origin[joint, valid]
            )
            centres[step, joint] = (
                initial_centres[joint] + np.median(displacement, axis=0)
            )
    centres[0] = initial_centres
    confidence[0] = 1.0
    return centres, confidence


def repair_and_resample_tracks(
    sampled_centres: np.ndarray,
    sampled_confidence: np.ndarray,
    sampled_indices: np.ndarray,
    output_steps: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Repair occlusion gaps, reject weak outliers and resample to every frame."""
    repaired = sampled_centres.astype(np.float64).copy()
    confidence = sampled_confidence.astype(np.float64).copy()
    sample_axis = np.asarray(sampled_indices, dtype=np.float64)

    for joint in range(repaired.shape[1]):
        for axis in range(2):
            values = repaired[:, joint, axis]
            valid = np.isfinite(values)
            if valid.sum() < 2:
                values[:] = sampled_centres[0, joint, axis]
            else:
                values[~valid] = np.interp(
                    sample_axis[~valid], sample_axis[valid], values[valid]
                )

            local_median = median_filter(values, size=3, mode="nearest")
            suspicious = (
                (np.abs(values - local_median) > 45.0)
                & (confidence[:, joint] < 0.56)
            )
            values[suspicious] = local_median[suspicious]
            if len(values) >= 7:
                values[:] = savgol_filter(values, 7, 2, mode="interp")
            repaired[:, joint, axis] = values

    output_axis = np.arange(output_steps, dtype=np.float64)
    full = np.empty((output_steps, repaired.shape[1], 2), dtype=np.float32)
    full_confidence = np.empty((output_steps, repaired.shape[1]), dtype=np.float32)
    for joint in range(repaired.shape[1]):
        for axis in range(2):
            full[:, joint, axis] = PchipInterpolator(
                sample_axis, repaired[:, joint, axis], extrapolate=True
            )(output_axis)
        full_confidence[:, joint] = np.interp(
            output_axis, sample_axis, confidence[:, joint]
        )

    full[..., 0] = np.clip(full[..., 0], 2, 1277)
    full[..., 1] = np.clip(full[..., 1], 2, 717)
    return full, np.clip(full_confidence, 0.0, 1.0)


def visual_motion(tracks: np.ndarray) -> np.ndarray:
    """Median inter-frame landmark speed in pixels/frame."""
    speed = np.linalg.norm(np.diff(tracks, axis=0, prepend=tracks[:1]), axis=2)
    return np.median(speed, axis=1).astype(np.float32)


def run_cotracker(
    frames_bgr: list[np.ndarray],
    cotracker_repo: Path,
    checkpoint: Path,
    initial_centres: np.ndarray = DEFAULT_LANDMARKS,
    tracking_stride: int = 2,
    inference_size: tuple[int, int] = (640, 360),
    device: str | None = None,
) -> dict[str, np.ndarray | str | int]:
    """Track ABB landmarks across a video with the official CoTracker3 model."""
    repo = cotracker_repo.resolve()
    checkpoint = checkpoint.resolve()
    if not (repo / "cotracker" / "predictor.py").exists():
        raise FileNotFoundError(f"CoTracker repository not found: {repo}")
    if not checkpoint.exists():
        raise FileNotFoundError(f"CoTracker checkpoint not found: {checkpoint}")
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from cotracker.predictor import CoTrackerPredictor

    frame_count = len(frames_bgr)
    sampled_indices = np.arange(0, frame_count, tracking_stride, dtype=np.int32)
    if sampled_indices[-1] != frame_count - 1:
        sampled_indices = np.r_[sampled_indices, frame_count - 1]

    input_width, input_height = inference_size
    original_height, original_width = frames_bgr[0].shape[:2]
    rgb = [
        cv2.cvtColor(
            cv2.resize(frames_bgr[index], inference_size, interpolation=cv2.INTER_AREA),
            cv2.COLOR_BGR2RGB,
        )
        for index in sampled_indices
    ]
    video = torch.from_numpy(np.stack(rgb)).permute(0, 3, 1, 2).float()[None]

    groups_original = support_points(initial_centres)
    scale = np.asarray(
        [input_width / original_width, input_height / original_height],
        dtype=np.float32,
    )
    query_xy = (groups_original.reshape(-1, 2) * scale).astype(np.float32)
    queries = torch.from_numpy(
        np.column_stack([np.zeros(len(query_xy), dtype=np.float32), query_xy])
    )[None]

    selected_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = CoTrackerPredictor(
        checkpoint=str(checkpoint), offline=True, window_len=60
    ).to(selected_device).eval()
    with torch.inference_mode():
        predicted, visible = model(
            video.to(selected_device), queries=queries.to(selected_device)
        )

    sampled_support = predicted[0].cpu().numpy() / scale
    sampled_visibility = visible[0].cpu().numpy().astype(bool)
    joints, support_count = groups_original.shape[:2]
    sampled_support = sampled_support.reshape(-1, joints, support_count, 2)
    sampled_visibility = sampled_visibility.reshape(-1, joints, support_count)
    sampled_centres, sampled_confidence = aggregate_support_tracks(
        sampled_support,
        sampled_visibility,
        groups_original,
        initial_centres,
    )
    full_centres, full_confidence = repair_and_resample_tracks(
        sampled_centres, sampled_confidence, sampled_indices, frame_count
    )

    return {
        "keypoints_2d": full_centres,
        "joint_confidence": full_confidence,
        "visual_motion": visual_motion(full_centres),
        "sampled_support_tracks": sampled_support.astype(np.float32),
        "sampled_support_visibility": sampled_visibility,
        "sampled_joint_centres": sampled_centres,
        "sampled_indices": sampled_indices,
        "initial_support_points": groups_original,
        "tracking_stride": int(tracking_stride),
        "tracker": "CoTracker3 scaled offline",
        "device": selected_device,
    }
