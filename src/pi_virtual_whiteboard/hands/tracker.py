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

from pi_virtual_whiteboard.cli import Hand
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


MAX_PALMS: Final = 2  # With both hands in view, the second palm is tried when the first is the wrong hand


@dataclass(frozen=True)
class TrackResult:
    landmarks: Points | None
    """The hand's 21 landmarks in frame pixels, or None if no hand is visible."""
    world_landmarks: Points | None = None
    """The same 21 landmarks in 3D, in metres around the hand's centre: its true shape, whichever way it faces.

    Not turned to match the frame (they're in the crop's orientation), so only distances between them mean anything.
    """
    hand: Hand | None = None
    """Which hand it is."""
    palm_score: float | None = None
    """Best palm detector confidence, or None if it didn't need to run."""
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
    """Tracks one hand (left or right) across video frames."""

    def __init__(self, hand: Hand) -> None:
        self._hand = hand
        self._palm_model = Model(PALM_MODEL)
        self._landmark_model = Model(LANDMARK_MODEL)
        self._anchors = _palm_anchors()
        self._roi: Roi | None = None  # Where the hand was last frame
        self._velocity = np.zeros(2)  # Of the hand's centre, in pixels/second
        self._timestamp = 0.0

    def track(self, frame_bgr: MatLike, timestamp: float) -> TrackResult:
        """Find the hand in a frame captured at `timestamp` seconds (used to predict where a moving hand went)."""
        found = presence = palm_score = None
        if self._roi is not None:
            # Look where the hand should be now if it kept moving at the same speed
            predicted = replace(self._roi, centre=self._roi.centre + self._velocity * (timestamp - self._timestamp))
            # No handedness check while following: a wavering guess mid-track would just drop the hand
            found, presence = self._detect_landmarks(frame_bgr, predicted, check_hand=False)

        if found is None:
            # Lost (or never had) the hand: search the whole frame
            self._roi, self._velocity = None, np.zeros(2)
            palms, palm_score = self._detect_palms(frame_bgr)
            for palm in palms:
                found, presence = self._detect_landmarks(frame_bgr, palm, check_hand=True)
                if found is not None:
                    break

        if found is None:
            return TrackResult(None, None, None, palm_score, presence)

        landmarks, world_landmarks, hand = found
        roi = _roi_from_landmarks(landmarks)
        if self._roi is not None and timestamp > self._timestamp:
            self._velocity = (roi.centre - self._roi.centre) / (timestamp - self._timestamp)

        self._roi, self._timestamp = roi, timestamp
        return TrackResult(landmarks, world_landmarks, hand, palm_score, presence)

    def _detect_palms(self, frame_bgr: MatLike) -> tuple[list[Roi], float]:
        """Return crops around the likeliest palms (best first, up to MAX_PALMS) and the best palm score."""

        # Letterbox to a square so the detector sees undistorted proportions
        height, width = frame_bgr.shape[:2]
        side = max(height, width)
        top, left = (side - height) // 2, (side - width) // 2
        square = cv2.copyMakeBorder(frame_bgr, top, side - height - top, left, side - width - left, cv2.BORDER_CONSTANT)
        boxes, scores = self._palm_model.run(cv2.resize(square, (PALM_INPUT_SIZE, PALM_INPUT_SIZE)))

        order = np.argsort(scores[:, 0])[::-1]
        palms: list[Roi] = []
        for index in order:
            if _sigmoid(float(scores[index, 0])) < MIN_PALM_SCORE or len(palms) == MAX_PALMS:
                break

            # Box: centre offset from its anchor, size, then 7 keypoint offsets, all in input pixels
            box = boxes[index].reshape(-1, 2) / PALM_INPUT_SIZE
            anchor = self._anchors[index]
            to_frame = np.array([left, top])
            centre = (box[0] + anchor) * side - to_frame
            box_width, box_height = box[1] * side
            keypoints = (box[2:] + anchor) * side - to_frame

            angle = angle_towards(keypoints[PALM_KEYPOINT_WRIST], keypoints[PALM_KEYPOINT_MIDDLE_FINGER_BASE])
            roi = Roi.around(centre, float(box_width), float(box_height), angle, PALM_ROI_SCALE, PALM_ROI_SHIFT)

            # Neighbouring anchors fire for the same palm: skip detections centred on one already kept
            if all(np.linalg.norm(roi.centre - kept.centre) > kept.size / 2 for kept in palms):
                palms.append(roi)

        return palms, _sigmoid(float(scores[order[0], 0]))

    def _detect_landmarks(
        self, frame_bgr: MatLike, roi: Roi, *, check_hand: bool
    ) -> tuple[tuple[Points, Points, Hand] | None, float]:
        """Return the hand inside `roi` (None if absent, or the wrong hand when `check_hand`) and its presence."""
        crop_to_frame = roi.crop_to_frame(LANDMARK_INPUT_SIZE)
        crop = cv2.warpAffine(
            frame_bgr,
            crop_to_frame,
            (LANDMARK_INPUT_SIZE, LANDMARK_INPUT_SIZE),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        )

        landmarks_crop, presence, left_hand, world_landmarks = self._landmark_model.run(crop)
        # The model's handedness assumes a mirrored (selfie-view) image, which is what our camera gives
        hand: Hand = "left" if left_hand[0] > 0.5 else "right"  # noqa: PLR2004 -- a probability
        score = float(presence[0])
        if score < MIN_HAND_PRESENCE or (check_hand and hand != self._hand):
            return None, score

        landmarks_px = landmarks_crop.reshape(21, 3)[:, :2]  # Drop depth
        landmarks_frame = landmarks_px @ crop_to_frame[:, :2].T + crop_to_frame[:, 2]
        return (landmarks_frame, world_landmarks.reshape(21, 3), hand), score
