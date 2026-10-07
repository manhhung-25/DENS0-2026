"""python -m research_pipeline {generate,train,evaluate,benchmark,export}."""
import argparse
import csv
import json
from pathlib import Path
from .experiment import build_dataset, load_dataset, run_fold, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "train", "evaluate", "benchmark", "export"):
        p = sub.add_parser(name)
        p.add_argument("--output", type=Path, default=Path("research_artifacts"))
        p.add_argument("--seed", type=int, default=19)
        p.add_argument("--seeds", default="19,41,73")
        p.add_argument("--scarce", type=int, default=3)
        p.add_argument("--extra", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.scarce <= 40 or not 1 <= args.extra <= 80:
        parser.error("scarce 1..40, extra 1..80")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.command == "benchmark":
        seeds = [int(s) for s in args.seeds.split(",")]
        if not seeds or len(seeds) != len(set(seeds)) or any(s < 0 or s > 10000 for s in seeds):
            parser.error("Use distinct seeds in 0..10000")
        folds = []
        for seed in seeds:
            cases, manifest = build_dataset(args.output / f"seed_{seed}" / "dataset", seed,
                                            scarce=args.scarce, extra=args.extra)
            folds.append(run_fold(cases, manifest, args.output / f"seed_{seed}" / "models"))
            print(json.dumps({"seed": seed, "macro_f1": {k: v["macro_f1"] for k,v in folds[-1]["groups"].items()}}), flush=True)
        result = summarize(folds, args.output)
        print(json.dumps({"benchmark": str(args.output / "benchmark.json"),
                          "delta_macro_f1": result["improvement_macro_f1"]}))
    elif args.command == "generate":
        _, manifest = build_dataset(args.output / f"seed_{args.seed}" / "dataset", args.seed,
                                    scarce=args.scarce, extra=args.extra)
        print(json.dumps({"cases": len(manifest["cases"])}))
    elif args.command == "train":
        cases, manifest = load_dataset(args.output / f"seed_{args.seed}" / "dataset")
        result = run_fold(cases, manifest, args.output / f"seed_{args.seed}" / "models")
        print(json.dumps({"macro_f1": {k:v["macro_f1"] for k,v in result["groups"].items()}}))
    elif args.command == "evaluate":
        # Summarize persisted evaluations; train performs val calibration/test.
        folds = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.output.glob("seed_*/models/metrics.json"))]
        if not folds:
            parser.error("Run train or benchmark first")
        result = summarize(folds, args.output)
        print(json.dumps({"seeds": result["seeds"], "delta_macro_f1": result["improvement_macro_f1"]}))
    else:
        cases, manifest = load_dataset(args.output / f"seed_{args.seed}" / "dataset")
        path = args.output / f"seed_{args.seed}" / "timeseries.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["cycle_id","split","t_s","joint","target_rad","camera_rad","encoder_rad","vibration_sim_mm_s","acoustic_sim_db","current_sim_a","temperature_sim_c","fault_label","fault_active","source"])
            for row in manifest["cases"]:
                c = cases[row["id"]]
                for i,t in enumerate(c["t"]):
                    for j in range(7):
                        w.writerow([row["id"],row["split"],t,f"J{j+1}"]+[c[k][i,j] for k in ("target","camera","encoder","vibration","acoustic","current","temperature")]+[c["label"],int(c["truth"][i,j]),"synthetic"])
        print(path)


if __name__ == "__main__":
    main()
