import enum

import numpy as np
import numpy.typing as npt

class ImageFormat(enum.IntEnum):
    SRGB = 1

class Image:
    def __init__(self, image_format: ImageFormat, data: npt.NDArray[np.uint8]) -> None: ...
