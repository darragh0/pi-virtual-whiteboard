"""Hand gestures, read from the shape of the 21 landmarks.

Read from the 3D (world) landmarks, not the on-screen ones: a finger pointing at the camera looks short on screen,
so a fist facing the camera would look like any other shape. Every test compares distances within the hand, so a
gesture reads the same at any distance from the camera and whichever way the hand faces.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, final

from pi_virtual_whiteboard.config import EXTENDED_RATIO, GESTURE_HOLD_S, PINCH_RATIO, PINCH_REACH_RATIO
from pi_virtual_whiteboard.hands.landmarks import HandLandmark
from pi_virtual_whiteboard.hands.roi import Points


class Gesture(StrEnum):
    DRAW = "draw"  # Index finger up: the pen is down
    HOVER = "hover"  # Index and middle fingers up: move without drawing
    ERASE = "erase"  # Open palm: a wide eraser
    PINCH = "pinch"  # Thumb and index fingertips together
    FIST = "fist"  # All fingers curled (a thumbs up counts too: see classify)
    NONE = "none"  # Anything else, or no hand


_L = HandLandmark

# Each finger's middle joint and tip (the thumb isn't counted: it barely moves between these gestures)
_FINGERS: Final = (
    (_L.INDEX_FINGER_PIP, _L.INDEX_FINGER_TIP),
    (_L.MIDDLE_FINGER_PIP, _L.MIDDLE_FINGER_TIP),
    (_L.RING_FINGER_PIP, _L.RING_FINGER_TIP),
    (_L.PINKY_PIP, _L.PINKY_TIP),
)

# Which of index, middle, ring and pinky are up, for each gesture
_SHAPES: Final[dict[tuple[bool, ...], Gesture]] = {
    (True, False, False, False): Gesture.DRAW,
    (True, True, False, False): Gesture.HOVER,
    (True, True, True, True): Gesture.ERASE,
    (False, False, False, False): Gesture.FIST,
}


@final
@dataclass(frozen=True)
class HandShape:
    """The measurements gestures are read from, each compared to a threshold in config.py."""

    fingers: tuple[float, ...]
    """Index, middle, ring, pinky: tip's distance from the wrist over the middle joint's (vs EXTENDED_RATIO)."""
    pinch: float
    """Thumb tip to index tip, in palm lengths (vs PINCH_RATIO)."""
    reach: float
    """Index tip's distance from the wrist over its knuckle's (vs PINCH_REACH_RATIO)."""

    def describe(self) -> tuple[str, str]:
        """Two short lines of the measurements, for the --debug overlay."""
        fingers = " ".join(f"{ratio:.2f}" for ratio in self.fingers)
        return f"fingers {fingers}", f"pinch {self.pinch:.2f} reach {self.reach:.2f}"


def measure(world_landmarks: Points) -> HandShape:
    """Measure a hand's shape from its 3D landmarks."""

    def distance(start: HandLandmark, end: HandLandmark) -> float:
        return math.dist(world_landmarks[start], world_landmarks[end])

    palm = distance(_L.WRIST, _L.MIDDLE_FINGER_MCP)  # The hand's scale
    return HandShape(
        # A straight finger's tip is well past its middle joint, seen from the wrist; a curled one's is not
        fingers=tuple(distance(_L.WRIST, tip) / distance(_L.WRIST, pip) for pip, tip in _FINGERS),
        pinch=distance(_L.THUMB_TIP, _L.INDEX_FINGER_TIP) / palm,
        reach=distance(_L.WRIST, _L.INDEX_FINGER_TIP) / distance(_L.WRIST, _L.INDEX_FINGER_MCP),
    )


def classify(shape: HandShape) -> Gesture:
    """Read the gesture a hand is making in one frame."""
    # In a fist the thumb also rests near the index tip, but there the tip is curled back to the knuckles
    if shape.pinch < PINCH_RATIO and shape.reach > PINCH_REACH_RATIO:
        return Gesture.PINCH

    # The thumb isn't checked, so a thumbs up reads as a fist: measured on a real hand, the thumb's distance from the
    # fingers was the same in both (~0.5 palm lengths), so no threshold could tell them apart
    fingers_up = tuple(ratio > EXTENDED_RATIO for ratio in shape.fingers)
    return _SHAPES.get(fingers_up, Gesture.NONE)


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

    def update(self, gesture: Gesture, timestamp: float) -> Gesture:
        """Return the gesture to act on, given the one read from a frame captured at `timestamp` seconds."""
        if gesture != self._candidate:
            self._candidate, self._since = gesture, timestamp

        if gesture != self._current and timestamp - self._since >= GESTURE_HOLD_S:
            self._current = gesture

        return self._current
