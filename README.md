# virtual-whiteboard

Hand tracking with MediaPipe's Tasks API on a Raspberry Pi 4 camera, viewed from the laptop.

## Run

```sh
scripts/pi.sh run     # sync + run on the Pi, view at http://localhost:8000/
scripts/pi.sh watch   # keep the Pi's copy in sync while editing
```

## Why mediapipe 0.10.18 / Python 3.12

The Pi 4's CPU lacks the ARM AES extension, which every mediapipe 1.x wheel requires
(it crashes with `SIGILL`). 0.10.18 is the newest release that runs there, and its newest
wheels are for Python 3.12. The Pi camera is therefore read via `rpicam-vid` rather than
picamera2, which is only packaged for the system Python (3.13).
