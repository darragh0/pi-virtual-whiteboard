"""Video sources: the Pi's camera, or a webcam for developing on a laptop without the Pi."""

import os
from pathlib import Path
from typing import Final, Protocol

from cv2.typing import MatLike

from pi_virtual_whiteboard.cli import Args

_MODEL_FILE: Final = Path("/proc/device-tree/model")
ON_PI: Final = _MODEL_FILE.exists() and "Raspberry Pi" in _MODEL_FILE.read_text(errors="ignore")


class Camera(Protocol):
    def capture(self) -> MatLike:
        """Return the newest BGR frame, mirrored so on-screen movement matches the user's."""
        ...

    def close(self) -> None: ...


def open_camera(args: Args) -> Camera:
    # Imported only when chosen: picamera2/libcamera exist only on the Pi
    if not ON_PI:
        from pi_virtual_whiteboard.camera.webcam import Webcam  # noqa: PLC0415

        return Webcam(args.webcam)

    os.environ.setdefault("LIBCAMERA_LOG_LEVELS", "WARN")  # Its INFO logs are noise; read when it's imported
    from pi_virtual_whiteboard.camera.pi import PiCamera  # noqa: PLC0415

    return PiCamera(args.prefer)
