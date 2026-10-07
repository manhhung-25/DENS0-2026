"""Grouped low-shot comparisons; synthetic domain shift is not real validation."""
import csv
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, IsolationForest
from sklearn.metrics import (average_precision_score, confusion_matrix,
                            f1_score, precision_recall_fscore_support)
from . import VERSION
from .features import augment, extract_features, windows
from .physics import FAULTS, JOINT_IDS, PROFILES, quality_check, simulate_cycle


def build_dataset(output, seed=19, normal=48, scarce=3, extra=12, test_per_fault=6):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cases, records = {}, []
    counts = {"train": [normal] + [scarce]*7,
              "validation": [16] + [3]*7,
              "test": [16] + [test_per_fault]*7,
              "physics": [24] + [extra]*7}
    for split_index, (split, numbers) in enumerate(counts.items()):
        for label_index, (label, count) in enumerate(zip(FAULTS, numbers)):
            for n in range(count):
                ident = f"s{seed}-{split}-{label}-{n:03d}"
                case_seed = seed * 100000 + split_index * 10000 + label_index * 100 + n
                domain = split if split in ("validation", "test") else "train"
                c = simulate_cycle(label, seed=case_seed, domain=domain, profile=PROFILES[n % 3])
                check = quality_check(c)
                if not check["accepted"]:
                    raise ValueError(f"Rejected {ident}: {check}")
                path = output / f"{ident}.npz"
                arrays = {k: v for k, v in c.items() if isinstance(v, np.ndarray)}
                metadata = {k: v for k, v in c.items() if not isinstance(v, np.ndarray)}
                np.savez_compressed(path, **arrays, metadata=json.dumps(metadata))
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                record = dict(id=ident, split=split, file=path.name, sha256=digest,
                              metadata=metadata, quality=check)
                records.append(record)
                cases[ident] = c
    manifest = dict(schema=VERSION, seed=seed, joint_ids=JOINT_IDS, cases=records,
                    source="synthetic seven-joint lumped surrogate, no measured robot faults",
                    split_policy="entire cycles; held-out test load/speed/noise/harmonics; no augmented test data",
                    units=next(iter(cases.values()))["units"])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return cases, manifest


def load_dataset(path):
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"] != VERSION:
        raise ValueError("Dataset schema mismatch")
    cases = {}
    for row in manifest["cases"]:
        file = path / row["file"]
        if hashlib.sha256(file.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"Dataset checksum mismatch: {row['id']}")
        with np.load(file, allow_pickle=False) as z:
            c = json.loads(str(z["metadata"]))
            c.update({k: z[k] for k in z.files if k != "metadata"})
        cases[row["id"]] = c
    return cases, manifest


def select(cases, manifest, split):
    return [cases[r["id"]] for r in manifest["cases"] if r["split"] == split]


def matrix(cycles, modalities="all"):
    pairs = [windows(c, modalities) for c in cycles]
    return np.concatenate([p[0] for p in pairs]), np.concatenate([p[1] for p in pairs])


def score_classifier(model, validation, test, modalities="all"):
    vx, vy = matrix(validation, modalities)
    # Calibrate a normal-vs-fault threshold on VALIDATION, same policy for A/B/C.
    normal_index = list(model.classes_).index("normal")
    vp = 1 - model.predict_proba(vx)[:, normal_index]
    candidates = np.linspace(.05, .95, 37)
    best = max(candidates, key=lambda th: (f1_score(vy != "normal", vp >= th, zero_division=0), th))
    X, y = matrix(test, modalities)
    proba = model.predict_proba(X)
    p_fault = 1 - proba[:, normal_index]
    fault_indices = [i for i, name in enumerate(model.classes_) if name != "normal"]
    cause = np.asarray(model.classes_)[np.asarray(fault_indices)[np.argmax(proba[:, fault_indices], axis=1)]]
    pred = np.where(p_fault >= best, cause, "normal")
    precision, recall, _, support = precision_recall_fscore_support(y, pred, labels=FAULTS, zero_division=0)
    result = dict(macro_f1=float(f1_score(y, pred, labels=FAULTS, average="macro", zero_division=0)),
                  anomaly_pr_auc=float(average_precision_score(y != "normal", p_fault)),
                  confusion_matrix=confusion_matrix(y, pred, labels=FAULTS).tolist(),
                  threshold=float(best), threshold_source="validation binary F1, never test",
                  per_class={name: dict(precision=float(p), recall=float(r), support=int(s))
                             for name, p, r, s in zip(FAULTS, precision, recall, support)})
    result.update(event_metrics(test, lambda x: 1-model.predict_proba(x)[:, normal_index], best, modalities))
    return result


