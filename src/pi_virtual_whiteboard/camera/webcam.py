from typing import final

import cv2
from cv2.typing import MatLike

from pi_virtual_whiteboard.config import FRAME_SIZE


@final
class Webcam:
    """A V4L2 webcam (e.g. a laptop's), for developing without the Pi."""

    def __init__(self, device: int) -> None:
        self._capture = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not self._capture.isOpened():
            msg = f"can't open webcam /dev/video{device}"
            raise RuntimeError(msg)

        width, height = FRAME_SIZE
        # MJPG: most webcams only reach their top frame rate in it, not in raw YUYV
        self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        # Hold one frame, not a queue: a frame read late is then still the newest, so lag can't build up
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def capture(self) -> MatLike:
        """Return the newest BGR frame."""
        ok, frame = self._capture.read()
        if not ok:
            msg = "webcam stopped sending frames"
            raise RuntimeError(msg)

        # Like the Pi camera, mirror so on-screen movement matches the user's (as the tracker assumes)
        return cv2.flip(frame, 1)

    def close(self) -> None:
        self._capture.release()
