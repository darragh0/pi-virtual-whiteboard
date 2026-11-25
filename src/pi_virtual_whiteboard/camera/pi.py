from typing import TYPE_CHECKING, Final, final

from cv2.typing import MatLike
from libcamera import Transform, controls
from picamera2 import Picamera2

from pi_virtual_whiteboard.config import FLICKER_PERIOD_US, FRAME_SIZE, MAX_EXPOSURE_US, MAX_GAIN

if TYPE_CHECKING:
    from picamera2 import Tuning  # Stub-only alias


# 2x2-binned: each pixel averages 4 sensor pixels, so much less noise; the ISP scales it to FRAME_SIZE
SENSOR_SIZE: Final = (1296, 972)
SENSOR_FPS: Final = 46  # This mode's max: less time between frames means less lag


def _tuning() -> "Tuning":
    tuning = Picamera2.load_tuning_file("ov5647.json")
    for channel in Picamera2.find_tuning_algo(tuning, "rpi.agc")["channels"]:
        for mode in channel["exposure_modes"].values():
            mode["gain"][-1] = MAX_GAIN
            mode["shutter"] = [min(shutter, MAX_EXPOSURE_US) for shutter in mode["shutter"]]
    return tuning


@final
class PiCamera:
    """The Raspberry Pi CSI camera (OV5647 sensor)."""

    def __init__(self) -> None:
        self._camera = Picamera2(tuning=_tuning())
        config = self._camera.create_video_configuration(
            # libcamera's "RGB888" is BGR byte order in memory, i.e. what OpenCV expects
            main={"size": FRAME_SIZE, "format": "RGB888"},
            sensor={"output_size": SENSOR_SIZE},
            transform=Transform(hflip=1),  # Mirror so on-screen movement matches the user's
            controls={
                "FrameRate": SENSOR_FPS,
                "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.HighQuality,
                "AeFlickerMode": controls.AeFlickerModeEnum.Manual,
                "AeFlickerPeriod": FLICKER_PERIOD_US,
            },
        )
        self._camera.configure(config)
        self._camera.start()

    def capture(self) -> MatLike:
        """Return the newest BGR frame."""
        return self._camera.capture_array()

    def close(self) -> None:
        self._camera.stop()
        self._camera.close()
