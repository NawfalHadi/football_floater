#!/usr/bin/env bash
# Self-contained Linux AppImage (bundles Python + Tk + deps via PyInstaller).
# Needs: python3 + python3-tkinter on the *build* machine only.
# Output: output/FootballFloater-x86_64.AppImage
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT_DIR="$ROOT/output"
APPDIR="$OUT_DIR/FootballFloater.AppDir"
APPIMAGE="$OUT_DIR/FootballFloater-x86_64.AppImage"
TOOL="$OUT_DIR/appimagetool-x86_64.AppImage"
VENV="$OUT_DIR/build-venv"
PI_DIST="$OUT_DIR/pyinstaller"
PI_WORK="$OUT_DIR/pyinstaller-work"

python3 -c "import tkinter" 2>/dev/null || {
  echo "Build host needs python3-tkinter (dnf/apt install python3-tkinter)." >&2
  exit 1
}

rm -rf "$APPDIR" "$PI_DIST" "$PI_WORK"
mkdir -p "$OUT_DIR"

if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q --upgrade pip
pip install -q -r requirements.txt pyinstaller

echo "PyInstaller onedir (bundles interpreter + Tk)…"
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name FootballFloater \
  --distpath "$PI_DIST" \
  --workpath "$PI_WORK" \
  --specpath "$OUT_DIR" \
  --collect-all tkinter \
  --collect-all tcl \
  --hidden-import=PIL._tkinter_finder \
  --hidden-import=football_floater \
  --hidden-import=football_floater.app \
  main.py

BIN_DIR="$PI_DIST/FootballFloater"
test -x "$BIN_DIR/FootballFloater"

mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$APPDIR/usr/share/applications"
# Whole standalone tree under usr/lib/FootballFloater/ (binary + _internal)
cp -a "$BIN_DIR" "$APPDIR/usr/lib/FootballFloater"

cat > "$APPDIR/usr/bin/football-floater" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export FOOTBALL_FLOATER_FORCE_SOLID=1
# Prefer bundled libs over host
export LD_LIBRARY_PATH="$HERE/../lib/FootballFloater${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/../lib/FootballFloater/FootballFloater" "$@"
EOF
chmod +x "$APPDIR/usr/bin/football-floater"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export FOOTBALL_FLOATER_FORCE_SOLID=1
export LD_LIBRARY_PATH="$HERE/usr/lib/FootballFloater${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/usr/lib/FootballFloater/FootballFloater" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/football-floater.desktop" <<'EOF'
[Desktop Entry]
Name=Football Floater
Exec=football-floater
Icon=football-floater
Type=Application
Categories=Utility;
EOF
cp "$APPDIR/football-floater.desktop" "$APPDIR/usr/share/applications/"

python3 - <<PY
from pathlib import Path
from PIL import Image, ImageDraw
p = Path("$APPDIR/football-floater.png")
img = Image.new("RGB", (256, 256), (32, 28, 37))
d = ImageDraw.Draw(img)
d.ellipse((48, 48, 208, 208), outline=(0, 255, 133), width=8)
d.text((98, 112), "FF", fill=(245, 245, 247))
img.save(p)
PY

if [[ ! -x "$TOOL" ]]; then
  echo "Downloading appimagetool…"
  curl -fsSL -o "$TOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "$TOOL"
fi

EXTRACT="$OUT_DIR/squashfs-root"
if [[ ! -x "$EXTRACT/AppRun" ]]; then
  rm -rf "$EXTRACT"
  (cd "$OUT_DIR" && "$TOOL" --appimage-extract >/dev/null)
fi

ARCH=x86_64 "$EXTRACT/AppRun" "$APPDIR" "$APPIMAGE"
chmod +x "$APPIMAGE"
echo "Built self-contained $APPIMAGE"
ls -lh "$APPIMAGE"
