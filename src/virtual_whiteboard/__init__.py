import argparse
import time
from typing import Final

import cv2
from cv2.typing import MatLike

from virtual_whiteboard.camera import PREFERENCES, PiCamera, Preference
from virtual_whiteboard.models import ensure_model
from virtual_whiteboard.smoothing import LandmarkSmoother
from virtual_whiteboard.stream import MjpegStream
from virtual_whiteboard.tracking import HandTracker, draw_hand

# Localhost only: scripts/pi.py forwards the port to the laptop over SSH
STREAM_HOST: Final = "127.0.0.1"
STREAM_PORT: Final = 8000


class Args(argparse.Namespace):
    # Class-level defaults double as argparse defaults (it skips attributes already set)
    prefer: Preference = "quality"
    debug: bool = False


def _parse_args() -> Args:
    parser = argparse.ArgumentParser(prog="virtual-whiteboard")
    _ = parser.add_argument(
        "--prefer",
        choices=PREFERENCES,
        help="quality: cleaner image (46 fps camera); speed: grainier, ~5 ms less lag (60 fps camera)",
    )
    _ = parser.add_argument("--debug", action="store_true", help="overlay the models' confidence scores")
    return parser.parse_args(namespace=Args())


def _draw_text(frame: MatLike, text: str, line: int) -> None:
    _ = cv2.putText(frame, text, (10, 30 + 30 * line), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)


def _score(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def main() -> None:
    args = _parse_args()
    tracker = HandTracker(ensure_model("palm_detection_lite"), ensure_model("hand_landmark_lite"))
    smoother = LandmarkSmoother()
    stream = MjpegStream(STREAM_HOST, STREAM_PORT)
    camera = PiCamera(args.prefer)
    last = time.perf_counter()

    try:
        while True:
            frame = camera.capture()
            captured = time.perf_counter()

            if (landmarks := tracker.track(frame, captured)) is not None:
                draw_hand(frame, smoother.smooth(landmarks, captured))
            else:
                smoother.reset()

            _draw_text(frame, f"{1 / (captured - last):.0f} fps", 0)
            if args.debug:
                _draw_text(frame, f"palm {_score(tracker.palm_score)}", 1)
                _draw_text(frame, f"presence {_score(tracker.presence)}", 2)
            last = captured

            stream.publish(frame)

    except KeyboardInterrupt:
        pass

    finally:
        camera.close()
        stream.close()
