# Local type stubs

Partial, hand-written stubs for untyped dependencies, picked up by (based)pyright via its
default `stubPath`. They cover only the API surface this project uses: extend them as needed.

- `mediapipe/`: mediapipe ships no `py.typed` and re-exports names dynamically.
