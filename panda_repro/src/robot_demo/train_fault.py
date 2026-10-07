"""Train the multimodal synthetic-fault classifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split

from .faults import FAULTS, extract_features, simulate_cycle


def train(output: Path, samples: int = 5000, seed: int = 19) -> dict:
    rng = np.random.default_rng(seed)
    features, labels, joints = [], [], []
    feature_names = None
    for idx in range(samples):
        label = FAULTS[int(rng.integers(len(FAULTS)))]
        joint = -1 if label == "normal" else int(rng.integers(0, 6))
        cycle = simulate_cycle(label, joint, seed=seed * 100000 + idx)
        x, feature_names = extract_features(cycle)
        features.append(x)
        labels.append(label)
        joints.append(joint)
    X = np.asarray(features)
    y = np.asarray(labels)
    j = np.asarray(joints)
    X_train, X_test, y_train, y_test, j_train, j_test = train_test_split(
        X, y, j, test_size=0.22, random_state=seed, stratify=y
    )
    cause_model = ExtraTreesClassifier(n_estimators=260, min_samples_leaf=2, n_jobs=-1, random_state=seed)
    joint_model = ExtraTreesClassifier(n_estimators=260, min_samples_leaf=2, n_jobs=-1, random_state=seed + 1)
    cause_model.fit(X_train, y_train)
    joint_model.fit(X_train, j_train)
    cause_pred = cause_model.predict(X_test)
    joint_pred = joint_model.predict(X_test)
    metrics = {
        "scope": "synthetic historical six-DoF toy generator; not factory accuracy",
        "evaluation_protocol": "random cycle split from the same generator; no external fault test",
        "feature_schema": "derivatives_v2",
        "samples": samples,
        "fault_accuracy": float(accuracy_score(y_test, cause_pred)),
        "joint_accuracy": float(accuracy_score(j_test[y_test != "normal"], joint_pred[y_test != "normal"])),
        "labels": FAULTS,
        "confusion_matrix": confusion_matrix(y_test, cause_pred, labels=FAULTS).tolist(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "feature_schema": "derivatives_v2",
        "cause_model": cause_model, "joint_model": joint_model,
        "feature_names": feature_names, "metrics": metrics,
    }, output)
    (output.parent / "fault_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/fault_model.joblib"))
    parser.add_argument("--samples", type=int, default=5000)
    args = parser.parse_args()
    train(args.output, args.samples)


if __name__ == "__main__":
    main()
