"""Local concept dashboard for time-synchronized Franka visual pose."""
import csv
import io
import json
import os
import random
import sqlite3
import uuid
import zipfile
import sys
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_v3 import DEFAULT_INJECTIONS, FAULTS, ROOT, generate, validate_context, validate_injections
import event_store

def database_path():
    """Keep mutable feedback outside the (possibly read-only) source tree."""
    override = os.environ.get("DENSO_DEMO_DB")
    if override:
        path = Path(override).expanduser()
    elif os.environ.get("LOCALAPPDATA"):
        path = Path(os.environ["LOCALAPPDATA"]) / "DENSO" / "pose_demo.sqlite3"
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "DENSO" / "pose_demo.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


DB = database_path()
app = FastAPI(title="Franka Panda — visual pose concept demo")


@contextmanager
def connect():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, injections TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE TABLE IF NOT EXISTS feedback (run_id TEXT NOT NULL, incident_id TEXT NOT NULL, correct INTEGER NOT NULL, actual_cause TEXT NOT NULL, action TEXT NOT NULL, technician TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(run_id,incident_id))")
    event_store.ensure_schema(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


with connect() as c:
    c.execute("INSERT INTO runs(id,injections) VALUES(?,?) ON CONFLICT(id) DO NOTHING", ("default", json.dumps(DEFAULT_INJECTIONS)))


class RunInput(BaseModel):
    injections: list[dict] = Field(default_factory=list)
    seed: int = 0
    load: float = 1.0
    environment: str = "nominal"


class FeedbackInput(BaseModel):
    correct: bool
    actual_cause: str = ""
    action: str = ""
    technician: str = ""


def run_data(run_id):
    with connect() as c:
        row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Không tìm thấy lần chạy")
        result = event_store.read_snapshot(c, run_id)
        if result is None:
            saved = json.loads(row["injections"])
            if isinstance(saved, list):  # runs saved by the first concept demo
                saved = {"injections": saved, "seed": 0, "load": 1.0}
            result = generate(saved["injections"], saved.get("seed", 0), saved.get("load", 1.0), saved.get("environment", "nominal"))
            result["id"] = run_id
            result = event_store.persist_snapshot(c, result, ROOT)
        event_store.attach_event_keys(c, result)
        result["feedback"] = {r["incident_id"]: dict(r) for r in c.execute("SELECT * FROM feedback WHERE run_id=?", (run_id,))}
        return result


@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "index_v3.html").read_text(encoding="utf-8")


@app.get("/styles.css")
def style():
    return FileResponse(ROOT / "styles.css", media_type="text/css")


@app.get("/styles_v2.css")
def style_v2():
    return FileResponse(ROOT / "styles_v2.css", media_type="text/css")


@app.get("/styles_v3.css")
def style_v3():
    return FileResponse(ROOT / "styles_v3.css", media_type="text/css")


@app.get("/styles_v4.css")
def style_v4():
    return FileResponse(ROOT / "styles_v4.css", media_type="text/css")


@app.get("/app.js")
def script():
    return FileResponse(ROOT / "app.js", media_type="text/javascript")


@app.get("/app_v2.js")
def script_v2():
    return FileResponse(ROOT / "app_v2.js", media_type="text/javascript")


@app.get("/robot_original.mp4")
def video():
    return FileResponse(ROOT / "robot_original.mp4", media_type="video/mp4")


@app.get("/poster.jpg")
def poster():
    return FileResponse(ROOT / "poster.jpg", media_type="image/jpeg")


@app.get("/api/run/{run_id}")
def get_run(run_id: str):
    return run_data(run_id)


@app.post("/api/run")
def create_run(payload: RunInput):
    try:
        injections = validate_injections(payload.injections)
        seed, load = validate_context(payload.seed, payload.load, payload.environment)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    run_id = uuid.uuid4().hex[:10]
    with connect() as c:
        c.execute("INSERT INTO runs(id,injections) VALUES(?,?)", (run_id, json.dumps({"injections": injections, "seed": seed, "load": load, "environment": payload.environment})))
    data = run_data(run_id)
    return {"id": run_id, "logged_events": len(data["incidents"])}