def event_metrics(cycles, score, threshold, modalities="all"):
    detected, total, normal_hours, normal_alerts, delays = 0, 0, 0., 0, []
    examples = []
    for c in cycles:
        X, truth_labels, ts = windows(c, modalities)
        values = score(X)
        flags = values >= threshold
        # Confirmation uses current/past windows. No future gap bridging.
        confirmed = flags & np.r_[False, flags[:-1]]
        alert_starts = confirmed & ~np.r_[False, confirmed[:-1]]
        if c["label"] == "normal":
            normal_alerts += int(alert_starts.sum())
            normal_hours += (ts[-1] - ts[0] + c["dt"]) / 3600
        else:
            total += 1
            # An already-active false alarm must NOT count as detecting a later fault.
            valid = np.flatnonzero(alert_starts & (truth_labels != "normal") &
                                  (ts >= c["fault_start_s"]) & (ts <= c["fault_end_s"]))
            if len(valid):
                detected += 1
                delays.append(float(ts[valid[0]] - c["fault_start_s"]))
        if sum(e["label"] == c["label"] for e in examples) < 2:
            examples.append(dict(label=c["label"], seed=int(c["seed"]), domain=c["domain"],
                                 fault_start_s=c["fault_start_s"] if c["label"] != "normal" else None,
                                 fault_end_s=c["fault_end_s"] if c["label"] != "normal" else None,
                                 timestamps=ts.tolist(), scores=values.tolist(),
                                 detected_times=ts[alert_starts].tolist(), threshold=float(threshold)))
    return dict(event_recall=detected / total if total else None,
                detected_events=detected, total_fault_cycles=total,
                median_detection_delay_s=float(np.median(delays)) if delays else None,
                missed_fault_cycles=total-detected, false_alerts_normal_cycles=normal_alerts,
                normal_observation_hours=normal_hours,
                false_alerts_per_hour=normal_alerts/normal_hours if normal_hours else None,
                delay_definition="new confirmed alert after onset in a fault-active window; pre-existing alarms do not count; misses counted separately",
                examples=examples)


def train_isolation(normal_train, validation_normal, seed=19, modalities="all"):
    X, _ = matrix(normal_train, modalities)
    model = IsolationForest(n_estimators=120, random_state=seed, n_jobs=-1)
    model.fit(X)
    VX, _ = matrix(validation_normal, modalities)
    values = -model.score_samples(VX)
    threshold = float(np.quantile(values, .99))
    return model, threshold


