#!/usr/bin/env python3
"""
Run every (model x image x task) combination and record latency + answers.
Reads manifest.json (ground truth) + config.json; writes results.json.

    python3 ~/vlm_bench/run_bench.py                # all models in config
    python3 ~/vlm_bench/run_bench.py -m moondream   # just one/some models
"""
import argparse
import base64
import json
import os
import time
import urllib.request

BENCH = os.path.dirname(os.path.abspath(__file__))
CONFIG = json.load(open(os.path.join(BENCH, "config.json")))
MANIFEST = json.load(open(os.path.join(BENCH, "manifest.json")))
IMAGES = os.path.join(BENCH, "images")


def build_tasks(entry):
    """Expand one labeled image into concrete (type, key, prompt, expected) tasks."""
    p = CONFIG["prompts"]
    tasks = []
    if entry.get("caption"):
        tasks.append(("caption", "-", p["caption"], entry["caption"]))
    for obj, n in entry.get("objects", {}).items():
        tasks.append(("count", obj, p["count"].format(obj=obj), n))
        tasks.append(("presence", obj, p["presence"].format(obj=obj), "yes"))
    for obj in entry.get("absent", []):
        tasks.append(("presence", obj, p["presence"].format(obj=obj), "no"))
    for obj, col in entry.get("colors", {}).items():
        tasks.append(("color", obj, p["color"].format(obj=obj), col))
    for qa in entry.get("spatial", []):
        tasks.append(("spatial", qa["q"], p["spatial"].format(q=qa["q"]), qa["a"]))
    return tasks


def query(model, prompt, img_b64, num_predict):
    payload = {
        "model": model, "prompt": prompt, "images": [img_b64], "stream": False,
        "options": {**CONFIG["options"], "num_predict": num_predict},
    }
    req = urllib.request.Request(
        f"{CONFIG['host']}/api/generate", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    t = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=300))
    return {
        "response": d.get("response", "").strip(),
        "total_s": round(time.time() - t, 2),
        "prefill_s": round(d.get("prompt_eval_duration", 0) / 1e9, 2),
        "gen_s": round(d.get("eval_duration", 0) / 1e9, 2),
        "img_tokens": d.get("prompt_eval_count"),
        "gen_tokens": d.get("eval_count"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--models", nargs="+", default=CONFIG["models"])
    args = ap.parse_args()

    records = []
    for model in args.models:
        print(f"\n=== {model} ===")
        # warm-up / load (also tells us if the model is missing)
        try:
            b0 = base64.b64encode(
                open(os.path.join(IMAGES, MANIFEST["images"][0]["file"]), "rb").read()).decode()
            query(model, "hi", b0, 1)
        except Exception as e:
            print(f"  !! skipping {model}: {e}")
            continue

        for entry in MANIFEST["images"]:
            img_b64 = base64.b64encode(
                open(os.path.join(IMAGES, entry["file"]), "rb").read()).decode()
            for ttype, key, prompt, expected in build_tasks(entry):
                np_ = CONFIG["num_predict"].get(ttype, 20)
                try:
                    r = query(model, prompt, img_b64, np_)
                except Exception as e:
                    r = {"response": f"ERROR: {e}", "total_s": None,
                         "prefill_s": None, "gen_s": None,
                         "img_tokens": None, "gen_tokens": None}
                rec = {"model": model, "image": entry["file"], "type": ttype,
                       "key": key, "prompt": prompt, "expected": expected, **r}
                records.append(rec)
                print(f"  [{ttype:8s} {key[:18]:18s}] {r['total_s']}s  -> {r['response'][:50]}")

    out = {"records": records, "models": args.models}
    json.dump(out, open(os.path.join(BENCH, "results.json"), "w"), indent=2)
    print(f"\nWrote results.json ({len(records)} records). Now run:  python3 ~/vlm_bench/report.py")


if __name__ == "__main__":
    main()
