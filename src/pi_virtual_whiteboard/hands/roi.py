import math
from dataclasses import dataclass
from typing import Self

import numpy as np
import numpy.typing as npt

type Points = npt.NDArray[np.float64]
"""(N, 2) pixel coordinates, or (N, 3) for 3D landmarks."""


def rotation(angle: float) -> npt.NDArray[np.float64]:
    cos, sin = math.cos(angle), math.sin(angle)
    return np.array([[cos, -sin], [sin, cos]])


def angle_towards(start: Points, end: Points) -> float:
    """Rotation that turns "up" towards `end` as seen from `start`."""
    dx, dy = end - start
    return math.atan2(dx, -dy)


@dataclass(frozen=True)
class Roi:
    """A rotated square region of the frame: centre and side length in pixels, angle in radians."""

    centre: Points
    size: float
    angle: float

    @classmethod
    def around(cls, centre: Points, width: float, height: float, angle: float, scale: float, shift: float) -> Self:
        """Enlarge a hand-aligned box into a square crop, shifted along the hand's "up" by `shift` heights."""
        shifted = centre + rotation(angle) @ np.array([0.0, shift * height])

        return cls(shifted, max(width, height) * scale, angle)

    def crop_to_frame(self, crop_size: int) -> npt.NDArray[np.float64]:
        """2x3 affine matrix mapping crop pixels to frame pixels."""
        scaled_rotation = rotation(self.angle) * (self.size / crop_size)
        offset = self.centre - scaled_rotation @ np.full(2, crop_size / 2)

        return np.column_stack([scaled_rotation, offset])
