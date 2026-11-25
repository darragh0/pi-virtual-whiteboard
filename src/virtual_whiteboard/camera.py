from typing import TYPE_CHECKING, Final, final

from cv2.typing import MatLike
from libcamera import Transform
from picamera2 import Picamera2

if TYPE_CHECKING:
    from picamera2 import Tuning  # Stub-only alias

FRAME_SIZE: Final = (640, 480)
# The sensor's fastest mode at this size: less time between frames means less lag and motion blur
FRAME_RATE: Final = 60
# Auto-exposure's gain cap, raised from the default 8 to the sensor's max so 60 fps stays bright
# enough indoors (at the cost of some noise, which the landmark smoothing absorbs)
MAX_GAIN: Final = 16.0


def _tuning() -> "Tuning":
    tuning = Picamera2.load_tuning_file("ov5647.json")
    for channel in Picamera2.find_tuning_algo(tuning, "rpi.agc")["channels"]:
        for mode in channel["exposure_modes"].values():
            mode["gain"][-1] = MAX_GAIN
    return tuning


@final
class PiCamera:
    """The Raspberry Pi CSI camera (OV5647 sensor)."""

    def __init__(self) -> None:
        self._camera = Picamera2(tuning=_tuning())
        config = self._camera.create_video_configuration(
            # libcamera's "RGB888" is BGR byte order in memory, i.e. what OpenCV expects
            main={"size": FRAME_SIZE, "format": "RGB888"},
            transform=Transform(hflip=1),  # Mirror so on-screen movement matches the user's
            controls={"FrameRate": FRAME_RATE},
        )
        self._camera.configure(config)
        self._camera.start()

    def capture(self) -> MatLike:
        """Return the newest BGR frame."""
        return self._camera.capture_array()

    def close(self) -> None:
        self._camera.stop()
        self._camera.close()
