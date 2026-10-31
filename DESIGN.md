# PL Live — Design Guide

Desktop overlay for live Premier League scores. Visual language: **visionOS / macOS glass** (dark frosted capsules, thin silver rim, floating) with **Premier League accents**.

Tokens live in `football_floater/config.py` (sizes/timing) and `football_floater/theme.py` (palette/drawing). Change them there, not inline.

---

## 1. Principles

1. **Glass, not candy.** Panels are dark, flat, and quiet. Color is reserved for meaning.
2. **Color = state, label = action.** Every button says what it does in words. Color only signals state (on, busy, danger). Never rely on color alone.
3. **Information in chunks.** Each surface is its own capsule: control bar, ticker, pills, timeline, goal popup. No single big dashboard.
4. **Out of the way.** Popups close themselves. Nothing steals focus. Hidden things are remembered, not lost.
5. **Consistent match layout.** A match always reads the same everywhere (see §5).

---

## 2. Color

### Surfaces

| Token | Hex | Use |
|---|---|---|
| `PANEL_BG` | `#201C25` | Fill of every glass panel. Charcoal with a hint of PL purple. |
| `PANEL_RIM` | `#8E8E93` | 1px outer rim on panels |
| `BTN_BG` | `#2E2A33` | Button fill |
| `BTN_RIM` | `#55505C` | Button rim |
| `DIVIDER` | `#3A3640` | Separators between ticker items, timeline header line |
| `CHROMA` | `#FF00FF` | Transparency key (see §8). Never visible. |

### Text

| Token | Hex | Use |
|---|---|---|
| `TEXT_COLOR` | `#F5F5F7` | Primary text, scores, player names |
| `MUTED` | `#AEAEB2` | Secondary text: assists, event minutes, FT, disabled buttons |

### Premier League accents

| Token | Hex | Meaning |
|---|---|---|
| `PL_GREEN` | `#00FF85` | Goal, "on" state, kickoff time |
| `PL_PINK` | `#E90052` | Brand accent (avoid for tiny text on dark glass) |
| `CLOCK_LIVE` | `#FF7EB6` | Live match minute — brighter than brand pink for contrast |
| `PL_PURPLE` | `#3D195B` | Menu highlight, panel tint |
| `PL_CYAN` | `#04F5FF` | Reserved (not used for meaning yet) |

### Semantic

| Token | Hex | Meaning |
|---|---|---|
| `CARD_YELLOW` | `#FFD60A` | Yellow card, busy state |
| `DANGER` | `#FF6B6B` | Red card, destructive action (Quit) |

### Clock color rule (`clock_color()`)

| Match state | Example | Color |
|---|---|---|
| Not started | `20:00` | `PL_GREEN` |
| Live | `64'` | `CLOCK_LIVE` |
| Finished | `FT` | `MUTED` |

---

## 3. Typography

Family: **Segoe UI** (Windows). Tk falls back automatically on other OSes. Button labels are rendered by Pillow via `_load_ui_font()` (Segoe UI → SF Pro → DejaVu Sans → Arial).

| Token | Size / weight | Use |
|---|---|---|
| `FONT_SCORE` | 13 bold | Score `2 - 1` |
| `FONT_UI_BOLD` | 10 bold | Timeline header, "PL Live" handle |
| `FONT_UI` | 10 | Player names, empty states |
| `FONT_TINY` | 8 bold | Match clock, event tags (GOAL / YELLOW / RED), goal popup |
| `FONT_SMALL` | 8 | Assist line |
| Button label | 12 (Pillow px) | All buttons |

Rules:
- Scores are the largest text on any surface.
- Time always sits **under** the score, smaller.
- Event tags are uppercase words, not icons or single letters.

---

## 4. Shape and spacing

| Element | Size | Corner radius |
|---|---|---|
| Control bar | auto width × `CTRL_H` 44 | full pill (h/2) |
| Ticker | `TICKER_W` 720 × `TICKER_H` 56 | full pill |
| Match pill | `PILL_W` 168 × `PILL_H` 58 | full pill |
| Goal popup | auto × 32 | full pill |
| Timeline panel | auto (min 220 wide) | **16px** (tall panels must never use h/2 — it turns into an oval) |
| Button | auto (min_w optional) × 28 | full pill |
| Team logo | `ICON_SIZE` 24 (ticker), `PILL_ICON` 26 (pill) | circle on light `ICON_BADGE` disc (navy crests stay readable) |

