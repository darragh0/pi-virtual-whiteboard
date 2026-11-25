import shutil
import subprocess
import threading
from typing import IO, Final, cast, final

import cv2
import numpy as np
from cv2.typing import MatLike

from virtual_whiteboard.latest_frame import LatestFrame

FRAME_WIDTH: Final = 640
FRAME_HEIGHT: Final = 480
FRAMERATE: Final = 30
_FRAME_BYTES: Final = FRAME_WIDTH * FRAME_HEIGHT * 3 // 2  # YUV420


@final
class PiCamera:
    """The Raspberry Pi CSI camera, read as raw YUV420 frames from `rpicam-vid`.

    Uses the CLI rather than picamera2 since picamera2 is only packaged for the
    system Python (3.13), which mediapipe has no Pi 4-compatible wheels for.
    """

    def __init__(self) -> None:
        if (rpicam_vid := shutil.which("rpicam-vid")) is None:
            msg = "rpicam-vid not found (run `apt install rpicam-apps`)"
            raise RuntimeError(msg)

        # Width 640 is a multiple of the ISP's row alignment, so rows carry no padding
        self._process = subprocess.Popen(  # noqa: S603 -- fixed argv, no user input
            [
                rpicam_vid,
                *("--timeout", "0"),
                "--nopreview",
                "--hflip",  # Mirror so on-screen movement matches the user's
                *("--width", str(FRAME_WIDTH)),
                *("--height", str(FRAME_HEIGHT)),
                *("--framerate", str(FRAMERATE)),
                *("--codec", "yuv420"),
                "--flush",
                *("--output", "-"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        stdout = cast("IO[bytes]", self._process.stdout)  # Never None as long as stdout=PIPE is set above

        # Drain pipe continuously so a slow consumer gets the newest frame, not a backlog
        self._frames = LatestFrame()
        self._seen = 0
        self._reader = threading.Thread(target=self._drain, args=(stdout,), daemon=True)
        self._reader.start()

    def _drain(self, stdout: IO[bytes]) -> None:
        while len(data := stdout.read(_FRAME_BYTES)) == _FRAME_BYTES:
            self._frames.publish(data)

        self._frames.close()

    def read(self) -> MatLike | None:
        """Return the newest BGR frame, or None if the camera stopped."""
        if (latest := self._frames.wait_newer(self._seen)) is None:
            return None

        self._seen, data = latest
        yuv = np.frombuffer(data, dtype=np.uint8).reshape(FRAME_HEIGHT * 3 // 2, FRAME_WIDTH)

        return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)

    def close(self) -> None:
        self._process.terminate()
        _ = self._process.wait()
        self._reader.join()
