from typing import Final, final

from cv2.typing import MatLike
from libcamera import Transform
from picamera2 import Picamera2

FRAME_SIZE: Final = (640, 480)


@final
class PiCamera:
    """The Raspberry Pi CSI camera."""

    def __init__(self) -> None:
        self._camera = Picamera2()
        config = self._camera.create_video_configuration(
            # libcamera's "RGB888" is BGR byte order in memory, i.e. what OpenCV expects
            main={"size": FRAME_SIZE, "format": "RGB888"},
            transform=Transform(hflip=1),  # Mirror so on-screen movement matches the user's
        )
        self._camera.configure(config)
        self._camera.start()

    def capture(self) -> MatLike:
        """Return the newest BGR frame."""
        return self._camera.capture_array()

    def close(self) -> None:
        self._camera.stop()
        self._camera.close()
