"""The app's command-line options.

Standard library only, so scripts/pi.py can check them and show --help on the laptop, without the Pi's
camera libraries.
"""

import argparse
from collections.abc import Sequence
from typing import Final, Literal

type Preference = Literal["quality", "sharp-motion"]
PREFERENCES: Final[tuple[Preference, ...]] = ("quality", "sharp-motion")

type CameraKind = Literal["pi", "webcam"]
CAMERAS: Final[tuple[CameraKind, ...]] = ("pi", "webcam")

type Hand = Literal["left", "right"]
HANDS: Final[tuple[Hand, ...]] = ("left", "right")


class Args(argparse.Namespace):
    # Class-level defaults double as argparse defaults (it skips attributes already set)
    camera: CameraKind = "pi"
    webcam: int = 0
    prefer: Preference = "quality"
    hand: Hand | None = None
    debug: bool = False


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pi-virtual-whiteboard")
    parser.add_argument(
        "--camera",
        choices=CAMERAS,
        help="pi: the Pi's camera (default); webcam: e.g. a laptop's, to develop without the Pi",
    )
    parser.add_argument("--webcam", type=int, metavar="N", help="with --camera webcam: use /dev/videoN (default: 0)")
    parser.add_argument(
        "--prefer",
        choices=PREFERENCES,
        help="Pi camera only. quality: cleaner image; sharp-motion: half the motion blur, but darker and grainier",
    )
    parser.add_argument("--hand", choices=HANDS, help="only track this hand (default: whichever is found)")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="overlay the hand's skeleton, fps, model confidences and gesture measurements",
    )
    return parser


def parse_args(args: Sequence[str] | None = None) -> Args:
    return parser().parse_args(args, namespace=Args())
