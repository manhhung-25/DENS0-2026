#!/usr/bin/env bash
set -euo pipefail

mkdir -p checkpoints data/downloads
python -m gdown 'https://drive.google.com/uc?id=1UPGXkEhOPTvib0k5RyDvPJsR4HMjxmMl' \
  -O checkpoints/horopose_panda_realsense_model.pk
python -m gdown 'https://drive.google.com/uc?id=1FFAFpJFwzsjD83S9-Y1ODwDWiWlh1X6P' \
  -O data/downloads/panda-3cam_realsense.zip

echo 'Expected checkpoint SHA-256:'
echo '8611ff23183d1ada861627f728b19f3318f755a95c6d7d75a0944b5dd5b8614c'
sha256sum checkpoints/horopose_panda_realsense_model.pk
