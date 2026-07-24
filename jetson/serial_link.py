#!/usr/bin/env python3
"""
Serial link to the mouse-droid Arduino (flight firmware mouse_droid_controller.ino).

Protocol (BUILD.md §7 / firmware/WIRING.md):
  send : "L<mm/s> R<mm/s>\\n"   or   "stop\\n"
  recv : "TEL L<mm/s> R<mm/s> V<volts> Y<deg/s>"   every 200 ms

Why the heartbeat thread: the firmware stops the motors if it hears no command
for CMD_TIMEOUT_MS (500 ms). A VLM frame can take longer than that, so we re-send
the current target ~every 150 ms in the background to keep the motors alive
between perception updates. A second thread keeps the latest telemetry fresh.

Run with the droid ON BLOCKS (wheels free) until you trust the loop.
"""
from __future__ import annotations

import re
import threading
import time

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover
    raise SystemExit("pyserial is required:  pip install pyserial")

_TEL_RE = re.compile(
    r"TEL\s+L(-?\d+(?:\.\d+)?)\s+R(-?\d+(?:\.\d+)?)"
    r"\s+V(-?\d+(?:\.\d+)?)\s+Y(-?\d+(?:\.\d+)?)"
)


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class MouseDroid:
    """Talks to the Arduino flight firmware over USB serial (thread-safe)."""

    def __init__(self, port="/dev/ttyACM0", baud=115200,
                 heartbeat_s=0.15, max_mms=400.0, boot_wait_s=2.5):
        self.max_mms = float(max_mms)
        self.heartbeat_s = float(heartbeat_s)
        self._l = 0.0
        self._r = 0.0
        self._lock = threading.Lock()
        self._telemetry = None
        self._stop = threading.Event()

        self.ser = serial.Serial(port, baud, timeout=0.2)
        time.sleep(boot_wait_s)            # opening the port resets the Uno
        self.ser.reset_input_buffer()

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._hb = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._reader.start()
        self._hb.start()

    # ---- commands ----
    def drive(self, left_mms, right_mms):
        """Set target wheel speeds (mm/s). Held by the heartbeat until changed."""
        left = _clamp(left_mms, -self.max_mms, self.max_mms)
        right = _clamp(right_mms, -self.max_mms, self.max_mms)
        with self._lock:
            self._l, self._r = left, right
        self._send(f"L{left:.0f} R{right:.0f}")

    def stop(self):
        with self._lock:
            self._l = self._r = 0.0
        self._send("stop")

    # ---- telemetry ----
    @property
    def telemetry(self):
        """Latest TEL dict or None. Keys: left_mms, right_mms, volts, yaw_dps, t."""
        return self._telemetry

    def wait_for_telemetry(self, timeout_s=3.0):
        t0 = time.time()
        while self._telemetry is None and time.time() - t0 < timeout_s:
            time.sleep(0.05)
        return self._telemetry

    # ---- lifecycle ----
    def close(self):
        try:
            self.stop()
            time.sleep(0.1)
        finally:
            self._stop.set()
            try:
                self.ser.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---- internals ----
    def _send(self, line):
        try:
            self.ser.write((line + "\n").encode())
            self.ser.flush()
        except serial.SerialException:
            pass

    def _heartbeat_loop(self):
        while not self._stop.wait(self.heartbeat_s):
            with self._lock:
                l, r = self._l, self._r
            self._send("stop" if (l == 0.0 and r == 0.0) else f"L{l:.0f} R{r:.0f}")

    def _read_loop(self):
        while not self._stop.is_set():
            try:
                raw = self.ser.readline()
            except serial.SerialException:
                break
            if not raw:
                continue
            m = _TEL_RE.search(raw.decode(errors="replace"))
            if m:
                self._telemetry = {
                    "left_mms": float(m.group(1)),
                    "right_mms": float(m.group(2)),
                    "volts": float(m.group(3)),
                    "yaw_dps": float(m.group(4)),
                    "t": time.time(),
                }


if __name__ == "__main__":
    # tiny self-test: connect and print telemetry for a few seconds (no motion).
    import sys
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    with MouseDroid(port=port) as d:
        print(f"connected to {port}; reading telemetry (no motion)...")
        for _ in range(10):
            time.sleep(0.5)
            print(" ", d.telemetry)
