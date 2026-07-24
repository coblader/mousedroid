#!/usr/bin/env python3
"""
Benchmark several Ollama VLMs on the SAME image: latency + the answer.

Usage:
    ./bench_vlms.py [IMAGE] [-m model1 model2 ...] [-p "prompt"]

Defaults to /tmp/bench.jpg and a small model set. Forces full GPU offload
(num_gpu=99) so every model runs on the Jetson GPU, not the CPU.
"""
import argparse
import base64
import json
import time
import urllib.request

DEFAULT_MODELS = ["moondream", "llava-phi3", "granite3.2-vision", "qwen2.5vl:3b"]
HOST = "http://localhost:11434"


def run(model, img_b64, prompt, num_predict):
    payload = {
        "model": model, "prompt": prompt, "images": [img_b64], "stream": False,
        "options": {"num_gpu": 99, "num_ctx": 4096, "num_predict": num_predict},
    }
    req = urllib.request.Request(
        f"{HOST}/api/generate", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    t = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=300))
    except Exception as e:
        return None, f"ERROR: {e}"
    wall = time.time() - t
    stats = {
        "wall": wall,
        "img_tok": d.get("prompt_eval_count"),
        "prefill": d.get("prompt_eval_duration", 0) / 1e9,
        "gen": d.get("eval_duration", 0) / 1e9,
        "gen_tok": d.get("eval_count"),
    }
    return stats, d.get("response", "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", default="/tmp/bench.jpg")
    ap.add_argument("-m", "--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("-p", "--prompt", default="Describe what you see in one sentence.")
    ap.add_argument("-n", "--num-predict", type=int, default=60)
    args = ap.parse_args()

    img_b64 = base64.b64encode(open(args.image, "rb").read()).decode()
    print(f"Image: {args.image}   Prompt: {args.prompt!r}\n")

    for m in args.models:
        print(f"### {m}")
        # first call also loads the model (cold); do a warm-up then a timed run
        run(m, img_b64, "hi", 1)                      # warm/load
        stats, ans = run(m, img_b64, args.prompt, args.num_predict)
        if stats is None:
            print(f"   {ans}\n")
            continue
        gen_rate = (stats["gen_tok"] or 0) / max(stats["gen"], 1e-3)
        print(f"   img_tokens={stats['img_tok']}  prefill={stats['prefill']:.1f}s  "
              f"gen={stats['gen']:.1f}s ({gen_rate:.1f} tok/s)  "
              f"TOTAL={stats['wall']:.1f}s")
        print(f"   -> {ans}\n")


if __name__ == "__main__":
    main()
