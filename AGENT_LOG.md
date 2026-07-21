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
| opus | main | Motor + BTS7960 bring-up (from nothing) | 2026-07-20 | In progress — RIGHT-front motor wired to BTS7960 #2; open-loop direction test next |

---

## Motor + BTS7960 bring-up — current state (2026-07-20, IN PROGRESS)

Starting the motor/driver stage from nothing (nothing on this side was wired
before today). LEFT side first, then RIGHT.

**Key decision — open-loop first, bench supply:**
- The flight firmware is closed-loop PID on the encoders. With LEFT encoder-B
  still flaky (see section below), commanding a speed would make the PID see
  measured≈0, wind the integral up, and slam the motors to full PWM. So motor
  bring-up is done **open-loop** to decouple driver/motor wiring from encoders.
- New diagnostic sketch `firmware/motor_test/motor_test.ino` (committed to repo
  this time, unlike `enc_test`): raw PWM via serial `L<pwm>`/`R<pwm>`/`stop`,
  drivers enabled on D8, same RPWM/LPWM direction convention as the flight
  firmware so any lead-swap fix carries over.
- First spin uses a **current-limited bench supply** (11–12 V, ~1.5 A for one
  free motor, ~3 A for two) on the BTS7960 B+/B- rail — NOT the LiPo yet. A
  miswire trips the limit instead of dumping 40 A.