def run_fold(cases, manifest, output):
    seed = manifest["seed"]
    train = select(cases, manifest, "train")
    val = select(cases, manifest, "validation")
    test = select(cases, manifest, "test")
    added = select(cases, manifest, "physics")
    rng = np.random.default_rng(seed)
    # Match added sample count by class between simple and physics augmentation.
    simple = []
    for new in added:
        pool = [c for c in train if c["label"] == new["label"]]
        simple.append(augment(pool[int(rng.integers(len(pool)))], rng))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    groups = {"A_original": train, "B_simple": train + simple, "C_physics": train + added}
    result = dict(seed=seed, labels=FAULTS, groups={}, ablations={},
                  feature_schema="observable-window-v3", simulation_only=True,
                  manifest_sha256=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest())
    for name, training in groups.items():
        X, y = matrix(training)
        model = ExtraTreesClassifier(n_estimators=120, min_samples_leaf=2,
                                    class_weight="balanced", n_jobs=-1, random_state=seed)
        model.fit(X, y)
        metrics = score_classifier(model, val, test)
        metrics.update(training_cycles=len(training), training_windows=len(X), estimator="ExtraTrees")
        result["groups"][name] = metrics
        joblib.dump(dict(model=model, threshold=metrics["threshold"], schema=VERSION,
                         features=extract_features(training[0])[1], training_scope="synthetic",
                         split="train only; validation calibration", metrics=metrics), output / f"{name}.joblib")
    for mode in ("vibration", "vibration_pose"):
        X, y = matrix(groups["C_physics"], mode)
        m = ExtraTreesClassifier(n_estimators=120, min_samples_leaf=2,
                                class_weight="balanced", n_jobs=-1, random_state=seed).fit(X, y)
        result["ablations"][mode] = score_classifier(m, val, test, mode)
        joblib.dump(dict(model=m,schema=VERSION,threshold=result["ablations"][mode]["threshold"],modalities=mode,
                         training_scope="synthetic train + physics"),output / f"C_{mode}.joblib")
    normal = [c for c in train if c["label"] == "normal"]
    vn = [c for c in val if c["label"] == "normal"]
    isolation, threshold = train_isolation(normal, vn, seed)
    tx, ty = matrix(test)
    score = -isolation.score_samples(tx)
    result["isolation_forest"] = dict(threshold=threshold, normal_training_cycles=len(normal),
                                    threshold_source="99th percentile of normal validation windows",
                                    anomaly_pr_auc=float(average_precision_score(ty != "normal", score)))
    result["isolation_forest"].update(event_metrics(test, lambda x: -isolation.score_samples(x), threshold))
    joblib.dump(dict(model=isolation, threshold=threshold, schema=VERSION,
                     features=extract_features(train[0])[1], training_scope="normal synthetic cycles"), output / "isolation.joblib")
    (output / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def summarize(folds, output):
    output = Path(output)
    keys = ("macro_f1", "anomaly_pr_auc", "event_recall", "median_detection_delay_s", "false_alerts_per_hour")
    groups = {}
    for name in folds[0]["groups"]:
        stats = {}
        for key in keys:
            vals = [f["groups"][name][key] for f in folds if f["groups"][name][key] is not None]
            stats[key] = dict(mean=float(np.mean(vals)) if vals else None,
                              std=float(np.std(vals, ddof=1)) if len(vals)>1 else 0., values=vals)
        groups[name] = stats
    result = dict(schema=VERSION, scope="SYNTHETIC DOMAIN-SHIFT BENCHMARK — not factory accuracy",
                  runtime=dict(python=platform.python_version(), numpy=version("numpy"),
                               scikit_learn=version("scikit-learn"), joblib=version("joblib")),
                  seeds=[f["seed"] for f in folds], labels=FAULTS, groups=groups,
                  folds=folds, limitations=["Lumped seven-servo surrogate, not calibrated Panda dynamics",
                      "All sensors and failure labels are synthetic", "Held-out conditions share the simulator equations",
                      "No real-fault test; no RUL or pre-failure prediction evidence",
                      "Envelope signals; no vibration-frequency or microphone waveform claims"],
                  improvement_macro_f1=groups["C_physics"]["macro_f1"]["mean"]-groups["A_original"]["macro_f1"]["mean"])
    tmp=output / "benchmark.json.tmp"
    tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    tmp.replace(output / "benchmark.json")
    with (output / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as file:
        w = csv.writer(file)
        w.writerow(["group", "metric", "mean", "std", "scope"])
        for name, stats in groups.items():
            for key, val in stats.items():
                w.writerow([name, key, val["mean"], val["std"], "synthetic"])
    return result
