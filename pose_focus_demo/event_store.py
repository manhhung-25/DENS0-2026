"""Immutable offline evidence snapshots and event index; SQLite handles commits.

Video time is NOT acquisition wall-clock time. Future samples are available here
because this dashboard analyses an entire prerecorded synthetic replay.
"""
import hashlib
import json
import zlib
from datetime import datetime, timezone
from functools import lru_cache


SCHEMA = "anomaly-evidence-v1"
CONTEXT_SECONDS = 1.


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS evidence_runs (
        run_id TEXT PRIMARY KEY, saved_at_utc TEXT NOT NULL,
        schema_version TEXT NOT NULL, sha256 TEXT NOT NULL, payload_zlib BLOB NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS anomaly_events (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, incident_id TEXT NOT NULL,
        saved_at_utc TEXT NOT NULL, label TEXT NOT NULL, landmark INTEGER NOT NULL,
        start_s REAL NOT NULL, detected_s REAL NOT NULL, end_s REAL NOT NULL,
        peak_s REAL NOT NULL, score REAL NOT NULL, UNIQUE(run_id, incident_id))""")
    conn.execute("CREATE INDEX IF NOT EXISTS anomaly_saved_idx ON anomaly_events(saved_at_utc DESC, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS anomaly_run_idx ON anomaly_events(run_id)")
    conn.execute("""CREATE TABLE IF NOT EXISTS maintenance_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL,
        saved_at_utc TEXT NOT NULL, feedback_json TEXT NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS maintenance_event_idx ON maintenance_audit(event_id, id)")


@lru_cache(maxsize=1)
def asset_checksums(root):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("pose_recording.json", "robot_original.mp4")}


def read_snapshot(conn, run_id):
    row = conn.execute("SELECT * FROM evidence_runs WHERE run_id=?", (run_id,)).fetchone()
    if not row:
        return None
    raw = zlib.decompress(row["payload_zlib"])
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("Evidence snapshot checksum mismatch")
    result = json.loads(raw)
    result["evidence_archive"] = dict(schema=row["schema_version"], saved_at_utc=row["saved_at_utc"],
        sha256=row["sha256"], mode="offline_replay_analysis",
        clock_definition="t is video seconds; saved_at_utc is archive time, not real robot acquisition time")
    return result


