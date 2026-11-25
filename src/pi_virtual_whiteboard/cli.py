"""The app's command-line options.

Standard library only, so scripts/pi.py can check them and show --help on the laptop, without the Pi's
camera libraries.
"""

import argparse
from collections.abc import Sequence
from typing import Final, Literal

type Preference = Literal["quality", "speed"]
PREFERENCES: Final[tuple[Preference, ...]] = ("quality", "speed")

type Hand = Literal["left", "right"]
HANDS: Final[tuple[Hand, ...]] = ("left", "right")


class Args(argparse.Namespace):
    # Class-level defaults double as argparse defaults (it skips attributes already set)
    prefer: Preference = "quality"
    hand: Hand | None = None
    debug: bool = False


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pi-virtual-whiteboard")
    parser.add_argument(
        "--prefer",
        choices=PREFERENCES,
        help="quality: cleaner image (46 fps camera); speed: grainier, ~5 ms less lag (60 fps camera)",
    )
    parser.add_argument("--hand", choices=HANDS, help="only track this hand (default: whichever is found)")
    parser.add_argument("--debug", action="store_true", help="overlay the models' confidence scores")
    return parser


def parse_args(args: Sequence[str] | None = None) -> Args:
    return parser().parse_args(args, namespace=Args())
