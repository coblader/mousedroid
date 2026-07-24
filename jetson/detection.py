"""Shared perception type: where the target (a person) is in the frame.

Every perception backend (the VLM locator now; an OAK-D Lite detector later)
returns a Detection, so the controller and follow loop don't care which one is
in use.
"""
from dataclasses import dataclass


@dataclass
class Detection:
    found: bool
    cx: float = 0.5          # horizontal center, 0.0 (left) .. 1.0 (right)
    cy: float = 0.5          # vertical center,   0.0 (top)  .. 1.0 (bottom)
    area: float = 0.0        # bbox area as a fraction of the frame, 0..1 (size ~ closeness)
    distance_m: float = None  # real distance if a depth sensor gives it (OAK-D); else None

    @property
    def x_error(self):
        """Signed horizontal error: <0 target is left of center, >0 to the right."""
        return self.cx - 0.5
