#!/usr/bin/env python3
"""
Score results.json and print a comparison report.

Objective tasks (count / presence / color) are auto-scored against the
manifest. Subjective tasks (caption / spatial) are collected for review --
paste them back to Claude with the images and Claude will judge them.

    python3 ~/vlm_bench/report.py            # summary + accuracy table
    python3 ~/vlm_bench/report.py --full     # also dump every subjective answer
"""
import argparse
import json
import os
import re
from collections import defaultdict

BENCH = os.path.dirname(os.path.abspath(__file__))
RESULTS = json.load(open(os.path.join(BENCH, "results.json")))

# a few color synonyms so "grey"/"gray" etc. match
COLOR_SYN = {"grey": "gray", "silver": "gray", "gold": "yellow"}


def norm_color(c):
    c = c.lower().strip()
    return COLOR_SYN.get(c, c)


def score(rec):
    """Return True/False for objective tasks, or None if subjective."""
    resp = rec["response"].lower()
    exp = rec["expected"]
    if rec["type"] == "count":
        nums = re.findall(r"-?\d+", resp)
        return bool(nums) and int(nums[0]) == int(exp)
    if rec["type"] == "presence":
        said = "yes" if re.search(r"\byes\b", resp) else ("no" if re.search(r"\bno\b", resp) else "")
        return said == str(exp).lower()
    if rec["type"] == "color":
        return norm_color(str(exp)) in norm_color(resp) or norm_color(resp) in norm_color(str(exp))
    return None  # caption, spatial -> judged separately


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    recs = RESULTS["records"]
    models = RESULTS["models"]

    # ---- accuracy (objective) + latency, per model ----
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # model -> type -> [correct,total]
    lat = defaultdict(list)
    pref = defaultdict(list)
    for r in recs:
        if r["total_s"] is not None:
            lat[r["model"]].append(r["total_s"])
            if r["prefill_s"] is not None:
                pref[r["model"]].append(r["prefill_s"])
        s = score(r)
        if s is not None:
            a = acc[r["model"]][r["type"]]
            a[1] += 1
            a[0] += int(s)

    types = ["count", "presence", "color"]
    print("\n=== ACCURACY (auto-scored objective tasks) ===")
    hdr = f"{'model':16s} " + " ".join(f"{t:>10s}" for t in types) + f" {'overall':>9s}"
    print(hdr); print("-" * len(hdr))
    for m in models:
        cells, tc, tt = [], 0, 0
        for t in types:
            c, n = acc[m][t]
            tc += c; tt += n
            cells.append(f"{(100*c/n):>9.0f}%" if n else f"{'-':>10s}")
        overall = f"{(100*tc/tt):>8.0f}%" if tt else f"{'-':>9s}"
        if lat[m]:
            print(f"{m:16s} " + " ".join(cells) + f" {overall}")
    print()

    print("=== LATENCY (seconds per query) ===")
    print(f"{'model':16s} {'n':>4s} {'avg_total':>10s} {'avg_prefill':>12s} {'max':>7s}")
    for m in models:
        if lat[m]:
            L = lat[m]
            print(f"{m:16s} {len(L):>4d} {sum(L)/len(L):>10.1f} "
                  f"{(sum(pref[m])/len(pref[m]) if pref[m] else 0):>12.1f} {max(L):>7.1f}")
    print()

    # ---- subjective answers for Claude to judge ----
    subj = [r for r in recs if r["type"] in ("caption", "spatial")]
    print(f"=== SUBJECTIVE ({len(subj)} caption/spatial answers) — review with the images ===")
    if args.full:
        by_img = defaultdict(list)
        for r in subj:
            by_img[(r["image"], r["type"], r["key"])].append((r["model"], r["response"]))
        for (img, ttype, key), rows in by_img.items():
            print(f"\n[{img}] {ttype}: {key}")
            for model, resp in rows:
                print(f"   {model:14s}: {resp}")
    else:
        print("(run with --full to print them, or ask Claude to judge)")


if __name__ == "__main__":
    main()
