# virtual-whiteboard

Hand tracking on a Raspberry Pi 4 camera, viewed from the laptop.

## Run

```sh
scripts/pi.sh run     # sync + run on the Pi, view at http://localhost:8000/
scripts/pi.sh watch   # keep the Pi's copy in sync while editing
```

## How it works

MediaPipe's palm detection and hand landmark models (lite variants) run directly on
[LiteRT](https://pypi.org/project/ai-edge-litert/) with 4 threads, following MediaPipe's own
pipeline: the slow palm detector only runs while no hand is tracked; otherwise the previous
frame's landmarks give the crop for the next, so only the fast landmark model runs.

The `mediapipe` package itself is not used: every recent wheel needs the ARM AES extension,
which the Pi 4's CPU lacks (it crashes with `SIGILL`), and its Pi-compatible releases run
single-threaded.
