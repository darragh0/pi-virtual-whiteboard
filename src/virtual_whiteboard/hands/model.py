import os
import urllib.request
from pathlib import Path
from typing import Final, final

import cv2
import numpy as np
import numpy.typing as npt
from ai_edge_litert.interpreter import Interpreter
from cv2.typing import MatLike

from virtual_whiteboard.config import NUM_THREADS

_BASE_URL: Final = "https://storage.googleapis.com/mediapipe-assets"

type Array = npt.NDArray[np.float64]


def _download(name: str) -> Path:
    """Return the local path of a MediaPipe `.tflite` model, downloading it on first use."""
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "virtual-whiteboard"
    path = cache / f"{name}.tflite"
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")

    print(f"Downloading {name} to {path} ...")
    urllib.request.urlretrieve(f"{_BASE_URL}/{name}.tflite", partial)  # noqa: S310 -- fixed https URL
    partial.rename(path)

    return path


@final
class Model:
    """A MediaPipe model that takes one RGB image, run on LiteRT."""

    def __init__(self, name: str) -> None:
        self._interpreter = Interpreter(model_path=str(_download(name)), num_threads=NUM_THREADS)
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]["index"]

        # MediaPipe's models name their outputs Identity, Identity_1, ...: that order is the documented one
        outputs = sorted(self._interpreter.get_output_details(), key=lambda output: output["name"])

        self._outputs = [output["index"] for output in outputs]

    def run(self, image_bgr: MatLike) -> list[Array]:
        """Run on one BGR image and return its outputs in order, batch dimension removed."""
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pixels = np.asarray(image_rgb, np.float32) / np.float32(255)  # The models expect RGB in [0, 1]

        self._interpreter.set_tensor(self._input, pixels[np.newaxis])
        self._interpreter.invoke()

        return [self._interpreter.get_tensor(index)[0].astype(np.float64) for index in self._outputs]
