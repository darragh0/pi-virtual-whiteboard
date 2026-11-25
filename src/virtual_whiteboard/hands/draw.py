from typing import Final

import cv2
from cv2.typing import MatLike

from virtual_whiteboard.hands.landmarks import HAND_CONNECTIONS
from virtual_whiteboard.hands.roi import Points

type BGR = tuple[int, int, int]

LANDMARK_COLOUR: Final[BGR] = (0, 0, 255)
CONNECTION_COLOUR: Final[BGR] = (255, 255, 255)


def draw_hand(frame_bgr: MatLike, landmarks: Points) -> None:
    """Draw a hand's skeleton onto the frame, in place."""
    points = [(round(x), round(y)) for x, y in landmarks]

    for start, end in HAND_CONNECTIONS:
        cv2.line(frame_bgr, points[start], points[end], CONNECTION_COLOUR, 2)

    for point in points:
        cv2.circle(frame_bgr, point, 4, LANDMARK_COLOUR, -1)
