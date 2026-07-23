#!/usr/bin/env python3
"""
motor_test.py - drive the mouse-droid motors over serial for bench testing.

Pairs with the open-loop diagnostic firmware `firmware/motor_test/motor_test.ino`
(raw PWM, no PID/encoders). Also works with the flight firmware
`mouse_droid_controller.ino`, but there the values are mm/s, not raw PWM, and a
500 ms command-timeout applies (this script re-sends to hold, so it's fine).

What it does:
  1. Opens the serial port (this resets the Uno, which re-runs setup()).
  2. Health-gates: reads the boot banner and a harmless "L0 R0" echo. If the
     board doesn't respond, it ABORTS without commanding motion (so a browned-out
     Uno from a wiring short can't be driven).
  3. Sends the requested L/R command, holds it for --seconds (re-sending every
     250 ms to beat the flight firmware's command timeout), then sends "stop".

Requires: pyserial  (python3 -m pip install pyserial)

Examples:
  ./motor_test.py                       # both sides forward (L120 R120) for 3s
  ./motor_test.py -l 120 -r 120 -s 5    # all four forward, hold 5s
  ./motor_test.py -l -120 -r 120        # pivot in place (left back, right fwd)
  ./motor_test.py -l 150 -r 0           # left side only
  ./motor_test.py --check               # health check only, no motion
  ./motor_test.py -p /dev/ttyACM1       # different port

Tip: if the port is stuck ("device busy"), a stray process may hold it; this
script does not kill holders. Run:  fuser -k /dev/ttyACM0
"""
import argparse
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed. Run: python3 -m pip install pyserial")


def main():
    ap = argparse.ArgumentParser(description="Bench-test the mouse-droid motors over serial.")
    ap.add_argument("-l", "--left", type=int, default=120,
                    help="left command (PWM -255..255 for motor_test; mm/s for flight fw). Default 120.")
    ap.add_argument("-r", "--right", type=int, default=120,
                    help="right command. Default 120.")
    ap.add_argument("-s", "--seconds", type=float, default=3.0,
                    help="how long to hold the command before stopping. Default 3.")
    ap.add_argument("-p", "--port", default="/dev/ttyACM0", help="serial port. Default /dev/ttyACM0.")
    ap.add_argument("-b", "--baud", type=int, default=115200, help="baud. Default 115200.")
    ap.add_argument("--check", action="store_true", help="health check only; do not command any motion.")
    args = ap.parse_args()

    try:
        s = serial.Serial(args.port, args.baud, timeout=0.4)
    except Exception as e:
        sys.exit(f"Could not open {args.port}: {e}")

    with s:
        time.sleep(2.5)  # opening the port resets the Uno; wait out the bootloader
        banner = s.read(2000).decode(errors="replace").strip()
        print("banner:", repr(banner) if banner else "[none]")

        s.reset_input_buffer()
        s.write(b"L0 R0\n"); s.flush()   # harmless, no motion
        time.sleep(0.5)
        echo = s.readline().decode(errors="replace").strip()
        print("echo  :", repr(echo))

        healthy = ("ready" in banner) or bool(echo)
        if not healthy:
            sys.exit(">>> Uno not responding (no banner/echo). NOT commanding motion. "
                     "Check the sketch is flashed and no wiring short is browning out the board.")

        if args.check:
            print(">>> Uno healthy. (--check: no motion commanded.)")
            return

        cmd = f"L{args.left} R{args.right}".encode()
        print(f">>> healthy - holding '{cmd.decode()}' for {args.seconds:g}s")
        s.reset_input_buffer()
        t = time.time()
        while time.time() - t < args.seconds:
            s.write(cmd + b"\n"); s.flush()
            ln = s.readline().decode(errors="replace").strip()
            if ln:
                print("   ", ln)
            time.sleep(0.25)

        s.write(b"stop\n"); s.flush()
        time.sleep(0.4)
        print("   stop ->", s.readline().decode(errors="replace").strip())


if __name__ == "__main__":
    main()
