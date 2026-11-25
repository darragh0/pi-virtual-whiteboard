"""The app's command-line options.

Standard library only, so scripts/pi.py can check them and show --help on the laptop, without the Pi's
camera libraries.
"""

import argparse
from collections.abc import Sequence
from typing import Final, Literal

type Preference = Literal["quality", "sharp-motion"]
PREFERENCES: Final[tuple[Preference, ...]] = ("quality", "sharp-motion")

type Hand = Literal["left", "right"]
HANDS: Final[tuple[Hand, ...]] = ("left", "right")


class Args(argparse.Namespace):
    # Class-level defaults double as argparse defaults (it skips attributes already set)
    webcam: int = 0
    prefer: Preference = "quality"
    hand: Hand = "right"  # Placeholder: --hand is required, so always set
    skeleton: bool = False
    debug: bool = False


def parser() -> argparse.ArgumentParser:
    # Own groups, so --help lists the required option first (argparse puts its built-in "options" group first)
    parser = argparse.ArgumentParser(
        prog="pi-virtual-whiteboard", usage="%(prog)s --hand {left,right} [options]", add_help=False
    )
    required = parser.add_argument_group("required")
    required.add_argument("--hand", choices=HANDS, required=True, help="The hand you draw with")

    options = parser.add_argument_group("options")
    options.add_argument("-h", "--help", action="help", help="Show this help and exit")
    options.add_argument("--webcam", type=int, metavar="N", help="Off the Pi: use /dev/videoN (default: 0)")
    options.add_argument(
        "--prefer",
        choices=PREFERENCES,
        help="Pi camera only. quality (default): cleaner image; sharp-motion: less blur, but darker and grainier",
    )
    options.add_argument("--skeleton", action="store_true", help="Draw the hand's skeleton on the video")
    options.add_argument(
        "--debug",
        action="store_true",
        help="Same as --skeleton, plus fps, model confidences and gesture measurements",
    )
    return parser


def parse_args(args: Sequence[str] | None = None) -> Args:
    return parser().parse_args(args, namespace=Args())
