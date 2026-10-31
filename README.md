# Football Floater

Desktop live-score overlay for Premier League + Bundesliga (ESPN). Glass ticker, control dock, free-float match pills, multi-monitor aware.

## Run

```bash
pip install -r requirements.txt
python main.py
# or
python -m football_floater
```

Windows: Tk `transparentcolor` chroma key. Linux: same path when compositor allows; otherwise solid panels.

## Layout

```
main.py                     # thin entry
football_floater/
  config.py                 # constants + settings paths
  theme.py                  # palette + glass/button drawing
  monitors.py               # multi-display detect
  matchday.py               # 06:00 local slate window
  espn.py                   # API URLs
  overlay.py                # topmost / chroma helpers
  app.py                    # SmartTicker (data loop + ticker)
  widgets/                  # dock, pills, timeline, settings, …
DESIGN.md                   # UI / behavior guide
```

Settings live in `settings.json` / `pill_positions.json` next to the repo root.

## Remote

`git@github.com:NawfalHadi/football_floater.git`
