"""Check that the browser timeline is the saved checkpoint/video timeline."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from import_horopose import REPRO, ROOT, build
from engine import RECORDING
from engine_v2 import generate


class HoRoPoseIntegrationTests(unittest.TestCase):
    def test_import_rebuilds_same_frame_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build(output=Path(tmp) / "pose.json")
            rebuilt = json.loads((Path(tmp) / "pose.json").read_text(encoding="utf-8"))
        self.assertEqual(result["frames"], 500)
        self.assertEqual(result["unique_source_frames"], 120)
        self.assertEqual(rebuilt, RECORDING)

    def test_video_sensor_and_ai_joint_rows_share_source_frame(self):
        with np.load(REPRO / "artifacts/panda_pose_predictions.npz", allow_pickle=False) as saved:
            scene_to_index = {int(scene): i for i, scene in enumerate(saved["scene_id"])}
            with (REPRO / "artifacts/panda_multimodal_timeseries.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            for i in (0, 119, 238, 262, 400, 499):
                record = RECORDING["frames"][i]
                source = rows[i]
                k = scene_to_index[int(source["source_frame"])]
                self.assertEqual(record["source_frame"], int(source["source_frame"]))
                self.assertEqual(record["cycle"], int(source["cycle"]))
                self.assertAlmostEqual(record["q_deg"][3], float(np.rad2deg(saved["q_calibrated"][k, 3])), places=2)
                self.assertAlmostEqual(record["source_sim"]["vibration_mm_s"], float(source["vibration_mm_s"]), places=2)
                self.assertAlmostEqual(record["t"], i / 30, places=3)
        live = generate([])["timeline"]
        self.assertEqual(live[262]["q_deg"], RECORDING["frames"][262]["q_deg"])
        self.assertEqual(live[262]["source_sim"], RECORDING["frames"][262]["source_sim"])


if __name__ == "__main__":
    unittest.main()
