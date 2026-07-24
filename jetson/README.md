# jetson/ — Jetson-side control & perception software

The Jetson "cortex": camera + VLM, and the loop that commands the Arduino
"reflexes" over USB serial. The flagship demo is **follow-a-person**, end to end.

See the master doc for the big picture: [`../BUILD.md`](../BUILD.md) §2
(architecture), §7 (serial protocol), §8 (perception/command pipeline).

> ⚠️ **Run everything with the droid ON BLOCKS (wheels free)** until you trust it.

---

## Layout

| File | What it is |
|---|---|
| `capture_camera.py` | CSI camera capture (`CsiCamera`) + gray-world white balance. Reused everywhere. |
| `ask_camera.py` | Ask the VLM about a live frame (one-shot or chat). Quick camera+VLM sanity check. |
| `serial_link.py` | `MouseDroid`: `drive()` / `stop()` / telemetry over serial, with a heartbeat thread. |
| `detection.py` | `Detection` — shared perception output (found, cx, cy, area, distance). |
| `vlm_locator.py` | `VlmLocator`: person bounding box via Ollama/Qwen-VL → `Detection`. |
| `control.py` | `follow_command()`: `Detection` → `(left, right)` mm/s. |
| `follow_person.py` | **The end-to-end follow demo.** |
| `check_serial.py` | Serial smoke test (drive pattern + telemetry). |
| `setup_ollama_qwen.sh`, `enable_imx219_camera.sh`, `capture_camera.sh` | One-time setup / bash helpers. |
| `vlm_bench/`, `bench_vlms.py` | VLM benchmarking (reference). |

Perception is deliberately behind the `Detection` interface, so a faster detector
or the **OAK-D Lite** (real depth for follow-distance) drops in later as e.g.
`oak_locator.py` without touching the controller or the loop.

## One-time setup

1. **Camera:** `sudo bash enable_imx219_camera.sh` then `sudo reboot`.
   Verify: `python3 capture_camera.py /tmp/x.jpg`
2. **VLM:** `bash setup_ollama_qwen.sh` (installs Ollama + `qwen2.5vl:3b` + swap).
   Verify: `python3 ask_camera.py "what do you see?"`
3. **Python deps:** GStreamer/PyGObject via apt (see `requirements.txt`), then
   `pip install -r requirements.txt`
4. **Arduino flight firmware:**
   `arduino-cli upload --fqbn arduino:avr:uno -p /dev/ttyACM0 ../firmware/mouse_droid_controller`
   (`BATTERY_MONITOR_ENABLED=false` for bench — see `../firmware`).

## Run the follow demo — bring it up in stages (safest first)

```bash
# 1. Perception only, NO motors — prints "person cx=.. area=.." and the L/R it *would* send
python3 follow_person.py --dry-run

# 2. Serial only (on blocks) — gentle drive pattern + telemetry
python3 check_serial.py

# 3. Full loop wired but motion suppressed
python3 follow_person.py --no-move

# 4. Full loop, ON BLOCKS (start with a low clamp)
python3 follow_person.py --max-mms 200
```
Ctrl-C stops (it always sends `stop` on exit). Put it on the floor only once the
on-blocks behavior looks right.

## Notes / caveats

- **The VLM is slow** (seconds per frame on the Orin Nano) → following is laggy.
  This proves the pipeline; it is not real-time. The `serial_link` **heartbeat**
  re-sends the last command so the firmware's 500 ms failsafe doesn't stall the
  motors between frames.
- **Port** defaults to `/dev/ttyACM0`. If it's busy: `fuser -k /dev/ttyACM0`.
- **Tuning** lives in `control.py` (`FollowConfig`): `target_area` = follow
  distance, `turn_gain_mms` / `fwd_gain_mms` = responsiveness, deadbands, etc.
