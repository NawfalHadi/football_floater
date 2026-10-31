"""Transient goal / penalty toast bubble."""
import math
import tkinter as tk
from PIL import ImageTk

from ..config import FONT_SMALL, FONT_TINY
from ..overlay import setup_overlay
from ..theme import (
    CHROMA,
    CLOCK_LIVE,
    MUTED,
    PANEL_BG,
    PL_GREEN,
    SPEECH_TAIL,
    TEXT_COLOR,
    make_glass,
    make_speech_glass,
    speech_outer_size,
)


def _rects_hit(a, b, pad=6):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw + pad <= bx or bx + bw + pad <= ax or ay + ah + pad <= by or by + bh + pad <= ay)


def stick_above_origin(anchor, bubble_w, bubble_h, bounds, lift=0):
    """Ticker popup: track the scrolling match horizontally. Only pin Y so it stays above the bar."""
    ax, ay, aw, _ah = anchor
    gap = 8
    bx = int(ax + (aw - bubble_w) / 2)
    by = int(ay - gap - bubble_h - lift)
    if bounds:
        _mx, my, _mw, _mh = bounds
        if by < my + 4 and my + 4 + bubble_h + gap <= ay:
            by = my + 4
    return bx, by


def _tail_for_angle(deg):
    """Which side of the bubble faces the pill (opposite the placement angle)."""
    d = deg % 360
    if 45 <= d < 135:
        return "top"  # bubble below pill
    if 135 <= d < 225:
        return "right"  # bubble left of pill
    if 225 <= d < 315:
        return "bottom"  # bubble above pill
    return "left"  # bubble right of pill


def _angle_sweep():
    """Prefer above the pill, then fan out full 360°."""
    seen = set()
    out = []
    for i in range(0, 360, 15):
        for deg in ((270 + i) % 360, (270 - i) % 360):
            if deg in seen:
                continue
            seen.add(deg)
            out.append(deg)
    return out


def choose_bubble_origin(anchor, body_w, body_h, bounds, avoid, lift=0):
    """
    Pick an empty in-bounds slot around the pill (full circle).
    Returns (x, y, tail) — top-left of the speech bitmap, and which side the tip uses.
    """
    ax, ay, aw, ah = anchor
    if bounds:
        mx, my, mw, mh = bounds
    else:
        mx, my, mw, mh = ax - 4000, ay - 4000, 8000, 8000
    gap = 12
    cx, cy = ax + aw / 2, ay + ah / 2
    # Keep clear of the owning pill itself.
    blockers = list(avoid) + [(ax, ay, aw, ah)]

    def fits(x, y, bw, bh):
        if x < mx + 4 or y < my + 4 or x + bw > mx + mw - 4 or y + bh > my + mh - 4:
            return False
        rect = (x, y, bw, bh)
        return not any(_rects_hit(rect, other) for other in blockers)

    # Try rings: tight first, then push out if crowded (lift stacks extra rings).
    base_reach = max(aw, ah) / 2 + gap + max(body_w, body_h) / 2
    for ring in (0, 18, 36, 54):
        dist = base_reach + ring + lift
        for deg in _angle_sweep():
            tail = _tail_for_angle(deg)
            bw, bh = speech_outer_size(body_w, body_h, tail)
            rad = math.radians(deg)
            bcx = cx + math.cos(rad) * dist
            bcy = cy + math.sin(rad) * dist
            bx = int(bcx - bw / 2)
            by = int(bcy - bh / 2)
            if fits(bx, by, bw, bh):
                return bx, by, tail

    # Last resort: above, even if tight — still draw a bottom tip.
    bw, bh = speech_outer_size(body_w, body_h, "bottom")
    bx = int(cx - bw / 2)
    by = int(ay - gap - bh)
    bx = max(mx + 4, min(bx, mx + mw - bw - 4))
    by = max(my + 4, min(by, my + mh - bh - 4))
    return bx, by, "bottom"


def _fill_toast_body(body, text, tag, detail, lines):
    tag_color = CLOCK_LIVE if tag == "SUB" else PL_GREEN
    tk.Label(body, text=tag, bg=PANEL_BG, fg=tag_color, font=FONT_TINY).pack(side=tk.LEFT, anchor="n", padx=(0, 6))
    col = tk.Frame(body, bg=PANEL_BG)
    col.pack(side=tk.LEFT, anchor="n")
    if lines:
        tk.Label(col, text=text, bg=PANEL_BG, fg=MUTED, font=FONT_TINY, anchor="w").pack(anchor="w")
        for i, line in enumerate(lines):
            pair = tk.Frame(col, bg=PANEL_BG)
            pair.pack(anchor="w", pady=(5 if i else 1, 0))
            on_line = tk.Frame(pair, bg=PANEL_BG)
            on_line.pack(anchor="w")
            tk.Label(on_line, text=line.get("on") or "?", bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, anchor="w").pack(
                side=tk.LEFT
            )
            tk.Label(on_line, text=" on", bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor="w").pack(side=tk.LEFT)
            if line.get("off"):
                tk.Label(pair, text=f"{line['off']} off", bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor="w").pack(
                    anchor="w"
                )
    else:
        tk.Label(
            col, text=text, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, anchor="w", justify="left", wraplength=200
        ).pack(anchor="w")
        if detail:
            tk.Label(
                col, text=detail, bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor="w", justify="left", wraplength=200
            ).pack(anchor="w")


