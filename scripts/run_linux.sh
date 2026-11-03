#!/usr/bin/env bash
# Linux compat runner — solid glass panels (no Windows chroma).
# Prefer X11. Wayland: try GDK_BACKEND=x11 or a nested Xwayland session.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  echo "No DISPLAY/WAYLAND_DISPLAY — need a GUI session." >&2
  exit 1
fi

python3 -m pip install -q -r requirements.txt
# Force solid panels even if a weird Tk build claims chroma.
export FOOTBALL_FLOATER_FORCE_SOLID="${FOOTBALL_FLOATER_FORCE_SOLID:-1}"
exec python3 -m football_floater "$@"
