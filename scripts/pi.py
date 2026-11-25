#!/usr/bin/env python3
"""Mirror this project onto the Raspberry Pi and run it there."""

import argparse
import importlib
import os
import shlex
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Final, Literal

ROOT: Final = Path(__file__).resolve().parent.parent
PI_HOST: Final = os.environ.get("PI_HOST", "dar@rpi")
PI_DIR: Final = os.environ.get("PI_DIR", "pi-virtual-whiteboard")  # Relative to the Pi user's home

# Run from a terminal on the Pi itself, there's nothing to copy or connect to: setup and run work in place
_MODEL_FILE: Final = Path("/proc/device-tree/model")
ON_PI: Final = _MODEL_FILE.exists() and "Raspberry Pi" in _MODEL_FILE.read_text(errors="ignore")

LOG_NOISE: Final = "^INFO: Created TensorFlow Lite XNNPACK delegate"  # Harmless; no setting turns it off

SETUP_SCRIPT: Final = """
set -euo pipefail
cd "$1"
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
# System site-packages exposes the apt-installed picamera2/libcamera to the venv
grep -qs "include-system-site-packages = true" .venv/pyvenv.cfg ||
    uv venv --quiet --clear --python /usr/bin/python3 --system-site-packages
uv sync --locked --no-dev --quiet
"""

# Colour only on a terminal, and never when NO_COLOR is set (https://no-color.org)
_COLOUR: Final = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _style(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOUR else text


def step(text: str) -> None:
    print(f"{_style('1;34', '::')} {_style('1', text)}")


def ok(text: str) -> None:
    print(f"{_style('32', '✓')} {text}")


def _sh(*args: str, stdin: str | None = None) -> None:
    subprocess.run(args, input=stdin, text=True, check=True)  # noqa: S603 -- our own fixed commands


def _app_module(name: str) -> ModuleType:
    """Import a module of the app that needs no third-party packages (e.g. `config`, `cli`)."""
    sys.path.insert(0, str(ROOT / "src"))
    return importlib.import_module(f"pi_virtual_whiteboard.{name}")


def sync() -> None:
    # Skips whatever .gitignore (at any level) ignores; excluded files on the Pi, e.g. its .venv, are kept
    _sh("rsync", "-az", "--delete", "--filter=:- .gitignore", "--exclude=.git/", f"{ROOT}/", f"{PI_HOST}:{PI_DIR}/")


def setup() -> None:
    if ON_PI:
        step("Installing dependencies")
        _sh("bash", "-s", "--", str(ROOT), stdin=SETUP_SCRIPT)
        ok("Up to date")
        return

    step(f"Syncing to {PI_HOST}:{PI_DIR}")
    sync()
    step("Installing dependencies on the Pi")
    _sh("ssh", PI_HOST, "bash", "-s", "--", PI_DIR, stdin=SETUP_SCRIPT)
    ok("Pi is up to date")


def run(app_args: Sequence[str]) -> None:
    port = int(_app_module("config").STREAM_PORT)

    setup()
    step(f"Running on the Pi {_style('2', '(Ctrl+C to stop)')}")
    ok(f"View at {_style('1;36', f'http://localhost:{port}/')}")

    app = shlex.join([".venv/bin/pi-virtual-whiteboard", *app_args])
    command = f"LIBCAMERA_LOG_LEVELS=WARN {app} 2> >(grep --line-buffered -vE '{LOG_NOISE}' >&2)"

    try:
        if ON_PI:
            _sh("bash", "-c", f"cd {shlex.quote(str(ROOT))} && {command}")
        else:
            # The stream binds to the Pi's localhost only; SSH forwards it to this machine
            # LogLevel=ERROR hides "connect failed" noise from a still-open browser tab retrying after Ctrl+C
            ssh = ("ssh", "-t", "-o", "LogLevel=ERROR", "-L", f"{port}:127.0.0.1:{port}")
            _sh(*ssh, PI_HOST, f"cd {PI_DIR} && {command}")
    finally:
        print()  # End the "^C" line, so the shell prompt starts on a fresh one


class Args(argparse.Namespace):
    command: Literal["sync", "setup", "run"] = "run"  # Placeholder: the subcommand is required, so always set


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=f"The Pi is {PI_HOST}:~/{PI_DIR}; set PI_HOST / PI_DIR to change it.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sync", help="copy the working tree to the Pi")
    commands.add_parser("setup", help="sync + install uv and dependencies on the Pi")
    # The app's options (--debug, --hand, ...) are defined in the app, so `run -h` shows its help
    commands.add_parser(
        "run",
        add_help=False,
        help="setup + run, then view the stream in a browser; `run -h` lists the app's options",
    )
    args, app_args = parser.parse_known_args(namespace=Args())

    match args.command:
        case "sync" | "setup" if app_args:
            parser.error(f"unrecognized arguments: {' '.join(app_args)}")
        case "sync" if ON_PI:
            parser.error("sync copies the code to the Pi from another machine; this is the Pi")
        case "sync":
            sync()
        case "setup":
            setup()
        case "run":
            _app_module("cli").parse_args(app_args)  # Checks them (and handles -h) right away, before syncing
            run(app_args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()  # End the "^C" line, so the shell prompt starts on a fresh one
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
