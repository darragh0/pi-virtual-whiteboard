from typing import Final

import cv2
from cv2.typing import MatLike

from virtual_whiteboard.hands.roi import Points

type BGR = tuple[int, int, int]

HAND_CONNECTIONS: Final = (
    *((0, 1), (0, 5), (0, 17), (5, 9), (9, 13), (13, 17)),  # Palm
    *((1, 2), (2, 3), (3, 4)),  # Thumb
    *((5, 6), (6, 7), (7, 8)),  # Index
    *((9, 10), (10, 11), (11, 12)),  # Middle
    *((13, 14), (14, 15), (15, 16)),  # Ring
    *((17, 18), (18, 19), (19, 20)),  # Pinky
)
LANDMARK_COLOUR: Final[BGR] = (0, 0, 255)
CONNECTION_COLOUR: Final[BGR] = (255, 255, 255)


def draw_hand(frame_bgr: MatLike, landmarks: Points) -> None:
    """Draw a hand's skeleton onto the frame, in place."""
    points = [(round(x), round(y)) for x, y in landmarks]

    for start, end in HAND_CONNECTIONS:
        cv2.line(frame_bgr, points[start], points[end], CONNECTION_COLOUR, 2)

    for point in points:
        cv2.circle(frame_bgr, point, 4, LANDMARK_COLOUR, -1)
