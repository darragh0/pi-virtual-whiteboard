import threading
from contextlib import suppress
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final, final, override

import cv2
from cv2.typing import MatLike

from pi_virtual_whiteboard.config import JPEG_QUALITY

# Shows the video scaled up to most of the browser window (the browser does the scaling, not the Pi).
# The page asks for one frame at a time, and only once the last one has shown: frames can never queue up
# on a slow network, so the view stays live and the frame rate drops instead of lag building up
PAGE: Final = b"""<!doctype html>
<title>Virtual Whiteboard</title>
<style>
  html, body { margin: 0; height: 100%; background: #111; }
  body { display: flex; flex-direction: column; align-items: center; justify-content: center; }
  img { height: 75vh; max-width: 95vw; object-fit: contain; }
  p { color: #888; font: 14px monospace; }
</style>
<img alt="Camera stream">
<p>connecting...</p>
<script>
  // fetch() rather than setting img.src to the URL, so the browser doesn't flash "Waiting for localhost..."
  const img = document.querySelector("img");
  const stats = document.querySelector("p");
  let fps = 0, mbps = 0;  // Smoothed, so the numbers don't flicker
  (async () => {
    for (;;) {
      try {
        const start = performance.now();
        const frame = await (await fetch("/frame", { cache: "no-store" })).blob();
        const url = URL.createObjectURL(frame);
        img.src = url;
        await img.decode();
        URL.revokeObjectURL(url);

        // Received rate: if well below the fps on the video, the network is what's holding it back
        const seconds = (performance.now() - start) / 1000;
        fps = 0.9 * fps + 0.1 / seconds;
        mbps = 0.9 * mbps + 0.1 * (frame.size * 8) / seconds / 1e6;
        stats.textContent = `network: ${fps.toFixed(0)} fps received, ${mbps.toFixed(1)} Mbit/s`;
      } catch {
        stats.textContent = "reconnecting...";
        await new Promise((resolve) => setTimeout(resolve, 500));  // App restarting: retry
      }
    }
  })();
</script>
"""


@final
class FrameServer:
    """Serves the newest frame to any browser, one JPEG per request."""

    def __init__(self, host: str, port: int) -> None:
        self._frame: MatLike | None = None
        self._closed = False
        self._new_frame = threading.Condition()
        self._server = ThreadingHTTPServer((host, port), self._handler_class())
        self._server.daemon_threads = True

        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def _wait_for_frame(self) -> MatLike | None:
        """Block until a new frame is published; None once closed."""
        with self._new_frame:
            self._new_frame.wait()
            return None if self._closed else self._frame

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version: str = "HTTP/1.1"  # Keep-alive: reuse one connection for every frame

            def do_GET(self) -> None:
                match self.path.split("?")[0]:
                    case "/":
                        self._send(PAGE, "text/html; charset=utf-8")
                    case "/frame":
                        self._send_frame()
                    case _:
                        self.send_error(HTTPStatus.NOT_FOUND)

            def _send_frame(self) -> None:
                if (frame := server._wait_for_frame()) is None:
                    self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)
                    return

                # Encoded here, off the tracking thread, so it doesn't add to the tracking loop's time
                ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ok:
                    self._send(jpeg.tobytes(), "image/jpeg")
                else:
                    self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)

            def _send(self, body: bytes, content_type: str) -> None:
                with suppress(BrokenPipeError, ConnectionResetError):  # Viewer closed the tab
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)

            @override
            def log_message(self, format: str, *args: object) -> None:
                pass  # Silence per-request logging

        return Handler

    def publish(self, frame: MatLike) -> None:
        """Send a BGR frame to viewers. The caller must not modify it afterwards."""
        with self._new_frame:
            self._frame = frame
            self._new_frame.notify_all()

    def close(self) -> None:
        with self._new_frame:
            self._closed = True
            self._new_frame.notify_all()
        self._server.shutdown()
        self._server.server_close()
