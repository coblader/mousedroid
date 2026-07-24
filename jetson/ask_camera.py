#!/usr/bin/env python3
"""
Ask a vision-language model (via Ollama) about what the IMX219 camera sees.

Captures a frame through the Jetson ISP (reusing CsiCamera from
capture_camera.py), color-corrects it, sends it to a local Ollama VLM, and
streams the answer. Single-shot or interactive.

Examples:
    ./ask_camera.py "What do you see?"          # one question about a fresh frame
    ./ask_camera.py                              # interactive chat (new frame each turn)
    ./ask_camera.py -m moondream "Describe it"   # try a different model
    ./ask_camera.py --image /tmp/x.jpg "Read the text"   # use a file instead of the camera

Requires: `bash ~/setup_ollama_qwen.sh` first (installs Ollama + qwen2.5vl:3b).
"""

import argparse
import base64
import io
import json
import sys
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

# reuse the camera + white-balance code we already wrote
from capture_camera import CsiCamera, gray_world_correct

DEFAULT_MODEL = "qwen2.5vl:3b"
DEFAULT_HOST = "http://localhost:11434"


def frame_to_jpeg_b64(rgb, quality=90):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def capture_frame(args):
    """Return an RGB numpy frame, from the camera or an image file."""
    if args.image:
        return np.asarray(Image.open(args.image).convert("RGB"))
    with CsiCamera(*args.resolution, sensor_id=args.sensor_id) as cam:
        rgb = cam.capture(settle_frames=args.settle_frames)
    return rgb if args.no_correct else gray_world_correct(rgb)


def ask(host, model, prompt, image_b64, stream=True, num_gpu=99, num_ctx=4096):
    """POST to Ollama /api/generate and stream the response text to stdout.

    num_gpu=99 forces all layers onto the GPU (essential on Jetson unified
    memory -- otherwise Ollama may leave half the model on the slow CPU).
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": stream,
        "options": {"num_gpu": num_gpu, "num_ctx": num_ctx},
    }
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            full = []
            for line in resp:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if "response" in obj:
                    sys.stdout.write(obj["response"])
                    sys.stdout.flush()
                    full.append(obj["response"])
                if obj.get("error"):
                    sys.exit(f"\nOllama error: {obj['error']}")
            print()
            return "".join(full)
    except urllib.error.URLError as e:
        sys.exit(
            f"\nERROR: could not reach Ollama at {host} ({e}).\n"
            f"Is it running?  Try:  ollama serve   (or run ~/setup_ollama_qwen.sh)"
        )


def parse_args():
    p = argparse.ArgumentParser(
        description="Ask a local VLM (Ollama) about what the camera sees.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("prompt", nargs="?", help="question about the frame; omit for interactive chat")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL, help="Ollama model name")
    p.add_argument("--host", default=DEFAULT_HOST, help="Ollama server URL")
    p.add_argument("-r", "--resolution", nargs=2, type=int, metavar=("W", "H"),
                   default=[1280, 720], help="capture resolution (smaller = faster)")
    p.add_argument("-s", "--sensor-id", type=int, default=0, help="CSI sensor id")
    p.add_argument("-n", "--settle-frames", type=int, default=15,
                   help="frames to grab so auto-exposure settles")
    p.add_argument("--no-correct", action="store_true", help="skip white balance")
    p.add_argument("--image", help="use this image file instead of the camera")
    p.add_argument("--save", help="save the captured frame to this path")
    p.add_argument("--num-gpu", type=int, default=99,
                   help="layers on GPU (99 = all; keep high on Jetson)")
    p.add_argument("--num-ctx", type=int, default=4096,
                   help="context window; lower it if you hit memory limits")
    return p.parse_args()


def main():
    args = parse_args()

    if args.prompt:  # single shot
        rgb = capture_frame(args)
        if args.save:
            Image.fromarray(rgb).save(args.save, quality=92)
        print(f"[{args.model}] > ", end="", flush=True)
        ask(args.host, args.model, args.prompt, frame_to_jpeg_b64(rgb),
            num_gpu=args.num_gpu, num_ctx=args.num_ctx)
        return

    # interactive: grab a fresh frame for each question
    print(f"Interactive VLM chat with '{args.model}'. Each question grabs a NEW frame.")
    print("Type a question (or 'q' to quit).")
    while True:
        try:
            q = input("\nyou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in ("q", "quit", "exit"):
            break
        if not q:
            continue
        rgb = capture_frame(args)
        if args.save:
            Image.fromarray(rgb).save(args.save, quality=92)
        print(f"{args.model} > ", end="", flush=True)
        ask(args.host, args.model, q, frame_to_jpeg_b64(rgb),
            num_gpu=args.num_gpu, num_ctx=args.num_ctx)


if __name__ == "__main__":
    main()
