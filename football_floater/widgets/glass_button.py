"""Labeled glass button (Pillow-backed Label)."""
import tkinter as tk
from PIL import ImageTk

from ..theme import PANEL_BG, make_button


class GlassButton(tk.Label):
    def __init__(self, parent, label, command, kind="default", min_w=0, height=28):
        super().__init__(parent, bg=PANEL_BG, bd=0, cursor="hand2")
        self.command = command
        self.min_w = min_w
        self.height = height
        self.set(label, kind)
        self.bind("<Enter>", lambda e: self.configure(image=self._hover))
        self.bind("<Leave>", lambda e: self.configure(image=self._normal))
        self.bind("<Button-1>", lambda e: self.command())

    def set(self, label, kind="default"):
        self._normal = ImageTk.PhotoImage(make_button(label, kind, min_w=self.min_w, height=self.height))
        self._hover = ImageTk.PhotoImage(
            make_button(label, kind, hover=True, min_w=self.min_w, height=self.height)
        )
        self.configure(image=self._normal)

