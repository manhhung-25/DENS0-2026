"""Re-evaluate saved datasets without changing their split or samples."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from research_pipeline.experiment import load_dataset,run_fold,summarize

out=Path(sys.argv[1]) if len(sys.argv)>1 else Path("research_artifacts")
folds=[]
for path in sorted(out.glob("seed_*/dataset/manifest.json")):
    cases,manifest=load_dataset(path.parent)
    result=run_fold(cases,manifest,path.parent.parent / "models")
    folds.append(result)
    print(manifest["seed"],{k:round(v["macro_f1"],4) for k,v in result["groups"].items()},flush=True)
if not folds:
    raise SystemExit("Generate datasets first")
result=summarize(folds,out)
print("delta_macro_f1",result["improvement_macro_f1"])
