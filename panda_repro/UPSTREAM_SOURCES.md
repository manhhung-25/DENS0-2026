# Reproducible upstream source references

The demo's own code is contained in this package. The two research repositories
remain separate Git histories and should be cloned directly:

```bash
git clone https://github.com/yannlabb/robopose.git
git clone https://github.com/Nimolty/RoboKeyGen.git
git clone https://github.com/facebookresearch/co-tracker.git
```

Exact commit hashes used during this build are recorded below after checkout.
They can be verified with `git rev-parse HEAD` in each clone.

- RoboPose commit: `97b86f33fdd3320ce34b931debbd204e12883d99`
- RoboKeyGen commit: `6028c3366e1badae05fa9944d9bf2b81a265d977`
- CoTracker commit: `82e02e8029753ad4ef13cf06be7f4fc5facdda4d`

RoboPose contains full training/inference/evaluation code and an MIT license.
RoboKeyGen currently provides dataset/checkpoint links but not its announced
training or inference implementation.

CoTracker3 contains the temporal point-tracking implementation used by the ABB
v2 video. Its repository license is CC BY-NC 4.0. Download the scaled offline
checkpoint with:

```bash
curl -L -o scaled_offline.pth \
  https://huggingface.co/facebook/cotracker3/resolve/main/scaled_offline.pth
```
