#!/usr/bin/env python3
"""
Digital Indicator Panel

Professional seven-segment display panel for real-time dataset monitoring.
Inspired by industrial panel meters (Omega, Laurel, Red Lion).

Features:
  - Master window to browse datasets and spawn indicator windows
  - Canvas-rendered seven-segment digits with authentic segment geometry
  - Per-display color themes: green, amber, red, cyan, white
  - Hold (freeze), Tare (zero offset), Peak hold, and Min/Max tracking
  - Configurable decimal places and display label
  - Alert flash when value exceeds user-set threshold
  - Auto-reconnect to Serial Studio API

Requirements: Serial Studio API server on port 7777, Python 3.6+, tkinter.
"""

import json, math, signal, socket, sys, threading, time
from collections import deque

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    sys.exit("[Indicator] tkinter required")

# ── Theme ────────────────────────────────────────────────────────────────────

BG       = "#0d1117"
SURFACE  = "#161b22"
HEADER   = "#1c2633"
BORDER   = "#30363d"
TEXT     = "#e6edf3"
DIM      = "#8b949e"
ACCENT   = "#58a6ff"
GREEN    = "#3fb950"
RED      = "#f85149"

# Platform-aware font families
MONO_FONT = MONO_FONT if sys.platform == "darwin" else "Consolas" if sys.platform == "win32" else "Monospace"
SANS_FONT = SANS_FONT if sys.platform == "darwin" else "Segoe UI" if sys.platform == "win32" else "Sans"

IDLE_SEC = 3

# Color presets for indicator displays
PRESETS = {
    "blue":  {"digit": "#58a6ff", "dim": "#0a1a2e", "bg": "#060c14", "label": "#4090e0"},
    "green": {"digit": "#39ff14", "dim": "#0a2e06", "bg": "#050d04", "label": "#2ecc40"},
    "amber": {"digit": "#ffbf00", "dim": "#2e2400", "bg": "#0d0b04", "label": "#f0a000"},
    "red":   {"digit": "#ff3030", "dim": "#2e0808", "bg": "#0d0404", "label": "#e04040"},
    "cyan":  {"digit": "#00e5ff", "dim": "#002a2e", "bg": "#040d0d", "label": "#00c0d0"},
    "white": {"digit": "#e0e0e0", "dim": "#1a1a1a", "bg": "#080808", "label": "#c0c0c0"},
}
DEFAULT_PRESET = "blue"

# ── Seven-segment geometry ───────────────────────────────────────────────────

#  _aa_
# |    |
# f    b
# |_gg_|
# |    |
# e    c
# |_dd_|  .dp

SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg",
    "4": "bcfg",   "5": "acdfg", "6": "acdefg", "7": "abc",
    "8": "abcdefg","9": "abcdfg", "-": "g", " ": "", ".": "dp",
    "E": "adefg",  "e": "adefg", "r": "eg", "o": "cdeg",
    "L": "def",    "H": "bcefg", "d": "bcdeg", "P": "abefg",
    "F": "aefg",   "n": "ceg",  "t": "defg",
}

def _h_seg(canvas, x1, y_mid, x2, sw, fill):
    """Draw a horizontal segment as a tapered hexagon (pointed ends)."""
    hs = sw // 2
    canvas.create_polygon(
        x1, y_mid,
        x1 + hs, y_mid - hs,
        x2 - hs, y_mid - hs,
        x2, y_mid,
        x2 - hs, y_mid + hs,
        x1 + hs, y_mid + hs,
        fill=fill, outline="", tags="seg", smooth=False)


def _v_seg(canvas, x_mid, y1, y2, sw, fill):
    """Draw a vertical segment as a tapered hexagon (pointed ends)."""
    hs = sw // 2
    canvas.create_polygon(
        x_mid, y1,
        x_mid + hs, y1 + hs,
        x_mid + hs, y2 - hs,
        x_mid, y2,
        x_mid - hs, y2 - hs,
        x_mid - hs, y1 + hs,
        fill=fill, outline="", tags="seg", smooth=False)


