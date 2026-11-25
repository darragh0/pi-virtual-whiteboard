"""Hand gestures, read from the shape of the 21 landmarks.

Read from the 3D (world) landmarks, not the on-screen ones: a finger pointing at the camera looks short on screen,
so a fist facing the camera would look like any other shape. Every test compares distances within the hand, so a
gesture reads the same at any distance from the camera and whichever way the hand faces.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, final

from pi_virtual_whiteboard.config import (
    EXTENDED_RATIO,
    GESTURE_HOLD_S,
    INDEX_DOWN_RATIO,
    THUMB_OUT_RATIO,
    THUMB_TUCKED_RATIO,
)
from pi_virtual_whiteboard.hands.landmarks import HandLandmark
from pi_virtual_whiteboard.hands.roi import Points


class Gesture(StrEnum):
    DRAW = "draw"  # Pointing with the thumb tucked in, like pulling a finger gun's trigger: pen down at the index tip
    ERASE = "erase"  # Open palm (all four fingers up): a wide eraser under the palm
    NONE = "none"  # Thumb out, index finger down (e.g. a fist), or no hand: the cursor just moves


_L = HandLandmark

# Each finger's middle joint and tip (the thumb is measured on its own: see HandShape.thumb)
_FINGERS: Final = (
    (_L.INDEX_FINGER_PIP, _L.INDEX_FINGER_TIP),
    (_L.MIDDLE_FINGER_PIP, _L.MIDDLE_FINGER_TIP),
    (_L.RING_FINGER_PIP, _L.RING_FINGER_TIP),
    (_L.PINKY_PIP, _L.PINKY_TIP),
)


@final
@dataclass(frozen=True)
class HandShape:
    """The measurements gestures are read from, each compared to a threshold in config.py."""

    fingers: tuple[float, ...]
    """Index, middle, ring, pinky: tip's distance from the wrist over the middle joint's (vs EXTENDED_RATIO)."""
    thumb: float
    """Thumb tip to the middle finger's middle joint, in palm lengths (vs THUMB_TUCKED_RATIO and THUMB_OUT_RATIO)."""

    def describe(self) -> str:
        """Describe the measurements in one short line, for the --debug readout."""
        return "fingers " + " ".join(f"{ratio:.2f}" for ratio in self.fingers) + f" thumb {self.thumb:.2f}"


def measure(world_landmarks: Points) -> HandShape:
    """Measure a hand's shape from its 3D landmarks."""

    def distance(start: HandLandmark, end: HandLandmark) -> float:
        return math.dist(world_landmarks[start], world_landmarks[end])

    palm = distance(_L.WRIST, _L.MIDDLE_FINGER_MCP)  # The hand's scale
    return HandShape(
        # A straight finger's tip is well past its middle joint, seen from the wrist; a curled one's is not
        fingers=tuple(distance(_L.WRIST, tip) / distance(_L.WRIST, pip) for pip, tip in _FINGERS),
        thumb=distance(_L.THUMB_TIP, _L.MIDDLE_FINGER_PIP) / palm,
    )


def classify(shape: HandShape, *, drawing: bool) -> Gesture:
    """Read the gesture a hand is making in one frame. `drawing`: whether the pen is down at the moment."""
    if all(ratio > EXTENDED_RATIO for ratio in shape.fingers):
        return Gesture.ERASE
    # Only a pointing finger draws: a fist's thumb is tucked in too
    if shape.fingers[0] < (INDEX_DOWN_RATIO if drawing else EXTENDED_RATIO):
        return Gesture.NONE
    # The trigger moves only the thumb, not the index tip: the pen goes down and up without a stray mark
    return Gesture.DRAW if shape.thumb < (THUMB_OUT_RATIO if drawing else THUMB_TUCKED_RATIO) else Gesture.NONE


@final
class GestureFilter:
    """Holds the current gesture until a new one has lasted GESTURE_HOLD_S.

    A hand changing shape passes through in-between shapes, and one misread frame happens: without this, each
    would flash a different gesture (e.g. a gap in a stroke, or a stray erase).
    """

    def __init__(self) -> None:
        self._current = Gesture.NONE
        self._candidate = Gesture.NONE  # Seen since `_since`, but not held long enough yet
        self._since = 0.0

    @property
    def current(self) -> Gesture:
        return self._current

    def update(self, gesture: Gesture, timestamp: float) -> Gesture:
        """Return the gesture to act on, given the one read from a frame captured at `timestamp` seconds."""
        if gesture != self._candidate:
            self._candidate, self._since = gesture, timestamp

        if gesture != self._current and timestamp - self._since >= GESTURE_HOLD_S:
            self._current = gesture

        return self._current
