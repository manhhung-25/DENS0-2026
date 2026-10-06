"""Local concept dashboard for time-synchronized Franka visual pose."""
import csv
import io
import json
import os
import random
import sqlite3
import uuid
import zipfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field

from engine_v2 import DEFAULT_INJECTIONS, FAULTS, ROOT, generate, validate_context, validate_injections

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


def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, injections TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE TABLE IF NOT EXISTS feedback (run_id TEXT NOT NULL, incident_id TEXT NOT NULL, correct INTEGER NOT NULL, actual_cause TEXT NOT NULL, action TEXT NOT NULL, technician TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(run_id,incident_id))")
    conn.commit()
    return conn


with connect() as c:
    c.execute("INSERT INTO runs(id,injections) VALUES(?,?) ON CONFLICT(id) DO NOTHING", ("default", json.dumps(DEFAULT_INJECTIONS)))


class RunInput(BaseModel):
    injections: list[dict] = Field(default_factory=list)
    seed: int = 0
    load: float = 1.0


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
        saved = json.loads(row["injections"])
        if isinstance(saved, list):  # runs saved by the first concept demo
            saved = {"injections": saved, "seed": 0, "load": 1.0}
        result = generate(saved["injections"], saved.get("seed", 0), saved.get("load", 1.0))
        result["id"] = run_id
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
        seed, load = validate_context(payload.seed, payload.load)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    run_id = uuid.uuid4().hex[:10]
    with connect() as c:
        c.execute("INSERT INTO runs(id,injections) VALUES(?,?)", (run_id, json.dumps({"injections": injections, "seed": seed, "load": load})))
    return {"id": run_id}


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
    return {"saved": True}


def csv_bytes(data):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["t_s", "landmark", "pose_x_px_observed", "pose_y_px_observed",
                     "twin_x_px_synthetic", "twin_y_px_synthetic", "speed_px_s_observed",
                     "still_duration_s_observed", "reference_distance_px_observed", "coverage_observed",
                     "vibration_baseline_sim_mm_s", "vibration_sim_mm_s",
                     "temperature_baseline_sim_c", "temperature_sim_c",
                     "sound_baseline_sim_db", "sound_sim_db", "pose_gap_sim_px",
                     "cycle_delay_sim_s", "score_sim", "fault_truth_sim", "pose_source", "sensor_source"])
    for row in data["timeline"]:
        for j, sig in enumerate(row["signals"]):
            p = row["points"][j]
            twin = row["twin_points"][j]
            writer.writerow([row["t"], data["landmarks"][j], p[0] if p else "", p[1] if p else "",
                             twin[0] if twin else "", twin[1] if twin else "",
                             row["speed_px_s"][j] if row["speed_px_s"][j] is not None else "",
                             row["still_duration_s"][j] if row["still_duration_s"][j] is not None else "",
                             row["reference_distance_px"] if row["reference_distance_px"] is not None else "",
                             row["coverage"], sig["baseline"]["vibration"], sig["vibration"],
                             sig["baseline"]["temperature"], sig["temperature"],
                             sig["baseline"]["sound"], sig["sound"], sig["pose_gap_px"],
                             sig["cycle_delay_s"], sig["score"], "|".join(sig["truth"]),
                             "image_extracted_from_annotated_video", "synthetic"])
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
                "warning": "Only observed 2D marker coordinates come from video; all faults, what-if pose and sensors are synthetic. Do not report simulation performance as field accuracy.",
                "source_video": "16.67 s recorded Franka Panda clip, repeated reference across cases",
                "engine": "causal what-if v2", "cases": []}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for n in range(count):
            load = round(rng.uniform(.7, 1.3), 2)
            case_seed = rng.randrange(1000000)
            fault = None if n % 5 == 0 else list(FAULTS)[(n-1) % len(FAULTS)]
            injections = [] if fault is None else [{"fault": fault,
                "landmark": rng.randint(2, 6), "start_s": round(rng.uniform(1.0, 8.5), 1),
                "duration_s": round(rng.uniform(3.0, 5.5), 1),
                "intensity": round(rng.uniform(.7, 1.5), 2)}]
            data = generate(injections, case_seed, load)
            name = f"case_{n+1:02d}.csv"
            archive.writestr(name, csv_bytes(data))
            manifest["cases"].append({"file": name, "seed": case_seed, "load": load,
                                      "injections": injections, "detected_incidents": data["incidents"]})
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="franka_synthetic_ensemble_{count}.zip"'})
