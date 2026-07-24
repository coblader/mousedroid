#!/usr/bin/env python3
"""
Workbench: stage a scene, capture a frame from the IMX219, and label it with
ground truth. Appends to manifest.json so the benchmark can score accuracy.

Run it once per scene:
    python3 ~/vlm_bench/capture_labeled.py

You'll be prompted for the ground truth (leave any field blank to skip it).
For downloaded images instead of the camera:
    python3 ~/vlm_bench/capture_labeled.py --import /path/to/pic.jpg
"""
import argparse
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.expanduser("~"))          # find capture_camera.py
BENCH = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(BENCH, "images")
MANIFEST = os.path.join(BENCH, "manifest.json")


def load_manifest():
    if os.path.exists(MANIFEST):
        return json.load(open(MANIFEST))
    return {"images": []}


def save_manifest(m):
    json.dump(m, open(MANIFEST, "w"), indent=2)


def ask_kv(label, cast=str):
    """Parse 'a:1, b:2' style input into a dict."""
    raw = input(f"  {label} (e.g. 'cup:2, laptop:1'; blank to skip): ").strip()
    out = {}
    for part in filter(None, [p.strip() for p in raw.split(",")]):
        if ":" in part:
            k, v = part.split(":", 1)
            try:
                out[k.strip()] = cast(v.strip())
            except ValueError:
                print(f"    (skipped '{part}')")
    return out


def ask_spatial():
    print("  spatial Q/A (format 'question | answer'; blank line to finish):")
    pairs = []
    while True:
        line = input("    > ").strip()
        if not line:
            break
        if "|" in line:
            q, a = line.split("|", 1)
            pairs.append({"q": q.strip(), "a": a.strip()})
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--import", dest="imp", help="import an existing image file")
    ap.add_argument("-r", "--resolution", nargs=2, type=int, default=[1280, 720])
    args = ap.parse_args()

    os.makedirs(IMAGES, exist_ok=True)
    m = load_manifest()
    idx = len(m["images"]) + 1

    if args.imp:
        fname = f"img_{idx:02d}_{os.path.basename(args.imp)}"
        Image.open(args.imp).convert("RGB").save(os.path.join(IMAGES, fname), quality=92)
        source = "download"
    else:
        input("Stage the scene, then press Enter to capture...")
        from capture_camera import CsiCamera, gray_world_correct
        with CsiCamera(*args.resolution, sensor_id=0) as cam:
            rgb = cam.capture(settle_frames=15)
        fname = f"img_{idx:02d}_cam.jpg"
        Image.fromarray(gray_world_correct(rgb)).save(os.path.join(IMAGES, fname), quality=92)
        source = "camera"
    print(f"Saved images/{fname}\n")

    print("Enter ground truth (this is what we score the models against):")
    entry = {
        "file": fname,
        "source": source,
        "caption": input("  caption (one true sentence): ").strip(),
        "objects": ask_kv("object counts", int),
        "absent": [s.strip() for s in
                   input("  objects definitely NOT present (comma list): ").split(",") if s.strip()],
        "colors": ask_kv("colors  'object:color'"),
        "spatial": ask_spatial(),
    }
    m["images"].append(entry)
    save_manifest(m)
    print(f"\nAdded to manifest ({len(m['images'])} images total). Run capture_labeled.py again for the next scene.")


if __name__ == "__main__":
    main()
