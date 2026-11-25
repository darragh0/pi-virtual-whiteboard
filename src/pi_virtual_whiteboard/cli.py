"""The app's command-line options.

Standard library only, so scripts/pi.py can check them and show --help on the laptop, without the Pi's
camera libraries.
"""

import argparse
from collections.abc import Sequence
from typing import Final, Literal

type Hand = Literal["left", "right"]
HANDS: Final[tuple[Hand, ...]] = ("left", "right")

type Mode = Literal["thumb", "space"]
MODES: Final[tuple[Mode, ...]] = ("thumb", "space")


class Args(argparse.Namespace):
    # Class-level defaults double as argparse defaults (it skips attributes already set)
    webcam: int = 0
    # Placeholders: --hand and --mode are required, so always set
    hand: Hand = "right"
    mode: Mode = "thumb"
    skeleton: bool = False
    debug: bool = False


def parser() -> argparse.ArgumentParser:
    # Own groups, so --help lists the required option first (argparse puts its built-in "options" group first)
    parser = argparse.ArgumentParser(
        prog="pi-virtual-whiteboard",
        usage="%(prog)s --hand {left,right} --mode {thumb,space} [options]",
        add_help=False,
    )
    required = parser.add_argument_group("required")
    required.add_argument("--hand", choices=HANDS, required=True, help="The hand you draw with")
    required.add_argument(
        "--mode",
        choices=MODES,
        required=True,
        help="What puts the pen down. thumb: tucking your thumb in while pointing; space: holding Space",
    )

    options = parser.add_argument_group("options")
    options.add_argument("-h", "--help", action="help", help="Show this help and exit")
    options.add_argument("--webcam", type=int, metavar="N", help="Off the Pi: use /dev/videoN (default: 0)")
    options.add_argument("--skeleton", action="store_true", help="Draw the hand's skeleton on the video")
    options.add_argument(
        "--debug",
        action="store_true",
        help="Same as --skeleton, plus fps, model confidences and gesture measurements",
    )
    return parser


def parse_args(args: Sequence[str] | None = None) -> Args:
    return parser().parse_args(args, namespace=Args())