**Wiring plan (LEFT = BTS7960 #1):** D5→RPWM, D6→LPWM, D8→R_EN+L_EN, Arduino
5V→VCC, Arduino GND→driver GND. Supply(+)→B+, supply(−)→B− **and** →Arduino GND
(common ground is mandatory). Motors L-Front/L-Rear parallel on M+/M−; connect
just one motor for the first direction read, then add the second.

**Procedure:** flash `motor_test` → `L120` → left wheel should go forward; wrong
way = swap that motor's M+/M− (or D5↔D6); no spin = D8 not HIGH or logic VCC/GND
missing; supply hits limit = short/miswire. Repeat for RIGHT (D9/D10, shares D8).

**Progress:**
- RIGHT-front motor wired to BTS7960 #2 (single motor, for a clean direction read).
- `motor_test` compiled + uploaded to the Uno from the Jetson via arduino-cli
  (`arduino:avr:uno`, /dev/ttyACM0). Boot banner confirmed live over pyserial:
  `# motor_test ready (OPEN-LOOP, no PID)...`. (Serial driven from the Jetson
  with pyserial 3.5; watch for stray processes holding /dev/ttyACM0 — a stopped
  `stty` job blocked reads until `fuser -k`'d.)
- Power for the test: **12 V / 5 A wall adapter** (not a bench supply, not the
  LiPo) to the driver B+/B-, with a **5 A inline fuse on the + lead**. Adapter −
  tied to Arduino GND (common ground). Polarity metered before power-up.
- ✅ First motor verified spinning FORWARD under RPWM (PWM 120) — driver logic +
  power + motor path all good.
- **CORRECTION:** that motor is the **FRONT-LEFT** wheel, not front-right (mislabel).
  It was tested on the driver wired to D9/D10 (the RIGHT pins) with `R120`. Fix:
  reassign that board to LEFT by moving its two PWM jumpers D9→D5, LPWM D10→D6
  (D8/VCC/GND/B+/B-/M+/M- unchanged), then re-verify with `L120`. That board is
  now BTS7960 #1 (LEFT).

- ✅ After the D9→D5 / D10→D6 move, `L120` → **FRONT-LEFT spins FORWARD.** LEFT
  driver (BTS7960 #1) correctly assigned and verified.
- ✅ REAR-LEFT added in parallel on BTS7960 #1 M+/M-; `L120` → **both LEFT wheels
  spin FORWARD together.** LEFT SIDE COMPLETE (both motors, correct direction).

RIGHT driver (BTS7960 #2) wired: RPWM→D9, LPWM→D10, R_EN+L_EN→D8, VCC→5V, GND→GND,
12V(+5A fuse)→B+/B-, front-right motor on M+/M-.

⚠️ **FAULT — right-side wiring took down the Uno.** On `R120`: no command echo.
Follow-up serial checks: DTR ioctl `BrokenPipeError` (USB re-enumerated) then Uno
stopped printing its banner entirely (port opens, no data). Symptom = Arduino
browning out / resetting → strongly suggests a **5V↔GND short (or 12V leaking
into logic) in the new right-side splices**. LEFT side was fully working before
this. Debug in progress:
  1. Disconnect 12V adapter.
  2. Meter 5V↔GND for a dead short (top suspect: IBT-2 #2 VCC/GND swap or a
     bridging strand; also check encoder VCC/GND not reversed, and no B+ strand
     touching a logic pin).
  3. Fix, then USB unplug/replug to hard-reset the Uno; confirm banner returns
     before re-testing.

**FAULT ISOLATED:** with the right-side 5V/GND pulled, the Uno recovered (banner
back, echo works) and `L120` → **both LEFT wheels spin FORWARD.** So the Arduino
is undamaged and the LEFT side is still good — the short is definitively in the
**right-side wiring** (top suspect: IBT-2 #2 VCC/GND swapped or bridged, or the
right encoder's VCC/GND reversed).

**NEXT STEP — re-add RIGHT side incrementally, 12V OFF until verified:**
  1. Inspect IBT-2 #2 VCC/GND (not swapped, no bridging strand); if encoder wired,
     check its VCC→5V / GND→GND not reversed.
  2. Reconnect right GND→GND, then VCC→5V. Meter 5V↔GND (no dead short), replug
     USB, confirm banner still returns.
  3. Add D9/D10/D8 signals, then motor M+/M-.
  4. Only then reconnect 12V (polarity metered), test `R120` → forward.
Then add rear-right, then `L120 R120` all-four check.

- Right-side short cleared (Uno stayed healthy with right side connected). `R120`
  → FRONT-RIGHT spun **BACKWARD**; swapped its M+/M- → forward. (NOTE: right side
  needs M+/M- reversed vs left — correct, because motors are mirror-mounted; same
  will likely apply to right encoder A/B (D3/D7) in closed-loop.)
- ⚠️ **FAULT AGAIN after wiring BACK-RIGHT motor** — Uno dead (no banner/echo)
  the moment back-right M+/M- was added. Same brownout signature → short in the
  back-right additions (stray strand bridging a terminal, a motor lead touching
  driver #2's small logic header, disturbed 5V/GND splice, or an accidentally
  plugged reversed back-right encoder). Back-right should be ONLY M+/M- in
  parallel — encoder stays unplugged. Debug: 12V off, meter 5V↔GND, fix, replug
  USB, confirm banner, then re-test `R120` (both right wheels forward together).
- ✅ Back-right short cleared; `R120` → **both RIGHT wheels spin FORWARD together.**
  RIGHT SIDE COMPLETE. All four motors now wired and verified forward.

- ✅✅ **`L120 R120` → ALL FOUR wheels spin FORWARD together.** OPEN-LOOP
  DRIVETRAIN FULLY VERIFIED: both BTS7960 drivers, all 4 motors, correct
  directions, common ground, 12V/5A adapter path (+5A fuse). Highest-risk stage
  done.

Wiring summary that works (open-loop, on blocks):
- LEFT driver = BTS7960 #1: RPWM→D5, LPWM→D6, R_EN+L_EN→D8, VCC→5V, GND→GND;
  both left motors parallel on M+/M- (NOT swapped).
- RIGHT driver = BTS7960 #2: RPWM→D9, LPWM→D10, R_EN+L_EN→D8, VCC→5V, GND→GND;
  both right motors parallel on M+/M- **reversed vs left** (mirror-mount).
- Shared: 5V, GND, D8, and 12V rail (B+/B- via 5A fuse), one common ground.
- Power: 12V/5A wall adapter (bench-test only — LiPo power stage still not built).

**NEXT STEP (new session ok):**
  1. (optional) pivot check `L-120 R120`.
  2. LEFT encoder-B fix (see paused section below) + wire/verify encoders.
  3. Switch motor_test → mouse_droid_controller.ino (closed-loop PID). Verify TEL
     reads POSITIVE speed on BOTH sides when driving forward; expect to swap the
     RIGHT encoder A/B (D3/D7) so its sign matches (mirror-mount).
  4. Later: build the real power stage (LiPo→15A fuse→switch→12V bus, buck-boost
     to Jetson) — replaces the bench adapter. Then floor test + PID tune.

**After both sides spin correctly open-loop:** resume the LEFT encoder-B fix
(below), then switch back to `mouse_droid_controller.ino` for the closed-loop
direction/sign checks (BUILD.md §9 steps 5–8). Power system (LiPo→15A fuse→
switch→12V bus, buck-boost) is still NOT wired — that comes after open-loop
driver verification.

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