Spacing:
- Gap between control bar and ticker: `ROW_GAP` 8
- Gap between pills: `PILL_GAP` 10
- Pill distance from screen edge: `PILL_MARGIN` 24 (plus 40px extra at bottom to clear the taskbar)
- Panel inner padding: 16px left/right, ~8–12px top/bottom
- Between buttons: 3px; Quit gets 10px extra on its left to separate it

Glass recipe (`make_glass()`): flat `PANEL_BG` fill → 1px `PANEL_RIM` outer rim → 1px white (alpha 70) inner highlight on the **top third only**. The body area stays flat `PANEL_BG` so Tk widgets placed on it blend in perfectly.

Window opacity: `WINDOW_ALPHA` 0.92 (popups 0.96).

---

## 5. Components

### Control dock (separate window)
Own movable glass capsule. Default sits **under** the ticker so timelines open above the scores.

Expanded:

```
Live │ ↻ Refresh │ ⚽ Test │ ▣ Float: Off │ ⊘ Hidden 0 │ ⚙ Settings │ – Mini │ ✕ Quit
```

Colors: blue refresh, amber test, green when float on, purple settings, red quit. Minimized: `⋮⋮  ↻  ⚽  ▣  ⊘  ⚙  ▢  ✕`

- Drag independently of the ticker; position saved in `settings.json`.
- **Minimize** → icons only; **▢** expands again.
- **Settings** opens leagues + past/live/future (same dialog as startup).
- In float mode the ticker hides; the dock stays.

### Startup / Settings dialog
Shown **every app open** unless **Don't ask next time** is checked.

- **Leagues:** Premier League (`eng.1`), Bundesliga (`ger.1`) — multi-select with league logos
- **Theme:** `default` (current glass) or `experimental` (PL × Bundesliga scorebug — dark opaque panel, light rim, mint live clock). Saved in `settings.json`.
- **Match types:** Past / Live / Future (matchday window)
- **Display:** detected monitors (Windows API / xrandr / Gdk / Tk fallback). Default radio = OS **primary** until user picks. Free-float pills also spawn on that screen’s bottom-right.
- Opt-out checkbox; reopen anytime via **Settings**
- Match chips show league short (`PL` / `BL`) under the clock

### Buttons (`GlassButton`, `make_button`)

| Kind | Fill / rim / text | When |
|---|---|---|
| `default` | grey / grey / white | Normal action |
| `muted` | grey / grey / muted | Toggle that is off, or nothing to act on (Hidden (0)) |
| `on` | dark green / green / green | Toggle that is on (Float matches: On) |
| `busy` | amber | Working (refresh in flight) |
| `refresh` | blue | Reload scores |
| `test` | amber | Fire a fake goal |
| `settings` | purple | Open settings |
| `hidden` | grey | No hidden pills |
| `danger` | dark red / red / red | Destructive (Quit) |

- Hover: fill lightens 10%.
- Toggle buttons use `min_w` so the width doesn't jump when the label changes.
- Each action has an icon prefix plus a word. Toggles still show state: `▣  Float: On`.

### Match layout (ticker item and pill)

```
[home logo]   2 - 1   [away logo]
               64'
```

- If a logo fails to load, show the team abbreviation (`ARS`) in its place.
- Ticker items are separated by a 1px `DIVIDER` line.

### Match pill (float mode)

| Input | Result |
|---|---|
| Left click | Toggle timeline |
| Left drag (> `DRAG_THRESHOLD` 4px) | Move pill; position saved |
| Right click | Menu: Show timeline / Hide this match |

No visible hide button on the pill — keeps it clean.

### Timeline panel (`TimelinePanel`)

```
CHE  2 - 0  MUN                64'
────────────────────────────────
50'   GOAL    M. Rogers
              Assist: R. Lavia
58'   YELLOW  L. Martinez
64'   GOAL    C. Palmer (P)
```

