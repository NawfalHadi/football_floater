"""Labeled glass button (Pillow-backed Label)."""
import tkinter as tk
from PIL import ImageTk

from ..theme import PANEL_BG, make_button


class GlassButton(tk.Label):
    def __init__(self, parent, label, command, kind="default", min_w=0, height=28, icon=None):
        super().__init__(parent, bg=PANEL_BG, bd=0, cursor="hand2")
        self.command = command
        self.min_w = min_w
        self.height = height
        self.icon = icon
        self.set(label, kind)
        self.bind("<Enter>", lambda e: self.configure(image=self._hover))
        self.bind("<Leave>", lambda e: self.configure(image=self._normal))
        # Release — not press. Press+destroy (Settings Start/Save) leaves B1-Motion
        # on the widget under the cursor with a stale drag offset → windows jump.
        self.bind("<ButtonRelease-1>", self._on_click)

    def _on_click(self, _event=None):
        if self.command:
            self.command()
        return "break"

    def set(self, label, kind="default", icon=None):
        if icon is not None:
            self.icon = icon
        self._normal = ImageTk.PhotoImage(
            make_button(label, kind, min_w=self.min_w, height=self.height, icon=self.icon)
        )
        self._hover = ImageTk.PhotoImage(
            make_button(label, kind, hover=True, min_w=self.min_w, height=self.height, icon=self.icon)
        )
        self.configure(image=self._normal)

