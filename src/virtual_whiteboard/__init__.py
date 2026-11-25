import time
from typing import Final

import cv2

from virtual_whiteboard.camera import PiCamera
from virtual_whiteboard.models import ensure_model
from virtual_whiteboard.smoothing import LandmarkSmoother
from virtual_whiteboard.stream import MjpegStream
from virtual_whiteboard.tracking import HandTracker, draw_hand

# Localhost only: scripts/pi.sh forwards the port to the laptop over SSH
STREAM_HOST: Final = "127.0.0.1"
STREAM_PORT: Final = 8000


def main() -> None:
    tracker = HandTracker(ensure_model("palm_detection_lite"), ensure_model("hand_landmark_lite"))
    smoother = LandmarkSmoother()
    stream = MjpegStream(STREAM_HOST, STREAM_PORT)
    camera = PiCamera()
    last = time.perf_counter()

    try:
        while True:
            frame = camera.capture()
            captured = time.perf_counter()

            if (landmarks := tracker.track(frame, captured)) is not None:
                draw_hand(frame, smoother.smooth(landmarks, captured))
            else:
                smoother.reset()

            _ = cv2.putText(
                frame, f"{1 / (captured - last):.0f} fps", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
            )
            last = captured

            stream.publish(frame)

    except KeyboardInterrupt:
        pass

    finally:
        camera.close()
        stream.close()