- Header: teams + score (bold), clock right-aligned in clock color.
- Rows: minute · event icon (goal / penalty / yellow / red) · player; assist row uses assist icon.
- Own goals keep `(OG)` suffix. Penalties use penalty icon (no text `(P)`). Assists skipped on pens/OG.
- Empty state: "No goals or cards yet".
- Placement: ticker click → prefer **above** ticker, flip below only if clipped. Pill click → beside first (left of right-edge stack). Clamp to **monitor that holds the anchor** (multi-display safe).

### Goal popup (`GoalBubble`)

```
GOAL  M. Rogers 50'  ·  assist R. Lavia
```

- `GOAL` in `PL_GREEN`, rest in `TEXT_COLOR`.
- Floats 6px above its match (ticker item or pill). Hidden when the item scrolls out of view.
- Lives `ALERT_DURATION` 60s.

---

## 6. Behavior and timing

| What | Value | Token |
|---|---|---|
| Data refresh | 60 s | `REFRESH_RATE` |
| Ticker frame interval | 40 ms | `ANIMATION_SPEED` |
| Ticker scroll per frame | 2 px | `SCROLL_STEP` |
| Goal popup lifetime | 60 s | `ALERT_DURATION` |
| Timeline: opened, never hovered | closes after 4 s | `TIMELINE_IDLE_MS` |
| Timeline: hovered, then pointer left | closes after 1.5 s | `TIMELINE_LEAVE_MS` |
| Click vs drag threshold | 4 px | `DRAG_THRESHOLD` |

Ticker pauses while: hovering a match, the timeline is open, or float mode is on.

Clicking the same match again closes its timeline.

---

## 7. Float mode and pill placement

- Toggle with **Float matches**. Each match becomes its own draggable pill.
- **Default placement:** bottom-right of the screen, stacking **upward** in one column. A new column starts to the left only when the column is full.
- New matches go into the first free slot. They never overlap or sit on top of existing pills.
- Positions and hidden matches persist in `pill_positions.json` across toggles and restarts.
- **Hidden (N)** opens a menu: Show all, or show one match. Hidden matches that are no longer on the scoreboard are dropped from the list.

---

## 8. Implementation rules (Tk gotchas)

1. **Transparency via chroma key.** Windows use `-transparentcolor CHROMA`. Anything outside a rounded shape is painted pure `#FF00FF`.
2. **Never blend into CHROMA.** Any semi-transparent pixel composited over magenta becomes visible pink. Draw buttons and icons on an opaque `PANEL_BG` base. Only `make_glass()` touches CHROMA, and it thresholds alpha to fully on/off.
3. **`ImageDraw` on RGBA replaces pixels, it doesn't blend.** Draw translucent highlights on a separate layer and `alpha_composite` them.
4. **Never assign `self._w` on a Tk widget.** It is Tk's internal window path; overwriting it breaks `withdraw()` and friends.
5. **Create background labels before body frames.** Tk stacks later siblings on top.
6. **Keep `PhotoImage` references** on the owning object, or Tk shows blank images.
7. **Tall panels use a fixed radius (16).** `height // 2` only for short capsules (≤ 64px).

---

## 9. Data notes

- Scores and events: ESPN scoreboard (`ESPN_URL`).
- Penalty goals are type `"Penalty - Scored"` — no "Goal" substring. Use `is_scoring_detail()`, never a text match.
- Assists are **not** in the scoreboard. They come from the summary endpoint (`SUMMARY_URL`, `keyEvents[].participants[1]`), fetched only when a match's score changes.
- Assist names are shortened to `R. Lavia` style to match scorer names.

---

## 10. Checklist for new UI

- [ ] Uses tokens from the top of `main.py`, no new inline hex
- [ ] Glass surface via `make_glass()`; correct radius for its height
- [ ] Buttons via `GlassButton` with a word label and the right `kind`
- [ ] Color carries state only; meaning is also in text
- [ ] Popups auto-close and don't steal focus
- [ ] Nothing semi-transparent drawn over `CHROMA`
- [ ] Match shown as logo / score + time / logo
