"""RoboKeyGen-style keypoint detector and state lifting models."""

from __future__ import annotations

import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset


class PoseDataset(Dataset):
    def __init__(self, path: str, indices: np.ndarray, state_mean: np.ndarray,
                 state_std: np.ndarray):
        data = np.load(path)
        self.images = data["images"][indices]
        self.keypoints = data["keypoints"][indices]
        self.states = data["states"][indices]
        self.mean = state_mean.astype(np.float32)
        self.std = state_std.astype(np.float32)

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, idx: int):
        image = torch.from_numpy(self.images[idx].copy()).permute(2, 0, 1).float() / 255.0
        h, w = self.images.shape[1:3]
        kp = self.keypoints[idx].copy()
        kp[:, 0] = kp[:, 0] / (w - 1) * 2 - 1
        kp[:, 1] = kp[:, 1] / (h - 1) * 2 - 1
        state = (self.states[idx] - self.mean) / self.std
        return image, torch.from_numpy(kp), torch.from_numpy(state.astype(np.float32))


class KeypointNet(nn.Module):
    """Small integral-regression CNN that predicts seven 2D robot keypoints."""

    def __init__(self, n_keypoints: int = 7):
        super().__init__()
        self.n_keypoints = n_keypoints
        self.features = nn.Sequential(
            nn.Conv2d(3, 24, 5, stride=2, padding=2), nn.BatchNorm2d(24), nn.SiLU(),
            nn.Conv2d(24, 48, 3, stride=2, padding=1), nn.BatchNorm2d(48), nn.SiLU(),
            nn.Conv2d(48, 64, 3, padding=1), nn.BatchNorm2d(64), nn.SiLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.SiLU(),
        )
        self.head = nn.Conv2d(64, n_keypoints, 1)

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        heatmaps = self.head(self.features(image))
        b, k, h, w = heatmaps.shape
        # A modest temperature produces localized heatmaps while preserving a
        # fully differentiable soft-argmax.
        prob = torch.softmax((heatmaps * 5.0).reshape(b, k, -1), dim=-1).reshape(b, k, h, w)
        xs = torch.linspace(-1, 1, w, device=image.device, dtype=image.dtype)
        ys = torch.linspace(-1, 1, h, device=image.device, dtype=image.dtype)
        x = (prob * xs.view(1, 1, 1, w)).sum(dim=(2, 3))
        y = (prob * ys.view(1, 1, h, 1)).sum(dim=(2, 3))
        return torch.stack([x, y], dim=-1), heatmaps


class KeypointLifter(nn.Module):
    """Lift 2D keypoints into six joint angles plus 6D base pose."""

    def __init__(self, n_keypoints: int = 7, state_dim: int = 12):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_keypoints * 2, 192), nn.SiLU(), nn.Dropout(0.05),
            nn.Linear(192, 192), nn.SiLU(),
            nn.Linear(192, 96), nn.SiLU(),
            nn.Linear(96, state_dim),
        )

    def forward(self, keypoints: torch.Tensor) -> torch.Tensor:
        return self.net(keypoints.flatten(1))


class PosePipeline(nn.Module):
    def __init__(self):
        super().__init__()
        self.keypoints = KeypointNet()
        self.lifter = KeypointLifter()

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        kp, _ = self.keypoints(image)
        return kp, self.lifter(kp)
