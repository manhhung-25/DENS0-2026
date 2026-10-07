"""Exercise the packaged demo over HTTP, optionally checking a container restart.

Run against a test instance: this creates a scenario and a demo maintenance entry.
No third-party client dependency is required.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8767")
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--verify-persistence", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    def request(path, payload=None, expected=200, decode=True, headers=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(base + path, data=body,
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.code
            raw = response.read()
        if status != expected:
            raise AssertionError(f"{path}: expected HTTP {expected}, got {status}: {raw[:300]!r}")
        return json.loads(raw) if decode else raw

    health = request("/api/health")
    assert health["status"] == "ok"
    print("PASS health and startup assets", flush=True)

    if args.verify_persistence:
        if args.state_file is None:
            parser.error("--verify-persistence requires --state-file")
        state = json.loads(args.state_file.read_text(encoding="utf-8"))
        run = request("/api/run/" + state["run_id"])
        detail = request("/api/history/" + state["event_id"])
        assert run["evidence_archive"]["sha256"] == state["sha256"]
        assert detail["evidence_archive"]["sha256"] == state["sha256"]
        assert detail["feedback"]["technician"] == "Docker smoke test"
        assert detail["maintenance_history"]
        print("PASS scenario, frozen evidence and maintenance survive restart", flush=True)
        return

    assert b"<html" in request("/", decode=False).lower()
    for path in ("/app_v2.js", "/history.js", "/research.js", "/styles_v4.css", "/poster.jpg"):
        assert request(path, decode=False)
    video = request("/robot_original.mp4", expected=206, decode=False,
                    headers={"Range": "bytes=0-1023"})
    assert len(video) == 1024 and b"ftyp" in video[:32]
    print("PASS HTML, scripts, styles and playable MP4 byte range", flush=True)

    observed = request("/api/run/default")
    assert len(observed["timeline"]) == 500
    created = request("/api/run", payload={"injections": observed["injections"],
                      "seed": 0, "load": 1.0, "environment": "nominal"})
    run_id = created["id"]
    run = request("/api/run/" + run_id)
    assert run["incidents"]
    assert [row["points"] for row in run["timeline"]] == [row["points"] for row in observed["timeline"]]
    assert all(len(row["signals"]) == 7 for row in run["timeline"])
    assert all(b["t"] > a["t"] for a, b in zip(run["timeline"], run["timeline"][1:]))
    assert request("/api/run", payload={"injections": [], "environment": "invalid"}, expected=422)
    print("PASS time-aligned 500 frames, seven regional channels and scenario validation", flush=True)

    event = run["incidents"][0]
    detail = request("/api/history/" + event["log_id"])
    assert detail["timeline"] and detail["window"]["frame_count"] == len(detail["timeline"])
    raw_csv = request("/api/history/" + event["log_id"] + "/export.csv", decode=False)
    rows = list(csv.reader(io.StringIO(raw_csv.decode("utf-8-sig"))))
    assert len(rows) == 1 + 7 * len(detail["timeline"])
    exported = request("/api/history/" + event["log_id"] + "/export.json")
    assert exported["evidence_archive"]["sha256"] == detail["evidence_archive"]["sha256"]
    feedback_path = f"/api/run/{run_id}/incidents/{event['id']}/feedback"
    request(feedback_path, payload={"correct": False, "technician": "Docker smoke test",
            "action": "Demo verification"}, expected=422)
    request(feedback_path, payload={"correct": False, "technician": "Docker smoke test",
            "action": "Demo verification; no real maintenance performed",
            "actual_cause": "Synthetic smoke-test scenario"})
    saved = request("/api/history/" + event["log_id"])
    assert saved["maintenance_history"]
    assert saved["evidence_archive"]["sha256"] == detail["evidence_archive"]["sha256"]
    print("PASS event log, JSON/CSV export and maintenance audit", flush=True)

    research = request("/api/research")
    assert research["available"] and research["benchmark"]["seeds"] == [19, 41, 73]
    assert request("/api/research/comparison.csv", decode=False)
    print("PASS bundled synthetic benchmark", flush=True)
    if args.state_file:
        args.state_file.parent.mkdir(parents=True, exist_ok=True)
        args.state_file.write_text(json.dumps({"run_id": run_id, "event_id": event["log_id"],
            "sha256": detail["evidence_archive"]["sha256"]}, indent=2) + "\n", encoding="utf-8")
    print("All HTTP smoke checks passed", flush=True)


if __name__ == "__main__":
    main()
