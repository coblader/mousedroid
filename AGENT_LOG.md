# Agent Log

Shared running log for agents working on this repo. **Read this before starting
work; update it when you start, pause, restart, or finish.** See the
"Multi-agent coordination" section of `CLAUDE.md` for the rules.

Conventions for entries:
- Use the real calendar date (`YYYY-MM-DD`). Newest history entry on top.
- Identify yourself by a short handle + your git branch.
- Keep it factual: what you changed, why, and any follow-ups the next agent
  needs to know.

---

## Active work (in progress)

Add a row when you start; remove it (and add to history below) when you finish.

| Agent | Branch | Task | Started | Status |
|---|---|---|---|---|
| _(none)_ | | | | |

---

## Hardware bring-up — current state (2026-07-17, PAUSED mid-encoder-check)

Physical bench bring-up is underway, done incrementally and on blocks per
BUILD.md §9. Where things stand:

**Done / verified:**
- Firmware flashed to the Arduino Uno **from the Jetson via `arduino-cli`**
  (`arduino:avr:uno`). Board runs; serial verified at 115200 (`# mouse-droid
  controller ready` + `TEL` lines). "No boards found" earlier was a
  cable/port issue, now resolved.
- Jetson↔Arduino link = single USB cable (data + powers the Uno). Arduino has
  its own power source running; nothing else wired.
- **LEFT encoder A phase → D2 confirmed working** (counts respond to hand-spin).

**In progress — LEFT encoder B channel:**
- Symptom: `TEL L` pinned at 0 / ±35 mm/s regardless of spin speed, with a
  rare `70`. Root cause = B channel (D4) not seeing a toggling signal → the
  ISR's +1/−1 direction logic cancels every pulse (net ~±1/window). The rare
  `70` means B is *intermittent*, not fully dead → loose/marginal B wire.
- Cause of confusion: the connector pin numbering was offset from the vendor
  diagram (which also mislabels both signal pins as "A phase"). User found the
  real second signal wire is at **"pin 1"** by their counting.
- **Method that works: ignore the printed pin numbers — the 2 signal wires are
  simply the only 2 that toggle 0↔1 when the wheel turns.** Put both toggling
  wires on D2 and D4 (which is A vs B only flips direction sign, fixed later).
- A diagnostic sketch `enc_test/enc_test.ino` was given (prints `count`, live
  `A=`/`B=` levels). NOTE: this sketch is local on the Jetson, NOT in the repo.

**NEXT STEP (definitive test):** with `enc_test` loaded, note `count`, turn the
wheel **exactly one full revolution slowly**, read the delta.
- ~±360 (all one sign) → encoder perfect; the ±35 was just slow spinning.
- only a handful / wanders near 0 → B wire still not solid; reseat pin1→D4.
Then reflash `mouse_droid_controller` and confirm `TEL L` grows with speed.

**After LEFT encoder passes:** wire RIGHT encoder (A→D3, B→D7, share 5V/GND —
needs a breadboard/splice for the shared 5V), verify the same way. THEN the
higher-risk motor+driver+power stage (BTS7960 ×2, battery→15A fuse→switch→12V,
buck-boost 12V/center-positive metered BEFORE connecting Jetson), on blocks,
per BUILD.md §9 steps 5–10.

**Not yet touched:** motor power / BTS7960 wiring, battery/power system,
buck-boost, MPU6050 (IMU_ENABLED can be set false while unwired to skip the
~0.6s startup calibration — currently still `true` in the repo sketch).

---

## Completed / history (newest first)

### 2026-07-17 — agent "opus" (branch: main)
- Documented the 6-pin encoder connector pinout in `firmware/WIRING.md`
  (A/B phase, Vcc, GND, M-, M+ → Arduino pins) and noted the vendor diagram's
  duplicate "A phase" label on pin 2 is a typo (it's the B phase).
- Committed `chassis/` vendor reference photos (incl. the encoder diagram the
  doc links to). Excluded `.DS_Store`.
- Added `.gitignore` for `.DS_Store` and removed the 3 already-tracked ones
  under `cad/`.
- Added this `AGENT_LOG.md` and `CLAUDE.md` (repo conventions + multi-agent
  coordination rules).
- Pushed to `origin/main`.
- **Follow-ups / open items** (from BUILD.md §13): Jetson-side Python serial
  wrapper + tracking loop (not yet written); MPU6050 heading-hold folded into
  the control loop (firmware reads yaw rate but doesn't act on it — needed for
  precise "turn to angle" since the camera is too slow for fast heading
  feedback); wheel-size/shell fit (63 mm vs ~97 mm); camera calibration.
