#!/usr/bin/env python3
"""
Quick serial-link smoke test against the Arduino flight firmware.

Connects, prints telemetry, then (unless --no-move) drives a gentle pattern so
you can confirm the Jetson->Arduino->motors->telemetry path end to end.
RUN ON BLOCKS (wheels free).

  ./check_serial.py               # drive test on /dev/ttyACM0
  ./check_serial.py --no-move     # telemetry only, no motion
"""
import argparse
import time

from serial_link import MouseDroid


def main():
    p = argparse.ArgumentParser(description="Serial link smoke test.")
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--no-move", action="store_true", help="telemetry only, no motion")
    p.add_argument("--speed", type=float, default=120.0, help="test speed mm/s")
    args = p.parse_args()

    with MouseDroid(port=args.port) as d:
        print(f"connected to {args.port}")
        tel = d.wait_for_telemetry(3.0)
        print("telemetry:", tel if tel else "NONE (is the flight firmware flashed?)")
        if args.no_move:
            return

        for label, (l, r) in [
            ("forward", (args.speed, args.speed)),
            ("stop",    (0, 0)),
            ("spin",    (-args.speed, args.speed)),
            ("stop",    (0, 0)),
        ]:
            print(f">> {label}: L{l:.0f} R{r:.0f}")
            d.drive(l, r)
            for _ in range(6):                       # ~3 s per step
                time.sleep(0.5)
                t = d.telemetry
                if t:
                    print(f"   TEL L{t['left_mms']:.0f} R{t['right_mms']:.0f} V{t['volts']:.2f}")
        d.stop()
        print("done.")


if __name__ == "__main__":
    main()
