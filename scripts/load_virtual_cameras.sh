#!/usr/bin/env bash
set -euo pipefail

sudo modprobe v4l2loopback \
  video_nr=10,11,12,13,14 \
  card_label="VirtualCam10,VirtualCam11,VirtualCam12,VirtualCam13,VirtualCam14" \
  exclusive_caps=1

echo "Loaded v4l2loopback. Devices:"
ls -la /dev/video10 /dev/video11 /dev/video12 /dev/video13 /dev/video14 2>/dev/null || true

