#!/usr/bin/env python3
"""
Locate a person in a frame using the local Ollama VLM (default qwen2.5vl:3b).

Asks the model for the person's bounding box as JSON, parses it, and returns a
Detection (found, cx, cy, area). This is the SLOW perception path (seconds per
frame on the Orin Nano 8 GB) -- enough to prove the follow loop. Swap in a fast
detector or the OAK-D Lite behind the same Detection interface for smooth
real-time tracking + real depth (see BUILD.md §8 / §13).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

from detection import Detection

DEFAULT_MODEL = "qwen2.5vl:3b"
DEFAULT_HOST = "http://localhost:11434"

_PROMPT = (
    "You are the eyes of a small robot that follows a person. Look at the image. "
    "If a person is visible, reply with ONLY a compact JSON object: "
    '{"present": true, "box": [x0, y0, x1, y1]} where the box is the person\'s '
    "bounding box in NORMALIZED coordinates from 0.0 to 1.0 (x0,y0 = top-left, "
    "x1,y1 = bottom-right). If a person is only partly visible, box the visible "
    'part. If no person is visible, reply with {"present": false}. '
    "Reply with JSON only, no explanation."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class VlmLocator:
    def __init__(self, model=DEFAULT_MODEL, host=DEFAULT_HOST,
                 num_gpu=99, num_ctx=2048, timeout_s=120, debug=False):
        self.model = model
        self.host = host
        self.num_gpu = num_gpu       # 99 = all layers on GPU (essential on Jetson)
        self.num_ctx = num_ctx
        self.timeout_s = timeout_s
        self.debug = debug or bool(os.environ.get("MOUSEDROID_VLM_DEBUG"))

    def locate(self, rgb: np.ndarray) -> Detection:
        h, w = rgb.shape[:2]
        text = self._query(_frame_to_jpeg_b64(rgb))
        if self.debug:
            print(f"    [vlm raw] {text!r}")
        return _parse_detection(text, w, h)

    def _query(self, image_b64: str) -> str:
        payload = {
            "model": self.model,
            "prompt": _PROMPT,
            "images": [image_b64],
            "stream": False,
            "options": {"num_gpu": self.num_gpu, "num_ctx": self.num_ctx,
                        "temperature": 0},
        }
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                obj = json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"could not reach Ollama at {self.host} ({e}); "
                "is it running? (bash setup_ollama_qwen.sh / ollama serve)"
            )
        if obj.get("error"):
            raise RuntimeError(f"Ollama error: {obj['error']}")
        return obj.get("response", "")


def _frame_to_jpeg_b64(rgb, quality=85):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _normalize(a, b, dim):
    """Map a pair of coords on one axis to 0..1.

    VLMs return boxes in different scales: already 0..1, absolute pixels (0..dim),
    or a 0..1000 grounding grid (Qwen). Pick per axis from the magnitude.
    """
    m = max(abs(a), abs(b))
    if m <= 1.0:
        return a, b                      # already normalized
    if dim and m <= dim * 1.02:
        return a / dim, b / dim          # looks like pixel coords for this axis
    return a / 1000.0, b / 1000.0        # fall back to 0..1000 grid


def _parse_detection(text: str, w=None, h=None) -> Detection:
    m = _JSON_RE.search(text or "")
    if not m:
        return Detection(found=False)
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return Detection(found=False)
    if not obj.get("present"):
        return Detection(found=False)
    box = obj.get("box")
    if not (isinstance(box, (list, tuple)) and len(box) == 4):
        return Detection(found=False)
    try:
        x0, y0, x1, y1 = (float(v) for v in box)
    except (TypeError, ValueError):
        return Detection(found=False)
    x0, x1 = _normalize(x0, x1, w)
    y0, y1 = _normalize(y0, y1, h)
    x0, x1 = _clamp01(x0), _clamp01(x1)
    y0, y1 = _clamp01(y0), _clamp01(y1)
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return Detection(
        found=True,
        cx=(x0 + x1) / 2.0,
        cy=(y0 + y1) / 2.0,
        area=max(0.0, (x1 - x0) * (y1 - y0)),
    )


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Locate a person via the VLM (test).")
    p.add_argument("--image", help="image file (otherwise grab a camera frame)")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL)
    args = p.parse_args()
    if args.image:
        rgb = np.asarray(Image.open(args.image).convert("RGB"))
    else:
        from capture_camera import CsiCamera, gray_world_correct
        with CsiCamera(1280, 720) as cam:
            rgb = gray_world_correct(cam.capture(settle_frames=10))
    print(VlmLocator(model=args.model).locate(rgb))
