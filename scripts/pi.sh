#!/usr/bin/env bash
# Mirror this project onto the Raspberry Pi and run it there
#
#   scripts/pi.sh sync    one-off snapshot of the working tree to the Pi
#   scripts/pi.sh watch   re-sync on every local file change (Ctrl+C to stop)
#   scripts/pi.sh setup   sync + install uv and dependencies on the Pi
#   scripts/pi.sh run     setup + run, view at http://localhost:8000/
set -euo pipefail

PI_HOST="${PI_HOST:-dar@rpi}"
PI_DIR="${PI_DIR:-virtual-whiteboard}" # Relative to the Pi user's home
PORT=8000 # Must match STREAM_PORT in src/virtual_whiteboard/__init__.py
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

EXCLUDES=(.git/ .venv/ __pycache__/ .ruff_cache/ '*.egg-info/')
# Harmless LiteRT start-up line that no setting turns off
LOG_NOISE='^INFO: Created TensorFlow Lite XNNPACK delegate'
WATCH_EXCLUDE='/(\.git|\.venv|__pycache__|\.ruff_cache)/'

sync() {
    rsync -az --delete "${EXCLUDES[@]/#/--exclude=}" "$ROOT/" "$PI_HOST:$PI_DIR/"
}

watch() {
    sync
    echo "Watching $ROOT -> $PI_HOST:$PI_DIR"
    while inotifywait -qq -r -e modify,create,delete,move --exclude "$WATCH_EXCLUDE" "$ROOT"; do
        sync
        echo "$(date +%T) synced"
    done
}

setup() {
    sync
    ssh "$PI_HOST" bash -s -- "$PI_DIR" <<'EOF'
set -euo pipefail
cd "$1"
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
# System site-packages exposes the apt-installed picamera2/libcamera to the venv
grep -qs "include-system-site-packages = true" .venv/pyvenv.cfg ||
    uv venv --quiet --clear --python /usr/bin/python3 --system-site-packages
uv sync --locked --quiet
EOF
}

run() {
    setup
    echo "View at http://localhost:$PORT/ (Ctrl+C to stop)"
    # The stream binds to the Pi's localhost only; SSH forwards it to this machine
    ssh -t -L "$PORT:127.0.0.1:$PORT" "$PI_HOST" \
        "cd $PI_DIR && LIBCAMERA_LOG_LEVELS=WARN .venv/bin/virtual-whiteboard 2> >(grep --line-buffered -vE '$LOG_NOISE' >&2)"
}

case "${1:-}" in
sync | watch | setup | run) "$1" ;;
*)
    sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
