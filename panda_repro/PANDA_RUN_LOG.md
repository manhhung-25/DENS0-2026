# Panda demo run log

Run date: 2026-09-13 UTC

## Upstream and assets

- HoRoPose commit: `77cd316a36ff8de0c736a66c692ca9276fdc2eae`
- Model: `panda/panda_realsense/ckpt/curr_best_auc(add)_model.pk`
- Checkpoint SHA-256: `8611ff23183d1ada861627f728b19f3318f755a95c6d7d75a0944b5dd5b8614c`
- Dataset: DREAM `panda-3cam_realsense`, selected frames `002640..002759`

## Commands executed

```bash
python -m pip install --user gdown easydict opencv-python-headless imageio imageio-ffmpeg
python -m pip install --user --index-url https://download.pytorch.org/whl/cpu torch==2.9.1 torchvision==0.24.1
export PYTHONPATH="$PWD/src"
python -m robot_demo.horopose_panda --batch-size 4
python -m robot_demo.make_panda_video
python -m pytest -q
```

## Runtime

- Python 3.12.14
- PyTorch 2.9.1+cpu
- OpenCV 5.0.0
- NumPy 2.3.5
- SciPy 1.17.0
- scikit-learn 1.8.0

## Verification

- 120/120 real frames inferred.
- All 2,308 model-state tensors loaded with `strict=True`.
- 500-frame H.264/yuv420p video opens at 1280×720, 30 fps.
- 5/7 projected links move more than 10 px over the selected sequence.
- Tests: 4 passed.

