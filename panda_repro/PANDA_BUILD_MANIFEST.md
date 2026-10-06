# Panda deliverable manifest

| File | Purpose | SHA-256 |
|---|---|---|
| `checkpoints/horopose_panda_realsense_inference.pk` | Exact 2,308 model tensors, optimizer removed | `9c531ede1e32fcfc1d51a92cdef63f285483786730edda35e73838026c181c3c` |
| `artifacts/panda_horopose_health_demo.mp4` | Final H.264 demo video | `c91552e2b271160257938f1bf49a37aa86f22105450dcd88d6491696c21ac02e` |
| `artifacts/panda_pose_predictions.npz` | Raw, smoothed, calibrated predictions and GT | `2cac72e68a9baf371a3c7dcfa9e4383502c3644023d132e33b16917b0afb6358` |
| `artifacts/panda_multimodal_timeseries.csv` | Frame-synchronized pose and sensor timeline | `a77601f8ffc8bb7ff2509afd15f71541454b896b9f08354b005a7ed03a19a938` |
| `artifacts/panda_pose_metrics.json` | Quantitative pose evaluation | `afff4ceed3b5baad191a04db9d1f30e7e3d43a557485e1bc80d36effad1c7fce` |
| `artifacts/panda_horopose_demo_summary.json` | End-to-end summary | `0e1dc82171a8fe6eda87b4ed532668f2a345b70649b558e392125afa4cf96098` |
| `artifacts/panda_video_validation.json` | Video/motion validation | `0db8a28b6232fb01349e8a4ef68cf9d89e87598593fefdd5e23f1a7ef4fb478a` |

The bundle also contains the selected real RGB/JSON frames, vendored upstream
code, adapter source, simulator, trained sensor-fusion model, SQLite event
store, tests, documentation and exact asset download script.
