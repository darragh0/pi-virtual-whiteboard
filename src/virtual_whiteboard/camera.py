from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, final

from cv2.typing import MatLike
from libcamera import Transform, controls
from picamera2 import Picamera2

if TYPE_CHECKING:
    from picamera2 import Tuning  # Stub-only alias

type Preference = Literal["quality", "speed"]
PREFERENCES: Final[tuple[Preference, ...]] = ("quality", "speed")

FRAME_SIZE: Final = (640, 480)


@dataclass(frozen=True)
class _SensorMode:
    size: tuple[int, int]
    max_fps: int  # Less time between frames means less lag and motion blur


SENSOR_MODES: Final[dict[Preference, _SensorMode]] = {
    # 2x2-binned: each pixel averages 4 sensor pixels, so much less noise; the ISP scales it to FRAME_SIZE
    "quality": _SensorMode((1296, 972), 46),
    # Skips pixels instead of averaging them: grainier, but ~5 ms less lag
    "speed": _SensorMode((640, 480), 60),
}

# Mains lighting pulses at twice the 50 Hz grid frequency (Ireland/EU); exposures in multiples of
# this period stop it showing as bands rolling down the image
FLICKER_PERIOD_US: Final = 10_000
# Auto-exposure's gain cap, raised from the default 8 to the sensor's max so fast frames stay bright
# enough indoors (at the cost of some noise, which denoising and landmark smoothing absorb)
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

    def __init__(self, prefer: Preference) -> None:
        mode = SENSOR_MODES[prefer]
        self._camera = Picamera2(tuning=_tuning())
        config = self._camera.create_video_configuration(
            # libcamera's "RGB888" is BGR byte order in memory, i.e. what OpenCV expects
            main={"size": FRAME_SIZE, "format": "RGB888"},
            sensor={"output_size": mode.size},
            transform=Transform(hflip=1),  # Mirror so on-screen movement matches the user's
            controls={
                "FrameRate": mode.max_fps,
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
