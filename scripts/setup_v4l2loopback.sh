#!/usr/bin/env bash
set -euo pipefail

# This script installs the v4l2loopback kernel module (Ubuntu/Debian).
# It enables creating virtual video devices like /dev/video10 that apps can read from.

sudo apt update
sudo apt install -y v4l2loopback-dkms v4l2loopback-utils

echo "Installed v4l2loopback. Next run: ./scripts/load_virtual_cameras.sh"

