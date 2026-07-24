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
| opus | main | Drivetrain bring-up — CLOSED-LOOP WORKING ✅ | 2026-07-20 | Flight firmware runs; both sides hold commanded velocity (PID on single-channel encoders). Remaining: PID tune, wheel-dia calibration, real power stage (+A0 divider, re-enable batt monitor), docs, Jetson software. |

---

## Jetson software — follow-person pipeline (2026-07-23, IN PROGRESS)

New **`jetson/`** dir: consolidated the existing camera/VLM scripts from ~ and
built the first end-to-end demo (camera→VLM→Arduino→feedback, "follow a person").
Existing stack reused: `capture_camera.py` (CsiCamera, GStreamer/gi, gray-world WB),
`ask_camera.py` (Ollama VLM query), Ollama serving **qwen2.5vl:3b**.
New: `serial_link.py` (MouseDroid: drive/stop/telemetry + heartbeat thread so the
firmware 500ms failsafe doesn't stall between slow VLM frames), `detection.py`
(swappable Detection type — VLM now, OAK-D Lite later), `vlm_locator.py` (person
bbox→Detection), `control.py` (follow_command P-controller), `follow_person.py`
(the loop; --dry-run/--no-move/--once), `check_serial.py`. All compile; pushed.

Bench validation (flight fw on Uno, on blocks, axles only — wheels off):
- ✅ `check_serial.py` forward L120 R120 → TEL tracked ~120 both sides. serial_link
  (connect, drive, heartbeat, TEL parse) all work end-to-end.
- ⚠️→✅ DIAGNOSED: the `spin` (L-120 R120, hard reverse) **blew the 5A fuse
  again**. Forward worked, then the reverse spike killed the rail; a follow-up
  isolation test then read ALL zeros (incl. forward) = motor rail dead, Arduino
  fine (TEL still streams). Cause: **plugging** — reversing a still-spinning motor
  drives the H-bridge against back-EMF → current spike >5A on the bench adapter.
  FIX: replace the 5A fuse; on the 5A bench adapter AVOID hard reversals (the
  LiPo+15A fuse will handle them later). Tweaked `check_serial.py`: default test
  is now forward + gentle differential turn (no hard reverse); `--spin` is opt-in
  and warns it's LiPo-only. The follow demo already defaults allow_reverse=False.
- Minor: telemetry spikes at command transitions (small-dt artifact); cosmetic.
- (The "still 0 after fresh fuse" was just the adapter being UNPLUGGED — replugged
  and forward tracks ~120 again.)
- ⚠️ REAL MECHANISM: the forward→STOP transition trips the 5A adapter. On stop
  while spinning, the PID doesn't coast — it sees err=0-120 and **actively brakes
  by driving reverse** (telemetry shows huge negative spikes at stop, e.g.
  L-9564). Braking a spinning motor = plugging spike → trips the 5A bench adapter,
  so the NEXT motion phase reads 0 (happened both runs, reverse or gentle-fwd).
  It's the 5A bench-supply current limit, NOT a fault; LiPo+15A will handle it.
  Options: test at lower speed (60-80) to shrink the spike; add a firmware
  "coast on stop/decel" (output 0 instead of PID-braking) to cut spikes; or just
  move to the LiPo. The follow loop's constant start/stop will trip the 5A adapter
  as-is → prefer LiPo for a smooth end-to-end run, or coast-stop + low speed.
  Note: TEL V is the floating-A0 value (monitor off), NOT the motor-rail voltage.

NEXT (Jetson): decide coast-stop tweak and/or move to LiPo; then `check_serial.py`
→ `follow_person.py --dry-run` (camera+VLM, needs Ollama up) → `--no-move` → full
loop on blocks. OAK-D Lite remains the eventual camera (real depth) — drops in
behind the Detection interface.

---

## ▶ RESUME HERE (paused 2026-07-22, end of day)

Where we are: **all 4 motors drive forward (open-loop) ✅.** Encoder bring-up is
the remaining blocker before closed-loop. Bench setup: on blocks, 12V/5A wall
adapter (+5A fuse) on both BTS7960 B+/B-, common ground, Uno on Jetson USB
(/dev/ttyACM0). Board flashed with **`firmware/drivetrain_test`** (open-loop
drive + encoder count + live A/B levels).

**ROOT CAUSE FOUND (2026-07-22): hardware — 3 of the 4 motor encoder A channels
are DEAD** (meter-tested directly at the motor connectors). Only 1 of 4 motors
has a working A channel; both LEFT motors' A channels are dead → that's why the
left A was stuck all along (never a wiring mistake). The right side counted only
because the motor being read is the one good A. Consequence: a motor swap alone
can't give quadrature on both sides (only 1 good A exists). B channels appear to
work — CONFIRM B on all 4 next. Suspect the A damage came from the earlier
shorts/12V events; protect any replacements. DECISION MADE: **(A) single-channel firmware.** mouse_droid_controller.ino now
reads ONE channel per side on the interrupt pins (D2 left, D3 right), counts
every edge, and takes DIRECTION FROM THE COMMANDED PWM SIGN (leftDir/rightDir).
D4/D7 unused. COUNTS_PER_REV stays 360. Compiles clean. Right's earlier
negative-sign issue is moot (direction follows command). Requirement: motors
must physically spin forward on + command (already verified). Wiring: move left
working signal D4→D2, keep right working signal on D3, free D4/D7, one encoder
per side (VCC→5V, GND→GND). Golden (A+B) motor kept as spare/reference.
Docs updated 2026-07-22: BUILD.md §6/§7/§9/§13 + firmware/WIRING.md now describe
single-channel encoders (D2/D3 signal, D4/D7 unused, direction-from-command),
the IMU/battery-monitor flags, mirror-mount M+/M-, and the bench-adapter status.
- ✅ **SINGLE-CHANNEL VERIFIED (2026-07-22).** Rewired: left working signal→D2,
  right working signal→D3, D4/D7 empty, one encoder/side. `drivetrain_test`
  (single-channel) under power: `L80`→EL 35..861, `R80`→ER 32..794, both POSITIVE
  & monotonic, La/Ra toggle. Left encoder finally reads. Open-loop drivetrain
  (motors + encoders) fully working. mouse_droid_controller.ino + drivetrain_test
  both single-channel now.
  NEXT: closed-loop. Before flashing the flight fw, handle the A0 LiPo cutoff —
  on the bench adapter the A0 divider likely isn't wired, so readBatteryV may
  latch FAULT_LOWV and disable motors. Either wire the A0 divider, or bench-
  bypass the cutoff. Then `L100 R0`, watch TEL measured speed grow, PID tune.
- ✅ **CLOSED-LOOP VERIFIED (2026-07-22).** Added `BATTERY_MONITOR_ENABLED=false`
  (bench; A0 divider not wired — else the floating A0 reads ~5-7V and would latch
  FAULT_LOWV; MUST set true + wire divider R1 10k/R2 3.3k with the LiPo). Flashed
  mouse_droid_controller.ino: `L100 R0` → TEL L tracks ~100; `L100 R100` → both
  TEL L & R track ~100 mm/s. PID closes the loop on single-channel feedback.
  Measured quantizes to 70/105 at low speed (coarse counts/telemetry-window) but
  averages on target. Note TEL V is bogus (floating A0, monitor off) — ignore.

  REMAINING before "it drives on the floor":
  1. PID tune / check at higher speeds (smooth out low-speed quantization).
  2. Calibrate WHEEL_DIAMETER_MM (measure real wheel; placeholder 80) + confirm
     COUNTS_PER_REV so mm/s is real. Straight-line: L & R should match.
  3. Real power stage: LiPo→15A fuse→switch→12V bus→drivers + buck-boost→Jetson;
     wire A0 divider; set BATTERY_MONITOR_ENABLED=true; + LiPo balance-lead buzzer
     (BOTH protections — auto-stop cutoff AND per-cell alarm). Replaces bench adapter.
  4. ✅ DONE — BUILD.md §6/§7/§9/§13 + firmware/WIRING.md updated to single-channel.
  5. Jetson-side Python: serial wrapper (drive/stop + TEL parse), a `sounds` module
     (MSE-6 audio via a Jetson-driven speaker), then the vision loop.

Parts to order (2026-07-22; added to BUILD.md §3 BOM): A0 divider resistors
10kΩ + 3.3kΩ (1%, 1/4W); LiPo low-voltage buzzer (JST-XH balance lead); speaker
audio = MAX98357A I2S amp + 4Ω ~3W speaker (or a USB/BT speaker to prototype);
**ReSpeaker USB Mic Array v2.0** (voice input). MPU6050 (GY-521) needs NO extra
parts — onboard pull-ups + regulator, 4 jumpers.
Audio + voice are Jetson-controlled. Planned Jetson pipeline (BUILD.md §8):
mic→wake-word→Whisper STT→(text+frame)→VLM planner→goal→fast tracker→serial→Arduino;
VLM kept OUT of the real-time loop (layered by timescale). Docs: BUILD.md §1/§2/§3/§5/§8.

Proven facts (don't re-litigate):
- All 4 Arduino encoder pins (D2/D4/D3/D7) are HEALTHY; Uno undamaged; count
  logic good. (A good encoder counts fine on any of them.)
- RIGHT encoder: **hardware good** — counts cleanly, both channels toggle. BUT
  currently reads **NEGATIVE for forward** → needs O-A↔O-B (D3↔D7) swap so
  forward=positive.
- LEFT encoder: only its **B** channel produces a signal; its **A** signal is
  landing on the wrong connector pin (D2 reads constant 1). Two different left
  encoders both showed this → it's a wire/pin-ID issue, NOT the encoder or D2.
- Motor directions are correct — **leave M+/M- alone** on both sides.

Tomorrow, in order:
1. **Find the LEFT encoder's real A output.** Keep working B on D4. Probe the
   thin connector wires with a meter while spinning (signal = flickers 0↔5V;
   VCC = steady 5V; GND = 0) OR move a candidate to D2 and run
   `python3 tools/motor_test.py -l 80 -r 0 -s 3` — `La` should toggle & EL climb.
2. **Swap RIGHT O-A↔O-B (D3↔D7)**; re-run `-r 80` and confirm ER now climbs
   POSITIVE for forward.
3. Confirm BOTH: forward → EL and ER both climb POSITIVE (~600/3s at PWM 80).
4. Then switch off the test sketches: flash `firmware/mouse_droid_controller`
   (IMU already disabled), verify TEL shows positive speed both sides, PID tune.
5. Later (separate): real LiPo power stage; Jetson-side Python serial wrapper.

Test tools: `tools/motor_test.py` (drive), `tools/encoder_test.py` (hand-turn
check). Watch for stray procs on the port → `fuser -k /dev/ttyACM0`.

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

- Reusable tooling: added **`tools/motor_test.py`** (CLI over serial: -l/-r PWM,
  -s seconds, --check, -p port; health-gates the Uno, won't spin if unresponsive)
  and **`tools/README.md`**. Replaces the ad-hoc inline pyserial snippets.
  Usage: `python3 tools/motor_test.py -l 120 -r 120 -s 5`.
- "Wheels not spinning" scare after the shorts = **blown 5A inline fuse** (the
  earlier short popped it, so no 12V to the drivers though the Uno still sent
  PWM). Replaced the fuse → all four motors run forward again. Fuse did its job.

- Encoder verification tooling added: **`firmware/encoder_test/encoder_test.ino`**
  (reads counts + live A/B levels, `z` to zero) with **`tools/encoder_test.py`**
  (one-revolution hand-turn check), and **`firmware/drivetrain_test/drivetrain_test.ino`**
  (open-loop drive + encoder count in one sketch — spin under power and watch the
  count, driven via `tools/motor_test.py`). Hand-backdriving the 1:30 gearbox is
  unreliable; the powered spin test is the definitive encoder check.
- Encoder findings (via drivetrain_test, powered spin):
  - ✅ **RIGHT encoder GOOD** — `R80` → ER climbed 0→619 in 3s, monotonic +.
    Forward = POSITIVE count (correct sign for PID). No D3/D7 swap needed after
    the earlier swap. (Right encoder needed a VCC/GND connection fix first.)
  - ❌ **LEFT encoder FAULT — isolated to A channel / D2.** Live A/B levels: under
    `L80` (wheel spinning) `Lb`(D4) toggles = B good; `La`(D2) STUCK at 1 = A not
    reaching D2 → ISR never fires → EL frozen at 0.
  - **BOTH encoders per side had been wired in parallel** onto D2/D4 (left) and
    D3/D7 (right) — electrically wrong (open-collector outputs, hence INPUT_PULLUP;
    paralleling = wired-AND of two ~synced-but-not-identical signals → garbled).
    Right happened to still count (luck), left collapsed to stuck. Disconnected
    the extra encoder on each side (kept one per side; unused signal wires left
    floating, tucked so they can't short).
  - After going single-encoder: **RIGHT re-verified CLEAN** — `R80` → ER 33→813,
    Ra & Rb both toggle. Trustworthy for PID.
  - **LEFT still stuck** on a single encoder (La=1, Lb toggles, EL=0) → so it's
    NOT contention; the A signal isn't reaching D2. NEXT: swap the two left
    wires D2<->D4 to isolate: if La then toggles, D2 pin is good and this
    encoder's A lead/output is bad (try the other left encoder); if La still
    stuck, suspect the D2 pin itself.
  - **Tried a SECOND left encoder (front-left instead of rear-left): SAME fault**
    — La(D2) stuck at 1, Lb(D4) toggles, EL=0. Two different encoders failing
    identically on D2 ⇒ **problem is the D2 side, not the encoder** (D4 + count
    logic proven good). Decisive next test: swap the two left wires D2<->D4 (put
    the known-toggling wire on D2). La toggles ⇒ D2 pin OK, the wire landing on
    D2 is wrong/not-a-signal; La still stuck ⇒ D2 pin damaged (Uno has only D2/D3
    as ext-interrupts → would need a pin-change-interrupt firmware workaround).
    NOTE: encoders in use are the two REAR motors originally; FL was the 2nd try.
  - **RESULT of D2<->D4 swap: the stuck/good behavior FOLLOWED THE WIRES, not the
    pins.** After swap, La(D2) toggles ✅ and Lb(D4) went stuck. So **both D2 and
    D4 pins are healthy** (no board damage, no firmware workaround needed) and the
    count logic is fine. The fault is **ONE dead signal wire** that reads constant
    1 (open / not a real signal) regardless of pin. Same on two encoders ⇒ it's a
    **bad jumper or a wire tapping the wrong connector pin**, NOT the encoder.
    FIX: replace that one jumper and/or re-land it on the encoder's actual 2nd
    signal output (the two signal pins are the only two that toggle when the wheel
    spins). VCC/GND are fine (encoder powered). Then re-test `L80` → expect EL to
    climb. LEFT is the last thing between us and closed-loop.
  - **CROSS-SWAP TEST (decisive): right encoder→D2/D4, left encoder→D3/D7.**
    Right encoder on D2/D4 (drove R): EL 34→815, La+Lb both toggle = D2/D4 pins
    100% good. Left encoder on D3/D7 (drove L): ER frozen 0, Ra STUCK at 1, Rb
    toggles = SAME A-channel failure on the known-good right pins. ⇒ **Fault
    follows the LEFT ENCODER, not the board. All 4 pins good, no fw workaround.**
    Left encoder only ever produces its B signal; its A signal is missing. Two
    different left encoders both fail on A ⇒ A wire is systematically landing on
    the WRONG connector pin (reads constant 1 = power/unused), not the A output.
    FIX: find the left encoder's real A output — mirror the RIGHT connector's
    A-wire position (same part/pinout), or probe each left connector wire while
    spinning until A toggles. Then UN-CROSS (left enc→D2/D4, right enc→D3/D7 to
    match each side's motor) and verify both.
  - Un-crossed (rear-left enc→D2/D4, rear-right enc→D3/D7), re-tested both:
    RIGHT counts clean (both channels toggle) but **NEGATIVE for forward** (R80 →
    ER -35..-817) — A/B order got flipped in rewiring; **swap right O-A↔O-B
    (D3↔D7)** so forward=positive (BUILD.md §9 step 6). LEFT unchanged: La stuck
    1, Lb toggles, EL=0 → left A signal still on wrong connector pin. LEFT A wire
    is THE remaining blocker; fix by probe/mirror-the-right, then swap right A/B,
    then both sides verified → closed-loop.

- IMU: set **`IMU_ENABLED = false`** in mouse_droid_controller.ino (was true).
  MPU6050 is still unwired AND not yet folded into the control loop, so it's off
  until the drivetrain is solid. When we do add it: wire VCC→5V, GND→GND, SDA→A4,
  SCL→A5, mount flat/centered (Z vertical), still at boot; then implement
  heading-hold (BUILD.md §13) — treat wiring + control-loop code as one task.

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
