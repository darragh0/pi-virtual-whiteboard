"""Hand tracking with MediaPipe's palm detection and hand landmark models, run directly on LiteRT.

Follows MediaPipe's own pipeline, without the mediapipe package (which crashes on the Pi 4):
- The slow palm detector runs only while no hand is tracked
- Otherwise each frame's landmarks give the crop for the next, so only the fast landmark model runs
"""

import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, final

import cv2
import numpy as np
import numpy.typing as npt
from ai_edge_litert.interpreter import Interpreter
from cv2.typing import MatLike

type Points = npt.NDArray[np.float64]
"""(N, 2) pixel coordinates."""

type BGR = tuple[int, int, int]

NUM_THREADS: Final = 4
PALM_INPUT_SIZE: Final = 192
LANDMARK_INPUT_SIZE: Final = 224
MIN_PALM_SCORE: Final = 0.7  # Above MediaPipe's 0.5: faces in dim light can score ~0.6
MIN_HAND_PRESENCE: Final = 0.5

# Crop placement, from MediaPipe's hand landmark graph configs
PALM_ROI_SCALE: Final = 2.6
PALM_ROI_SHIFT: Final = -0.5
LANDMARK_ROI_SCALE: Final = 2.0
LANDMARK_ROI_SHIFT: Final = -0.1
ROI_LANDMARKS: Final = [0, 1, 2, 3, 5, 6, 9, 10, 13, 14, 17, 18]  # Wrist + finger bases: stable as fingers move

WRIST: Final = 0
MIDDLE_FINGER_BASE: Final = 9
PALM_KEYPOINT_WRIST: Final = 0
PALM_KEYPOINT_MIDDLE_FINGER_BASE: Final = 2

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


def _rotation(angle: float) -> npt.NDArray[np.float64]:
    cos, sin = math.cos(angle), math.sin(angle)
    return np.array([[cos, -sin], [sin, cos]])


def _angle(wrist: Points, finger_base: Points) -> float:
    """Rotation that turns the crop's "up" towards the fingers."""
    dx, dy = finger_base - wrist
    return math.atan2(dx, -dy)


@dataclass(frozen=True)
class Roi:
    """A rotated square region of the frame: centre and side length in pixels, angle in radians."""

    centre: Points
    size: float
    angle: float

    @classmethod
    def around(cls, centre: Points, width: float, height: float, angle: float, scale: float, shift: float) -> "Roi":
        """Enlarge a hand-aligned box into a square crop, shifted along the hand's "up" by `shift` heights."""
        shifted = centre + _rotation(angle) @ np.array([0.0, shift * height])
        return cls(shifted, max(width, height) * scale, angle)

    def crop_to_frame(self, crop_size: int) -> npt.NDArray[np.float64]:
        """2x3 affine matrix mapping crop pixels to frame pixels."""
        rotation = _rotation(self.angle) * (self.size / crop_size)
        offset = self.centre - rotation @ np.full(2, crop_size / 2)
        return np.column_stack([rotation, offset])


@final
class _Model:
    def __init__(self, path: Path) -> None:
        self._interpreter = Interpreter(model_path=str(path), num_threads=NUM_THREADS)
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]["index"]
        self._outputs = {d["name"]: d["index"] for d in self._interpreter.get_output_details()}

    def run(self, image_bgr: MatLike) -> dict[str, npt.NDArray[np.float64]]:
        """Run on one BGR image and return each output (batch dimension removed) by tensor name."""
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pixels = np.asarray(image_rgb, np.float32) / np.float32(255)  # The models expect RGB in [0, 1]
        self._interpreter.set_tensor(self._input, pixels[np.newaxis])
        self._interpreter.invoke()
        return {
            name: self._interpreter.get_tensor(index)[0].astype(np.float64) for name, index in self._outputs.items()
        }


def _palm_anchors() -> Points:
    """Normalised SSD anchor centres of the palm detector, in output order (MediaPipe's anchor config)."""
    centres: list[tuple[float, float]] = []
    for stride, anchors_per_cell in ((8, 2), (16, 6)):
        cells = PALM_INPUT_SIZE // stride
        for y in range(cells):
            for x in range(cells):
                centres += [((x + 0.5) / cells, (y + 0.5) / cells)] * anchors_per_cell
    return np.array(centres)


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


