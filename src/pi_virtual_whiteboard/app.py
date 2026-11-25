import argparse
import time
from contextlib import closing, suppress

import cv2
from cv2.typing import MatLike

from pi_virtual_whiteboard.camera import PREFERENCES, PiCamera, Preference
from pi_virtual_whiteboard.config import STREAM_HOST, STREAM_PORT
from pi_virtual_whiteboard.hands import HandTracker, draw_hand
from pi_virtual_whiteboard.smoothing import LandmarkSmoother
from pi_virtual_whiteboard.stream import FrameServer


class Args(argparse.Namespace):
    # Class-level defaults double as argparse defaults (it skips attributes already set)
    prefer: Preference = "quality"
    debug: bool = False


def _parse_args() -> Args:
    parser = argparse.ArgumentParser(prog="pi-virtual-whiteboard")
    parser.add_argument(
        "--prefer",
        choices=PREFERENCES,
        help="quality: cleaner image (46 fps camera); speed: grainier, ~5 ms less lag (60 fps camera)",
    )
    parser.add_argument("--debug", action="store_true", help="overlay the models' confidence scores")
    return parser.parse_args(namespace=Args())


def _draw_lines(frame: MatLike, *lines: str) -> None:
    for number, text in enumerate(lines):
        cv2.putText(frame, text, (10, 30 + 30 * number), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)


def _score(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def main() -> None:
    args = _parse_args()
    tracker = HandTracker()
    smoother = LandmarkSmoother()

    with (
        closing(FrameServer(STREAM_HOST, STREAM_PORT)) as stream,
        closing(PiCamera(args.prefer)) as camera,
        suppress(KeyboardInterrupt),
    ):
        last = time.perf_counter()
        while True:
            frame = camera.capture()
            captured, captured_wall = time.perf_counter(), time.time()

            result = tracker.track(frame, captured)
            if result.landmarks is None:
                smoother.reset()
            else:
                draw_hand(frame, smoother.smooth(result.landmarks, captured))

            lines = [f"{1 / (captured - last):.0f} fps"]
            if args.debug:
                lines += [f"palm {_score(result.palm_score)}", f"presence {_score(result.presence)}"]
            _draw_lines(frame, *lines)
            last = captured

            stream.publish(frame, captured_wall)
