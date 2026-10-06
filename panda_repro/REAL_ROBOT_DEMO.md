# Real ABB video demo

This extension replaces the geometric stick robot with footage of a real ABB
industrial robot. Version 2 fixes the frozen-overlay failure of local optical
flow and deliberately distinguishes what is measured from what is simulated.

## What runs in the demo

1. `make_real_robot_video_v2.py` reads every frame of the ABB video.
2. Seven coarse kinematic landmarks are initialized once.
3. `cotracker_pose.py` creates nine support queries around each landmark and
   runs the official CoTracker3 scaled-offline checkpoint.
4. Median support motion rejects background drift. CoTracker visibility marks
   occlusion; PCHIP interpolation and Savitzky–Golay filtering reconstruct a
   smooth 25-fps trajectory from memory-friendly sampled inference.
5. TCP motion is measured from the real video and autocorrelation estimates the
   repeated cycle period after removing slow camera drift.
6. Physics-guided J3 vibration, acoustic, temperature and current streams are
   injected in physical display units.
7. The ExtraTrees fusion model predicts fault type and faulty joint.
8. Raw support tracks, visibility, landmarks and sensors are saved to NPZ;
   frame-level data go to CSV; event and demo technician feedback go to SQLite.

The released RoboPose checkpoints do not support ABB or NACHI. Running genuine
RoboPose inference on either brand requires the exact robot URDF/CAD, joint
limits, renderer assets, camera calibration and a robot-specific
detector/refiner checkpoint. The overlay is therefore named `CoTracker3
temporal 2D pose`, not `RoboPose ABB`. It does not return calibrated physical
joint angles `q1..q6`.

CoTracker3 is licensed CC BY-NC 4.0. Together with the personal-use footage,
this makes the rendered demonstration research/non-commercial only.

## Reproduce

Use Python 3.12 with the dependencies in `requirements.txt`. Download the
personal-use 720p clip linked in `THIRD_PARTY_ASSETS.md`, clone the pinned
CoTracker commit, download its checkpoint, then run:

```bash
git clone https://github.com/facebookresearch/co-tracker.git ../cotracker_upstream
git -C ../cotracker_upstream checkout 82e02e8029753ad4ef13cf06be7f4fc5facdda4d
mkdir -p ../cotracker_upstream/checkpoints
curl -L -o ../cotracker_upstream/checkpoints/scaled_offline.pth \
  https://huggingface.co/facebook/cotracker3/resolve/main/scaled_offline.pth

PYTHONPATH=src python -m robot_demo.make_real_robot_video_v2 \
  --input-video /path/to/abb_production_line_47257.mp4 \
  --artifacts artifacts \
  --output artifacts/abb_real_robot_demo_source_v2.avi \
  --cotracker-repo ../cotracker_upstream \
  --checkpoint ../cotracker_upstream/checkpoints/scaled_offline.pth \
  --tracking-stride 4 --force-track

ffmpeg -y -i artifacts/abb_real_robot_demo_source_v2.avi \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -movflags +faststart -an artifacts/abb_real_robot_demo.mp4
```

`--tracking-stride 4` is the verified CPU/RAM-friendly setting. Use `2` on a
GPU runtime with enough memory. Subsequent re-renders can omit `--force-track`
to reuse `artifacts/abb_cotracker_tracks.npz`.

## Sensor interpretation in this scenario

| Channel | English keyword | Unit | Gearbox-backlash evidence |
|---|---|---:|---|
| Rung | Vibration | mm/s RMS | Increases around direction reversal |
| Âm thanh | Acoustic emission | dBA | Impulsive mechanical sound increases |
| Nhiệt | Temperature | °C | Remains near baseline in this short window |
| Dòng motor | Motor current | A | Remains near baseline; overload is less likely |

The pattern, not one threshold alone, drives the diagnosis. All four values in
this stock-footage demo are simulated and must be replaced by synchronized
plant sensors before validation.

## Upgrade to genuine RoboPose on ABB/NACHI

- Replace tracked 2D landmarks with model outputs `(base_6d_pose, q1..q6)`.
- Add the exact manufacturer URDF/CAD, joint limits and camera intrinsics.
- Generate synthetic domain-randomized training renders.
- Fine-tune a detector and iterative render-and-compare refiner.
- Align controller timestamps with camera, accelerometer, microphone and
  thermal channels.
- Preserve this demo's cycle segmentation, fusion and event-feedback stages.
