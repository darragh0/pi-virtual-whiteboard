import json
import time
from contextlib import closing, suppress

import cv2
import numpy as np
from cv2.typing import MatLike

from pi_virtual_whiteboard.camera import open_camera
from pi_virtual_whiteboard.cli import Hand, parse_args
from pi_virtual_whiteboard.config import STREAM_HOST, STREAM_PORT
from pi_virtual_whiteboard.hands import Gesture, GestureFilter, HandTracker, Points, classify, draw_hand, measure
from pi_virtual_whiteboard.smoothing import LandmarkSmoother
from pi_virtual_whiteboard.stream import FrameServer


def _draw_lines(frame: MatLike, *lines: str) -> None:
    for number, text in enumerate(lines):
        cv2.putText(frame, text, (10, 30 + 30 * number), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)


def _score(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _hand_json(frame: MatLike, landmarks: Points | None, hand: Hand | None, gesture: Gesture) -> str:
    """Describe the hand for the browser: its landmarks in 0..1 of the frame's size, so any view size works.

    The gesture is sent even while the hand is lost, as it outlasts a brief dropout.
    """
    normalised = None
    if landmarks is not None:
        height, width = frame.shape[:2]
        normalised = np.round(landmarks / (width, height), 4).tolist()  # 4 places: finer than a pixel, yet short
    return json.dumps({"hand": hand, "gesture": gesture, "landmarks": normalised}, separators=(",", ":"))


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
        last = time.perf_counter()
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
                gesture = gestures.update(classify(shape, drawing=gestures.current == Gesture.DRAW), captured)

            # The video stays clean for the whiteboard; the tracking's workings are shown only when debugging
            if args.debug:
                if landmarks is not None:
                    draw_hand(frame, landmarks)
                _draw_lines(
                    frame,
                    f"{1 / (captured - last):.0f} fps",
                    f"palm {_score(result.palm_score)}",
                    f"presence {_score(result.presence)}",
                    f"hand {result.hand or '-'}",
                    f"gesture {gesture}",
                    *(shape.describe() if shape else ()),
                )
            last = captured

            stream.publish(frame, captured_wall, _hand_json(frame, landmarks, result.hand, gesture))
