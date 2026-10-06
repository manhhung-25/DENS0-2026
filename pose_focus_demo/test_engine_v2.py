"""Meaningful invariants for the offline what-if demo."""
import unittest

from engine_v2 import FAULTS, generate


class EngineV2Tests(unittest.TestCase):
    def test_observed_pose_is_immutable_and_context_replays(self):
        empty = generate([], seed=42, load=1.1)
        fault = generate([{"fault": "backlash", "landmark": 5,
                           "start_s": 5, "duration_s": 5, "intensity": 1.2}],
                         seed=42, load=1.1)
        self.assertEqual([r["points"] for r in empty["timeline"]],
                         [r["points"] for r in fault["timeline"]])
        self.assertEqual(empty, generate([], seed=42, load=1.1))
        self.assertTrue(any(r["twin_points"] != r["points"]
                            for r in fault["timeline"]))

    def test_normal_and_six_faults(self):
        self.assertEqual(generate([])["incidents"], [])
        for name in FAULTS:
            with self.subTest(fault=name):
                data = generate([{"fault": name, "landmark": 5,
                                  "start_s": 5, "duration_s": 5,
                                  "intensity": 1.2}])
                self.assertTrue(any(i["fault"] == name and i["landmark"] == 5
                                    for i in data["incidents"]))

    def test_sensor_drift_does_not_move_pose_or_other_channels(self):
        normal = generate([], seed=9)
        drift = generate([{"fault": "sensor_drift", "landmark": 5,
                           "start_s": 5, "duration_s": 5,
                           "intensity": 1.2}], seed=9)
        for a, b in zip(normal["timeline"], drift["timeline"]):
            self.assertEqual(a["points"], b["points"])
            self.assertEqual(a["twin_points"], b["twin_points"])
            for field in ("temperature", "sound", "cycle_delay_s", "pose_gap_px"):
                self.assertEqual(a["signals"][5][field], b["signals"][5][field])
        self.assertTrue(any(a["signals"][5]["vibration"] != b["signals"][5]["vibration"]
                            for a, b in zip(normal["timeline"], drift["timeline"])))


if __name__ == "__main__":
    unittest.main()
