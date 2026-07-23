#!/usr/bin/env python3
"""
encoder_test.py - read live encoder counts for the "one full revolution" check.

Pairs with the diagnostic firmware `firmware/encoder_test/encoder_test.ino`.
It zeros the counts, then gives you a window to rotate a wheel exactly one full
turn by hand; at the end it reports the count delta per side.

  One full WHEEL revolution should read ~+-360 counts (6 PPR x 2 edges x 30:1).
    ~+-360, all one sign  -> encoder good.
    near 0 / wandering    -> that side's B channel isn't toggling (loose/wrong
                             wire); reseat it and retry.

Which wheel drives which count:
  RIGHT count = the wheel whose encoder is on D3/D7 (front-right in our wiring).
  LEFT  count = the wheel whose encoder is on D2/D4 (front-left).
  The other motor on each side has its encoder unplugged, so turning it does
  nothing here.

Requires: pyserial

Examples:
  ./encoder_test.py               # 30s window, zero then turn a wheel one turn
  ./encoder_test.py -s 45         # longer window
  ./encoder_test.py -p /dev/ttyACM1
"""
import argparse
import re
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed. Run: python3 -m pip install pyserial")

PAT = re.compile(r"L(-?\d+)\s+R(-?\d+)")


def main():
    ap = argparse.ArgumentParser(description="Encoder one-revolution check over serial.")
    ap.add_argument("-s", "--seconds", type=float, default=30.0,
                    help="window to turn the wheel(s) in. Default 30.")
    ap.add_argument("-p", "--port", default="/dev/ttyACM0", help="serial port. Default /dev/ttyACM0.")
    ap.add_argument("-b", "--baud", type=int, default=115200, help="baud. Default 115200.")
    args = ap.parse_args()

    try:
        s = serial.Serial(args.port, args.baud, timeout=0.4)
    except Exception as e:
        sys.exit(f"Could not open {args.port}: {e}")

    with s:
        time.sleep(2.5)  # opening resets the Uno; wait out the bootloader
        banner = s.read(2000).decode(errors="replace").strip()
        print("banner:", repr(banner) if banner else "[none]")
        if "encoder_test" not in banner:
            print("WARNING: didn't see the encoder_test banner - is encoder_test.ino flashed?")

        s.reset_input_buffer()
        s.write(b"z\n"); s.flush()   # zero the counts
        print(f">>> counts zeroed. Rotate a wheel EXACTLY ONE FULL TURN in the next {args.seconds:g}s.")
        print(">>> RIGHT count = front-right wheel (D3/D7); LEFT count = front-left wheel (D2/D4).")

        lastL = lastR = 0
        maxAbsL = maxAbsR = 0
        lastLine = ""
        t = time.time()
        lastprint = 0.0
        while time.time() - t < args.seconds:
            ln = s.readline().decode(errors="replace").strip()
            if not ln:
                continue
            m = PAT.search(ln)
            if m:
                lastL, lastR = int(m.group(1)), int(m.group(2))
                maxAbsL = max(maxAbsL, abs(lastL))
                maxAbsR = max(maxAbsR, abs(lastR))
                lastLine = ln
            now = time.time()
            if now - lastprint >= 1.0:
                lastprint = now
                print(f"   L={lastL:+5d}  R={lastR:+5d}   {lastLine}")

        def verdict(delta, mx):
            a = abs(delta)
            if 300 <= a <= 420:
                return "OK (~one revolution)"
            if a < 30:
                return "STUCK near 0 -> B channel not toggling (loose/wrong wire)"
            return f"off-target (turned <1 or >1 rev? peak |{mx}|)"

        print("\n=== RESULT (expect ~+-360 for one full wheel turn) ===")
        print(f"LEFT  delta: {lastL:+d}  (peak |{maxAbsL}|)  -> {verdict(lastL, maxAbsL)}")
        print(f"RIGHT delta: {lastR:+d}  (peak |{maxAbsR}|)  -> {verdict(lastR, maxAbsR)}")


if __name__ == "__main__":
    main()
