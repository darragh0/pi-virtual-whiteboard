<div align="center">

# pi-virtual-whiteboard

**Real-time hand tracking on a Raspberry Pi 4 camera, streamed to your browser.**

[![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Raspberry Pi 4](https://img.shields.io/badge/Raspberry_Pi-4-A22846?logo=raspberrypi&logoColor=white)](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/)
[![LiteRT](https://img.shields.io/badge/LiteRT-on--device_ML-FF6F00?logo=tensorflow&logoColor=white)](https://ai.google.dev/edge/litert)
[![MediaPipe models](https://img.shields.io/badge/MediaPipe-hand_models-0097A7?logo=google&logoColor=white)](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)
[![OpenCV](https://img.shields.io/badge/OpenCV-5-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

## Run

From the laptop (the Pi is reached over SSH as `dar@rpi`; override with `PI_HOST`):

```sh
scripts/pi.py run                 # sync + run on the Pi, view at http://localhost:8000/
scripts/pi.py run --debug         # same, with model confidence scores on screen
scripts/pi.py run --prefer speed  # grainier image, ~5 ms less lag
```

### On a monitor plugged into the Pi

After `scripts/pi.py setup` from the laptop (copies the code and installs dependencies), in a
terminal on the Pi:

```sh
cd ~/pi-virtual-whiteboard
LIBCAMERA_LOG_LEVELS=WARN .venv/bin/pi-virtual-whiteboard   # same options as above
```

Then open http://localhost:8000/ in the Pi's browser (F11 for fullscreen). The browser shares the
Pi's CPU with the tracking, so expect a few fps less than viewing from the laptop.

## How it works

```mermaid
flowchart LR
    cam[Camera<br>640×480] --> tracked{Hand tracked<br>last frame?}
    tracked -- no --> palm[Palm detector] --> crop
    tracked -- yes --> crop[Crop around<br>the hand]
    crop --> lm[Landmark model<br>21 points] --> smooth[One Euro<br>smoothing] --> stream[MJPEG<br>stream]
    lm -. next crop .-> crop
```

MediaPipe's palm detection and hand landmark models (lite variants) run directly on
[LiteRT](https://pypi.org/project/ai-edge-litert/) with 4 threads, following MediaPipe's own
pipeline: the slow palm detector only runs while no hand is tracked; otherwise the previous
frame's landmarks give the crop for the next, so only the fast landmark model runs.

> [!NOTE]
> The `mediapipe` package itself is not used: every recent wheel needs the ARM AES extension,
> which the Pi 4's CPU lacks (it crashes with `SIGILL`), and its Pi-compatible releases run
> single-threaded.

Landmark numbering: [`reference/hand_landmarks.png`](reference/hand_landmarks.png).

## Development

```sh
uv sync                  # install dependencies, including ruff and basedpyright
uv run ruff check        # lint (config in ruff.toml)
uv run ruff format       # format
uv run basedpyright      # type-check (config in pyproject.toml; stubs in typings/)
```
