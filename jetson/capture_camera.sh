#!/usr/bin/env bash
#
# Capture a frame from the IMX219 CSI camera (through the Jetson ISP) and
# apply a gray-world white-balance correction to remove the magenta cast.
#
# Usage: ./capture_camera.sh [WIDTH HEIGHT]
#   default 1920x1080; e.g. ./capture_camera.sh 3280 2464  for full 8MP
#
# Outputs:
#   /tmp/cam_raw.jpg        - straight from the ISP (with the magenta tint)
#   /tmp/cam_corrected.jpg  - after gray-world white balance

set -euo pipefail

W="${1:-1920}"
H="${2:-1080}"
RAW=/tmp/cam_raw.jpg
OUT=/tmp/cam_corrected.jpg

echo ">> Capturing ${W}x${H} (letting auto-exposure settle)..."
rm -f /tmp/_capframe_*.jpg
timeout 40 gst-launch-1.0 -e nvarguscamerasrc num-buffers=30 sensor-id=0 wbmode=1 \
  ! "video/x-raw(memory:NVMM),width=${W},height=${H},framerate=30/1" \
  ! nvvidconv ! 'video/x-raw,format=I420' \
  ! jpegenc quality=92 ! multifilesink location=/tmp/_capframe_%03d.jpg >/dev/null 2>&1

# keep the last settled frame
LAST=$(ls /tmp/_capframe_*.jpg | sort | tail -1)
cp "$LAST" "$RAW"
rm -f /tmp/_capframe_*.jpg
echo ">> Raw frame saved: $RAW"

echo ">> Applying gray-world white balance..."
python3 - "$RAW" "$OUT" <<'PY'
import sys
import numpy as np
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
img = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)

# Gray-world assumption: the average of each channel should be equal.
means = img.reshape(-1, 3).mean(axis=0)          # per-channel mean R,G,B
gray = means.mean()                              # target neutral gray
gains = gray / np.clip(means, 1e-6, None)        # scale each channel to it

# Don't over-boost: cap gains to a sane range so noise doesn't explode
gains = np.clip(gains, 0.5, 2.5)
img *= gains

out = np.clip(img, 0, 255).astype(np.uint8)
Image.fromarray(out).save(dst, quality=92)

print(f"   channel means (R,G,B): {means.round(1)}")
print(f"   applied gains  (R,G,B): {gains.round(3)}")
PY

echo ">> Corrected frame saved: $OUT"
