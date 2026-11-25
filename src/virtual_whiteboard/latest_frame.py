import threading
from typing import final


@final
class LatestFrame:
    """Holds only the newest frame: producers overwrite it, consumers wait for a newer one.

    Stale frames are dropped rather than queued, which keeps latency bounded when the
    consumer is slower than the producer.
    """

    def __init__(self) -> None:
        self._frame: bytes | None = None
        self._version = 0
        self._closed = False
        self._condition = threading.Condition()

    def publish(self, frame: bytes) -> None:
        with self._condition:
            self._frame = frame
            self._version += 1
            self._condition.notify_all()

    def close(self) -> None:
        """Wake all waiters; every later wait returns None."""
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def wait_newer(self, seen: int) -> tuple[int, bytes] | None:
        """Block until a frame newer than version `seen` exists; None once closed."""
        with self._condition:
            _ = self._condition.wait_for(lambda: self._closed or self._version > seen)

            if self._closed or self._frame is None:
                return None

            return self._version, self._frame