@final
class HandTracker:
    """Tracks one hand across video frames."""

    def __init__(self, palm_model: Path, landmark_model: Path) -> None:
        self._palm_model = _Model(palm_model)
        self._landmark_model = _Model(landmark_model)
        self._anchors = _palm_anchors()
        self._roi: Roi | None = None  # Where the hand was last frame
        self._velocity = np.zeros(2)  # Of the hand's centre, in pixels/second
        self._timestamp = 0.0
        # Confidences from the last frame, for debugging; None if that model didn't run
        self.palm_score: float | None = None
        self.presence: float | None = None

    def track(self, frame_bgr: MatLike, timestamp: float) -> Points | None:
        """Return the hand's 21 landmarks in frame pixels, or None if no hand is visible.

        `timestamp` is the frame's capture time in seconds, used to predict where a moving hand went.
        """
        landmarks = self.palm_score = self.presence = None
        if self._roi is not None:
            # Look where the hand should be now if it kept moving at the same speed
            predicted = replace(self._roi, centre=self._roi.centre + self._velocity * (timestamp - self._timestamp))
            landmarks = self._detect_landmarks(frame_bgr, predicted)

        if landmarks is None and (palm := self._detect_palm(frame_bgr)) is not None:
            # Lost (or never had) the hand: search the whole frame
            self._roi, self._velocity = None, np.zeros(2)
            landmarks = self._detect_landmarks(frame_bgr, palm)

        if landmarks is None:
            self._roi = None
            return None

        roi = self._roi_from_landmarks(landmarks)
        if self._roi is not None and timestamp > self._timestamp:
            self._velocity = (roi.centre - self._roi.centre) / (timestamp - self._timestamp)

        self._roi, self._timestamp = roi, timestamp
        return landmarks

    def _detect_palm(self, frame_bgr: MatLike) -> Roi | None:
        # Letterbox to a square so the detector sees undistorted proportions
        height, width = frame_bgr.shape[:2]
        side = max(height, width)
        top, left = (side - height) // 2, (side - width) // 2
        square = cv2.copyMakeBorder(frame_bgr, top, side - height - top, left, side - width - left, cv2.BORDER_CONSTANT)
        outputs = self._palm_model.run(cv2.resize(square, (PALM_INPUT_SIZE, PALM_INPUT_SIZE)))
        boxes, scores = outputs["Identity"], outputs["Identity_1"][:, 0]

        best = int(np.argmax(scores))
        self.palm_score = _sigmoid(float(scores[best]))
        if self.palm_score < MIN_PALM_SCORE:
            return None

        # Box: centre offset from its anchor, size, then 7 keypoint offsets, all in input pixels
        box = boxes[best].reshape(-1, 2) / PALM_INPUT_SIZE
        anchor = self._anchors[best]
        to_frame = np.array([left, top])
        centre = (box[0] + anchor) * side - to_frame
        width_px, height_px = box[1] * side
        keypoints = (box[2:] + anchor) * side - to_frame

        angle = _angle(keypoints[PALM_KEYPOINT_WRIST], keypoints[PALM_KEYPOINT_MIDDLE_FINGER_BASE])
        return Roi.around(centre, float(width_px), float(height_px), angle, PALM_ROI_SCALE, PALM_ROI_SHIFT)

    def _detect_landmarks(self, frame_bgr: MatLike, roi: Roi) -> Points | None:
        """Return the landmarks of the hand inside `roi`, or None if there is no hand there."""
        crop_to_frame = roi.crop_to_frame(LANDMARK_INPUT_SIZE)
        crop = cv2.warpAffine(
            frame_bgr,
            crop_to_frame,
            (LANDMARK_INPUT_SIZE, LANDMARK_INPUT_SIZE),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        )

        outputs = self._landmark_model.run(crop)
        self.presence = float(outputs["Identity_1"][0])
        if self.presence < MIN_HAND_PRESENCE:
            return None

        landmarks_crop = outputs["Identity"].reshape(21, 3)[:, :2]  # Drop depth
        return landmarks_crop @ crop_to_frame[:, :2].T + crop_to_frame[:, 2]

    @staticmethod
    def _roi_from_landmarks(landmarks: Points) -> Roi:
        angle = _angle(landmarks[WRIST], landmarks[MIDDLE_FINGER_BASE])
        rotation = _rotation(angle)

        # Bounding box in the hand's own (rotated) frame
        aligned = landmarks[ROI_LANDMARKS] @ rotation
        low, high = aligned.min(axis=0), aligned.max(axis=0)
        centre = rotation @ ((low + high) / 2)
        width, height = high - low

        return Roi.around(centre, float(width), float(height), angle, LANDMARK_ROI_SCALE, LANDMARK_ROI_SHIFT)


def draw_hand(frame_bgr: MatLike, landmarks: Points) -> None:
    """Draw a hand's skeleton onto the frame, in place."""
    points = [(round(x), round(y)) for x, y in landmarks]

    for start, end in HAND_CONNECTIONS:
        _ = cv2.line(frame_bgr, points[start], points[end], CONNECTION_COLOUR, 2)

    for point in points:
        _ = cv2.circle(frame_bgr, point, 4, LANDMARK_COLOUR, -1)
