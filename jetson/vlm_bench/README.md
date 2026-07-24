# VLM Benchmark Workbench

Systematically compares vision-language models on the Jetson: **latency**,
**memory**, and **accuracy** on captioning, counting/presence, and colors/spatial.

## Files
- `config.json` — models to test, prompts, generation limits
- `capture_labeled.py` — stage a scene → capture from camera → label ground truth
- `run_bench.py` — runs every model × image × task, records latency + answers → `results.json`
- `report.py` — auto-scores objective tasks, tabulates; collects subjective answers to judge
- `setup_models.sh` — installs all models (incl. SmolVLM GGUF import) + vision self-test
- `images/` + `manifest.json` — your labeled test set

## Workflow

### 1. Install the models (one time)
```bash
bash ~/vlm_bench/setup_models.sh
```
Check the vision self-test at the end — every model should name a color.

### 2. Build a labeled test set (the part I need from you)
Stage a scene in front of the camera, then:
```bash
python3 ~/vlm_bench/capture_labeled.py
```
It captures a frame and asks for the ground truth (counts, colors, spatial Q/A).
Repeat ~6–10 times with varied scenes (different lighting, clutter, distances).

Add a few downloaded images too:
```bash
python3 ~/vlm_bench/capture_labeled.py --import /path/to/image.jpg
```

**Tips for good test scenes:** include things that are *countable* (e.g. 3 mugs),
have *clear colors*, and *spatial relationships* ("the book left of the laptop").
Mix easy and hard (cluttered / dim) scenes so we see where small models break.

### 3. Run the benchmark
```bash
python3 ~/vlm_bench/run_bench.py
```

### 4. Get the report
```bash
python3 ~/vlm_bench/report.py          # accuracy + latency tables
python3 ~/vlm_bench/report.py --full   # + every caption/spatial answer
```
Then hand the subjective answers (and the images) to Claude to judge captioning
and spatial quality.
