# Mouse Droid — Wiring

Skid-steer 4WD. Left pair of motors on BTS7960 #1, right pair on BTS7960 #2.
Arduino Uno = motor controller (USB-powered from Jetson). One encoder read per side.

## 1. Power distribution (thick wire, 12–14 AWG)

```
        3S LiPo 11.1V ── XT60
             │ (+)
             ▼
      [ 15A inline fuse ]
             │
             ▼
      [ 20A main switch ]
             │  +12V (switched) bus
   ┌─────────┼───────────────────┬───────────────────────┐
   ▼         ▼                   ▼                        ▼
BTS7960 #1  BTS7960 #2      Buck-boost IN            (Vbat divider tap,
 B+  B-      B+  B-          IN+   IN-                 see signal view)
                              │ OUT = 12V
                              ▼
                    [ 5.5x2.5 barrel, CENTER +] ── verify with meter!
                              ▼
                    Jetson Orin Nano DC jack

GROUND BUS (battery −):  battery− ─ BTS7960#1 B− ─ BTS7960#2 B− ─
                         buck-boost IN− ─ Arduino GND ─ MPU6050 GND ─
                         divider GND   (ALL tied together — one common ground)
```

## 2. Motors (each driver runs its two motors in parallel)

```
BTS7960 #1 (LEFT)                    BTS7960 #2 (RIGHT)
  M+ ─┬─ Left-Front  (+)               M+ ─┬─ Right-Front (+)
  M- ─┤   Left-Front  (-)              M- ─┤   Right-Front (-)
      └─ Left-Rear   (+/-)                 └─ Right-Rear  (+/-)
```

## 3. Signal / logic (thin jumper wire)

```
Jetson Orin Nano ──── USB (data + powers Uno) ──── Arduino Uno
Arducam IMX219  ──── 22-pin MIPI-CSI ──────────── Jetson

Arduino Uno                         BTS7960 #1 (LEFT)
  D5  ──────────────────────────►   RPWM
  D6  ──────────────────────────►   LPWM
  D8  ──┬───────────────────────►   R_EN + L_EN (tied)
  5V  ──┼──────────────────────►    VCC (logic)
  GND ──┼──────────────────────►    GND (logic)
        │                           BTS7960 #2 (RIGHT)
  D9  ──┼───────────────────────►   RPWM
  D10 ──┼───────────────────────►   LPWM
  D8  ──┘  (same enable line)   ►    R_EN + L_EN (tied)
                                     VCC ◄ 5V,  GND ◄ GND

LEFT motor encoder (6-wire)          Arduino
  A phase  ───────────────────►      D2  (interrupt)
  B phase  ───────────────────►      D4
  Hall +   ◄───────────────────      5V
  Hall GND ◄───────────────────      GND
  M+ / M-  ── to BTS7960 #1 M+/M-

RIGHT motor encoder (6-wire)         Arduino
  A phase  ───────────────────►      D3  (interrupt)
  B phase  ───────────────────►      D7
  Hall +   ◄─ 5V   Hall GND ◄─ GND
  M+ / M-  ── to BTS7960 #2 M+/M-

MPU6050          Battery sense divider
  VCC ◄ 5V         +12V ─[R1 10k]─┬─[R2 3.3k]─ GND
  GND ◄ GND                       └──► A0
  SDA ► A4
  SCL ► A5
```

### Encoder connector pinout (6-pin JST on each motor)

Each motor breaks out to ONE 6-pin plug that carries **both** the encoder
signals (thin, to the Arduino) and the motor power (fat, to the BTS7960). Pin
order below matches the vendor diagram (`../chassis/4wd-mecanum-wheel-robot-motor-encoder-diagram.jpg.webp`).

```
Pin  Vendor label                       Actually is        Wire to (LEFT / RIGHT)
 1   "A phase signal from Hall sensor"  Encoder A phase    D2  / D3   (interrupt)
 2   "A phase signal from Hall sensor"  Encoder B phase *  D4  / D7
 3   Hall sensor positive (+)           Encoder Vcc 3.5-5V 5V
 4   Hall sensor GND (-)                Encoder GND        GND
 5   connect to motor M-                Motor -            BTS7960 M-
 6   connect to motor M+                Motor +            BTS7960 M+
```

* **The vendor diagram double-labels pins 1 & 2 both as "A phase" — that is a
  typo.** A 6-wire Hall encoder has two quadrature outputs; pin 2 is the **B
  phase**. The firmware reads A on the interrupt and compares it against B to get
  direction, so B must land on D4 (left) / D7 (right). If direction reads
  backwards, swap the encoder's A/B (pins 1↔2) — see BUILD.md §9 bring-up.
* Encoder logic is 3.5-5 V, so the Uno's **5V** rail is in range.
* Spec check: 6 pulses/rev × 1:30 gearbox, counted on CHANGE of A (2 edges) =
  360 counts per wheel revolution → firmware `COUNTS_PER_REV = 360`.

## Connection table (Arduino Uno)

| Uno pin | To | Notes |
|---|---|---|
| D2 | LEFT encoder A | hardware interrupt |
| D3 | RIGHT encoder A | hardware interrupt |
| D4 | LEFT encoder B | |
| D7 | RIGHT encoder B | |
| D5 / D6 | BTS7960#1 RPWM / LPWM | PWM |
| D9 / D10 | BTS7960#2 RPWM / LPWM | PWM |
| D8 | all four BTS enables | HIGH=run, LOW=e-stop |
| A0 | divider junction | Vbat sense |
| A4 / A5 | MPU6050 SDA / SCL | I2C |
| 5V | encoder Hall+ ×2, BTS VCC ×2, MPU VCC | logic power |
| GND | common ground bus | **must tie to battery −** |
| USB | Jetson | data + powers Uno |

## Critical notes
- **One common ground** — the #1 cause of flaky encoder/PWM behavior is the
  Arduino/logic ground not being tied to the motor-power (battery −) ground.
- **Only one encoder per side is read.** The other motor on each side still gets
  M+/M- power from the driver; its encoder wires can be left unconnected.
- **Barrel plug polarity: center positive.** Meter it before plugging the Jetson.
- Keep the fat 12V motor wiring physically away from the thin encoder/signal wires.
- The main switch cuts everything including the Jetson (buck-boost taps the switched bus).
```