@app.post("/api/run/{run_id}/incidents/{incident_id}/feedback")
def feedback(run_id: str, incident_id: str, payload: FeedbackInput):
    data = run_data(run_id)
    if incident_id not in {x["id"] for x in data["incidents"]}:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    actual = payload.actual_cause.strip()
    action = payload.action.strip()
    technician = payload.technician.strip()
    if not technician or not action or (not payload.correct and not actual):
        raise HTTPException(422, "Cần tên kỹ thuật viên, việc đã làm và nguyên nhân thực tế nếu dự đoán sai")
    with connect() as c:
        c.execute("INSERT INTO feedback(run_id,incident_id,correct,actual_cause,action,technician) VALUES(?,?,?,?,?,?) ON CONFLICT(run_id,incident_id) DO UPDATE SET correct=excluded.correct,actual_cause=excluded.actual_cause,action=excluded.action,technician=excluded.technician,created_at=CURRENT_TIMESTAMP",
                  (run_id, incident_id, int(payload.correct), actual, action, technician))
        event_store.record_maintenance(c,run_id,incident_id,dict(correct=payload.correct,actual_cause=actual,action=action,technician=technician))
    return {"saved": True}


def csv_bytes(data):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["t_s", "landmark", "source_frame", "cycle", "q_pred_deg", "q_reference_deg", "keypoint_error_px", "pose_x_px_pred", "pose_y_px_pred",
                     "twin_x_px_synthetic", "twin_y_px_synthetic", "speed_px_s_observed",
                     "still_duration_s_observed", "reference_distance_px_observed", "coverage_observed",
                     "vibration_baseline_sim_mm_s", "vibration_sim_mm_s",
                     "temperature_baseline_sim_c", "temperature_sim_c",
                     "sound_baseline_sim_db", "sound_sim_db", "pose_gap_sim_px",
                     "cycle_delay_sim_s", "score_sim", "fault_truth_sim", "pose_source", "sensor_source",
                     "video_vibration_sim_mm_s", "video_sound_sim_dba", "video_temperature_sim_c",
                     "video_motor_current_sim_a", "video_fault_blend_sim", "q_joint_id",
                     "q_velocity_pred_deg_s", "q_acceleration_pred_deg_s2", "q_jerk_pred_deg_s3",
                     "regional_current_sim_a", "ai_raw_score", "rule_score", "pose_quality_sim", "replay_discontinuity"])
    for row in data["timeline"]:
        for j, sig in enumerate(row["signals"]):
            p = row["points"][j]
            twin = row["twin_points"][j]
            writer.writerow([row["t"], data["landmarks"][j], row["source_frame"], row["cycle"], row["q_deg"][j], row["q_reference_deg"][j], row["keypoint_error_px"], p[0] if p else "", p[1] if p else "",
                             twin[0] if twin else "", twin[1] if twin else "",
                             row["speed_px_s"][j] if row["speed_px_s"][j] is not None else "",
                             row["still_duration_s"][j] if row["still_duration_s"][j] is not None else "",
                             row["reference_distance_px"] if row["reference_distance_px"] is not None else "",
                             row["coverage"], sig["baseline"]["vibration"], sig["vibration"],
                             sig["baseline"]["temperature"], sig["temperature"],
                             sig["baseline"]["sound"], sig["sound"], sig["pose_gap_px"],
                             sig["cycle_delay_s"], sig["score"], "|".join(sig["truth"]),
                             "saved_horopose_checkpoint_inference", "synthetic",
                             row["source_sim"]["vibration_mm_s"], row["source_sim"]["sound_dba"],
                             row["source_sim"]["temperature_c"], row["source_sim"]["motor_current_a"],
                             row["source_sim"]["fault_blend"], f"J{j+1}",
                             row["q_velocity_deg_s"][j],row["q_acceleration_deg_s2"][j],row["q_jerk_deg_s3"][j],
                             sig["current"],sig["ai_raw_score"],sig["rule_score"],sig["pose_quality"],row["replay_discontinuity"]])
    return out.getvalue().encode("utf-8-sig")


