import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final, final, override

import cv2
from cv2.typing import MatLike

from virtual_whiteboard.latest_frame import LatestFrame

BOUNDARY: Final = "frame"
JPEG_QUALITY: Final = 90

# Shows the stream scaled up to most of the browser window (the browser does the scaling, not the Pi)
PAGE: Final = b"""<!doctype html>
<title>Virtual Whiteboard</title>
<style>
  html, body { margin: 0; height: 100%; background: #111; }
  body { display: flex; align-items: center; justify-content: center; }
  img { height: 75vh; max-width: 95vw; object-fit: contain; }
</style>
<img src="/stream" alt="Camera stream">
"""


@final
class MjpegStream:
    """Serves frames as an MJPEG stream over HTTP, viewable in any browser."""

    def __init__(self, host: str, port: int) -> None:
        self._frames = LatestFrame()
        self._server = ThreadingHTTPServer((host, port), self._handler_class())
        self._server.daemon_threads = True

        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        frames = self._frames

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                match self.path:
                    case "/":
                        self._send_page()
                    case "/stream":
                        self._send_stream()
                    case _:
                        self.send_error(HTTPStatus.NOT_FOUND)

            def _send_page(self) -> None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(PAGE)))
                self.end_headers()
                _ = self.wfile.write(PAGE)

            def _send_stream(self) -> None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                seen = 0

                try:
                    while (latest := frames.wait_newer(seen)) is not None:
                        seen, frame = latest
                        # Encoded here, off the tracking thread, so it doesn't add to the tracking loop's time
                        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                        if not ok:
                            continue

                        jpeg = encoded.tobytes()
                        _ = self.wfile.write(
                            f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n".encode()
                        )
                        _ = self.wfile.write(jpeg + b"\r\n")

                except (BrokenPipeError, ConnectionResetError):
                    pass  # Viewer closed the tab

            @override
            def log_message(self, format: str, *args: object) -> None:
                pass  # Silence per-request logging

        return Handler

    def publish(self, frame: MatLike) -> None:
        """Send a BGR frame to viewers. The caller must not modify it afterwards."""
        self._frames.publish(frame)

    def close(self) -> None:
        self._frames.close()
        self._server.shutdown()
        self._server.server_close()
