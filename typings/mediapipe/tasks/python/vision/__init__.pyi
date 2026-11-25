import enum
from dataclasses import dataclass
from typing import ClassVar, Self

from mediapipe import Image
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.components.containers.landmark import NormalizedLandmark

class RunningMode(enum.Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    LIVE_STREAM = "LIVE_STREAM"

class HandLandmarksConnections:
    @dataclass
    class Connection:
        start: int
        end: int

    HAND_CONNECTIONS: ClassVar[list[Connection]]

@dataclass
class HandLandmarkerResult:
    hand_landmarks: list[list[NormalizedLandmark]]

@dataclass
class HandLandmarkerOptions:
    base_options: BaseOptions
    running_mode: RunningMode = RunningMode.IMAGE  # noqa: PYI015  # `...` would infer Any
    num_hands: int = 1

class HandLandmarker:
    @classmethod
    def create_from_options(cls, options: HandLandmarkerOptions) -> Self: ...
    def detect_for_video(self, image: Image, timestamp_ms: int) -> HandLandmarkerResult: ...
    def close(self) -> None: ...
