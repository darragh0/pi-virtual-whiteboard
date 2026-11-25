import os
import urllib.request
from pathlib import Path
from typing import Final

MODEL_URL: Final = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "virtual-whiteboard"


def ensure_model() -> Path:
    """Return the local hand landmarker model path, downloading it on first use."""
    path = _cache_dir() / "hand_landmarker.task"
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")

    print(f"Downloading hand landmarker model to {path} ...")
    _ = urllib.request.urlretrieve(MODEL_URL, partial)
    _ = partial.rename(path)

    return path
