"""Free-float per-match pill."""
import tkinter as tk
from PIL import ImageTk

from ..config import DRAG_THRESHOLD, FONT_SCORE, FONT_TINY, PILL_H, PILL_ICON, PILL_W
from ..overlay import clock_color, setup_overlay
from ..theme import CHROMA, MUTED, PANEL_BG, PL_PURPLE, TEXT_COLOR, make_glass


class MatchPill(tk.Toplevel):
    def __init__(self, app, match, x, y):
        super().__init__(app.root)
        setup_overlay(self)
        self.app = app
        self.match = match
        self._press = None
        self._dragging = False

        self._ph = ImageTk.PhotoImage(make_glass(PILL_W, PILL_H))
        self.bg = tk.Label(self, image=self._ph, bg=CHROMA, bd=0)
        self.bg.place(x=0, y=0, relwidth=1, relheight=1)

        self.body = tk.Frame(self, bg=PANEL_BG)
        self.body.place(x=14, y=8, width=PILL_W - 28, height=PILL_H - 16)
        self.lbl_home = tk.Label(self.body, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, bd=0)
        self.lbl_home.pack(side=tk.LEFT)
        self.lbl_away = tk.Label(self.body, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, bd=0)
        self.lbl_away.pack(side=tk.RIGHT)
        self.mid = tk.Frame(self.body, bg=PANEL_BG)
        self.mid.pack(side=tk.LEFT, expand=True)
        self.lbl_score = tk.Label(self.mid, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_SCORE)
        self.lbl_score.pack()
        self.lbl_clock = tk.Label(self.mid, bg=PANEL_BG, font=FONT_TINY)
        self.lbl_clock.pack()
        self.lbl_league = tk.Label(self.mid, bg=PANEL_BG, fg=MUTED, font=FONT_TINY)
        self.lbl_league.pack()

        for w in (
            self.bg,
            self.body,
            self.mid,
            self.lbl_home,
            self.lbl_away,
            self.lbl_score,
            self.lbl_clock,
            self.lbl_league,
        ):
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_motion)
            w.bind("<ButtonRelease-1>", self._on_release)
            w.bind("<Button-3>", self._on_menu)

        self.geometry(f"{PILL_W}x{PILL_H}+{int(x)}+{int(y)}")
        self.update_match(match)

    @property
    def match_id(self):
        return str(self.match["id"])

    def update_match(self, match):
        self.match = match
        for lbl, side in ((self.lbl_home, "home"), (self.lbl_away, "away")):
            img = self.app.get_team_icon(match[side]["tla"], match[side]["logo"], size=PILL_ICON)
            if img:
                lbl.configure(image=img, text="")
                lbl.image = img
            else:
                lbl.configure(image="", text=match[side]["tla"])
        self.lbl_score.configure(text=f"{match['home']['score']} - {match['away']['score']}")
        self.lbl_clock.configure(text=match["time"], fg=clock_color(match["time"]))
        self.lbl_league.configure(text=match.get("league_short", ""))

    def _on_press(self, event):
        self._press = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())
        self._dragging = False

    def _on_motion(self, event):
        if not self._press:
            return
        px, py, ox, oy = self._press
        dx, dy = event.x_root - px, event.y_root - py
        if not self._dragging and abs(dx) + abs(dy) < DRAG_THRESHOLD:
            return
        self._dragging = True
        self.geometry(f"+{ox + dx}+{oy + dy}")
        self.app.timeline.sync_follow()

    def _on_release(self, event):
        if self._dragging:
            self.app.pill_positions[self.match_id] = (self.winfo_x(), self.winfo_y())
            self.app.save_pill_state()
        else:
            self.app.timeline.toggle(self.match, self, prefer_above_ticker=False)
        self._press = None
        self._dragging = False

    def _on_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg=PANEL_BG, fg=TEXT_COLOR, activebackground=PL_PURPLE)
        menu.add_command(label="Show timeline", command=lambda: self.app.timeline.open(self.match, self))
        menu.add_command(label="Hide this match", command=lambda: self.app.hide_match_pill(self.match_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