def draw_segments(canvas, x, y, w, h, chars, color_on, color_off, spacing=10):
    """Draw seven-segment characters on a Canvas.

    Each segment is a tapered hexagonal polygon, wider in the middle,
    pointed at the ends, matching real LED/LCD panel displays.
    Decimal points are zero-width (drawn in the gap between digits).
    """
    canvas.delete("seg")
    sw = max(3, int(w * 0.13))
    step = w + spacing
    half_h = h // 2
    gap = max(1, sw // 3)

    col = 0
    i = 0

    while i < len(chars):
        ch_val = chars[i]

        # Decimal point is zero-width
        if ch_val == ".":
            dp_x = x + col * step - spacing // 2
            dp_y = y + h - sw // 2
            dp_r = max(2, sw // 2)
            canvas.create_oval(dp_x - dp_r, dp_y - dp_r,
                               dp_x + dp_r, dp_y + dp_r,
                               fill=color_on, outline="", tags="seg")
            i += 1
            continue

        cx = x + col * step
        active = SEGMENTS.get(ch_val, "")

        # Segment center positions
        hs = sw // 2
        left   = cx + hs
        right  = cx + w - hs
        top    = y + hs
        bot    = y + h - hs
        mid    = y + half_h

        # Horizontal segments: a (top), g (middle), d (bottom)
        _h_seg(canvas, left, top, right, sw,
               color_on if "a" in active else color_off)
        _h_seg(canvas, left, mid, right, sw,
               color_on if "g" in active else color_off)
        _h_seg(canvas, left, bot, right, sw,
               color_on if "d" in active else color_off)

        # Vertical segments: f (top-left), b (top-right)
        _v_seg(canvas, cx + hs, top + gap, mid - gap, sw,
               color_on if "f" in active else color_off)
        _v_seg(canvas, cx + w - hs, top + gap, mid - gap, sw,
               color_on if "b" in active else color_off)

        # Vertical segments: e (bottom-left), c (bottom-right)
        _v_seg(canvas, cx + hs, mid + gap, bot - gap, sw,
               color_on if "e" in active else color_off)
        _v_seg(canvas, cx + w - hs, mid + gap, bot - gap, sw,
               color_on if "c" in active else color_off)

        # Check if next char is a decimal point
        if i + 1 < len(chars) and chars[i + 1] == ".":
            dp_x = cx + w + spacing // 2
            dp_y = y + h - sw // 2
            dp_r = max(2, sw // 2)
            canvas.create_oval(dp_x - dp_r, dp_y - dp_r,
                               dp_x + dp_r, dp_y + dp_r,
                               fill=color_on, outline="", tags="seg")
            i += 1

        col += 1
        i += 1


def format_7seg(value, width=8, decimals=None):
    """Format a float for seven-segment display.

    Returns a string where non-dot characters == width exactly.
    Dots are zero-width (drawn attached to the preceding digit).
    No scientific notation. Real panel meters don't use it.
    """
    if value is None or math.isnan(value):
        return (" " * (width - 3) + "---")[:width]
    if math.isinf(value):
        s = "oFL" if value > 0 else "-FL"
        return (" " * (width - len(s)) + s)[:width]

    def digit_count(s):
        return sum(1 for c in s if c != ".")

    if decimals is not None:
        text = f"{value:.{decimals}f}"
    else:
        # Auto-select decimals to fill the display width
        sign_chars = 1 if value < 0 else 0
        int_part = int(abs(value))
        int_chars = max(1, len(str(int_part))) + sign_chars

        if int_chars >= width:
            text = str(int(value))
        else:
            avail = width - int_chars - 1  # -1 for the dot
            avail = max(0, min(avail, 6))
            text = f"{value:.{avail}f}"

    # Truncate trailing decimals if too wide
    while digit_count(text) > width:
        if "." in text and not text.endswith("."):
            text = text[:-1]
        elif text.endswith("."):
            text = text[:-1]
        else:
            # Integer overflow, show "oFL"
            text = "-oFL" if value < 0 else " oFL"
            break

    # Pad with leading spaces
    pad = width - digit_count(text)
    if pad > 0:
        text = " " * pad + text

    return text


# ── API Client ───────────────────────────────────────────────────────────────

class APIClient:
    def __init__(self, host="localhost", port=7777):
        self.host, self.port = host, port
        self.sock = None
        self.buffer = b""
        self.req_id = 0
        self.running = True
        self.connected = False
        self.on_frame = None
        self.on_event = None
        self.on_state_loaded = None
        self._pending_state_id = None

    def connect(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((self.host, self.port))
            self.sock, self.buffer, self.connected = s, b"", True
            self._send("initialize", {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "Digital Indicator", "version": "1.0.0"},
                "capabilities": {},
            })
            return True
        except (ConnectionRefusedError, OSError):
            self.connected = False
            return False

    def _send(self, method, params=None):
        if not self.sock:
            return
        self.req_id += 1
        try:
            self.sock.sendall((json.dumps({
                "jsonrpc": "2.0", "id": self.req_id,
                "method": method, "params": params or {}
            }) + "\n").encode())
        except OSError:
            self.connected = False

    def run_loop(self):
        while self.running:
            if not self.connected:
                time.sleep(2)
                self.connect()
                continue
            self.sock.settimeout(1.0)
            try:
                chunk = self.sock.recv(8192)
            except socket.timeout:
                continue
            except OSError:
                self.connected = False
                continue
            if not chunk:
                self.connected = False
                continue
            self.buffer += chunk
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "frames" in msg and self.on_frame:
                    for fw in msg["frames"]:
                        d = fw.get("data")
                        if d:
                            self.on_frame(d)

                elif "event" in msg and self.on_event:
                    self.on_event(msg["event"])

                elif "jsonrpc" in msg and self._pending_state_id:
                    if msg.get("id") == self._pending_state_id:
                        self._pending_state_id = None
                        state = msg.get("result", {}).get("state", {})
                        if self.on_state_loaded:
                            self.on_state_loaded(state)

    def save_state(self, plugin_id, state):
        self._send("extensions.saveState", {"pluginId": plugin_id, "state": state})

    def load_state_async(self, plugin_id):
        """Send loadState request. Response handled in run_loop via on_state_loaded."""
        self._pending_state_id = self.req_id + 1
        self._send("extensions.loadState", {"pluginId": plugin_id})


# ── Data store ───────────────────────────────────────────────────────────────

class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.fields = []           # [(key, group, title, units)]
        self.field_keys = set()
        self.current = {}
        self.frame_count = 0
        self.last_frame_time = None

    @property
    def is_active(self):
        return self.last_frame_time is not None and (time.time() - self.last_frame_time) < IDLE_SEC

    def ingest(self, frame):
        now = time.time()
        with self.lock:
            self.frame_count += 1
            self.last_frame_time = now
            idx = 0
            for group in frame.get("groups", []):
                gt = group.get("title", "")
                for ds in group.get("datasets", []):
                    title = ds.get("title", f"Field {idx}")
                    units = ds.get("units", "")
                    try:
                        val = float(ds.get("value", ""))
                    except (ValueError, TypeError):
                        idx += 1
                        continue
                    key = f"f{idx}"
                    self.current[key] = val
                    if key not in self.field_keys:
                        self.field_keys.add(key)
                        self.fields.append((key, gt, title, units))
                    idx += 1


# ── Indicator Display Window ─────────────────────────────────────────────────

class IndicatorWindow:
    """Single seven-segment indicator display."""

    DIGIT_W = 36
    DIGIT_H = 64
    NUM_DIGITS = 8
    DISPLAY_PAD = 20
    DIGIT_GAP = 10

    def __init__(self, master, store, key, group, title, units, preset=None):
        self.store = store
        self.key = key
        self.preset_name = preset or DEFAULT_PRESET
        self.colors = PRESETS[self.preset_name]
        self.units = units
        self.label = f"{group} / {title}" if group else title

        self.held = False
        self.held_value = None
        self.tare_offset = 0.0
        self.peak_max = None
        self.peak_min = None
        self.decimals = None
        self.alert_hi = None
        self.alert_lo = None
        self.flash_state = False

        step = self.DIGIT_W + self.DIGIT_GAP
        disp_w = self.NUM_DIGITS * step + self.DISPLAY_PAD * 2
        total_w = max(disp_w + 24, 420)

        self.win = tk.Toplevel(master)
        self.win.title(title)
        self.win.geometry(f"{total_w}x310")
        self.win.configure(bg=self.colors["bg"])
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        # ── Display area ─────────────────────────────────────────────────
        self.canvas = tk.Canvas(
            self.win, width=disp_w, height=self.DIGIT_H + self.DISPLAY_PAD * 2,
            bg=self.colors["bg"], highlightthickness=1,
            highlightbackground=self.colors["dim"],
        )
        self.canvas.pack(padx=10, pady=(10, 4))

        # ── Label + units ────────────────────────────────────────────────
        info_frame = tk.Frame(self.win, bg=self.colors["bg"])
        info_frame.pack(fill="x", padx=12)

        tk.Label(
            info_frame, text=self.label, bg=self.colors["bg"],
            fg=self.colors["label"], font=(SANS_FONT, 11, "bold"),
            anchor="w",
        ).pack(side="left")

        self.units_lbl = tk.Label(
            info_frame, text=units, bg=self.colors["bg"],
            fg=self.colors["label"], font=(SANS_FONT, 11),
            anchor="e",
        )
        self.units_lbl.pack(side="right")

        # ── Min/Max/Peak bar ─────────────────────────────────────────────
        stats_frame = tk.Frame(self.win, bg=self.colors["bg"])
        stats_frame.pack(fill="x", padx=12, pady=(2, 4))

        self.min_lbl = tk.Label(
            stats_frame, text="MIN: -", bg=self.colors["bg"],
            fg=DIM, font=(MONO_FONT, 9), anchor="w",
        )
        self.min_lbl.pack(side="left")

        self.max_lbl = tk.Label(
            stats_frame, text="MAX: -", bg=self.colors["bg"],
            fg=DIM, font=(MONO_FONT, 9), anchor="e",
        )
        self.max_lbl.pack(side="right")

        self.peak_lbl = tk.Label(
            stats_frame, text="", bg=self.colors["bg"],
            fg=DIM, font=(MONO_FONT, 9),
        )
        self.peak_lbl.pack()

        # ── Buttons ──────────────────────────────────────────────────────
        btn_frame = tk.Frame(self.win, bg=self.colors["bg"])
        btn_frame.pack(fill="x", padx=10, pady=(4, 8))

        self.btn_frame = btn_frame
        self.buttons = []

        self.hold_btn = self._make_btn(btn_frame, "HOLD", self._toggle_hold)
        self.hold_btn.pack(side="left", padx=(0, 3))

        self._make_btn(btn_frame, "TARE", self._tare).pack(side="left", padx=3)
        self._make_btn(btn_frame, "PEAK", self._toggle_peak).pack(side="left", padx=3)
        self._make_btn(btn_frame, "RESET", self._reset).pack(side="left", padx=3)

        # Color cycle button
        self._make_btn(btn_frame, "COLOR", self._cycle_color).pack(side="right", padx=(3, 0))

        # Decimals cycle button
        self.dec_btn = self._make_btn(btn_frame, "DEC:A", self._cycle_decimals)
        self.dec_btn.pack(side="right", padx=3)

        self._dec_options = ["Auto", "0", "1", "2", "3", "4", "5"]
        self._dec_idx = 0
        self._color_names = list(PRESETS.keys())
        self._color_idx = self._color_names.index(preset)

        self.peak_mode = False
        self.alive = True
        self._tick()

    def _make_btn(self, parent, text, command):
        """Create a styled label-button matching the indicator theme."""
        lbl = tk.Label(
            parent, text=f"  {text}  ", cursor="hand2",
            bg=self.colors["dim"], fg=self.colors["label"],
            font=(MONO_FONT, 9, "bold"), padx=6, pady=4,
        )
        lbl.bind("<Button-1>", lambda _: command())
        lbl.bind("<Enter>", lambda _: lbl.config(bg=self.colors["digit"], fg=self.colors["bg"]))
        lbl.bind("<Leave>", lambda _: lbl.config(
            bg=self.colors["dim"] if not getattr(lbl, "_active", False) else self.colors["digit"],
            fg=self.colors["label"] if not getattr(lbl, "_active", False) else self.colors["bg"],
        ))
        self.buttons.append(lbl)
        return lbl

    def _restyle_buttons(self):
        """Update all button colors to match current theme."""
        for lbl in self.buttons:
            try:
                if not getattr(lbl, "_active", False):
                    lbl.config(bg=self.colors["dim"], fg=self.colors["label"])
                else:
                    lbl.config(bg=self.colors["digit"], fg=self.colors["bg"])
            except tk.TclError:
                pass

    def _toggle_hold(self):
        self.held = not self.held
        if self.held:
            with self.store.lock:
                self.held_value = self.store.current.get(self.key, 0) - self.tare_offset
            self.hold_btn._active = True
            self.hold_btn.config(bg=self.colors["digit"], fg=self.colors["bg"])
        else:
            self.held_value = None
            self.hold_btn._active = False
            self.hold_btn.config(bg=self.colors["dim"], fg=self.colors["label"])

    def _tare(self):
        with self.store.lock:
            self.tare_offset = self.store.current.get(self.key, 0)
        self.peak_max = None
        self.peak_min = None

    def _toggle_peak(self):
        self.peak_mode = not self.peak_mode
        if not self.peak_mode:
            self.peak_max = None
            self.peak_min = None

    def _reset(self):
        self.tare_offset = 0.0
        self.peak_max = None
        self.peak_min = None
        self.held = False
        self.held_value = None
        self.hold_btn._active = False
        self.hold_btn.config(bg=self.colors["dim"], fg=self.colors["label"])

    def _cycle_color(self):
        self._color_idx = (self._color_idx + 1) % len(self._color_names)
        name = self._color_names[self._color_idx]
        self.preset_name = name
        self.colors = PRESETS[name]
        self.win.configure(bg=self.colors["bg"])
        self.canvas.configure(bg=self.colors["bg"],
                              highlightbackground=self.colors["dim"])

        # Update all child backgrounds
        def update_bg(widget):
            try:
                if isinstance(widget, (tk.Frame, tk.Label)):
                    widget.configure(bg=self.colors["bg"])
                if isinstance(widget, tk.Label):
                    if widget.cget("fg") != DIM:
                        widget.configure(fg=self.colors["label"])
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                update_bg(child)

        update_bg(self.win)
        self._restyle_buttons()
        self.btn_frame.configure(bg=self.colors["bg"])

    def _cycle_decimals(self):
        self._dec_idx = (self._dec_idx + 1) % len(self._dec_options)
        val = self._dec_options[self._dec_idx]
        self.decimals = None if val == "Auto" else int(val)
        label = "DEC:A" if val == "Auto" else f"DEC:{val}"
        self.dec_btn.config(text=label)

    def to_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "units": self.units,
            "preset": self.preset_name,
            "decimals": self.decimals,
            "tare": self.tare_offset,
        }

    def _close(self):
        self.alive = False
        self.win.destroy()

    def _tick(self):
        if not self.alive:
            return

        try:
            self._update_display()
            self.win.after(100, self._tick)
        except (tk.TclError, RuntimeError):
            self.alive = False

    def _update_display(self):
        with self.store.lock:
            raw = self.store.current.get(self.key, 0)

        val = raw - self.tare_offset

        # Peak tracking
        if self.peak_mode:
            if self.peak_max is None:
                self.peak_max = val
                self.peak_min = val
            else:
                self.peak_max = max(self.peak_max, val)
                self.peak_min = min(self.peak_min, val)

        # Min/Max labels
        if self.peak_min is not None:
            self.min_lbl.config(text=f"MIN: {self.peak_min:.4f}")
            self.max_lbl.config(text=f"MAX: {self.peak_max:.4f}")
        else:
            self.min_lbl.config(text="MIN: -")
            self.max_lbl.config(text="MAX: -")

        if self.peak_mode:
            self.peak_lbl.config(text="PEAK", fg=self.colors["digit"])
        else:
            self.peak_lbl.config(text="")

        # Display value
        display_val = self.held_value if self.held else val
        text = format_7seg(display_val, self.NUM_DIGITS, self.decimals)

        # Draw segments
        draw_segments(
            self.canvas,
            self.DISPLAY_PAD, self.DISPLAY_PAD,
            self.DIGIT_W, self.DIGIT_H,
            text, self.colors["digit"], self.colors["dim"],
            spacing=self.DIGIT_GAP,
        )


# ── Master Window ────────────────────────────────────────────────────────────

class MasterApp:
    def __init__(self, store, client):
        self.store = store
        self.client = client
        self.indicators = []

        self.root = tk.Tk()
        self.root.title("Digital Indicator Panel")
        self.root.geometry("480x500")
        self.root.minsize(380, 320)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        # ── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=HEADER, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="Digital Indicator Panel", bg=HEADER, fg=TEXT,
                 font=(SANS_FONT, 13, "bold")).pack(side="left", padx=14)

        self.status = tk.Label(hdr, text="● Connecting", bg=HEADER, fg=DIM,
                               font=(SANS_FONT, 11))
        self.status.pack(side="right", padx=14)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # ── Instructions ─────────────────────────────────────────────────
        tk.Label(
            self.root, text="Double-click a dataset to open an indicator display",
            bg=BG, fg=DIM, font=(SANS_FONT, 10), anchor="w",
        ).pack(fill="x", padx=14, pady=(8, 4))

        # ── Dataset list ─────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("DI.Treeview",
                        background=SURFACE, foreground=TEXT,
                        fieldbackground=SURFACE, rowheight=28,
                        borderwidth=0, font=(MONO_FONT, 11))
        style.configure("DI.Treeview.Heading",
                        background=HEADER, foreground=DIM,
                        borderwidth=0, relief="flat",
                        font=(SANS_FONT, 10, "bold"))
        style.map("DI.Treeview",
                  background=[("selected", "#1f3a5f")],
                  foreground=[("selected", ACCENT)])
        style.layout("DI.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        tf = tk.Frame(self.root, bg=BG)
        tf.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        cols = ("GROUP", "DATASET", "VALUE", "UNITS")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", style="DI.Treeview")
        ws = (120, 140, 100, 60)
        for col, w in zip(cols, ws):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w" if col in ("GROUP", "DATASET") else "e",
                             minwidth=40)

        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.tag_configure("even", background=SURFACE)
        self.tree.tag_configure("odd", background="#111820")
        self.tree.bind("<Double-1>", self._on_double_click)

        # ── Footer ───────────────────────────────────────────────────────
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        ftr = tk.Frame(self.root, bg=BG, height=28)
        ftr.pack(fill="x")
        ftr.pack_propagate(False)

        self.lbl_fc = tk.Label(ftr, text="0 frames", bg=BG, fg=DIM, font=(MONO_FONT, 10))
        self.lbl_fc.pack(side="left", padx=14)

        self.lbl_indicators = tk.Label(ftr, text="0 displays", bg=BG, fg=DIM,
                                       font=(MONO_FONT, 10))
        self.lbl_indicators.pack(side="right", padx=14)

        self.iid_map = {}
        self._tick()

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        vals = item["values"]
        group, title, _, units = vals

        # Find the key (release lock before creating the window)
        found = None
        with self.store.lock:
            for key, g, t, u in self.store.fields:
                if g == group and t == title:
                    found = (key, g, t, u)
                    break

        if found:
            key, g, t, u = found
            ind = IndicatorWindow(
                self.root, self.store, key, g, t, u,
                preset=DEFAULT_PRESET,
            )
            self.indicators.append(ind)

    def _fmt(self, v):
        a = abs(v)
        if a == 0: return "0"
        if a >= 1e6: return f"{v/1e6:.2f}M"
        if a >= 100: return f"{v:.1f}"
        if a >= 1:   return f"{v:.3f}"
        if a >= 0.01:return f"{v:.4f}"
        return f"{v:.2e}"

    def _tick(self):
        if not self.client.running:
            self.root.destroy()
            return

        # Status
        with self.store.lock:
            fc = self.store.frame_count
            active = self.store.is_active

        if not self.client.connected:
            self.status.config(text="● Reconnecting…", fg=RED)
        elif active:
            self.status.config(text="● Live", fg=GREEN)
        elif fc > 0:
            self.status.config(text="● Idle", fg=DIM)
        else:
            self.status.config(text="● Connected", fg=ACCENT)

        self.lbl_fc.config(text=f"{fc:,} frames")

        # Clean dead indicators
        self.indicators = [i for i in self.indicators if i.alive]
        self.lbl_indicators.config(text=f"{len(self.indicators)} displays")

        # Update dataset list
        with self.store.lock:
            for i, (key, group, title, units) in enumerate(self.store.fields):
                val = self.store.current.get(key, 0)
                tag = "even" if i % 2 == 0 else "odd"
                values = (group, title, self._fmt(val), units)

                if key in self.iid_map:
                    self.tree.item(self.iid_map[key], values=values, tags=(tag,))
                else:
                    iid = self.tree.insert("", "end", values=values, tags=(tag,))
                    self.iid_map[key] = iid

        self.root.after(150, self._tick)

    def _save_state(self):
        displays = [ind.to_dict() for ind in self.indicators if ind.alive]
        if self.client.connected:
            self.client.save_state("digital-indicator", {"displays": displays})

    def _restore_state(self):
        if not self.client.connected:
            return
        self.client.on_state_loaded = self._on_state_loaded
        self.client.load_state_async("digital-indicator")

    def _on_state_loaded(self, state):
        if not state or "displays" not in state:
            return

        def try_restore():
            with self.store.lock:
                has_fields = len(self.store.fields) > 0
            if not has_fields:
                self.root.after(500, try_restore)
                return

            for dc in state["displays"]:
                key = dc.get("key", "")
                if not key:
                    continue

                found = None
                with self.store.lock:
                    for k, g, t, u in self.store.fields:
                        if k == key:
                            found = (k, g, t, u)
                            break

                if found:
                    k, g, t, u = found
                    ind = IndicatorWindow(
                        self.root, self.store, k, g, t, u,
                        preset=dc.get("preset", DEFAULT_PRESET))
                    ind.decimals = dc.get("decimals")
                    ind.tare_offset = dc.get("tare", 0.0)
                    self.indicators.append(ind)

        self.root.after(100, try_restore)

    def _on_event(self, event_name):
        if event_name == "disconnected":
            self._save_state()
        elif event_name == "connected":
            self._restore_state()

    def _quit(self):
        self._save_state()
        for ind in self.indicators:
            ind.alive = False
            try:
                ind.win.destroy()
            except tk.TclError:
                pass
        self.client.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    store = DataStore()
    client = APIClient()
    client.on_frame = store.ingest

    signal.signal(signal.SIGTERM, lambda *_: setattr(client, "running", False))
    signal.signal(signal.SIGINT, lambda *_: setattr(client, "running", False))

    if not client.connect():
        print("[Indicator] Waiting for API server…", file=sys.stderr)

    threading.Thread(target=client.run_loop, daemon=True).start()

    try:
        app = MasterApp(store, client)
        client.on_event = app._on_event
        app._restore_state()
        app.run()
    except Exception as e:
        print(f"[Indicator] {e}", file=sys.stderr)

    client.running = False
    if client.sock:
        client.sock.close()


if __name__ == "__main__":
    main()
