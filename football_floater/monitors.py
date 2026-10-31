"""Multi-monitor detection (Windows / xrandr / Gdk / Tk fallback)."""
import tkinter as tk


def _monitors_windows():
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        MONITORINFOF_PRIMARY = 1
        monitors = []
        user32 = ctypes.windll.user32

        def _cb(hmon, hdc, pref, data):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            primary = False
            if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                r = info.rcMonitor
                primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
            else:
                r = pref.contents
            monitors.append(
                {
                    "x": int(r.left),
                    "y": int(r.top),
                    "w": int(r.right - r.left),
                    "h": int(r.bottom - r.top),
                    "name": f"Display {len(monitors) + 1}",
                    "primary": primary,
                }
            )
            return 1

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
        )
        user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_cb), 0)
        return monitors
    except Exception:
        return []


def _monitors_xrandr():
    import re
    import shutil
    import subprocess

    if not shutil.which("xrandr"):
        return []
    try:
        out = subprocess.check_output(["xrandr", "--query"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    monitors = []
    # e.g. HDMI-1 connected primary 1920x1080+0+0
    pat = re.compile(
        r"^(\S+)\s+connected(?:\s+primary)?\s+(\d+)x(\d+)\+(\d+)\+(\d+)", re.M
    )
    for m in pat.finditer(out):
        name, w, h, x, y = m.groups()
        monitors.append(
            {"name": name, "w": int(w), "h": int(h), "x": int(x), "y": int(y), "primary": "primary" in m.group(0)}
        )
    return monitors


def _monitors_gdk():
    try:
        import gi

        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        display = Gdk.Display.get_default()
        if not display:
            return []
        n = display.get_n_monitors()
        monitors = []
        for i in range(n):
            mon = display.get_monitor(i)
            geo = mon.get_geometry()
            primary = False
            try:
                primary = bool(mon.is_primary())
            except Exception:
                primary = False
            monitors.append(
                {
                    "name": f"Monitor {i + 1}",
                    "x": int(geo.x),
                    "y": int(geo.y),
                    "w": int(geo.width),
                    "h": int(geo.height),
                    "primary": primary,
                }
            )
        return monitors
    except Exception:
        return []


def list_monitors(tk_root=None):
    """Return [{name,x,y,w,h,primary,label}, ...] for connected displays."""
    monitors = _monitors_windows() or _monitors_xrandr() or _monitors_gdk()
    if not monitors:
        if tk_root is not None:
            try:
                w, h = tk_root.winfo_screenwidth(), tk_root.winfo_screenheight()
            except tk.TclError:
                w, h = 1920, 1080
        else:
            w, h = 1920, 1080
        monitors = [{"name": "Screen 1", "x": 0, "y": 0, "w": w, "h": h, "primary": True}]
    # Fallback: origin-containing screen counts as primary if OS never marked one
    if not any(m.get("primary") for m in monitors):
        for m in monitors:
            if m["x"] <= 0 < m["x"] + m["w"] and m["y"] <= 0 < m["y"] + m["h"]:
                m["primary"] = True
                break
        else:
            monitors[0]["primary"] = True
    for i, m in enumerate(monitors):
        m.setdefault("name", f"Screen {i + 1}")
        primary = " · primary" if m.get("primary") else ""
        m["label"] = f"{i + 1}. {m['name']}  {m['w']}×{m['h']}{primary}"
    return monitors


def primary_monitor_index(tk_root=None):
    monitors = list_monitors(tk_root)
    for i, m in enumerate(monitors):
        if m.get("primary"):
            return i
    return 0


def resolve_monitor_index(index=None, tk_root=None):
    """Use saved index when set; else OS primary."""
    monitors = list_monitors(tk_root)
    if not monitors:
        return 0
    if index is None or index == "":
        return primary_monitor_index(tk_root)
    try:
        i = int(index)
    except (TypeError, ValueError):
        return primary_monitor_index(tk_root)
    if i < 0 or i >= len(monitors):
        return primary_monitor_index(tk_root)
    return i


def get_monitor(index=None, tk_root=None):
    monitors = list_monitors(tk_root)
    if not monitors:
        return {"x": 0, "y": 0, "w": 1920, "h": 1080, "name": "Screen 1", "primary": True}
    i = resolve_monitor_index(index, tk_root)
    return monitors[i]

