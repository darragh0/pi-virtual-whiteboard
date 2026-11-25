from collections.abc import Mapping
from typing import Any, Literal, TypedDict

import numpy as np
import numpy.typing as npt
from libcamera import Transform

class StreamConfig(TypedDict, total=False):
    size: tuple[int, int]
    format: Literal["RGB888", "BGR888", "XRGB8888", "XBGR8888", "YUV420"]

type Tuning = dict[str, Any]  # pyright: ignore[reportExplicitAny] -- parsed JSON, arbitrarily nested

class Picamera2:
    def __init__(self, camera_num: int = 0, tuning: Tuning | None = None) -> None: ...
    @staticmethod
    def load_tuning_file(tuning_file: str) -> Tuning: ...
    @staticmethod
    def find_tuning_algo(tuning: Tuning, name: str) -> Tuning: ...
    def create_video_configuration(
        self,
        main: StreamConfig = ...,
        transform: Transform = ...,
        controls: Mapping[str, object] = ...,
    ) -> dict[str, object]: ...
    def configure(self, camera_config: dict[str, object]) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
    def capture_array(self, name: str = "main") -> npt.NDArray[np.uint8]: ...