def persist_snapshot(conn, result, root):
    # Insert-only: an existing run is never regenerated/overwritten by new code.
    frozen = {k:v for k,v in result.items() if k not in ("feedback", "evidence_archive")}
    frozen["asset_checksums"] = asset_checksums(root)
    raw = json.dumps(frozen, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    now = utc_now()
    conn.execute("INSERT OR IGNORE INTO evidence_runs VALUES(?,?,?,?,?)",
                 (result["id"], now, SCHEMA, hashlib.sha256(raw).hexdigest(), zlib.compress(raw, 6)))
    stored = read_snapshot(conn, result["id"])
    for incident in stored["incidents"]:
        key = hashlib.sha256(f'{result["id"]}:{incident["id"]}'.encode()).hexdigest()[:24]
        inserted = conn.execute("""INSERT OR IGNORE INTO anomaly_events
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (key, result["id"], incident["id"],
            stored["evidence_archive"]["saved_at_utc"], incident["label"], incident["landmark"],
            incident["start_s"], incident["detected_s"], incident["end_s"], incident["peak_s"], incident["score"]))
        # Preserve pre-existing technician conclusions when an old run is archived.
        if inserted.rowcount:
            previous = conn.execute("SELECT * FROM feedback WHERE run_id=? AND incident_id=?",
                                    (result["id"], incident["id"])).fetchone()
            if previous:
                conn.execute("INSERT INTO maintenance_audit(event_id,saved_at_utc,feedback_json) VALUES(?,?,?)",
                    (key, now, json.dumps(dict(previous) | {"origin":"imported_existing_feedback"}, ensure_ascii=False)))
    return stored


def attach_event_keys(conn, result):
    keys = {r["incident_id"]:r["id"] for r in conn.execute(
        "SELECT id,incident_id FROM anomaly_events WHERE run_id=?", (result["id"],))}
    for incident in result["incidents"]:
        incident["log_id"] = keys.get(incident["id"])
    return result


def list_events(conn, run_id=None, status="all", limit=20, offset=0):
    filters, args = [], []
    if run_id:
        filters.append("e.run_id=?")
        args.append(run_id)
    if status == "unconfirmed":
        filters.append("f.incident_id IS NULL")
    elif status == "confirmed":
        filters.append("f.incident_id IS NOT NULL")
    where = " WHERE " + " AND ".join(filters) if filters else ""
    join = " FROM anomaly_events e LEFT JOIN feedback f ON e.run_id=f.run_id AND e.incident_id=f.incident_id"
    total = conn.execute("SELECT COUNT(*)" + join + where, args).fetchone()[0]
    rows = conn.execute("""SELECT e.*,f.correct,f.actual_cause,f.technician,f.action,
        f.created_at AS feedback_at""" + join + where + " ORDER BY e.saved_at_utc DESC,e.id DESC LIMIT ? OFFSET ?",
        args + [limit, offset]).fetchall()
    return dict(events=[dict(r) for r in rows], total=total, limit=limit, offset=offset,
                mode="offline_replay_analysis", context_s=CONTEXT_SECONDS)


def event_detail(conn, event_id):
    event = conn.execute("SELECT * FROM anomaly_events WHERE id=?", (event_id,)).fetchone()
    if not event:
        return None
    frozen = read_snapshot(conn, event["run_id"])
    incident = next(x for x in frozen["incidents"] if x["id"] == event["incident_id"])
    start = max(0., incident["start_s"] - CONTEXT_SECONDS)
    end = min(frozen["duration_s"], incident["end_s"] + CONTEXT_SECONDS)
    timeline = [r for r in frozen["timeline"] if start <= r["t"] <= end]
    feedback = conn.execute("SELECT * FROM feedback WHERE run_id=? AND incident_id=?",
                            (event["run_id"], event["incident_id"])).fetchone()
    audits = conn.execute("SELECT * FROM maintenance_audit WHERE event_id=? ORDER BY id", (event_id,)).fetchall()
    return dict(id=event_id, run_id=event["run_id"], incident=incident,
        saved_at_utc=event["saved_at_utc"], evidence_archive=frozen["evidence_archive"],
        context=dict(seed=frozen["seed"], load=frozen["load"], environment=frozen.get("environment","nominal"),
                     injections=frozen["injections"]),
        provenance=frozen["provenance"], method=frozen["method"], mapping=frozen["mapping"],
        asset_checksums=frozen["asset_checksums"], fps=frozen["fps"], landmarks=frozen["landmarks"],
        window=dict(start_s=start, end_s=end, before_s=incident["start_s"]-start,
                    after_s=end-incident["end_s"], frame_count=len(timeline)),
        feedback=dict(feedback) if feedback else None,
        maintenance_history=[dict(id=r["id"],saved_at_utc=r["saved_at_utc"],feedback=json.loads(r["feedback_json"])) for r in audits],
        timeline=timeline,
        units=dict(points="px", twin_points="px synthetic", q_deg="deg HoRoPose prediction",
            vibration="mm/s synthetic envelope", temperature="degC synthetic", sound="dB synthetic envelope",
            current="A synthetic", pose_gap_px="px synthetic", cycle_delay_s="s estimated what-if", score="0..100 not probability"))


def record_maintenance(conn, run_id, incident_id, feedback):
    event = conn.execute("SELECT id FROM anomaly_events WHERE run_id=? AND incident_id=?", (run_id, incident_id)).fetchone()
    if event:
        conn.execute("INSERT INTO maintenance_audit(event_id,saved_at_utc,feedback_json) VALUES(?,?,?)",
                     (event["id"], utc_now(), json.dumps(feedback, ensure_ascii=False, allow_nan=False)))
