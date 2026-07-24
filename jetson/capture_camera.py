#!/usr/bin/env python3
"""
Capture a frame from the IMX219 CSI camera on the Jetson Orin Nano.

Uses the GStreamer Python API (PyGObject / gi) directly -- it builds the
pipeline as objects and pulls frames into numpy via an appsink, rather than
shelling out to gst-launch. Frames go through the Jetson ISP
(nvarguscamerasrc), then a gray-world white balance removes the IMX219
magenta cast.

Examples:
    ./capture_camera.py                        # -> /tmp/cam_corrected.jpg (1080p)
    ./capture_camera.py myshot.jpg             # custom filename
    ./capture_camera.py -r 3280 2464 8mp.jpg   # full 8 MP
    ./capture_camera.py -s 1 cam1.jpg          # use CAM1
    ./capture_camera.py --no-correct raw.jpg   # skip white balance
"""

import argparse
import sys

import numpy as np
from PIL import Image

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

DEFAULT_OUTPUT = "/tmp/cam_corrected.jpg"


class CsiCamera:
    """Minimal CSI-camera capture via GStreamer + appsink.

    Pipeline: nvarguscamerasrc -> (ISP) -> nvvidconv -> RGBA -> appsink.
    We request RGBA so rows are always 4-byte aligned (stride == width*4),
    which lets us reshape the buffer into numpy with no padding surprises.
    """

    def __init__(self, width=1920, height=1080, sensor_id=0, framerate=30):
        Gst.init(None)
        desc = (
            f"nvarguscamerasrc sensor-id={sensor_id} wbmode=1 "
            f"! video/x-raw(memory:NVMM),width={width},height={height},"
            f"framerate={framerate}/1 "
            f"! nvvidconv "
            f"! video/x-raw,format=RGBA "
            f"! appsink name=sink emit-signals=false max-buffers=4 drop=true sync=false"
        )
        self.pipeline = Gst.parse_launch(desc)
        self.sink = self.pipeline.get_by_name("sink")
        self.width = width
        self.height = height

    def __enter__(self):
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Failed to start pipeline (camera busy or not connected?)")
        return self

    def __exit__(self, *exc):
        self.pipeline.set_state(Gst.State.NULL)

    def _pull(self, timeout_s):
        """Pull one RGB frame (numpy HxWx3), or None on timeout."""
        sample = self.sink.emit("try-pull-sample", int(timeout_s * Gst.SECOND))
        if sample is None:
            return None
        buf = sample.get_buffer()
        caps = sample.get_caps().get_structure(0)
        w, h = caps.get_value("width"), caps.get_value("height")
        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            raise RuntimeError("Failed to map GStreamer buffer")
        try:
            frame = np.frombuffer(mapinfo.data, np.uint8).reshape(h, w, 4)
            return frame[:, :, :3].copy()  # drop alpha; copy so it survives unmap
        finally:
            buf.unmap(mapinfo)

    def capture(self, settle_frames=30, timeout_s=10.0):
        """Grab `settle_frames` frames so auto-exposure/AWB settle; return the last."""
        frame = None
        for _ in range(max(1, settle_frames)):
            got = self._pull(timeout_s)
            if got is None:
                break
            frame = got
        if frame is None:
            raise RuntimeError("No frames received (check the camera connection).")
        return frame


def gray_world_correct(rgb, gain_min=0.5, gain_max=2.5):
    """Scale each channel so its mean equals the overall gray mean."""
    img = rgb.astype(np.float32)
    means = img.reshape(-1, 3).mean(axis=0)
    gray = means.mean()
    gains = np.clip(gray / np.clip(means, 1e-6, None), gain_min, gain_max)
    img *= gains
    print(f"   channel means (R,G,B): {means.round(1)}")
    print(f"   applied gains  (R,G,B): {gains.round(3)}")
    return np.clip(img, 0, 255).astype(np.uint8)


def parse_args():
    p = argparse.ArgumentParser(
        description="Capture and white-balance a frame from the IMX219 CSI camera.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("output", nargs="?", default=DEFAULT_OUTPUT, help="output image file")
    p.add_argument("-r", "--resolution", nargs=2, type=int, metavar=("W", "H"),
                   default=[1920, 1080], help="capture resolution")
    p.add_argument("-s", "--sensor-id", type=int, default=0,
                   help="CSI sensor id (0 = CAM0, 1 = CAM1)")
    p.add_argument("-n", "--settle-frames", type=int, default=30,
                   help="frames to grab so auto-exposure can settle")
    p.add_argument("-t", "--timeout", type=float, default=10.0,
                   help="per-frame pull timeout in seconds")
    p.add_argument("--no-correct", action="store_true",
                   help="skip gray-world white balance")
    p.add_argument("--save-raw", metavar="PATH",
                   help="also save the uncorrected frame to PATH")
    return p.parse_args()


def main():
    args = parse_args()
    w, h = args.resolution

    print(f">> Capturing {w}x{h} via GStreamer appsink (settling auto-exposure)...")
    try:
        with CsiCamera(w, h, args.sensor_id) as cam:
            rgb = cam.capture(settle_frames=args.settle_frames, timeout_s=args.timeout)
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")

    if args.save_raw:
        Image.fromarray(rgb).save(args.save_raw, quality=92)
        print(f">> Raw frame saved: {args.save_raw}")

    if args.no_correct:
        out = rgb
        print(">> Skipping white balance.")
    else:
        print(">> Applying gray-world white balance...")
        out = gray_world_correct(rgb)

    Image.fromarray(out).save(args.output, quality=92)
    print(f">> Saved: {args.output}")


if __name__ == "__main__":
    main()
