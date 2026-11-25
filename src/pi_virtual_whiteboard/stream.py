import threading
from collections.abc import Mapping
from contextlib import suppress
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Final, final, override

import cv2
from cv2.typing import MatLike

from pi_virtual_whiteboard.config import JPEG_QUALITY

# The page and its files, served as-is. Read on every request, so edits show on a browser refresh
WEB_DIR: Final = (Path(__file__).parent / "web").resolve()
CONTENT_TYPES: Final = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


def web_file(url_path: str) -> tuple[bytes, str] | None:
    """Return the contents and content type of the page's file at `url_path`, or None if there's no such file.

    Only files inside WEB_DIR are served, so a path like /../config.py can't reach the rest of the app.
    """
    file = (WEB_DIR / (url_path.lstrip("/") or "index.html")).resolve()
    if not file.is_relative_to(WEB_DIR) or not file.is_file() or file.suffix not in CONTENT_TYPES:
        return None
    return file.read_bytes(), CONTENT_TYPES[file.suffix]


@final
class FrameServer:
    """Serves the newest frame to any browser, one JPEG per request."""

    def __init__(self, host: str, port: int) -> None:
        self._frame: MatLike | None = None
        self._captured = 0.0  # Unix time the frame was captured
        self._hand = ""  # JSON describing the hand found in the frame, published with it
        self._closed = False
        self._new_frame = threading.Condition()
        self._server = ThreadingHTTPServer((host, port), self._handler_class())
        self._server.daemon_threads = True

        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def _wait_for_frame(self) -> tuple[MatLike, float, str] | None:
        """Block until a new frame is published and return it with its capture time and hand; None once closed."""
        with self._new_frame:
            self._new_frame.wait()
            return None if self._closed or self._frame is None else (self._frame, self._captured, self._hand)

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version: str = "HTTP/1.1"  # Keep-alive: reuse one connection for every frame

            def do_GET(self) -> None:
                path = self.path.split("?")[0]
                if path == "/frame":
                    self._send_frame()
                elif (file := web_file(path)) is not None:
                    self._send(*file)
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)

            def _send_frame(self) -> None:
                if (latest := server._wait_for_frame()) is None:
                    self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)
                    return

                frame, captured, hand = latest

                # Encoded here, off the tracking thread, so it doesn't add to the tracking loop's time
                ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ok:
                    self._send(jpeg.tobytes(), "image/jpeg", {"X-Captured": f"{captured:.3f}", "X-Hand": hand})
                else:
                    self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)

            def _send(self, body: bytes, content_type: str, headers: Mapping[str, str] | None = None) -> None:
                with suppress(BrokenPipeError, ConnectionResetError):  # Viewer closed the tab
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    for name, value in (headers or {}).items():
                        self.send_header(name, value)
                    self.end_headers()
                    self.wfile.write(body)

            @override
            def log_message(self, format: str, *args: object) -> None:
                pass  # Silence per-request logging

        return Handler

    def publish(self, frame: MatLike, captured: float, hand: str) -> None:
        """Send a BGR frame captured at Unix time `captured` to viewers, with the hand found in it as JSON.

        The caller must not modify the frame afterwards.
        """
        with self._new_frame:
            self._frame, self._captured, self._hand = frame, captured, hand
            self._new_frame.notify_all()

    def close(self) -> None:
        with self._new_frame:
            self._closed = True
            self._new_frame.notify_all()
        self._server.shutdown()
        self._server.server_close()
