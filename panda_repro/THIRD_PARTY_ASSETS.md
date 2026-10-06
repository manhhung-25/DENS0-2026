# Third-party sources and boundaries

## RoboPose

- Repository: https://github.com/yannlabb/robopose
- Project: https://www.di.ens.fr/willow/research/robopose/
- License: MIT for the repository code.
- Used as the architectural reference for the articulated overlay and the
  proposed ABB/NACHI adaptation path. The upstream repository is not vendored
  into this package; clone the pinned commit listed in `UPSTREAM_SOURCES.md`.

## RoboKeyGen

- Repository: https://github.com/Nimolty/RoboKeyGen
- Project: https://nimolty.github.io/Robokeygen/
- Dataset and checkpoints are public, but the repository still marks training
  and inference code as unreleased. It is retained as a research reference.

## CoTracker3

- Repository: https://github.com/facebookresearch/co-tracker
- Checkpoint: https://huggingface.co/facebook/cotracker3/resolve/main/scaled_offline.pth
- License: Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0).
- Used at inference time to track support points around the ABB landmarks. The
  upstream repository and 98-MiB checkpoint are not vendored in the source ZIP;
  the exact commit and reproducible download command are documented separately.
- This component makes the demonstration non-commercial. Replacing it in a
  commercial deployment requires a tracker with appropriate licensing.

## ABB demonstration footage

- Title: Robot working in a production line
- Page: https://mixkit.co/free-stock-video/robot-working-in-a-production-line-47257/
- Clip ID: 47257, 720p, 25 fps.
- The page labels the 720p download as personal-use-only under the Mixkit
  Restricted License. Do not redistribute or use the footage commercially.
- The project source package records the source and download command but does
  not vendor the original clip.

The final MP4 labels the visual tracking and synthetic sensor/fault portions so
that it is not mistaken for a validated ABB diagnostic product. The rendered
demo inherits both the footage's personal-use restriction and CoTracker's
non-commercial boundary.
