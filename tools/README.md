# tools/ — bench & bring-up scripts

Small host-side helper scripts run from the **Jetson** (or any machine on the
Arduino's USB serial) during hardware bring-up and testing. These are utilities,
not part of the robot's runtime. For the master build doc see [`../BUILD.md`](../BUILD.md);
for bring-up state and history see [`../AGENT_LOG.md`](../AGENT_LOG.md).

## Requirements
- Python 3 + `pyserial` (`python3 -m pip install pyserial`)
- The Arduino connected over USB (usually `/dev/ttyACM0`, 115200 baud)
- The relevant sketch flashed (see each script below)

## Scripts

| Script | What it does | Needs flashed |
|---|---|---|
| `motor_test.py` | Drives the motors over serial for open-loop bench testing (forward / reverse / pivot / one side). Health-gates the Uno first and won't command motion if the board is unresponsive. | `firmware/motor_test/motor_test.ino` |

### `motor_test.py`
Open-loop motor driver test. Sends `L<pwm> R<pwm>` commands, holds for a set
duration (re-sending to beat any command timeout), then `stop`. It first reads
the boot banner + a harmless `L0 R0` echo and **aborts without spinning** if the
Uno doesn't respond — this is what caught the wiring shorts during bring-up (a
5V↔GND short browns out the board; better to detect than to drive into it).

```bash
python3 tools/motor_test.py                    # both sides forward (L120 R120), 3s
python3 tools/motor_test.py -l 120 -r 120 -s 5 # all four forward, hold 5s
python3 tools/motor_test.py -l -120 -r 120     # pivot in place
python3 tools/motor_test.py -l 150 -r 0        # left side only
python3 tools/motor_test.py --check            # health check only, no motion
python3 tools/motor_test.py -p /dev/ttyACM1    # different port
```

Values are **raw PWM (-255..255)** with the `motor_test.ino` firmware. (The same
script works against the flight firmware `mouse_droid_controller.ino`, where the
numbers are mm/s instead — but that runs a closed-loop PID, so prefer the
open-loop sketch for pure wiring/direction checks.)

If the port is stuck (`device busy`), a stray process may be holding it:
```bash
fuser -k /dev/ttyACM0
```

## Adding a script here
Drop it in this folder and **add a row to the table above** plus a short section
describing what it does and which firmware it expects. Keep these scripts
self-contained and safe-by-default (health-check before driving hardware).
