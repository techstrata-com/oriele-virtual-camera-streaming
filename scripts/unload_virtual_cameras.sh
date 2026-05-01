#!/usr/bin/env bash
set -euo pipefail

sudo modprobe -r v4l2loopback
echo "Unloaded v4l2loopback."

