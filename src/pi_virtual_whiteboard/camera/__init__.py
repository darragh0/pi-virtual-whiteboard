"""Video sources: the Pi's camera, or a webcam for developing on a laptop without the Pi."""

from typing import Protocol

from cv2.typing import MatLike

from pi_virtual_whiteboard.cli import Args


class Camera(Protocol):
    def capture(self) -> MatLike:
        """Return the newest BGR frame, mirrored so on-screen movement matches the user's."""
        ...

    def close(self) -> None: ...


def open_camera(args: Args) -> Camera:
    # Imported only when chosen: picamera2/libcamera exist only on the Pi
    if args.camera == "webcam":
        from pi_virtual_whiteboard.camera.webcam import Webcam  # noqa: PLC0415

        return Webcam(args.webcam)

    from pi_virtual_whiteboard.camera.pi import PiCamera  # noqa: PLC0415

    return PiCamera(args.prefer)
