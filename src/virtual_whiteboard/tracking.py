import time
from pathlib import Path
from types import TracebackType
from typing import Final, Self, final

import cv2
import mediapipe as mp
import numpy as np
from cv2.typing import MatLike
from mediapipe.tasks.python import BaseOptions, vision
from mediapipe.tasks.python.components.containers.landmark import NormalizedLandmark

type BGR = tuple[int, int, int]

LANDMARK_COLOUR: Final[BGR] = (0, 0, 255)
CONNECTION_COLOUR: Final[BGR] = (255, 255, 255)


@final
class HandTracker:
    """Synchronous per-frame hand landmark detection over a video stream."""

    def __init__(self, model_path: Path, num_hands: int = 2) -> None:
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
        )

        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._start_ns = time.monotonic_ns()
        self._last_timestamp_ms = -1

    def detect(self, frame_bgr: MatLike) -> vision.HandLandmarkerResult:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(frame_rgb, dtype=np.uint8))

        # VIDEO mode requires strictly increasing timestamps
        elapsed_ms = (time.monotonic_ns() - self._start_ns) // 1_000_000
        timestamp_ms = max(elapsed_ms, self._last_timestamp_ms + 1)

        self._last_timestamp_ms = timestamp_ms
        return self._landmarker.detect_for_video(image, timestamp_ms)

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def _to_pixel(landmark: NormalizedLandmark, width: int, height: int) -> tuple[int, int] | None:
    if landmark.x is None or landmark.y is None:
        return None

    x = min(max(landmark.x, 0.0), 1.0)
    y = min(max(landmark.y, 0.0), 1.0)

    return round(x * (width - 1)), round(y * (height - 1))


def draw_hands(frame_bgr: MatLike, result: vision.HandLandmarkerResult) -> None:
    """Draw landmarks and connections for every detected hand, in place."""

    height, width = frame_bgr.shape[:2]

    for landmarks in result.hand_landmarks:
        points = [_to_pixel(landmark, width, height) for landmark in landmarks]

        for connection in vision.HandLandmarksConnections.HAND_CONNECTIONS:
            start, end = points[connection.start], points[connection.end]
            if start is not None and end is not None:
                _ = cv2.line(frame_bgr, start, end, CONNECTION_COLOUR, 2)

        for point in points:
            if point is not None:
                _ = cv2.circle(frame_bgr, point, 4, LANDMARK_COLOUR, -1)
