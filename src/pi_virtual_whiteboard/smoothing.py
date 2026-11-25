"""Landmark jitter reduction with the One Euro filter (Casiez et al., https://gery.casiez.net/1euro/).

It's a low-pass filter whose cutoff rises with speed: heavy smoothing while the hand is still
(no jitter), light smoothing while it moves (no lag). MediaPipe smooths hand landmarks the same way.
"""

import math
from typing import final

import numpy as np
import numpy.typing as npt

from pi_virtual_whiteboard.config import (
    SMOOTHING_BETA,
    SMOOTHING_DERIVATIVE_CUTOFF_HZ,
    SMOOTHING_MIN_CUTOFF_HZ,
)
from pi_virtual_whiteboard.hands import Points


def _smoothing_factor[T: (float, npt.NDArray[np.float64])](dt: float, cutoff_hz: T) -> T:
    """How much of a new sample to blend in (0..1): more for a higher cutoff or a longer gap."""
    return 1 / (1 + 1 / (2 * math.pi * cutoff_hz * dt))


@final
class LandmarkSmoother:
    def __init__(self) -> None:
        self._landmarks: Points | None = None
        self._velocity: Points | None = None
        self._timestamp = 0.0

    def reset(self) -> None:
        """Forget the previous hand, e.g. once it's lost, so a new one doesn't get dragged from the old position."""
        self._landmarks = None

    def smooth(self, landmarks: Points, timestamp: float) -> Points:
        """Return `landmarks` (from a frame captured at `timestamp` seconds) with jitter filtered out."""
        dt = timestamp - self._timestamp
        if self._landmarks is None or self._velocity is None or dt <= 0:
            self._landmarks, self._velocity, self._timestamp = landmarks, np.zeros_like(landmarks), timestamp
            return landmarks

        hand_size = float(np.mean(landmarks.max(axis=0) - landmarks.min(axis=0)))
        velocity = (landmarks - self._landmarks) / (dt * hand_size)
        velocity_alpha = _smoothing_factor(dt, SMOOTHING_DERIVATIVE_CUTOFF_HZ)
        self._velocity = velocity_alpha * velocity + (1 - velocity_alpha) * self._velocity

        # Each coordinate gets its own cutoff, so a moving fingertip isn't held back by a still wrist
        alpha = _smoothing_factor(dt, SMOOTHING_MIN_CUTOFF_HZ + SMOOTHING_BETA * np.abs(self._velocity))
        self._landmarks = alpha * landmarks + (1 - alpha) * self._landmarks
        self._timestamp = timestamp

        return self._landmarks
