"""Multi-monitor detection (Windows / xrandr / Gdk / Tk fallback)."""
import re
import shutil
import subprocess


def _with_work(mon, wx=None, wy=None, ww=None, wh=None):
    """Attach workarea (taskbar-free). Falls back to full geometry."""
    mon["wx"] = int(mon["x"] if wx is None else wx)
    mon["wy"] = int(mon["y"] if wy is None else wy)
    mon["ww"] = int(mon["w"] if ww is None else ww)
    mon["wh"] = int(mon["h"] if wh is None else wh)
    return mon


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
                wr = info.rcWork
                primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
            else:
                r = pref.contents
                wr = r
            monitors.append(
                _with_work(
                    {
                        "x": int(r.left),
                        "y": int(r.top),
                        "w": int(r.right - r.left),
                        "h": int(r.bottom - r.top),
                        "name": f"Display {len(monitors) + 1}",
                        "primary": primary,
                    },
                    wx=int(wr.left),
                    wy=int(wr.top),
                    ww=int(wr.right - wr.left),
                    wh=int(wr.bottom - wr.top),
                )
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
            _with_work(
                {
                    "name": name,
                    "w": int(w),
                    "h": int(h),
                    "x": int(x),
                    "y": int(y),
                    "primary": "primary" in m.group(0),
                }
            )
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
            wx = wy = ww = wh = None
            try:
                wa = mon.get_workarea()
                wx, wy, ww, wh = int(wa.x), int(wa.y), int(wa.width), int(wa.height)
            except Exception:
                pass
            monitors.append(
                _with_work(
                    {
                        "name": f"Monitor {i + 1}",
                        "x": int(geo.x),
                        "y": int(geo.y),
                        "w": int(geo.width),
                        "h": int(geo.height),
                        "primary": primary,
                    },
                    wx=wx,
                    wy=wy,
                    ww=ww,
                    wh=wh,
                )
            )
        return monitors
    except Exception:
        return []


def _net_workareas():
    """EWMH _NET_WORKAREA tuples (x, y, w, h) — often excludes panels when Gdk does not."""
    if not shutil.which("xprop"):
        return []
    try:
        out = subprocess.check_output(
            ["xprop", "-root", "_NET_WORKAREA"], text=True, stderr=subprocess.DEVNULL
        )
    except Exception:
        return []
    # _NET_WORKAREA(CARDINAL) = 0, 0, 1920, 1036[, ...]
    m = re.search(r"=\s*([\d,\s]+)", out)
    if not m:
        return []
    nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
    areas = []
    for i in range(0, len(nums) - 3, 4):
        areas.append((nums[i], nums[i + 1], nums[i + 2], nums[i + 3]))
    return areas


def _intersect(ax, ay, aw, ah, bx, by, bw, bh):
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2 - x1, y2 - y1


def _attach_linux_workareas(monitors):
    """Prefer smaller of Gdk workarea vs EWMH intersect — Cosmic Gdk often reports full screen."""
    ewmh = _net_workareas()
    for m in monitors:
        wx, wy, ww, wh = m["wx"], m["wy"], m["ww"], m["wh"]
        candidates = [(wx, wy, ww, wh)]
        for area in ewmh:
            hit = _intersect(m["x"], m["y"], m["w"], m["h"], *area)
            if hit:
                candidates.append(hit)
        # Pick shortest usable height (panel reserved) among candidates that still fit a pill row.
        best = min(candidates, key=lambda a: (a[3], a[2]))
        if best[3] >= 80 and best[2] >= 80:
            m["wx"], m["wy"], m["ww"], m["wh"] = best
        # If workarea still equals full geo, leave a small bottom reserve for panels.
        if m["wx"] == m["x"] and m["wy"] == m["y"] and m["ww"] == m["w"] and m["wh"] == m["h"]:
            m["wh"] = max(80, m["h"] - 48)


def list_monitors(tk_root=None):
    """Return [{name,x,y,w,h,wx,wy,ww,wh,primary,label}, ...] for connected displays."""
    win = _monitors_windows()
    monitors = win or _monitors_xrandr() or _monitors_gdk()
    if not monitors:
        w = h = None
        if tk_root is not None:
            try:
                w, h = tk_root.winfo_screenwidth(), tk_root.winfo_screenheight()
            except Exception:
                w = h = None
        if not w or not h:
            w, h = 1920, 1080
        monitors = [_with_work({"name": "Screen 1", "x": 0, "y": 0, "w": w, "h": h, "primary": True})]
    # Fallback: origin-containing screen counts as primary if OS never marked one
    if not any(m.get("primary") for m in monitors):
        for m in monitors:
            if m["x"] <= 0 < m["x"] + m["w"] and m["y"] <= 0 < m["y"] + m["h"]:
                m["primary"] = True
                break
        else:
            monitors[0]["primary"] = True
    for m in monitors:
        _with_work(m, m.get("wx"), m.get("wy"), m.get("ww"), m.get("wh"))
    if not win:
        _attach_linux_workareas(monitors)
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

