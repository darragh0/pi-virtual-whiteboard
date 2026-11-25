"""The 21 hand landmarks MediaPipe's landmark model outputs, in output order.

Diagram: reference/hand_landmarks.png (from https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker).
"""

from enum import IntEnum
from itertools import pairwise
from typing import Final


class HandLandmark(IntEnum):
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_FINGER_MCP = 5
    INDEX_FINGER_PIP = 6
    INDEX_FINGER_DIP = 7
    INDEX_FINGER_TIP = 8
    MIDDLE_FINGER_MCP = 9
    MIDDLE_FINGER_PIP = 10
    MIDDLE_FINGER_DIP = 11
    MIDDLE_FINGER_TIP = 12
    RING_FINGER_MCP = 13
    RING_FINGER_PIP = 14
    RING_FINGER_DIP = 15
    RING_FINGER_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20


_L = HandLandmark

# Each finger from where it joins the palm to its tip; consecutive landmarks are connected
_CHAINS: Final = (
    (_L.WRIST, _L.THUMB_CMC, _L.THUMB_MCP, _L.THUMB_IP, _L.THUMB_TIP),
    (_L.WRIST, _L.INDEX_FINGER_MCP, _L.INDEX_FINGER_PIP, _L.INDEX_FINGER_DIP, _L.INDEX_FINGER_TIP),
    (_L.INDEX_FINGER_MCP, _L.MIDDLE_FINGER_MCP, _L.MIDDLE_FINGER_PIP, _L.MIDDLE_FINGER_DIP, _L.MIDDLE_FINGER_TIP),
    (_L.MIDDLE_FINGER_MCP, _L.RING_FINGER_MCP, _L.RING_FINGER_PIP, _L.RING_FINGER_DIP, _L.RING_FINGER_TIP),
    (_L.RING_FINGER_MCP, _L.PINKY_MCP, _L.PINKY_PIP, _L.PINKY_DIP, _L.PINKY_TIP),
    (_L.PINKY_MCP, _L.WRIST),
)

HAND_CONNECTIONS: Final = tuple(pair for chain in _CHAINS for pair in pairwise(chain))
