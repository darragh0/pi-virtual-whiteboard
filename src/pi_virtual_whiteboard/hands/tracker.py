"""Hand tracking with MediaPipe's palm detection and hand landmark models, run directly on LiteRT.

Follows MediaPipe's own pipeline, without the mediapipe package (which crashes on the Pi 4):
- The slow palm detector runs only while no hand is tracked
- Otherwise each frame's landmarks give the crop for the next, so only the fast landmark model runs
"""

import math
from dataclasses import dataclass, replace
from typing import Final, final

import cv2
import numpy as np
from cv2.typing import MatLike

from pi_virtual_whiteboard.config import LANDMARK_MODEL, MIN_HAND_PRESENCE, MIN_PALM_SCORE, PALM_MODEL
from pi_virtual_whiteboard.hands.landmarks import HandLandmark
from pi_virtual_whiteboard.hands.model import Model
from pi_virtual_whiteboard.hands.roi import Points, Roi, angle_towards, rotation

PALM_INPUT_SIZE: Final = 192
LANDMARK_INPUT_SIZE: Final = 224

# Crop placement, from MediaPipe's hand landmark graph configs
PALM_ROI_SCALE: Final = 2.6
PALM_ROI_SHIFT: Final = -0.5
LANDMARK_ROI_SCALE: Final = 2.0
LANDMARK_ROI_SHIFT: Final = -0.1
# Wrist + finger bases: they barely move as the fingers bend, so the crop stays steady
ROI_LANDMARKS: Final = [
    HandLandmark.WRIST,
    *(HandLandmark.THUMB_CMC, HandLandmark.THUMB_MCP, HandLandmark.THUMB_IP),
    *(HandLandmark.INDEX_FINGER_MCP, HandLandmark.INDEX_FINGER_PIP),
    *(HandLandmark.MIDDLE_FINGER_MCP, HandLandmark.MIDDLE_FINGER_PIP),
    *(HandLandmark.RING_FINGER_MCP, HandLandmark.RING_FINGER_PIP),
    *(HandLandmark.PINKY_MCP, HandLandmark.PINKY_PIP),
]

# The palm detector's own keypoints (7, separate from the 21 hand landmarks)
PALM_KEYPOINT_WRIST: Final = 0
PALM_KEYPOINT_MIDDLE_FINGER_BASE: Final = 2


@dataclass(frozen=True)
class TrackResult:
    landmarks: Points | None
    """The hand's 21 landmarks in frame pixels, or None if no hand is visible."""
    palm_score: float | None = None
    """Palm detector confidence, or None if it didn't need to run."""
    presence: float | None = None
    """Landmark model's confidence that its crop holds a hand."""


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


def _roi_from_landmarks(landmarks: Points) -> Roi:
    angle = angle_towards(landmarks[HandLandmark.WRIST], landmarks[HandLandmark.MIDDLE_FINGER_MCP])
    hand_rotation = rotation(angle)

    # Bounding box in the hand's own (rotated) frame
    aligned = landmarks[ROI_LANDMARKS] @ hand_rotation
    low, high = aligned.min(axis=0), aligned.max(axis=0)
    centre = hand_rotation @ ((low + high) / 2)
    width, height = high - low

    return Roi.around(centre, float(width), float(height), angle, LANDMARK_ROI_SCALE, LANDMARK_ROI_SHIFT)


@final
class HandTracker:
    """Tracks one hand across video frames."""

    def __init__(self) -> None:
        self._palm_model = Model(PALM_MODEL)
        self._landmark_model = Model(LANDMARK_MODEL)
        self._anchors = _palm_anchors()
        self._roi: Roi | None = None  # Where the hand was last frame
        self._velocity = np.zeros(2)  # Of the hand's centre, in pixels/second
        self._timestamp = 0.0

    def track(self, frame_bgr: MatLike, timestamp: float) -> TrackResult:
        """Find the hand in a frame captured at `timestamp` seconds (used to predict where a moving hand went)."""
        landmarks = presence = palm_score = None
        if self._roi is not None:
            # Look where the hand should be now if it kept moving at the same speed
            predicted = replace(self._roi, centre=self._roi.centre + self._velocity * (timestamp - self._timestamp))
            landmarks, presence = self._detect_landmarks(frame_bgr, predicted)

        if landmarks is None:
            # Lost (or never had) the hand: search the whole frame
            self._roi, self._velocity = None, np.zeros(2)
            palm, palm_score = self._detect_palm(frame_bgr)

            if palm is not None:
                landmarks, presence = self._detect_landmarks(frame_bgr, palm)

        if landmarks is None:
            return TrackResult(None, palm_score, presence)

        roi = _roi_from_landmarks(landmarks)
        if self._roi is not None and timestamp > self._timestamp:
            self._velocity = (roi.centre - self._roi.centre) / (timestamp - self._timestamp)

        self._roi, self._timestamp = roi, timestamp
        return TrackResult(landmarks, palm_score, presence)

    def _detect_palm(self, frame_bgr: MatLike) -> tuple[Roi | None, float]:
        """Return a crop around the most likely palm (None if not likely enough) and its score."""

        # Letterbox to a square so the detector sees undistorted proportions
        height, width = frame_bgr.shape[:2]
        side = max(height, width)
        top, left = (side - height) // 2, (side - width) // 2
        square = cv2.copyMakeBorder(frame_bgr, top, side - height - top, left, side - width - left, cv2.BORDER_CONSTANT)
        boxes, scores = self._palm_model.run(cv2.resize(square, (PALM_INPUT_SIZE, PALM_INPUT_SIZE)))

        best = int(np.argmax(scores))
        score = _sigmoid(float(scores[best, 0]))
        if score < MIN_PALM_SCORE:
            return None, score

        # Box: centre offset from its anchor, size, then 7 keypoint offsets, all in input pixels
        box = boxes[best].reshape(-1, 2) / PALM_INPUT_SIZE
        anchor = self._anchors[best]
        to_frame = np.array([left, top])
        centre = (box[0] + anchor) * side - to_frame
        box_width, box_height = box[1] * side
        keypoints = (box[2:] + anchor) * side - to_frame

        angle = angle_towards(keypoints[PALM_KEYPOINT_WRIST], keypoints[PALM_KEYPOINT_MIDDLE_FINGER_BASE])
        roi = Roi.around(centre, float(box_width), float(box_height), angle, PALM_ROI_SCALE, PALM_ROI_SHIFT)

        return roi, score

    def _detect_landmarks(self, frame_bgr: MatLike, roi: Roi) -> tuple[Points | None, float]:
        """Return the landmarks of the hand inside `roi` (None if there's no hand there) and the presence score."""
        crop_to_frame = roi.crop_to_frame(LANDMARK_INPUT_SIZE)
        crop = cv2.warpAffine(
            frame_bgr,
            crop_to_frame,
            (LANDMARK_INPUT_SIZE, LANDMARK_INPUT_SIZE),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        )

        landmarks_crop, presence, _handedness, _world_landmarks = self._landmark_model.run(crop)
        score = float(presence[0])
        if score < MIN_HAND_PRESENCE:
            return None, score

        landmarks_px = landmarks_crop.reshape(21, 3)[:, :2]  # Drop depth
        return landmarks_px @ crop_to_frame[:, :2].T + crop_to_frame[:, 2], score
