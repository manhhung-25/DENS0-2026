from pathlib import Path

import numpy as np

from robot_demo.event_store import EventStore
from robot_demo.faults import FAULTS, extract_features, simulate_cycle
from robot_demo.geometry import Camera, forward_kinematics_np, project_np, sample_state
from robot_demo.simulator import generate_dataset
from robot_demo.cotracker_pose import aggregate_support_tracks, repair_and_resample_tracks


def test_geometry_visible_shapes():
    state = sample_state(np.random.default_rng(1))
    points = forward_kinematics_np(state)
    pixels, depth = project_np(points, Camera())
    assert points.shape == (7, 3)
    assert pixels.shape == (7, 2)
    assert np.all(depth > 0)


def test_all_faults_have_same_features():
    lengths = []
    for idx, fault in enumerate(FAULTS):
        cycle = simulate_cycle(fault, None, seed=idx)
        features, names = extract_features(cycle)
        lengths.append(len(features))
        assert np.isfinite(features).all()
        assert len(features) == len(names)
    assert len(set(lengths)) == 1


def test_dataset_and_event_store(tmp_path: Path):
    path = generate_dataset(tmp_path / "tiny.npz", samples=8, image_size=96)
    data = np.load(path)
    assert data["images"].shape == (8, 96, 96, 3)
    store = EventStore(tmp_path / "events.db")
    event_id = store.add_event("R1", "C1", 6.2, "motor_overload", 2, 0.9, {"temp": 44})
    store.add_feedback(event_id, "motor_overload", 2, "checked", "confirmed")
    assert store.get_event(event_id)["label_status"] == "confirmed"


def test_support_track_consensus_and_occlusion_repair():
    initial_centres = np.asarray([[20.0, 30.0], [70.0, 80.0]], dtype=np.float32)
    offsets = np.asarray([[0, 0], [-3, 0], [3, 0]], dtype=np.float32)
    initial_support = initial_centres[:, None, :] + offsets[None, :, :]
    translations = np.asarray([[0, 0], [4, 2], [8, 4]], dtype=np.float32)
    tracks = initial_support[None] + translations[:, None, None, :]
    visibility = np.ones(tracks.shape[:-1], dtype=bool)
    tracks[1, 0, 2] += 70.0  # one support point drifts to the background
    visibility[2, 1] = False  # complete occlusion for one landmark

    centres, confidence = aggregate_support_tracks(
        tracks, visibility, initial_support, initial_centres
    )
    assert np.allclose(centres[1, 0], initial_centres[0] + translations[1])
    assert np.isnan(centres[2, 1]).all()

    repaired, full_confidence = repair_and_resample_tracks(
        centres, confidence, np.asarray([0, 2, 4]), output_steps=5
    )
    assert repaired.shape == (5, 2, 2)
    assert np.isfinite(repaired).all()
    assert np.isfinite(full_confidence).all()