class TickerToast(tk.Frame):
    """
    Running-text toast living inside the ticker window.
    place() rides scroll_x — avoids separate Toplevels that freeze on some WMs.
    """

    def __init__(self, master, text, tag="GOAL", detail="", lines=None):
        super().__init__(master, bg=CHROMA, bd=0)
        self.visible = True
        bg = tk.Label(self, bg=CHROMA, bd=0)
        bg.place(x=0, y=0)
        body = tk.Frame(self, bg=PANEL_BG)
        _fill_toast_body(body, text, tag, detail or "", lines)
        body.update_idletasks()
        w = body.winfo_reqwidth() + 32
        h = max(32, body.winfo_reqheight() + 16)
        self._ph = ImageTk.PhotoImage(make_glass(w, h))
        bg.configure(image=self._ph)
        body.place(x=16, y=(h - body.winfo_reqheight()) // 2)
        self.w = w
        self.h = h
        self.configure(width=w, height=h)
        self.place(x=-4000, y=0, width=w, height=h)

    def update_position(self, x, y, lift=0, gap=8):
        """x = left edge in root; y = top of glass bar. Never draw into the glass."""
        bx = int(x)
        # Bottom of toast at y - gap. Caller must grow the toast band if by would go < 0.
        by = int(y - self.h - gap - lift)
        if by < 0:
            by = 0
        if not self.visible:
            self.visible = True
        self.place(x=bx, y=by, width=self.w, height=self.h)
        try:
            self.lift()
        except tk.TclError:
            pass

    def hide(self):
        if self.visible:
            self.place_forget()
            self.visible = False


class GoalBubble(tk.Toplevel):
    """Free-float toast beside a pill — speech tip points at the owner."""

    def __init__(self, master, text, tag="GOAL", detail="", lines=None):
        super().__init__(master)
        setup_overlay(self, 0.96)
        self.visible = True
        self._tail = "bottom"
        self._bg = tk.Label(self, bg=CHROMA, bd=0)
        self._bg.place(x=0, y=0)
        self._body = tk.Frame(self, bg=PANEL_BG)
        _fill_toast_body(self._body, text, tag, detail or "", lines)
        self._body.update_idletasks()
        self.body_w = self._body.winfo_reqwidth() + 32
        self.body_h = max(32, self._body.winfo_reqheight() + 16)
        self._body_req_h = self._body.winfo_reqheight()
        self._ph = None
        self._apply_tail("bottom")
        self.geometry(f"{self.w}x{self.h}+-2000+-2000")

    def _apply_tail(self, tail):
        self._tail = tail
        self._ph = ImageTk.PhotoImage(make_speech_glass(self.body_w, self.body_h, tail=tail))
        self.w, self.h = speech_outer_size(self.body_w, self.body_h, tail)
        self._bg.configure(image=self._ph)
        self._bg.place(x=0, y=0, width=self.w, height=self.h)
        ox = SPEECH_TAIL if tail == "left" else 0
        oy = SPEECH_TAIL if tail == "top" else 0
        self._body.place(x=ox + 16, y=oy + (self.body_h - self._body_req_h) // 2)

    def place_near(self, anchor, lift=0, bounds=None, avoid=(), stick_above=False):
        if not self.visible:
            self.deiconify()
            self.visible = True
            self._placed = None
        if stick_above:
            bx, by = stick_above_origin(anchor, self.body_w, self.body_h, bounds, lift=lift)
            tail = "bottom"
        else:
            bx, by, tail = choose_bubble_origin(
                anchor, self.body_w, self.body_h, bounds, avoid, lift=lift
            )
        if (bx, by, tail) == getattr(self, "_placed", None):
            return bx, by
        if tail != self._tail:
            self._apply_tail(tail)
        self._placed = (bx, by, tail)
        self.geometry(f"{self.w}x{self.h}+{bx}+{by}")
        try:
            self.lift()
        except tk.TclError:
            pass
        return bx, by

    def hide(self):
        if self.visible:
            self.withdraw()
            self.visible = False

