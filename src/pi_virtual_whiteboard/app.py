import json
import os
import sys
import time
from contextlib import closing, suppress
from typing import Final

import numpy as np
from cv2.typing import MatLike

from pi_virtual_whiteboard.camera import open_camera
from pi_virtual_whiteboard.cli import Hand, Mode, parse_args
from pi_virtual_whiteboard.config import STREAM_HOST, STREAM_PORT
from pi_virtual_whiteboard.hands import (
    Gesture,
    GestureFilter,
    HandTracker,
    Points,
    classify,
    draw_hand,
    measure,
)
from pi_virtual_whiteboard.smoothing import LandmarkSmoother
from pi_virtual_whiteboard.stream import FrameServer

# Colour only on a terminal, and never when NO_COLOR is set (https://no-color.org)
_COLOUR: Final = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _style(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOUR else text


def _score(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _hand_json(
    frame: MatLike,
    landmarks: Points | None,
    hand: Hand | None,
    gesture: Gesture,
    *,
    mode: Mode,
    fps: int,
    debug: list[str] | None,
) -> str:
    """Describe the hand for the browser: its landmarks in 0..1 of the frame's size, so any view size works.

    The gesture is sent even while the hand is lost, as it outlasts a brief dropout. `mode`: --mode. `fps`: frames
    tracked per second. `debug`: lines for --debug, shown by the browser as text (sharper than text drawn on the
    frame, which the JPEG and scaling blur)
    """
    normalised = None
    if landmarks is not None:
        height, width = frame.shape[:2]
        normalised = np.round(landmarks / (width, height), 4).tolist()  # 4 places: finer than a pixel, yet short
    fields = {
        "mode": mode,
        "fps": fps,
        "hand": hand,
        "gesture": gesture,
        "landmarks": normalised,
        "debug": debug,
    }
    return json.dumps(fields, separators=(",", ":"))


def main() -> None:
    args = parse_args()
    tracker = HandTracker(args.hand)
    smoother = LandmarkSmoother()
    world_smoother = LandmarkSmoother()
    gestures = GestureFilter()

    with (
        closing(FrameServer(STREAM_HOST, STREAM_PORT)) as stream,
        closing(open_camera(args)) as camera,
        suppress(KeyboardInterrupt),
    ):
        url = f"http://localhost:{STREAM_PORT}/"
        print(f"{_style('32', '✓')} View at {_style('1;36', url)} {_style('2', '(Ctrl+C to stop)')}", flush=True)

        last, fps = time.perf_counter(), 0.0
        while True:
            frame = camera.capture()
            captured, captured_wall = time.perf_counter(), time.time()

            result = tracker.track(frame, captured)
            landmarks, shape = None, None
            if result.landmarks is None or result.world_landmarks is None:
                smoother.reset()
                world_smoother.reset()
                # Like any other gesture, "none" must last GESTURE_HOLD_S: a dropout of a frame or two (common with
                # fast motion) then doesn't lift the pen mid-stroke
                gesture = gestures.update(Gesture.NONE, captured)
            else:
                landmarks = smoother.smooth(result.landmarks, captured)
                # Smoothed too: jitter near a threshold would otherwise flip the reading
                world_landmarks = world_smoother.smooth(result.world_landmarks, captured)
                shape = measure(world_landmarks)
                reading = classify(shape, drawing=gestures.current == Gesture.DRAW)
                if args.mode == "space" and reading == Gesture.DRAW:
                    reading = Gesture.NONE  # Space is the pen instead (in the browser)
                gesture = gestures.update(reading, captured)

            if landmarks is not None and (args.skeleton or args.debug):
                draw_hand(frame, landmarks)
            debug = None
            if args.debug:
                debug = [
                    f"palm {_score(result.palm_score)}",
                    f"presence {_score(result.presence)}",
                    f"hand {result.hand or '-'}",
                    f"gesture {gesture}",
                    *([shape.describe()] if shape else []),
                ]
            fps = 0.9 * fps + 0.1 / (captured - last)  # Smoothed, so the number doesn't flicker
            last = captured

            stream.publish(
                frame,
                captured_wall,
                _hand_json(frame, landmarks, result.hand, gesture, mode=args.mode, fps=round(fps), debug=debug),
            )
