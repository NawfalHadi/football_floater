"""Transient goal / penalty toast bubble."""
import math
import tkinter as tk
from PIL import ImageTk

from ..config import FONT_SMALL, FONT_TINY
from ..overlay import setup_overlay, window_fill
from ..theme import (
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

# Keep a toast glued once placed — recomputing every frame makes crowded stacks jump.
_STICK_OWNER_MOVE = 14
_STICK_MAX_GAP = 96


def _rects_hit(a, b, pad=6):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw + pad <= bx or bx + bw + pad <= ax or ay + ah + pad <= by or by + bh + pad <= ay)


def stick_above_origin(anchor, bubble_w, bubble_h, bounds, lift=0):
    """Pin toast above the owner (ticker or pill). Horizontal center on owner."""
    ax, ay, aw, ah = anchor
    gap = 8
    bx = int(ax + (aw - bubble_w) / 2)
    by = int(ay - gap - bubble_h - lift)
    if bounds:
        mx, my, mw, mh = bounds
        bx = max(mx + 4, min(bx, mx + mw - bubble_w - 4))
        if by < my + 4:
            # Flip below owner when clipped at top.
            by = int(ay + max(1, ah) + gap + lift)
            by = min(by, my + mh - bubble_h - 4)
        by = max(my + 4, by)
    return bx, by

def _tail_toward_pill(bx, by, bw, bh, ax, ay, aw, ah):
    """Tip side from bubble center → pill center (always aims at the owner)."""
    bcx, bcy = bx + bw / 2, by + bh / 2
    pcx, pcy = ax + aw / 2, ay + ah / 2
    dx, dy = pcx - bcx, pcy - bcy
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "bottom" if dy > 0 else "top"


def _angle_sweep():
    """Above / below first (clear ownership on stacks), then sides, then fill."""
    primary = [270, 90, 250, 290, 110, 70, 180, 0, 210, 330, 150, 30]
    seen = set(primary)
    out = list(primary)
    for i in range(0, 360, 15):
        for deg in ((270 + i) % 360, (270 - i) % 360):
            if deg in seen:
                continue
            seen.add(deg)
            out.append(deg)
    return out


def _wedge_penalty(bcx, bcy, ax, ay, aw, ah, others):
    """
    Heavy cost when the toast sits in the side corridor between this pill and a
    stacked neighbor — tip looks like it belongs to both.
    """
    pcx, pcy = ax + aw / 2, ay + ah / 2
    penalty = 0
    for ox, oy, ow, oh in others:
        overlap = min(ax + aw, ox + ow) - max(ax, ox)
        if overlap < min(aw, ow) * 0.45:
            continue
        ocy = oy + oh / 2
        lo, hi = (pcy, ocy) if pcy < ocy else (ocy, pcy)
        if not (lo + 4 < bcy < hi - 4):
            continue
        stack_left = min(ax, ox)
        stack_right = max(ax + aw, ox + ow)
        if bcx < stack_left - 4 or bcx > stack_right + 4:
            penalty += 600
        else:
            penalty += 250
    return penalty


def _clarity_penalty(bcx, bcy, ax, ay, aw, ah, others):
    """Toast must read as belonging to owner, not a nearer neighbor pill."""
    pcx, pcy = ax + aw / 2, ay + ah / 2
    d_owner = math.hypot(bcx - pcx, bcy - pcy)
    penalty = 0
    for ox, oy, ow, oh in others:
        ocx, ocy = ox + ow / 2, oy + oh / 2
        d_other = math.hypot(bcx - ocx, bcy - ocy)
        if d_other + 12 < d_owner:
            penalty += 900
        elif d_other < d_owner + 24:
            penalty += 280
        # Extra: sitting on top of another pill's bounding box
        if ox - 4 <= bcx <= ox + ow + 4 and oy - 4 <= bcy <= oy + oh + 4:
            penalty += 500
    return penalty


