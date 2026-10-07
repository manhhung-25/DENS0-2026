"""Observable-only features. Labels/latent severity/baseline never enter X."""
import numpy as np
from .physics import FAULTS, derivatives

WINDOW_S = 1.4
STRIDE_S = .4


def extract_features(cycle, end=None, modalities="all"):
    end = len(cycle["t"]) if end is None else end
    start = max(0, end - round(WINDOW_S / cycle["dt"]))
    s = slice(start, end)
    v, a, j = derivatives(cycle["camera"][s], cycle["dt"])
    # Commands/context are observed simulator inputs; camera/encoder are separate.
    channels = {"vibration": cycle["vibration"][s],
                "acoustic": cycle["acoustic"][s],
                "temperature_rise": cycle["temperature"][s] - cycle["ambient"],
                "current": cycle["current"][s] / cycle["load"],
                "tracking_error": cycle["camera"][s] - cycle["target"][s],
                "encoder_camera_error": cycle["encoder"][s] - cycle["camera"][s],
                "velocity": v, "acceleration": a, "jerk": j}
    if modalities == "vibration":
        channels = {"vibration": channels["vibration"]}
    elif modalities == "vibration_pose":
        channels = {k: x for k, x in channels.items() if k in ("vibration", "tracking_error", "encoder_camera_error", "velocity", "acceleration", "jerk")}
    elif modalities != "all":
        raise ValueError("Unknown modality group")
    values, names = [], []
    for name, x in channels.items():
        # Robust quantiles reduce camera-noise derivative spikes.
        for stat, value in (("rms", np.sqrt(np.mean(x*x, axis=0))),
                            ("p90", np.quantile(np.abs(x), .9, axis=0)),
                            ("std", np.std(x, axis=0))):
            values.extend(value)
            names.extend(f"{name}_{stat}_J{k+1}" for k in range(7))
            # Joint-invariant evidence matters when only a few faulty cycles exist.
            # Preserve per-joint features while exposing excess over other joints.
            ordered = np.sort(value)
            values.extend([ordered[-1],ordered[-2],np.median(value),ordered[-1]-np.median(value)])
            names.extend(f"{name}_{stat}_{pool}" for pool in ("max_joint","second_joint","median_joint","excess_joint"))
    return np.asarray(values), names


def windows(cycle, modalities="all"):
    minimum = round(WINDOW_S / cycle["dt"])
    stride = max(1, round(STRIDE_S / cycle["dt"]))
    ends = list(range(minimum, len(cycle["t"]) + 1, stride))
    if ends[-1] != len(cycle["t"]):
        ends.append(len(cycle["t"]))
    X, y = [], []
    for end in ends:
        X.append(extract_features(cycle, end, modalities)[0])
        # This is a supervision label only, never a feature.
        active = bool(cycle["truth"][end - 1].any())
        y.append(cycle["label"] if active else "normal")
    return np.asarray(X), np.asarray(y), cycle["t"][np.asarray(ends)-1]


def augment(cycle, rng):
    """Small measurement gain/noise augmentation; retain timing and shared motion.

    Derived motion features are recomputed from the transformed measurements.
    Never augment validation/test; label/severity metadata is evaluation-only.
    """
    out = {k: v.copy() if isinstance(v, np.ndarray) else v for k, v in cycle.items()}
    for key, noise in (("vibration", .04), ("acoustic", .35), ("current", .025)):
        out[key] = out[key] * rng.uniform(.96, 1.04, (1, 7)) + rng.normal(0, noise, out[key].shape)
        if key != "acoustic":
            out[key] = np.maximum(.001, out[key])
    # A shared offset preserves the encoder-camera residual.
    shift = rng.normal(0, .002, (1, 7))
    out["camera"] += shift
    out["encoder"] += shift
    out["temperature"] += rng.normal(0, .08, (1, 7))
    return out
