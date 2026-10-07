"""Historical six-DoF toy cycles; seven-joint research lives in research_pipeline.

Legacy extraction is explicit for already packaged checkpoint compatibility.
These parameters and signals are not calibrated Panda mechanical measurements.
"""

from __future__ import annotations

import numpy as np


FAULTS = ["normal", "bearing_fault", "gearbox_backlash", "motor_overload", "encoder_error"]


def simulate_cycle(label: str = "normal", faulty_joint: int | None = None,
                   steps: int = 96, seed: int = 0) -> dict[str, np.ndarray | float | int | str]:
    if label not in FAULTS:
        raise ValueError(f"Unknown fault: {label}")
    rng = np.random.default_rng(seed)
    if faulty_joint is None:
        faulty_joint = -1 if label == "normal" else int(rng.integers(0, 6))
    phase = np.linspace(0, 2 * np.pi, steps, endpoint=False)
    offsets = rng.uniform(-0.35, 0.35, 6)
    amplitudes = rng.uniform(0.22, 0.7, 6)
    phases = rng.uniform(-0.5, 0.5, 6)
    target = offsets[None] + amplitudes[None] * np.sin(phase[:, None] + phases[None])
    actual = target + rng.normal(0, 0.0035, target.shape)
    severity = float(rng.uniform(0.48, 1.18))
    load_factor = float(rng.uniform(0.78, 1.28))
    ambient = float(rng.uniform(29.0, 37.0))
    vibration = np.abs(rng.normal(0.045, 0.018, target.shape)) * rng.uniform(0.78, 1.28, (1, 6))
    acoustic = np.abs(rng.normal(0.038, 0.016, target.shape)) * rng.uniform(0.8, 1.25, (1, 6))
    temperature = ambient + rng.normal(0, 0.38, target.shape) + np.linspace(0, rng.uniform(0.3, 1.2), steps)[:, None]
    velocity = np.gradient(actual, axis=0)
    current = (0.7 + 1.9 * np.abs(velocity)) * load_factor + rng.normal(0, 0.08, target.shape)
    cycle_time = float(rng.normal(5.0, 0.18))

    if label != "normal":
        j = faulty_joint
        if label == "bearing_fault":
            impulses = (np.sin(phase * 13.0) > 0.92).astype(float)
            vibration[:, j] += severity * (0.08 + 0.17 * impulses + 0.025 * np.sin(phase * 18.0))
            acoustic[:, j] += severity * (0.045 + 0.10 * impulses)
            temperature[:, j] += severity * np.linspace(0.25, 1.8, steps)
            cycle_time += severity * 0.14
        elif label == "gearbox_backlash":
            direction = np.sign(np.gradient(target[:, j]))
            actual[:, j] -= severity * 0.048 * direction
            reversals = np.abs(np.gradient(direction)) > 0
            vibration[:, j] += severity * (0.055 + 0.13 * reversals)
            acoustic[:, j] += severity * (0.04 + 0.11 * reversals)
            cycle_time += severity * 0.52
        elif label == "motor_overload":
            lag = 4
            actual[:, j] = np.roll(target[:, j], lag)
            actual[:lag, j] = target[0, j]
            current[:, j] += severity * (0.9 + 0.4 * np.abs(velocity[:, j]))
            temperature[:, j] += severity * np.linspace(0.55, 3.8, steps)
            vibration[:, j] += severity * 0.035
            cycle_time += severity * 0.95
        elif label == "encoder_error":
            bias = rng.choice([-1, 1]) * severity * rng.uniform(0.05, 0.12)
            actual[:, j] += bias + rng.normal(0, 0.022, steps)
            cycle_time += severity * 0.28

    position_error = actual - target
    return {
        "label": label, "faulty_joint": int(faulty_joint), "cycle_time": cycle_time,
        "target": target.astype(np.float32), "actual": actual.astype(np.float32),
        "vibration": vibration.astype(np.float32), "acoustic": acoustic.astype(np.float32),
        "temperature": temperature.astype(np.float32), "current": current.astype(np.float32),
        "position_error": position_error.astype(np.float32),
    }


def extract_features(cycle: dict, *, feature_schema="derivatives_v2") -> tuple[np.ndarray, list[str]]:
    values, names = [float(cycle["cycle_time"])], ["cycle_time"]
    for modality in ["vibration", "acoustic", "temperature", "current", "position_error"]:
        x = np.asarray(cycle[modality])
        for stat_name, stat in [("mean", np.mean), ("max", np.max), ("std", np.std)]:
            result = stat(np.abs(x), axis=0)
            values.extend(result.tolist())
            names.extend([f"{modality}_{stat_name}_j{j + 1}" for j in range(6)])
    actual = np.asarray(cycle["actual"])
    if feature_schema == "legacy_v1":
        # Historical weights learned this second difference without a time unit.
        # Retain it only when reading those weights; it is NOT physical jerk.
        jerk = np.diff(actual, n=2, axis=0)
        motion_name = "legacy_second_difference"
    elif feature_schema == "derivatives_v2":
        dt = float(cycle["cycle_time"]) / len(actual)
        jerk = np.diff(actual, n=3, axis=0) / dt**3
        motion_name = "pose_jerk_rad_s3"
    else:
        raise ValueError("Unknown feature schema")
    values.extend(np.max(np.abs(jerk), axis=0).tolist())
    names.extend([f"{motion_name}_j{j + 1}" for j in range(6)])
    return np.asarray(values, dtype=np.float32), names
