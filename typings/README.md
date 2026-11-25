# Local type stubs

Partial, hand-written stubs for untyped dependencies, picked up by (based)pyright via its
default `stubPath`. They cover only the API surface this project uses: extend them as needed.

- `ai_edge_litert/`: ships no `py.typed`.
- `picamera2/`, `libcamera/`: untyped, and only installed on the Pi (via apt).
