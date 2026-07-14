# MSE-6 "Mouse Droid" — Build & Reproduction Guide

A Star Wars MSE-6 mouse droid: a wooden (CNC plywood) shell over an off-the-shelf
4WD encoder chassis, driven by an Arduino for real-time motion and an NVIDIA
Jetson Orin Nano for vision/tracking. This document is intended to be enough,
on its own, to reproduce the droid.

---

## Table of contents
1. [What it is](#1-what-it-is)
2. [System architecture](#2-system-architecture)
3. [Bill of materials](#3-bill-of-materials)
4. [The body (CNC plywood shell)](#4-the-body-cnc-plywood-shell)
5. [Power system](#5-power-system)
6. [Wiring](#6-wiring)
7. [Firmware (Arduino)](#7-firmware-arduino)
8. [Jetson software](#8-jetson-software)
9. [Assembly & first bring-up](#9-assembly--first-bring-up)
10. [PID tuning](#10-pid-tuning)
11. [Design decisions & rationale](#11-design-decisions--rationale)
12. [Troubleshooting](#12-troubleshooting)
13. [Open items / future work](#13-open-items--future-work)

---

## 1. What it is
The on-screen MSE-6 is a small, low, wedge-shaped droid that darts around
Imperial corridors. This build recreates the look with a plywood shell and gives
it autonomy: it can see and track/follow a target using a camera on the Jetson,
while an Arduino handles smooth closed-loop wheel motion.

**Control philosophy — two brains:**
- **Arduino = reflexes** (hard real-time): encoder reading, PID velocity control, motor driver PWM.
- **Jetson = cortex** (perception/decisions): camera tracking, turns high-level goals into simple speed commands.

They talk over one USB cable. This split keeps timing-critical work off Linux
(which isn't real-time) and keeps the high-level code simple.

---

## 2. System architecture

```
                 ┌───────────────────────────┐
   Arducam ─CSI─►│  Jetson Orin Nano 8GB      │
   IMX219        │  - camera / tracking       │
                 │  - decides where to go     │
                 └──────────┬────────────────┘
                            │ USB serial (115200)
                            │  "L<mm/s> R<mm/s>" / "stop"
                            ▼
                 ┌───────────────────────────┐
                 │  Arduino Uno               │
                 │  - reads encoders          │
                 │  - PID velocity loop       │
                 │  - PWM to drivers          │
                 └───┬───────────────┬────────┘
                     ▼               ▼
              BTS7960 #1        BTS7960 #2
              (left pair)       (right pair)
                     ▼               ▼
              2× left motors    2× right motors   ← skid-steer
```

**Drive style:** skid-steer (differential). The two left wheels always move
together and the two right wheels together, so 4 motors reduce to **2 control
channels**. It turns by driving the sides at different speeds and can pivot in
place — matching the droid's darting behavior. (The chassis ships with mecanum
wheels; we simply drive them as skid-steer. The wheels are hidden under the shell.)

---

## 3. Bill of materials

### Compute & sensing (owned)
| Item | Purpose | Notes |
|---|---|---|
| NVIDIA Jetson Orin Nano 8GB Dev Kit | Vision / high-level | Powered via **DC barrel jack only** (7–20 V, ~45 W). **USB-C does NOT power it.** |
| Arducam 8MP IMX219 autofocus, 160° CSI | Camera | Native to Orin Nano MIPI-CSI (22-pin). No depth. |

### Chassis & drivetrain
| Item | ASIN | Purpose | Key specs |
|---|---|---|---|
| "Premium 4WD Mecanum" metal chassis | B0CBRMTCH2 | Rolling base + motors | 37 mm DC motors, **6-wire Hall quadrature encoders**, 12 V, stall 2.8 A, rated 360 mA, gearbox 1:30, encoder 6 pulses/rev |
| BTS7960 driver, 2-pack | B099N8XS5P (or B0BGR92TCD) | Motor drivers | 43 A, 6–27 V, one module per side |
| Arduino Uno (or ELEGOO) | B01EWOE0UU / B008GRTSV6 | Motor controller | 2 hardware interrupts (D2/D3) |
| MPU6050 IMU | B0CRVR1P66 | Heading reference | I²C; optional (encoders cover most of it) |

### Power
| Item | ASIN | Purpose | Key specs |
|---|---|---|---|
| EMEPOVGY 3S LiPo | B0FSXSJK56 | Main battery | 11.1 V, 5200 mAh, 80C, XT60 |
| Havcybin iMAX B6 (w/ PSU) | B0D9RWC46T | Balance charger | 80 W, 1–6S, incl. 12 V/5 A supply |
| HOMELYLIFE buck-boost | B07WFMKMV9 | Jetson power | 8–40 V → **fixed 12 V**, 6 A / 72 W |
| Fancasee 5.5×2.5 mm barrel pigtail | B0FH4FMFSH | Buck-boost → Jetson jack | 16 AWG, **center-positive** |
| Yeebline XT60 pigtails | B0FVXCN126 | Battery connections | 12 AWG, M+F |
| Nilight inline fuse holder + fuses | B0B24YYYCF | Main-line protection | use a **15 A** fuse |
| DaierTek rocker switch | B07S1MV462 | Main power switch | 20 A @ 12 V, SPST |
| ELEGOO Dupont jumpers | B01EV70C78 | Signal wiring | M-F/M-M/F-F |

### Body
| Item | Purpose |
|---|---|
| 1/4" plywood (approx one 48×32" sheet) | CNC shell panels |
| 3/8" square dowel | Side belt rails |
| Wood glue, fasteners, dark-gray paint | Assembly & finish |

---

## 4. The body (CNC plywood shell)

Screen-style MSE-6, 1/4" plywood, rib-and-skin, cut on a Shaper Origin.

**Source files (in `~/mouse-droid/cad/`):**
- `mouse-droid.blend` — full assembly + flat cut layout. Reference OBJ in collection `MSE6_Reference`.
- `mouse-droid-panels.svg` — 19 CNC pieces on a 48 × 31.9" sheet. Shaper color coding: white fill / black stroke = exterior cut, black fill = interior cut.
- `Mse-6/` — geometrically accurate reference OBJ (scale ×2 = inches).
- `assembly-guide.html`, `renders/`, `README.md` — illustrated step-by-step assembly guide, step renders, and CAD notes.

**Overall dimensions (inches, ground = z0):** 19.1 L (rail tips) × 9.0 W × 11.15 H.
- Skirt 1.5–3.3; belt zone 3.3–4.425 = a 1/4" plywood band (face recessed 0.2") + two 3/8" square dowel rails (0.175" proud, 3/8" gap → double lip).
- Side rails overshoot the ends by 0.68" (bumper stubs): 4 @ 19-1/8", ends 4 @ 8-1/4".
- Shell base at 4.425, flat top at 10.9; facet angles ≈ 47° front / 71° rear.
- 4 internal ribs at x = ±7, ±2.5 with recessed waists (top at 3.87).
- Wheels Ø2.5 × 1" at x −4.8 / +5.0, y ±3.4, exposed through 2.9"-wide skirt openings.

**Construction notes:**
- The shell (4 facets + top + tray) is a **removable lid** that rests on the rib edges + top-rail ledge. Because the wheels hook through the skirt openings, the body cannot lift straight off the base plate — so **top access is the service path** for electronics.
- Mirror-paired panels (skirt/shell sides): cut 2 identical, flip one.
- Optional greebles (antennas, top waffle detail) can be added as Shaper pocket cuts.

> ⚠️ **Fit note:** the shell was designed for Ø2.5" (≈63 mm) wheels. The B0CBRMTCH2
> chassis ships with larger mecanum wheels (~80–96 mm). Reproduce with **63 mm
> round wheels** on the chassis, or widen the skirt openings, or scale the shell up.

---

## 5. Power system

**Topology (single 3S pack):**
```
3S LiPo → 15A fuse → main switch → +12V bus ─┬─► BTS7960 ×2 → motors
                                             └─► buck-boost → 12V → Jetson jack
```

**Design rationale:**
- **3S (11.1 V nominal)** matches the 12 V motors directly — no converter needed on the motor rail.
- The **Jetson gets its own buck-boost** (fixed 12 V out) rather than the raw battery. Motors cause large current spikes; a regulated, isolated 12 V rail keeps the Jetson from browning out. Buck-*boost* (not just buck) holds 12 V even as the pack sags under load.
- The Jetson accepts 7–20 V, so 12 V is comfortably mid-range; ~45 W max draw vs the converter's 72 W gives margin.
- **Arduino is powered over USB from the Jetson** — no separate regulator.

**Safety:**
- **15 A fuse** on the battery positive, closest to the pack.
- **Never over-discharge the LiPo.** Firmware cuts off at 3.30 V/cell (9.9 V pack). Charge and store in a LiPo bag; balance-charge via the JST-XH lead.
- Barrel plug is **center-positive** — verify with a meter before connecting the Jetson.

---

## 6. Wiring

Full diagram + connection table: **`firmware/WIRING.md`**. Summary of the Arduino pin map:

| Uno pin | Connection |
|---|---|
| D2 / D4 | LEFT encoder A (interrupt) / B |
| D3 / D7 | RIGHT encoder A (interrupt) / B |
| D5 / D6 | BTS7960 #1 (left) RPWM / LPWM |
| D9 / D10 | BTS7960 #2 (right) RPWM / LPWM |
| D8 | all four BTS7960 enables (R_EN + L_EN) — HIGH = run, LOW = e-stop |
| A0 | battery voltage divider junction (R1 10k / R2 3.3k) |
| A4 / A5 | MPU6050 SDA / SCL |
| 5V | encoder Hall+ ×2, BTS VCC ×2, MPU VCC |
| GND | **common ground bus — must tie to battery negative** |
| USB | Jetson (data + powers the Uno) |

**Critical:** one common ground between logic and motor power; keep fat 12 V wires
away from thin signal wires; only one encoder per side is read (the other motor
just gets M+/M− power).

---

## 7. Firmware (Arduino)

Sketch: **`firmware/mouse_droid_controller/mouse_droid_controller.ino`** (no external libraries beyond built-in `Wire`).

**What it does:** interrupt-driven encoder counting → 50 Hz per-side PID velocity
loop → BTS7960 PWM. Command-timeout failsafe and latching LiPo cutoff.

**Configure before first run:**
| Constant | Meaning | Default |
|---|---|---|
| `WHEEL_DIAMETER_MM` | actual wheel diameter | 80 (measure yours) |
| `COUNTS_PER_REV` | 6 PPR × 2 edges × 30 gear | 360 (verify by hand-rotating one turn) |
| `VOLTAGE_DIVIDER_RATIO` | (R1+R2)/R2 | 4.03 (for 10k/3.3k) |
| `Kp, Ki, Kd` | PID gains | 0.35 / 1.20 / 0.004 |

**Serial protocol (115200 baud):**
- In: `L<mm/s> R<mm/s>` (e.g. `L200 R200`, `L-150 R150`), or `stop`.
- Out (every 200 ms): `TEL L<mm/s> R<mm/s> V<volts> Y<deg/s>` (+`FAULT_LOWV` if latched).

---

## 8. Jetson software

**OS/setup:** flash JetPack, connect the Arducam to a CSI port, confirm capture
(`nvgstcapture` or GStreamer `nvarguscamerasrc`). Open the Arduino as
`/dev/ttyACM0` at 115200.

**Perception → motion loop (planned):**
1. Grab frames from the Arducam.
2. Run a detector/tracker (e.g. a person/object detector on the Orin's GPU) to get the target's position in frame.
3. Convert target error → drive command:
   - target left/right of center → asymmetric wheel speeds (steer toward it),
   - target near/far (from bounding-box size) → forward/back speed.
4. Send `L<mm/s> R<mm/s>` over serial; read `TEL` for feedback; send `stop` on target loss.

A thin Python serial wrapper (`drive(left, right)` / `stop()` + telemetry parsing)
is the recommended first module. *(Not yet written.)*

---

## 9. Assembly & first bring-up

**Do electronics bring-up with the droid up on blocks (wheels free).**
1. Assemble the chassis; wire power per §5/§6 but **leave motor leads accessible**.
2. Meter the buck-boost output: **12 V, center-positive**, then connect the Jetson.
3. Flash the Arduino sketch; set the config constants (§7).
4. Open a serial monitor at 115200. You should see `# mouse-droid controller ready`.
5. Send `L100 R0`: left wheels spin **forward**. If backward → swap that side's motor leads.
6. Watch `TEL`: forward motion → **positive** measured speed. If negative → swap that encoder's A/B.
7. Repeat for the right side.
8. Verify `stop` halts; verify the failsafe (stop sending → it stops in <0.5 s).
9. Check the voltage reading in `TEL` matches a meter on the pack.
10. Only now: PID tune (§10), then put it on the floor and mount the shell.

---

## 10. PID tuning
Start with defaults; command a mid speed (e.g. `L200 R200`) and watch `TEL`:
- **Slow to reach target** → increase `Kp`.
- **Steady offset (never reaches target)** → increase `Ki`.
- **Oscillation / buzzing** → decrease `Kp`, then add a little `Kd`.
Tune one side at a time; the two sides should track the same command closely
(that's what keeps it driving straight).

---

## 11. Design decisions & rationale

- **Skid-steer, not Ackermann/RC:** the droid needs to pivot and dart in tight
  spaces and do smooth low-speed tracking. Ackermann/RC bases can't turn in place
  and are poor at slow precise motion. Wheels are hidden, so nothing is lost visually.
- **Encoder motors are the core requirement:** closed-loop velocity = smooth,
  straight, controllable motion + odometry. Several "encoder" chassis listings
  turned out to ship **without** encoders despite the title — **always verify
  6-wire motors / "Hall" / a pulses-per-rev figure before buying.** The chosen
  B0CBRMTCH2 has genuine 6-wire Hall quadrature encoders.
- **BTS7960 over L298N:** the L298N is only ~2 A/channel and drops ~2 V as heat —
  too weak for two motors per side. BTS7960 (43 A, near-zero dropout) has huge margin.
- **3S LiPo:** matches 12 V motors directly; single pack keeps it simple.
- **Separate buck-boost for the Jetson:** isolates it from motor-current brownouts;
  the Orin Nano can't be powered over USB-C, so it must come in via the barrel jack.
- **Arducam CSI over OAK-D Lite:** the Orin Nano 8GB is powerful enough to track on
  its own GPU; the CSI camera is native (no USB-mode issues), cheap, wide-FOV. The
  OAK-D Lite's depth/on-camera AI weren't needed for a first build.
- **Arduino + Jetson, no Raspberry Pi:** the Pi would be redundant — the Arduino
  owns real-time motion, the Jetson owns perception.

---

## 12. Troubleshooting
| Symptom | Likely cause |
|---|---|
| Encoders erratic / counts jump | logic ground not tied to motor/battery ground |
| Measured speed negative when driving forward | encoder A/B swapped (or motor leads) — see §9 |
| Wheel spins wrong way | swap that side's motor leads (or RPWM/LPWM) |
| Jetson resets under acceleration | Jetson on raw battery instead of buck-boost, or shared noisy rail |
| Instant `FAULT_LOWV` at boot | A0 divider not wired / wrong ratio |
| Motors twitch but don't run | BTS7960 enables (D8) not HIGH, or VCC/GND to driver logic missing |
| Won't drive at all, no telemetry | wrong serial port/baud, or USB not enumerated |

---

## 13. Open items / future work
- **Wheel-size/shell fit** (§4 note) — use 63 mm wheels or adjust the shell.
- **Jetson-side Python** serial wrapper + tracking loop — not yet written.
- **MPU6050 heading-hold** — firmware reads yaw rate but doesn't yet fold it into
  the control loop; add for straighter driving between camera updates.
- **Camera calibration** — the 160° lens has fisheye distortion; calibrate if you
  need accurate angles/distance from the image.
- Optional: depth (add OAK-D Lite) for precise follow-distance / obstacle avoidance.
```