def _placement_valid(bx, by, bw, bh, anchor, bounds, avoid, others):
    ax, ay, aw, ah = anchor
    if bounds:
        mx, my, mw, mh = bounds
        if bx < mx + 2 or by < my + 2 or bx + bw > mx + mw - 2 or by + bh > my + mh - 2:
            return False
    rect = (bx, by, bw, bh)
    blockers = list(avoid) + [(ax, ay, aw, ah)]
    if any(_rects_hit(rect, other, pad=4) for other in blockers):
        return False
    bcx, bcy = bx + bw / 2, by + bh / 2
    pcx, pcy = ax + aw / 2, ay + ah / 2
    if math.hypot(bcx - pcx, bcy - pcy) > _STICK_MAX_GAP + max(bw, bh) / 2:
        return False
    if _clarity_penalty(bcx, bcy, ax, ay, aw, ah, others) >= 900:
        return False
    return True


def choose_bubble_origin(anchor, body_w, body_h, bounds, avoid, lift=0):
    """
    Pick an empty in-bounds slot around the pill.
    Prefers above/below so tips stay readable when many pills stack.
    Returns (x, y, tail).
    """
    ax, ay, aw, ah = anchor
    if bounds:
        mx, my, mw, mh = bounds
    else:
        mx, my, mw, mh = ax - 4000, ay - 4000, 8000, 8000
    gap = 8
    cx, cy = ax + aw / 2, ay + ah / 2
    others = [r for r in avoid if r != (ax, ay, aw, ah)]
    blockers = list(avoid) + [(ax, ay, aw, ah)]

    def fits(x, y, bw, bh):
        if x < mx + 4 or y < my + 4 or x + bw > mx + mw - 4 or y + bh > my + mh - 4:
            return False
        return not any(_rects_hit((x, y, bw, bh), other) for other in blockers)

    best = None
    for ring in (0, 10, 22, 36, 52, 72):
        for deg in _angle_sweep():
            prov_tail = "bottom"
            d = deg % 360
            if 45 <= d < 135:
                prov_tail = "top"
            elif 135 <= d < 225:
                prov_tail = "right"
            elif d < 45 or d >= 315:
                prov_tail = "left"
            bw, bh = speech_outer_size(body_w, body_h, prov_tail)
            rad = math.radians(deg)
            c, s = abs(math.cos(rad)), abs(math.sin(rad))
            pill_r = (aw / 2) * c + (ah / 2) * s
            bub_r = (bw / 2) * c + (bh / 2) * s
            dist = pill_r + gap + bub_r + ring + lift
            bcx = cx + math.cos(rad) * dist
            bcy = cy + math.sin(rad) * dist
            bx = int(bcx - bw / 2)
            by = int(bcy - bh / 2)
            if not fits(bx, by, bw, bh):
                continue
            tail = _tail_toward_pill(bx, by, bw, bh, ax, ay, aw, ah)
            if tail != prov_tail:
                bw2, bh2 = speech_outer_size(body_w, body_h, tail)
                bx2 = int(bcx - bw2 / 2)
                by2 = int(bcy - bh2 / 2)
                if not fits(bx2, by2, bw2, bh2):
                    continue
                bx, by, bw, bh = bx2, by2, bw2, bh2
            angle_bias = 0 if deg in (270, 90) else 12 if deg in (250, 290, 110, 70) else 28 if deg in (180, 0) else 45
            score = (
                dist
                + angle_bias
                + _wedge_penalty(bx + bw / 2, by + bh / 2, ax, ay, aw, ah, others)
                + _clarity_penalty(bx + bw / 2, by + bh / 2, ax, ay, aw, ah, others)
            )
            cand = (score, bx, by, tail)
            if best is None or cand < best:
                best = cand

    if best is not None:
        _score, bx, by, tail = best
        return bx, by, tail

    # Last resort: above owner, tip down.
    bw, bh = speech_outer_size(body_w, body_h, "bottom")
    bx = int(cx - bw / 2)
    by = int(ay - gap - bh - lift)
    bx = max(mx + 4, min(bx, mx + mw - bw - 4))
    by = max(my + 4, min(by, my + mh - bh - 4))
    return bx, by, _tail_toward_pill(bx, by, bw, bh, ax, ay, aw, ah)


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
        fill = window_fill()
        super().__init__(master, bg=fill, bd=0)
        self.visible = True
        bg = tk.Label(self, bg=fill, bd=0)
        bg.place(x=0, y=0)
        body = tk.Frame(self, bg=PANEL_BG)
        _fill_toast_body(body, text, tag, detail or "", lines)
        body.update_idletasks()
        w = body.winfo_reqwidth() + 32
        h = max(32, body.winfo_reqheight() + 16)
        self._ph = ImageTk.PhotoImage(make_glass(w, h))
        bg.configure(image=self._ph, bg=fill)
        body.place(x=16, y=(h - body.winfo_reqheight()) // 2)
        self.w = w
        self.h = h
        self.configure(width=w, height=h)
        self.place(x=-4000, y=0, width=w, height=h)

    def update_position(self, x, y, lift=0, gap=8):
        """x = left edge in root; y = top of glass bar. Never draw into the glass."""
        bx = int(x)
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
        self._bg = tk.Label(self, bg=window_fill(), bd=0)
        self._bg.place(x=0, y=0)
        self._body = tk.Frame(self, bg=PANEL_BG)
        _fill_toast_body(self._body, text, tag, detail or "", lines)
        self._body.update_idletasks()
        self.body_w = self._body.winfo_reqwidth() + 32
        self.body_h = max(32, self._body.winfo_reqheight() + 16)
        self._body_req_h = self._body.winfo_reqheight()
        self._ph = None
        self._placed = None
        self._anchor_at_place = None
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
            self._anchor_at_place = None

        ax, ay, aw, ah = anchor
        others = [r for r in avoid if r != (ax, ay, aw, ah)]

        # Sticky: keep last good slot unless owner moved a lot or slot went bad.
        prev = self._placed
        prev_anchor = self._anchor_at_place
        if prev and not stick_above:
            pbx, pby, ptail = prev
            bw, bh = speech_outer_size(self.body_w, self.body_h, ptail)
            owner_moved = True
            if prev_anchor is not None:
                owner_moved = abs(prev_anchor[0] - ax) + abs(prev_anchor[1] - ay) >= _STICK_OWNER_MOVE
            if not owner_moved and _placement_valid(pbx, pby, bw, bh, anchor, bounds, avoid, others):
                if ptail != self._tail:
                    self._apply_tail(ptail)
                self.geometry(f"{self.w}x{self.h}+{pbx}+{pby}")
                try:
                    self.lift()
                except tk.TclError:
                    pass
                return pbx, pby

        if stick_above:
            # Outer size with tip down; may flip below inside stick_above_origin.
            bw, bh = speech_outer_size(self.body_w, self.body_h, "bottom")
            bx, by = stick_above_origin(anchor, bw, bh, bounds, lift=lift)
            # If that overlaps neighbors, fall back to full search.
            if _placement_valid(bx, by, bw, bh, anchor, bounds, avoid, others):
                tail = _tail_toward_pill(bx, by, bw, bh, ax, ay, aw, ah)
            else:
                bx, by, tail = choose_bubble_origin(
                    anchor, self.body_w, self.body_h, bounds, avoid, lift=lift
                )
        else:
            bx, by, tail = choose_bubble_origin(
                anchor, self.body_w, self.body_h, bounds, avoid, lift=lift
            )

        if (bx, by, tail) == prev:
            return bx, by
        if tail != self._tail:
            self._apply_tail(tail)
        self._placed = (bx, by, tail)
        self._anchor_at_place = (ax, ay, aw, ah)
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
            self._placed = None
            self._anchor_at_place = None
