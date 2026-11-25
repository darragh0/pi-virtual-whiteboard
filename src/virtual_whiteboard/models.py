import os
import urllib.request
from pathlib import Path
from typing import Final

_BASE_URL: Final = "https://storage.googleapis.com/mediapipe-assets"


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "virtual-whiteboard"


def ensure_model(name: str) -> Path:
    """Return the local path of a MediaPipe `.tflite` model, downloading it on first use."""
    path = _cache_dir() / f"{name}.tflite"
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")

    print(f"Downloading {name} to {path} ...")
    _ = urllib.request.urlretrieve(f"{_BASE_URL}/{name}.tflite", partial)  # noqa: S310 -- fixed https URL
    _ = partial.rename(path)

    return path
