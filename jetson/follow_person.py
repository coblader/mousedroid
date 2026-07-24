#!/usr/bin/env python3
"""
End-to-end demo: the mouse droid follows a person.

  camera frame -> VLM locates person -> controller -> drive L/R -> read TEL -> repeat

RUN WITH THE DROID ON BLOCKS (wheels free) until you trust it. The VLM is slow
(seconds per frame), so following is laggy -- the point is to prove the whole
pipeline end to end. Swap in a faster detector / the OAK-D Lite later behind the
same Detection interface.

Prereqs:
  * camera enabled (bash enable_imx219_camera.sh + reboot)
  * Ollama + model  (bash setup_ollama_qwen.sh)
  * flight firmware on the Arduino (firmware/mouse_droid_controller)
  * python deps      (pip install -r requirements.txt)

  ./follow_person.py                # full loop on /dev/ttyACM0
  ./follow_person.py --dry-run      # perception + control only, NO serial/motors
  ./follow_person.py --no-move      # runs the loop but only ever sends stop
  ./follow_person.py --once         # one frame -> print detection + command, exit
"""
from __future__ import annotations

import argparse
import time

from capture_camera import CsiCamera, gray_world_correct
from control import FollowConfig, follow_command
from vlm_locator import VlmLocator, DEFAULT_MODEL, DEFAULT_HOST


def parse_args():
    p = argparse.ArgumentParser(description="Follow a person (camera -> VLM -> Arduino).")
    p.add_argument("--port", default="/dev/ttyACM0", help="Arduino serial port")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL, help="Ollama VLM model")
    p.add_argument("--host", default=DEFAULT_HOST, help="Ollama server URL")
    p.add_argument("-r", "--resolution", nargs=2, type=int, metavar=("W", "H"),
                   default=[640, 360], help="capture resolution (small = faster VLM)")
    p.add_argument("-s", "--sensor-id", type=int, default=0)
    p.add_argument("--max-mms", type=float, default=250.0, help="wheel-speed clamp")
    p.add_argument("--target-area", type=float, default=0.18,
                   help="desired person bbox area fraction (~follow distance)")
    p.add_argument("--dry-run", action="store_true",
                   help="no serial: just print detections + intended commands")
    p.add_argument("--no-move", action="store_true",
                   help="run the loop but only send stop (safe wiring test)")
    p.add_argument("--once", action="store_true", help="one iteration then exit")
    return p.parse_args()


def main():
    args = parse_args()
    cfg = FollowConfig(max_mms=args.max_mms, target_area=args.target_area)
    locator = VlmLocator(model=args.model, host=args.host)

    droid = None
    if not args.dry_run:
        from serial_link import MouseDroid
        droid = MouseDroid(port=args.port, max_mms=args.max_mms)
        tel = droid.wait_for_telemetry(3.0)
        print(f"[serial] {args.port}: telemetry {'ok' if tel else 'NONE (flight fw flashed?)'}")

    w, h = args.resolution
    print(f"[camera] {w}x{h}   [vlm] {args.model}")
    print("Ctrl-C to stop.\n")

    n = 0
    try:
        with CsiCamera(w, h, sensor_id=args.sensor_id) as cam:
            cam.capture(settle_frames=10)               # warm up auto-exposure once
            while True:
                t0 = time.time()
                rgb = gray_world_correct(cam.capture(settle_frames=3))
                det = locator.locate(rgb)
                left, right = follow_command(det, cfg)

                if args.dry_run:
                    tag = "(dry-run)"
                elif args.no_move:
                    droid.stop()
                    tag = "(no-move)"
                else:
                    droid.drive(left, right)
                    tag = ""

                where = (f"person cx={det.cx:.2f} area={det.area:.2f}"
                         if det.found else "no person")
                tel = droid.telemetry if droid else None
                telstr = (f" | TEL L{tel['left_mms']:.0f} R{tel['right_mms']:.0f}"
                          if tel else "")
                print(f"[{n:03d}] {time.time()-t0:4.1f}s  {where}  -> "
                      f"L{left:.0f} R{right:.0f} {tag}{telstr}")

                n += 1
                if args.once:
                    break
    except KeyboardInterrupt:
        print("\nstopping.")
    finally:
        if droid:
            droid.stop()
            droid.close()


if __name__ == "__main__":
    main()
