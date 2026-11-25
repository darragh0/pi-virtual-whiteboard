from typing import Final

from virtual_whiteboard.camera import PiCamera
from virtual_whiteboard.model import ensure_model
from virtual_whiteboard.stream import MjpegStream
from virtual_whiteboard.tracking import HandTracker, draw_hands

# Localhost only: scripts/pi.sh forwards the port to the laptop over SSH
STREAM_HOST: Final = "127.0.0.1"
STREAM_PORT: Final = 8000


def main() -> None:
    camera = PiCamera()
    stream = MjpegStream(STREAM_HOST, STREAM_PORT)
    model = ensure_model()

    try:
        with HandTracker(model) as tracker:
            while (frame := camera.read()) is not None:
                draw_hands(frame, tracker.detect(frame))
                stream.publish(frame)

    except KeyboardInterrupt:
        pass

    finally:
        stream.close()
        camera.close()
