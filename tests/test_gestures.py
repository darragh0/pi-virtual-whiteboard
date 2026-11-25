import math
from typing import Final

import numpy as np
import pytest

from pi_virtual_whiteboard.config import (
    EXTENDED_RATIO,
    GESTURE_HOLD_S,
    INDEX_DOWN_RATIO,
    THUMB_OUT_RATIO,
    THUMB_TUCKED_RATIO,
)
from pi_virtual_whiteboard.hands import Gesture, GestureFilter, HandLandmark, HandShape, Points, classify, measure

_L = HandLandmark

# Knuckle (MCP) of each finger, in palm lengths from the wrist; the hand points up (y grows downwards, as on screen)
_KNUCKLES: Final = {
    _L.INDEX_FINGER_MCP: (-0.3, -1.0),
    _L.MIDDLE_FINGER_MCP: (-0.1, -1.0),
    _L.RING_FINGER_MCP: (0.1, -0.97),
    _L.PINKY_MCP: (0.28, -0.9),
}
# Each joint's offset from the one before (PIP, DIP, tip)
_STRAIGHT: Final = ((0, -0.45), (0, -0.28), (0, -0.22))
_CURLED: Final = ((0, -0.35), (0, 0.2), (0, 0.25))  # Folds back down towards the palm


def _hand(*fingers_up: bool, thumb_out: bool = False) -> Points:
    """Build a flat synthetic right hand in palm lengths, with index, middle, ring and pinky up or curled."""
    points = np.zeros((21, 2))
    points[_L.THUMB_CMC], points[_L.THUMB_MCP], points[_L.THUMB_IP] = (-0.25, -0.15), (-0.45, -0.35), (-0.6, -0.55)
    points[_L.THUMB_TIP] = (-0.7, -0.75)

    for (knuckle, start), up in zip(_KNUCKLES.items(), fingers_up, strict=True):
        joint = np.array(start)
        points[knuckle] = joint
        bends = _STRAIGHT if up else _CURLED
        for offset, step in enumerate(bends, start=1):
            joint = joint + step
            points[knuckle + offset] = joint

    if thumb_out:
        points[_L.THUMB_TIP] = (-0.95, -0.5)  # Sticking out sideways, like a finger gun's cocked thumb
    elif not any(fingers_up):
        points[_L.THUMB_TIP] = points[_L.INDEX_FINGER_TIP] + (0.05, 0.05)  # A fist's thumb wraps over the fingers
    else:
        points[_L.THUMB_TIP] = (-0.15, -1.25)  # Tucked in against the curled middle finger
    return np.column_stack([points, np.zeros(21)])


def _posed(hand: Points, spin: float, tilt: float, palm: float) -> Points:
    """Turn a hand `spin` degrees on screen, then tilt it `tilt` degrees towards the camera, at `palm` metres long."""
    spin_rad, tilt_rad = math.radians(spin), math.radians(tilt)
    spin_matrix = np.array(
        [[math.cos(spin_rad), -math.sin(spin_rad), 0], [math.sin(spin_rad), math.cos(spin_rad), 0], [0, 0, 1]]
    )
    tilt_matrix = np.array(
        [[1, 0, 0], [0, math.cos(tilt_rad), -math.sin(tilt_rad)], [0, math.sin(tilt_rad), math.cos(tilt_rad)]]
    )
    return hand @ (tilt_matrix @ spin_matrix).T * palm


HANDS: Final = {
    "pointing, thumb tucked in": (_hand(True, False, False, False), Gesture.DRAW),
    "pointing, thumb out": (_hand(True, False, False, False, thumb_out=True), Gesture.NONE),
    "open palm": (_hand(True, True, True, True), Gesture.ERASE),
    "fist": (_hand(False, False, False, False), Gesture.NONE),  # Its thumb is tucked in too, but it isn't pointing
}


@pytest.mark.parametrize("name", HANDS)
@pytest.mark.parametrize("spin", [0, 45, 180])
# 85 degrees: fingers pointing nearly straight at the camera, where on-screen landmarks would make every finger look
# curled (why gestures read the 3D landmarks)
@pytest.mark.parametrize("tilt", [0, 60, 85])
@pytest.mark.parametrize("palm", [0.07, 0.1])  # A small and a large hand, in metres
def test_classify_reads_each_gesture_however_the_hand_is_held(name: str, spin: float, tilt: float, palm: float) -> None:
    hand, gesture = HANDS[name]
    assert classify(measure(_posed(hand, spin, tilt, palm)), drawing=False) == gesture


def test_filter_switches_once_a_gesture_has_held() -> None:
    gestures = GestureFilter()
    assert gestures.update(Gesture.DRAW, 0.0) == Gesture.NONE
    assert gestures.update(Gesture.DRAW, GESTURE_HOLD_S / 2) == Gesture.NONE
    assert gestures.update(Gesture.DRAW, GESTURE_HOLD_S) == Gesture.DRAW


def test_filter_ignores_a_brief_misread() -> None:
    gestures = GestureFilter()
    gestures.update(Gesture.DRAW, 0.0)
    gestures.update(Gesture.DRAW, 1.0)
    frame = GESTURE_HOLD_S / 4  # Several frames per hold time, as at any real frame rate
    assert gestures.update(Gesture.ERASE, 1.0 + frame) == Gesture.DRAW
    assert gestures.update(Gesture.DRAW, 1.0 + 2 * frame) == Gesture.DRAW
    # The misread doesn't count towards a later switch: ERASE must hold for the full time again
    assert gestures.update(Gesture.ERASE, 1.0 + 3 * frame) == Gesture.DRAW
    assert gestures.update(Gesture.ERASE, 1.0 + 6 * frame) == Gesture.DRAW
    assert gestures.update(Gesture.ERASE, 1.0 + 8 * frame) == Gesture.ERASE


def test_filter_keeps_the_pen_down_through_a_brief_dropout() -> None:
    gestures = GestureFilter()
    gestures.update(Gesture.DRAW, 0.0)
    gestures.update(Gesture.DRAW, 1.0)
    # The app reads a lost hand as NONE: for a moment, that's the same as any other misread
    assert gestures.update(Gesture.NONE, 1.0 + GESTURE_HOLD_S / 2) == Gesture.DRAW
    assert gestures.update(Gesture.DRAW, 1.0 + GESTURE_HOLD_S) == Gesture.DRAW


def test_a_drifting_thumb_keeps_the_pen_down() -> None:
    drifting = HandShape(fingers=(1.4, 0.8, 0.8, 0.8), thumb=(THUMB_TUCKED_RATIO + THUMB_OUT_RATIO) / 2)
    assert classify(drifting, drawing=False) == Gesture.NONE  # Not tucked enough to start drawing...
    assert classify(drifting, drawing=True) == Gesture.DRAW  # ...but not out enough to stop


def test_a_slightly_bent_index_keeps_the_pen_down() -> None:
    bent = HandShape(fingers=((INDEX_DOWN_RATIO + EXTENDED_RATIO) / 2, 0.8, 0.8, 0.8), thumb=0.3)
    assert classify(bent, drawing=False) == Gesture.NONE  # Too bent to start drawing...
    assert classify(bent, drawing=True) == Gesture.DRAW  # ...but not to stop
