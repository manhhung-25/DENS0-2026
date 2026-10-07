"""Scientific invariants, leakage barriers, artifact compatibility and API flow."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT / "pose_focus_demo"))
sys.path.insert(0,str(ROOT / "panda_repro" / "src"))
from research_pipeline.physics import derivatives,simulate_cycle,thermal_step,quality_check
from research_pipeline.features import extract_features,windows


class ScientificTests(unittest.TestCase):
    def test_jerk_is_third_derivative_in_seconds(self):
        for dt in (.01,.025):
            t=np.arange(100)*dt
            v,a,j=derivatives((t**3)[:,None],dt)
            np.testing.assert_allclose(j[5:-5,0],6.,rtol=1e-6)
            np.testing.assert_allclose(a[5:-5,0],6*t[5:-5],rtol=1e-6)

    def test_measurement_fault_does_not_damage_mechanical_state(self):
        common=dict(seed=27,profile="transient",severity=1.)
        normal=simulate_cycle("normal",**common)
        for fault in ("sensor_drift","encoder_error"):
            c=simulate_cycle(fault,2,**common)
            np.testing.assert_array_equal(c["actual"],normal["actual"])
            np.testing.assert_array_equal(c["temperature"],normal["temperature"])
            if fault=="encoder_error":
                self.assertGreater(np.max(np.abs(c["encoder"]-normal["encoder"])),.03)
            else:
                self.assertGreater(np.max(c["vibration"]-normal["vibration"]),1.)

    def test_thermal_inertia_and_seven_joints(self):
        self.assertLess(thermal_step(50,30,0,.5,.1),50)
        self.assertGreater(thermal_step(50,30,0,.5,.1),30)
        c=simulate_cycle("friction",6,seed=18)
        self.assertEqual(c["actual"].shape[1],7)
        self.assertTrue(quality_check(c)["accepted"])
        other=simulate_cycle("friction",6,seed=18)
        np.testing.assert_array_equal(c["temperature"],other["temperature"])

    def test_feature_extractor_cannot_read_label_or_latent_state(self):
        c=simulate_cycle("backlash",3,seed=5)
        modified=copy.deepcopy(c)
        for key in ("label","faulty_joint","truth","profile","severity","fault_start_s","fault_end_s","generator_version"):
            modified.pop(key,None)
        np.testing.assert_array_equal(extract_features(c)[0],extract_features(modified)[0])
        # Changing only future observations cannot affect an earlier window.
        altered=copy.deepcopy(c)
        for key in ("camera","encoder","vibration","acoustic","current","temperature","target"):
            altered[key][100:]+=1000
        np.testing.assert_array_equal(extract_features(c,100)[0],extract_features(altered,100)[0])

    def test_grouped_manifest_and_domain_shift(self):
        from research_pipeline.experiment import build_dataset,load_dataset
        with tempfile.TemporaryDirectory() as path:
            cases,manifest=build_dataset(path,seed=9,normal=1,scarce=1,extra=1,test_per_fault=1)
            ids=[r["id"] for r in manifest["cases"]]
            self.assertEqual(len(ids),len(set(ids)))
            train=[r for r in manifest["cases"] if r["split"]=="train"]
            test=[r for r in manifest["cases"] if r["split"]=="test"]
            self.assertTrue(all(r["metadata"]["load"]<=1.2 for r in train))
            self.assertTrue(all(r["metadata"]["speed_hz"]>=.22 for r in test))
            recovered,_=load_dataset(path)
            np.testing.assert_array_equal(next(iter(cases.values()))["camera"],next(iter(recovered.values()))["camera"])
            file=Path(path)/manifest["cases"][0]["file"]
            file.write_bytes(file.read_bytes()+b"changed")
            with self.assertRaises(ValueError):
                load_dataset(path)

    def test_legacy_checkpoint_and_correct_new_jerk_both_work(self):
        from robot_demo.faults import simulate_cycle as old_cycle,extract_features as old_features
        import joblib
        c=old_cycle("gearbox_backlash",3,seed=0)
        legacy,names=old_features(c,feature_schema="legacy_v1")
        np.testing.assert_allclose(legacy[-6:],np.max(np.abs(np.diff(c["actual"],n=2,axis=0)),axis=0))
        b=joblib.load(ROOT/"panda_repro/artifacts/fault_model.joblib")
        self.assertEqual(b["cause_model"].predict(legacy[None])[0],"gearbox_backlash")
        t=np.arange(20)*.05
        c["actual"]=np.tile((t**3)[:,None],(1,6))
        c["cycle_time"]=1.
        x,names=old_features(c)
        np.testing.assert_allclose(x[-6:],6.,rtol=1e-4)
        self.assertTrue(names[-1].startswith("pose_jerk_rad_s3"))

    def test_always_on_alarm_cannot_claim_to_detect_later_fault(self):
        from research_pipeline.experiment import event_metrics
        c=simulate_cycle("bearing",2,seed=11)
        r=event_metrics([c],lambda X:np.ones(len(X)),.5)
        self.assertEqual(r["event_recall"],0.)
        self.assertEqual(r["missed_fault_cycles"],1)


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        os.environ["DENSO_DEMO_DB"]=str(Path(cls.temp.name)/"feedback.db")
        from fastapi.testclient import TestClient
        import app
        cls.module=app
        cls.client=TestClient(app.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.temp.cleanup()
        os.environ.pop("DENSO_DEMO_DB",None)

    def test_invalid_scenario_rejected(self):
        c=self.client
        self.assertEqual(c.post("/api/run",json={"environment":"bad"}).status_code,422)
        self.assertEqual(c.post("/api/run",json={"injections":[{"fault":"bearing","landmark":3,"start_s":16,"duration_s":5}]}).status_code,422)

    def test_video_pose_and_labels_stay_immutable_and_csv_matches(self):
        from engine import POSE
        result=self.client.get("/api/run/default")
        self.assertEqual(result.status_code,200)
        d=result.json()
        self.assertEqual([r["points"] for r in d["timeline"]],[r["points"] for r in POSE])
        self.assertEqual([r["q_deg"] for r in d["timeline"]],[r["q_deg"] for r in POSE])
        self.assertTrue(all(e["detected_s"]>=e["start_s"]+1/d["fps"] for e in d["incidents"]))
        import csv,io
        rows=list(csv.reader(io.StringIO(self.client.get("/api/run/default/export.csv").text.lstrip("\ufeff"))))
        self.assertEqual(len(rows),1+len(POSE)*7)
        self.assertTrue(all(len(r)==len(rows[0]) for r in rows))
        self.assertIn("q_jerk_pred_deg_s3",rows[0])

    def test_feedback_requires_description_on_wrong_hypothesis(self):
        d=self.client.get("/api/run/default").json()
        self.assertTrue(d["incidents"])
        event=d["incidents"][0]["id"]
        path=f"/api/run/default/incidents/{event}/feedback"
        self.assertEqual(self.client.post(path,json={"correct":False,"technician":"Test","action":"Checked"}).status_code,422)
        self.assertEqual(self.client.post(path,json={"correct":False,"technician":"Test","action":"Checked","actual_cause":"Sensor mount"}).status_code,200)

    def test_research_status_and_path_lookup(self):
        self.assertEqual(self.client.get("/api/research").status_code,200)
        self.assertEqual(self.client.get("/api/research/case/unknown-id").status_code,404)

    def test_immutable_event_history_contains_pose_and_all_sensors(self):
        from unittest.mock import patch
        original=self.client.get('/api/run/default').json()
        event=original['incidents'][0]
        self.assertTrue(event['log_id'])
        listing=self.client.get('/api/history?run_id=default').json()
        self.assertEqual(listing['total'],len(original['incidents']))
        # Evidence must survive code/model changes, not be silently regenerated.
        with patch.object(self.module,'generate',side_effect=AssertionError('must read persisted evidence')):
            again=self.client.get('/api/run/default').json()
            detail=self.client.get('/api/history/'+event['log_id']).json()
        self.assertEqual(again['evidence_archive'],original['evidence_archive'])
        self.assertEqual(again['timeline'],original['timeline'])
        expected=[r for r in original['timeline'] if detail['window']['start_s']<=r['t']<=detail['window']['end_s']]
        self.assertEqual(detail['timeline'],expected)
        self.assertTrue(any(r['t']<event['start_s'] for r in expected))
        self.assertTrue(any(r['t']>event['end_s'] for r in expected))
        self.assertTrue(all(len(r['points'])==len(r['signals'])==len(r['q_deg'])==7 for r in expected))
        self.assertIn('robot_original.mp4',detail['asset_checksums'])
        self.assertIn('clock_definition',detail['evidence_archive'])
        # Re-reading does not duplicate events.
        self.assertEqual(self.client.get('/api/history?run_id=default').json()['total'],listing['total'])
        self.assertEqual(self.client.get('/api/history/unknown-event').status_code,404)
        self.assertEqual(self.client.get('/api/history?status=bad').status_code,422)

    def test_history_export_matches_frozen_frames_and_phase(self):
        import csv,io
        original=self.client.get('/api/run/default').json()
        key=original['incidents'][0]['log_id']
        detail=self.client.get('/api/history/'+key).json()
        export=self.client.get('/api/history/'+key+'/export.json')
        self.assertEqual(export.json(),detail)
        rows=list(csv.DictReader(io.StringIO(self.client.get('/api/history/'+key+'/export.csv').text.lstrip('\ufeff'))))
        self.assertEqual(len(rows),len(detail['timeline'])*7)
        self.assertEqual({r['event_phase'] for r in rows},{'before','during','after'})
        self.assertEqual({r['snapshot_sha256'] for r in rows},{original['evidence_archive']['sha256']})
        for row in rows[:7]:
            j=int(row['q_joint_id'][1:])-1
            frame=detail['timeline'][0]
            self.assertAlmostEqual(float(row['vibration_sim_mm_s']),frame['signals'][j]['vibration'])
            self.assertAlmostEqual(float(row['q_pred_deg']),frame['q_deg'][j])

    def test_maintenance_revisions_do_not_change_evidence(self):
        original=self.client.get('/api/run/default').json()
        event=original['incidents'][0]
        url='/api/history/'+event['log_id']
        before=self.client.get(url).json()
        feedback=f'/api/run/default/incidents/{event["id"]}/feedback'
        for correct,cause in ((True,'Bearing confirmed'),(False,'External source')):
            self.assertEqual(self.client.post(feedback,json={'correct':correct,'actual_cause':cause,'technician':'Test','action':'Measured again'}).status_code,200)
        after=self.client.get(url).json()
        self.assertEqual(len(after['maintenance_history']),len(before['maintenance_history'])+2)
        self.assertFalse(after['feedback']['correct'])
        self.assertEqual(after['timeline'],before['timeline'])
        self.assertEqual(after['evidence_archive'],before['evidence_archive'])

    def test_case_chart_matches_saved_benchmark_scores_and_events(self):
        path=self.module.RESEARCH_DIR / "seed_19/models/metrics.json"
        if not path.exists():
            self.skipTest("Run benchmark to verify saved model/chart consistency")
        saved=json.loads(path.read_text(encoding="utf-8"))
        response=self.client.get("/api/research/case/s19-test-bearing-000")
        self.assertEqual(response.status_code,200)
        case=response.json()
        for group in ("A_original","B_simple","C_physics"):
            expected=next(e for e in saved["groups"][group]["examples"] if e["label"]=="bearing")
            observed=case["evaluations"][group]
            np.testing.assert_allclose(observed["scores"],expected["scores"],rtol=1e-12)
            self.assertEqual(observed["timestamps"],expected["timestamps"])
            self.assertEqual(observed["detected_times"],expected["detected_times"])
            self.assertEqual(observed["threshold"],expected["threshold"])


if __name__=="__main__":
    unittest.main()
