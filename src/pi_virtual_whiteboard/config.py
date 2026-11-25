"""Settings, in one place.

Plain values only (no third-party imports), so scripts/pi.py can read them on the laptop.
"""

from typing import Final

# Stream: localhost only, as scripts/pi.py forwards the port to the laptop over SSH
STREAM_HOST: Final = "127.0.0.1"
STREAM_PORT: Final = 8000
JPEG_QUALITY: Final = 75  # ~Half the data of 90 for nearly the same look: more fps on slow Wi-Fi

# Camera
FRAME_SIZE: Final = (640, 480)
# Auto-exposure's gain cap, raised from the default 8 to the sensor's max so fast frames stay bright
# enough indoors (at the cost of some noise, which denoising and landmark smoothing absorb)
MAX_GAIN: Final = 16.0
# Mains lighting pulses at twice the 50 Hz grid frequency (Ireland/EU); exposures in multiples of
# this period stop it showing as bands rolling down the image
FLICKER_PERIOD_US: Final = 10_000

# Hand tracking: MediaPipe's lite models (the full ones are more accurate but twice as slow on a Pi 4)
PALM_MODEL: Final = "palm_detection_lite"
LANDMARK_MODEL: Final = "hand_landmark_lite"
NUM_THREADS: Final = 4
MIN_PALM_SCORE: Final = 0.7  # Above MediaPipe's 0.5: faces in dim light can score ~0.6
MIN_HAND_PRESENCE: Final = 0.5

# Landmark smoothing (One Euro filter). Speeds are in hand sizes per second, so the filter behaves the
# same whether the hand is near or far. Tuned for responsiveness over MediaPipe's defaults (0.05, 80, 1.0)
SMOOTHING_MIN_CUTOFF_HZ: Final = 0.5  # Lower = less jitter when still, but more lag when starting to move
SMOOTHING_BETA: Final = 80.0  # Higher = less lag when moving fast
SMOOTHING_DERIVATIVE_CUTOFF_HZ: Final = 4.0  # Higher = notices a movement starting sooner

# Gestures, read from the 3D landmarks. Ratios compare distances within the hand, so they hold at any distance
# from the camera
# A finger is up when its tip is this many times further from the wrist than its middle joint is. Measured on a real
# hand: 1.37 straight, 0.41-1.00 curled (including a fist facing the camera)
EXTENDED_RATIO: Final = 1.15
# Pinching (pen down): thumb and index tips closer than this many palm lengths (wrist to middle finger knuckle)...
PINCH_RATIO: Final = 0.35
# ...and the pen lifts only once they're further apart than this: a gap between the two, so a pinch that loosens
# slightly mid-stroke doesn't break the line
PINCH_RELEASE_RATIO: Final = 0.5
# ...with the index tip this many times further from the wrist than its knuckle (rules out a fist, whose thumb rests
# near the curled index tip). Synthetic hands: ~1.5 pinching, ~0.9 in a fist; check yours with --debug
PINCH_REACH_RATIO: Final = 1.0
# A new gesture takes over only once it has lasted this long, so in-between shapes and misread frames don't flash,
# and losing the hand for a frame or two doesn't end a stroke
GESTURE_HOLD_S: Final = 0.12
