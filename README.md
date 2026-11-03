# Football Floater

Desktop **live-score overlay** for football broadcasts. Glass ticker, small Live dock, optional free-float match pills. Scores from ESPN (Premier League, Bundesliga, La Liga, Champions League).

Built for watching a stream on **Windows**: stay on top, chroma-key friendly, out of the way until you need it. Linux is a best-effort compat build (solid glass panels when transparency is unavailable).

---

## Download (Windows first)

1. On a Windows machine with Python 3.10+:

```powershell
git clone git@github.com:NawfalHadi/football_floater.git
cd football_floater
.\scripts\build_windows.ps1
```

2. Zip `dist\FootballFloater\` and ship `FootballFloater.exe` (plus the folder next to it) via GitHub Releases.

Optional: Nuitka notes are in [`scripts/build_windows.ps1`](scripts/build_windows.ps1).

Settings live in `%APPDATA%\FootballFloater\` (not beside the `.exe`).

### Linux (compat)

```bash
./scripts/run_linux.sh
# self-contained AppImage (bundles Python + Tk) → output/
./scripts/build_appimage.sh
./output/FootballFloater-x86_64.AppImage
```

Build needs `python3-tkinter` (+ `binutils`) on the build machine only; the AppImage bundles Python + Tk + deps (~28MB). Run needs FUSE (`fuse3` / `fusermount3`) on the host — or extract: `./FootballFloater-x86_64.AppImage --appimage-extract`. Solid glass panels on Linux. Prefer X11 if Wayland looks wrong. Config: `~/.config/football-floater/`.

---

## Screenshots

### 1. Running-text ticker

![Running-text ticker — glass capsule with live scores](docs/screenshots/01-ticker.png)

Glass score capsule. Crests/abbreviations, score, and clock (live minute, `FT`, or kickoff countdown). Strip scrolls when the slate is long.

### 2. Control dock

![Live control dock](docs/screenshots/02-dock.png)

Small movable **Live** dock: Refresh, Settings, Hide, Quit. Drag anywhere; position is saved. Extra float-only actions appear only when pills are enabled.

### 3. Start / Settings

![Glass start panel — leagues and display](docs/screenshots/03-settings.png)

First launch asks **leagues + which display**. Filters, theme, and “detach matches as pills” live under Settings afterward.

### 4. Free-float pills

![Match pills floating on the broadcast](docs/screenshots/04-float-pills.png)

Settings → **Detach matches as pills**. Drag to place; right-click to hide; **Reset layout** / **Show hidden** on the dock.

### 5. Float goal toast

![Speech-bubble goal toast pointing at its match pill](docs/screenshots/05-float-toast.png)

Goal / sub toast beside a pill, tip aimed at the owner. Short TTL so it does not cover the pitch.

### 6. Running-text goal toast

![Goal toast above a match chip in the ticker](docs/screenshots/06-ticker-toast.png)

In ticker mode the toast rides above the glass with its match chip.

### 7. Match timeline

![Per-match timeline](docs/screenshots/07-timeline.png)

Click a chip or pill for the timeline: score header, clock, then events (home left / away right of the minute).

---

## Features

- **Running-text ticker** — default view; scrolling glass capsule
- **Free-float pills** — optional; enable in Settings
- **Goal / sub toasts** — ticker strip or speech tip on pills
- **Timeline** — goals, cards, assists
- **Matchday window** — local 06:00 → next 06:00
- **Filters / themes** — under Settings (not on first run)
- **Multi-monitor** — pick display; positions remember with off-screen fallback
- **One-time tips** — short coach hints the first time you see a toast or pill

Visual tokens: [`DESIGN.md`](DESIGN.md).

---

## Run from source

```bash
pip install -r requirements.txt
python main.py
# or
python -m football_floater
```

| Platform | Notes |
|---|---|
| Windows | Tk `transparentcolor` chroma key (`#FF00FF`) — primary |
| Linux / macOS | Solid glass panels (no magenta). `FOOTBALL_FLOATER_FORCE_SOLID=1` also forces solid on Windows if needed |

Needs network access to ESPN scoreboards.

---

## Usage

1. On launch, pick leagues + display (or skip next time).
2. Scores scroll in the ticker; click a match for the timeline.
3. **Settings** for filters, theme, or **Detach matches as pills**.
4. **Hide** tuck scores away; dock stays so you can **Show** again.
5. Dock / ticker positions save under the user config dir.

Regenerate README shots: `python3 scripts/capture_screenshots.py`
