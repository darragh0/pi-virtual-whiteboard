#!/usr/bin/env python3
"""Mirror this project onto the Raspberry Pi and run it there.

scripts/pi.py sync    one-off snapshot of the working tree to the Pi
scripts/pi.py setup   sync + install uv and dependencies on the Pi
scripts/pi.py run     setup + run, then view the stream in a browser (extra args, e.g. --debug, are passed on)
"""

import os
import runpy
import shlex
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
PI_HOST: Final = os.environ.get("PI_HOST", "dar@rpi")
PI_DIR: Final = os.environ.get("PI_DIR", "virtual-whiteboard")  # Relative to the Pi user's home

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


def _stream_port() -> int:
    # Run config.py directly rather than importing the package, which needs the Pi's camera libraries
    config = runpy.run_path(str(ROOT / "src" / "virtual_whiteboard" / "config.py"))
    return int(config["STREAM_PORT"])


def sync() -> None:
    # Skips whatever .gitignore (at any level) ignores; excluded files on the Pi, e.g. its .venv, are kept
    _sh("rsync", "-az", "--delete", "--filter=:- .gitignore", "--exclude=.git/", f"{ROOT}/", f"{PI_HOST}:{PI_DIR}/")


def setup() -> None:
    step(f"Syncing to {PI_HOST}:{PI_DIR}")
    sync()
    step("Installing dependencies on the Pi")
    _sh("ssh", PI_HOST, "bash", "-s", "--", PI_DIR, stdin=SETUP_SCRIPT)
    ok("Pi is up to date")


def run(app_args: Sequence[str]) -> None:
    port = _stream_port()

    setup()
    step(f"Running on the Pi {_style('2', '(Ctrl+C to stop)')}")
    ok(f"View at {_style('1;36', f'http://localhost:{port}/')}")

    app = shlex.join([".venv/bin/virtual-whiteboard", *app_args])
    remote = f"cd {PI_DIR} && LIBCAMERA_LOG_LEVELS=WARN {app} 2> >(grep --line-buffered -vE '{LOG_NOISE}' >&2)"

    # The stream binds to the Pi's localhost only; SSH forwards it to this machine
    # LogLevel=ERROR hides "connect failed" noise from a still-open browser tab retrying after Ctrl+C
    try:
        _sh("ssh", "-t", "-o", "LogLevel=ERROR", "-L", f"{port}:127.0.0.1:{port}", PI_HOST, remote)
    finally:
        print()  # End the "^C" line, so the shell prompt starts on a fresh one


def main() -> None:
    match sys.argv[1:]:
        case ["sync"]:
            sync()
        case ["setup"]:
            setup()
        case ["run", *app_args]:
            run(app_args)
        case _:
            print(__doc__, end="\b")
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()  # End the "^C" line, so the shell prompt starts on a fresh one
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
