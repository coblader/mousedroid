#!/usr/bin/env python3
"""
Turn a person Detection into left/right wheel speeds (mm/s).

Proportional controller:
  * horizontal error (cx - 0.5)  -> turn (differential; steer toward the person)
  * apparent size (area)         -> forward speed:
        person small / far  -> drive forward
        person at target    -> hold
        person big / near   -> stop (optionally back off)
  * not found                    -> stop (or a slow in-place search turn)

Deadbands stop it twitching on tiny errors. Everything is clamped to +/- max_mms.
Gentle defaults for on-blocks bring-up -- raise the gains once it's on the floor.

Later, when a depth sensor (OAK-D Lite) fills Detection.distance_m, swap the
area-based forward term for a real distance setpoint.
"""
from __future__ import annotations

from dataclasses import dataclass

from detection import Detection


@dataclass
class FollowConfig:
    max_mms: float = 250.0         # hard clamp on any wheel speed
    cruise_mms: float = 180.0      # forward-speed cap while approaching
    turn_gain_mms: float = 500.0   # mm/s per unit horizontal error (-0.5..0.5)
    fwd_gain_mms: float = 900.0    # mm/s per unit of (target_area - area)
    target_area: float = 0.18      # desired person bbox area fraction (~follow distance)
    area_deadband: float = 0.04    # ignore small size errors
    x_deadband: float = 0.06       # ignore small centering errors
    allow_reverse: bool = False    # back up if the person gets too close
    search_turn_mms: float = 0.0   # in-place turn when no person (0 = just stop)


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def follow_command(det: Detection, cfg: FollowConfig = FollowConfig()):
    """Return (left_mms, right_mms) for this detection."""
    if not det.found:
        s = cfg.search_turn_mms
        return (-s, s)             # spin in place to search (0,0 if disabled)

    # forward/back from apparent size (bigger area = closer)
    area_err = cfg.target_area - det.area          # >0 => too far => go forward
    if abs(area_err) < cfg.area_deadband:
        forward = 0.0
    else:
        lo = -cfg.cruise_mms if cfg.allow_reverse else 0.0
        forward = _clamp(cfg.fwd_gain_mms * area_err, lo, cfg.cruise_mms)

    # turn from horizontal error (person right of center => turn right)
    x_err = det.x_error                            # <0 left, >0 right
    turn = 0.0 if abs(x_err) < cfg.x_deadband else cfg.turn_gain_mms * x_err

    left = forward + turn
    right = forward - turn
    return (_clamp(left, -cfg.max_mms, cfg.max_mms),
            _clamp(right, -cfg.max_mms, cfg.max_mms))
