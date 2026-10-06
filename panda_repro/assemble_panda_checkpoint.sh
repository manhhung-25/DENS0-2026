#!/usr/bin/env bash
set -euo pipefail

parts_dir="${1:-checkpoint_parts}"
output="${2:-checkpoints/horopose_panda_realsense_inference.pk}"
mkdir -p "$(dirname "$output")"
cat "$parts_dir"/horopose_panda_realsense_inference.pk.part-* > "$output"
echo "Expected: 9c531ede1e32fcfc1d51a92cdef63f285483786730edda35e73838026c181c3c"
sha256sum "$output"
