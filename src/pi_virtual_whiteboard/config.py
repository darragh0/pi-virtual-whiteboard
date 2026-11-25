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
# Auto-exposure's longest exposure (one flicker period): half the default's motion blur and 10 ms less lag, for
# a little more noise in dim rooms
MAX_EXPOSURE_US: Final = FLICKER_PERIOD_US

# Hand tracking: MediaPipe's lite models (the full ones are more accurate but twice as slow on a Pi 4)
PALM_MODEL: Final = "palm_detection_lite"
LANDMARK_MODEL: Final = "hand_landmark_lite"
NUM_THREADS: Final = 4
MIN_PALM_SCORE: Final = 0.7  # Above MediaPipe's 0.5: faces in dim light can score ~0.6
MIN_HAND_PRESENCE: Final = 0.5
# A hand lost mid-track (usually a fast move outrunning the predicted crop) is first looked for in a crop this
# many times wider: one landmark run (~23 ms on the Pi) instead of a full palm search (~65 ms)
REACQUIRE_SCALE: Final = 1.6

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
# Drawing needs the index finger up (over EXTENDED_RATIO); once drawing, it counts as down only below this, so a
# finger bent slightly mid-stroke doesn't lift the pen
INDEX_DOWN_RATIO: Final = 1.0
# The thumb is the trigger, like a finger gun's: tucked in against the curled middle finger (pen down) when its tip
# is closer than this many palm lengths (wrist to middle finger knuckle) to the middle finger's middle joint...
THUMB_TUCKED_RATIO: Final = 0.4
# ...and out (pen up) only once it's further than this: a gap between the two, so a thumb that drifts slightly
# mid-stroke doesn't lift the pen. Measured on a real hand (5th-95th percentile): 0.07-0.22 tucked, up to 0.34 while
# drawing, 0.69-0.97 out. Check yours with --debug ("thumb")
THUMB_OUT_RATIO: Final = 0.55
# A new gesture takes over only once it has lasted this long, so in-between shapes and misread frames don't flash,
# and losing the hand for a frame or two doesn't end a stroke
GESTURE_HOLD_S: Final = 0.12