@app.get("/api/run/{run_id}/export.csv")
def export_csv(run_id: str):
    return Response(csv_bytes(run_data(run_id)), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="franka_pose_{run_id}.csv"'})


@app.get("/api/ensemble.zip")
def ensemble(count: int = 20, seed: int = 41):
    if not 1 <= count <= 40 or not 0 <= seed <= 1000000:
        raise HTTPException(422, "Số ca 1–40; seed 0–1.000.000")
    rng = random.Random(seed)
    manifest = {"purpose": "Offline synthetic stress testing only",
                "warning": "Pose and q are saved HoRoPose inference on DREAM RGB, mapped to repeated video frames. All faults, what-if pose and sensors are synthetic. Do not report simulation performance as field accuracy.",
                "source_video": "16.67 s rendered Panda HoRoPose repro clip, repeated reference across cases",
                "engine": "shared-surrogate + learned-normal v3", "cases": []}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for n in range(count):
            load = round(rng.uniform(.7, 1.3), 2)
            case_seed = rng.randrange(1000000)
            fault = None if n % 5 == 0 else list(FAULTS)[(n-1) % len(FAULTS)]
            injections = [] if fault is None else [{"fault": fault,
                "landmark": rng.randint(2, 6), "start_s": round(rng.uniform(1.0, 8.5), 1),
                "duration_s": round(rng.uniform(3.0, 5.5), 1),
                "intensity": round(rng.uniform(.7, 1.5), 2),
                "profile": ("transient","progressive","intermittent")[n % 3]}]
            data = generate(injections, case_seed, load)
            name = f"case_{n+1:02d}.csv"
            archive.writestr(name, csv_bytes(data))
            manifest["cases"].append({"file": name, "seed": case_seed, "load": load,
                                      "injections": injections, "detected_incidents": data["incidents"]})
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="franka_synthetic_ensemble_{count}.zip"'})


@app.get("/api/run/{run_id}/export.json")
def export_run(run_id: str):
    return Response(json.dumps(run_data(run_id),ensure_ascii=False,allow_nan=False),media_type="application/json",
        headers={"Content-Disposition":f'attachment; filename="franka_run_{run_id}.json"'})


@app.get("/history.js")
def history_script():
    return FileResponse(ROOT / "history.js", media_type="text/javascript")


@app.get("/api/history")
def history_list(run_id: str | None = None, status: str = "all",
                 limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    if status not in ("all", "unconfirmed", "confirmed"):
        raise HTTPException(422, "Trạng thái lịch sử không hợp lệ")
    with connect() as c:
        return event_store.list_events(c, run_id, status, limit, offset)


@app.get("/api/history/{event_id}")
def history_detail(event_id: str):
    with connect() as c:
        data = event_store.event_detail(c, event_id)
    if data is None:
        raise HTTPException(404, "Không tìm thấy sự kiện đã lưu")
    return data


@app.get("/api/history/{event_id}/export.json")
def history_json(event_id: str):
    data = history_detail(event_id)
    return Response(json.dumps(data,ensure_ascii=False,allow_nan=False),media_type="application/json",
        headers={"Content-Disposition":f'attachment; filename="anomaly_{data["id"]}.json"'})


@app.get("/api/history/{event_id}/export.csv")
def history_csv(event_id: str):
    data = history_detail(event_id)
    base = csv.reader(io.StringIO(csv_bytes(data).decode("utf-8-sig")))
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["event_id","run_id","saved_at_utc","snapshot_sha256","event_phase"] + next(base))
    for row in base:
        t = float(row[0])
        phase = "before" if t < data["incident"]["start_s"] else "after" if t > data["incident"]["end_s"] else "during"
        writer.writerow([data["id"],data["run_id"],data["saved_at_utc"],data["evidence_archive"]["sha256"],phase] + row)
    return Response(out.getvalue().encode("utf-8-sig"),media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":f'attachment; filename="anomaly_{data["id"]}.csv"'})


RESEARCH_DIR = Path(os.environ.get("DENSO_RESEARCH_DIR",PROJECT_ROOT / "research_artifacts"))
RESEARCH_LOCK = threading.Lock()
RESEARCH_JOB = {"state":"idle"}


@app.get("/research.js")
def research_script():
    return FileResponse(ROOT / "research.js",media_type="text/javascript")


@app.get("/api/research")
def research_status():
    path = RESEARCH_DIR / "benchmark.json"
    with RESEARCH_LOCK:
        job = dict(RESEARCH_JOB)
    result = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return {"job":job,"benchmark":result,"available":result is not None}


@app.post("/api/research/benchmark")
def start_benchmark():
    with RESEARCH_LOCK:
        if RESEARCH_JOB["state"]=="running":
            raise HTTPException(409,"Benchmark đang chạy; vui lòng chờ kết quả")
        RESEARCH_JOB.clear()
        RESEARCH_JOB.update(state="running",scope="synthetic",seeds=[19,41,73])
    def work():
        try:
            RESEARCH_DIR.mkdir(parents=True,exist_ok=True)
            result=subprocess.run([sys.executable,"-m","research_pipeline","benchmark","--output",str(RESEARCH_DIR),"--seeds","19,41,73"],
                cwd=PROJECT_ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
            with RESEARCH_LOCK:
                RESEARCH_JOB.update(state="complete" if result.returncode==0 else "failed",returncode=result.returncode,
                    log=(result.stdout+result.stderr)[-3000:])
        except Exception as exc:
            with RESEARCH_LOCK:
                RESEARCH_JOB.update(state="failed",log=str(exc))
    threading.Thread(target=work,daemon=True).start()
    return {"state":"running"}


@app.get("/api/research/comparison.csv")
def research_csv():
    path=RESEARCH_DIR / "comparison.csv"
    if not path.exists():
        raise HTTPException(404,"Chưa chạy benchmark")
    return FileResponse(path,media_type="text/csv",filename="comparison_synthetic.csv")


@app.get("/api/research/dataset.zip")
def research_dataset():
    # NPZs/manifest only, no model pickle or arbitrary filesystem paths.
    buf=io.BytesIO()
    paths=list(RESEARCH_DIR.glob("seed_*/dataset/manifest.json"))
    if not paths:
        raise HTTPException(404,"Chưa có tập dữ liệu nghiên cứu")
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as archive:
        for manifest_path in paths:
            manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
            archive.write(manifest_path,str(manifest_path.relative_to(RESEARCH_DIR)))
            for record in manifest["cases"]:
                file=manifest_path.parent / record["file"]
                archive.write(file,str(file.relative_to(RESEARCH_DIR)))
    return Response(buf.getvalue(),media_type="application/zip",headers={"Content-Disposition":'attachment; filename="synthetic_research_dataset.zip"'})


@app.get("/api/research/cases")
def research_cases():
    result=[]
    for path in sorted(RESEARCH_DIR.glob("seed_*/dataset/manifest.json")):
        manifest=json.loads(path.read_text(encoding="utf-8"))
        result.extend({k:r[k] for k in ("id","split","quality")} | {"label":r["metadata"]["label"],"seed":manifest["seed"]} for r in manifest["cases"] if r["split"]=="test")
    return {"cases":result}


@app.get("/api/research/case/{case_id}")
def research_case(case_id: str):
    import numpy as np
    for path in RESEARCH_DIR.glob("seed_*/dataset/manifest.json"):
        manifest=json.loads(path.read_text(encoding="utf-8"))
        record=next((r for r in manifest["cases"] if r["id"]==case_id and r["split"]=="test"),None)
        if record:
            with np.load(path.parent / record["file"],allow_pickle=False) as z:
                cycle=json.loads(str(z["metadata"]))
                cycle.update({k:z[k] for k in z.files if k!="metadata"})
                result={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in cycle.items()}
            import joblib
            from research_pipeline.features import windows
            X,_,times=windows(cycle)
            evaluations={}
            for group in ("A_original","B_simple","C_physics","isolation"):
                model_path=path.parent.parent / "models" / f"{group}.joblib"
                if not model_path.exists():
                    continue
                bundle=joblib.load(model_path)
                model=bundle["model"]
                scores=-model.score_samples(X) if group=="isolation" else 1-model.predict_proba(X)[:,list(model.classes_).index("normal")]
                flags=scores>=bundle["threshold"]
                confirmed=flags & np.r_[False,flags[:-1]]
                starts=confirmed & ~np.r_[False,confirmed[:-1]]
                evaluations[group]=dict(timestamps=times.tolist(),scores=scores.tolist(),threshold=float(bundle["threshold"]),detected_times=times[starts].tolist())
            result["evaluations"]=evaluations
            result["quality"]=record["quality"]
            result["id"]=case_id
            return result
    raise HTTPException(404,"Không tìm thấy ca kiểm thử")
