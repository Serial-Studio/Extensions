#!/usr/bin/env python3
"""
Custom Gauge Panel

Multi-needle analog gauge with Canvas-drawn dials. Add multiple datasets
to a single gauge to compare channels. Configurable min/max range, color
zones, needle colors, and gauge styles (270°, 180°, 90° sweep).

Requirements: Serial Studio API server on port 7777, Python 3.6+, tkinter.
"""

import json, math, signal, socket, sys, threading, time

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    sys.exit("[Gauge] tkinter required")

# ── Theme ────────────────────────────────────────────────────────────────────

BG       = "#0d1117"
SURFACE  = "#161b22"
HEADER   = "#1c2633"
BORDER   = "#30363d"
TEXT     = "#e6edf3"
DIM      = "#8b949e"
ACCENT   = "#58a6ff"
GREEN    = "#3fb950"
ORANGE   = "#d29922"
RED      = "#f85149"
ROW_ALT  = "#111820"
SELECT   = "#1f3a5f"

IDLE_SEC = 3

NEEDLE_COLORS = ["#58a6ff", "#3fb950", "#f85149", "#d29922", "#d2a8ff",
                 "#00e5ff", "#ff7b72", "#7ee787", "#ffa657", "#f778ba"]

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
                "clientInfo": {"name": "Custom Gauge", "version": "1.0.0"},
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

    def save_state(self, plugin_id, state):
        self._send("extensions.saveState", {"pluginId": plugin_id, "state": state})

    def load_state_async(self, plugin_id):
        """Send loadState request. Response handled in run_loop via on_state_loaded."""
        self._pending_state_id = self.req_id + 1
        self._send("extensions.loadState", {"pluginId": plugin_id})

    def run_loop(self):
        while self.running:
            if not self.connected:
                time.sleep(2); self.connect(); continue
            self.sock.settimeout(1.0)
            try:
                chunk = self.sock.recv(8192)
            except socket.timeout:
                continue
            except OSError:
                self.connected = False; continue
            if not chunk:
                self.connected = False; continue
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
                        if d: self.on_frame(d)

                elif "event" in msg and self.on_event:
                    self.on_event(msg["event"])

                elif "jsonrpc" in msg and self._pending_state_id:
                    if msg.get("id") == self._pending_state_id:
                        self._pending_state_id = None
                        state = msg.get("result", {}).get("state", {})
                        if self.on_state_loaded:
                            self.on_state_loaded(state)


# ── Data store ───────────────────────────────────────────────────────────────

class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.fields = []
        self.field_keys = set()
        self.current = {}
        self.range_min = {}    # key → configured min from project
        self.range_max = {}    # key → configured max from project
        self.frame_count = 0
        self.last_frame_time = None

    @property
    def is_active(self):
        return self.last_frame_time is not None and (time.time() - self.last_frame_time) < IDLE_SEC

    def get_range(self, key):
        """Return (min, max) from project config, or None if not configured."""
        lo = self.range_min.get(key)
        hi = self.range_max.get(key)
        if lo is None or hi is None:
            return None
        if lo == hi:
            return None
        return (min(lo, hi), max(lo, hi))

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
                        idx += 1; continue
                    key = f"f{idx}"
                    self.current[key] = val

                    if key not in self.field_keys:
                        self.field_keys.add(key)
                        self.fields.append((key, gt, title, units))

                        # Extract configured range (widgetMin/Max or plotMin/Max)
                        wmin = ds.get("widgetMin", 0)
                        wmax = ds.get("widgetMax", 0)
                        pmin = ds.get("plotMin", 0)
                        pmax = ds.get("plotMax", 0)

                        try:
                            wmin, wmax = float(wmin), float(wmax)
                        except (ValueError, TypeError):
                            wmin, wmax = 0, 0
                        try:
                            pmin, pmax = float(pmin), float(pmax)
                        except (ValueError, TypeError):
                            pmin, pmax = 0, 0

                        # Prefer plot range (explicitly set by user), then widget
                        # range, but skip the default widget range (0, 100)
                        # which is just Qt's struct default, not user-configured
                        is_default_wgt = (wmin == 0 and wmax == 100)
                        if pmin != pmax:
                            self.range_min[key] = pmin
                            self.range_max[key] = pmax
                        elif wmin != wmax and not is_default_wgt:
                            self.range_min[key] = wmin
                            self.range_max[key] = wmax

                    idx += 1


# ── Gauge drawing ────────────────────────────────────────────────────────────

def draw_dial(canvas, cx, cy, radius, sweep_deg, min_val, max_val, zones=None):
    """Draw the static dial face (ring, ticks, labels). Call once or on resize."""
    canvas.delete("dial")

    if sweep_deg >= 270:
        start_a, end_a = 225, -45
    elif sweep_deg >= 180:
        start_a, end_a = 180, 0
    else:
        start_a, end_a = 180, 90

    def frac_to_angle(frac):
        return start_a - frac * (start_a - end_a)

    rng = max_val - min_val if max_val != min_val else 1.0

    # Outer ring
    ring_w = max(3, int(radius * 0.04))
    canvas.create_arc(
        cx - radius, cy - radius, cx + radius, cy + radius,
        start=end_a, extent=start_a - end_a,
        style="arc", outline=BORDER, width=ring_w, tags="dial")

    # Color zones
    if zones:
        zone_r = radius - ring_w
        zone_w = max(6, int(radius * 0.08))
        for zs, ze, zc in zones:
            canvas.create_arc(
                cx - zone_r, cy - zone_r, cx + zone_r, cy + zone_r,
                start=frac_to_angle(ze), extent=frac_to_angle(zs) - frac_to_angle(ze),
                style="arc", outline=zc, width=zone_w, tags="dial")

    # Tick marks
    n_major, n_minor = 10, 50
    inner_major = radius - int(radius * 0.18)
    inner_minor = radius - int(radius * 0.10)
    label_r = radius - int(radius * 0.28)

    for i in range(n_minor + 1):
        frac = i / n_minor
        angle = math.radians(frac_to_angle(frac))
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        is_major = (i % (n_minor // n_major) == 0) if n_minor >= n_major else True

        x1 = cx + (inner_major if is_major else inner_minor) * cos_a
        y1 = cy - (inner_major if is_major else inner_minor) * sin_a
        x2 = cx + (radius - ring_w - 2) * cos_a
        y2 = cy - (radius - ring_w - 2) * sin_a
        canvas.create_line(x1, y1, x2, y2,
                           fill=TEXT if is_major else DIM,
                           width=2 if is_major else 1, tags="dial")

        if is_major:
            val = min_val + frac * rng
            lx = cx + label_r * cos_a
            ly = cy - label_r * sin_a
            txt = f"{val:.0f}" if abs(val) >= 1 else f"{val:.2f}"
            canvas.create_text(lx, ly, text=txt, fill=DIM, tags="dial",
                               font=("Menlo", max(8, int(radius * 0.07))))

    # Center dot (behind needles)
    dot_r = max(4, int(radius * 0.06))
    canvas.create_oval(cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r,
                       fill=DIM, outline="", tags="dial")


def draw_needles(canvas, cx, cy, radius, sweep_deg, needles, min_val, max_val):
    """Draw needles and readouts. Called every tick (fast, no ticks/labels)."""
    canvas.delete("needle")

    if sweep_deg >= 270:
        start_a, end_a = 225, -45
    elif sweep_deg >= 180:
        start_a, end_a = 180, 0
    else:
        start_a, end_a = 180, 90

    rng = max_val - min_val if max_val != min_val else 1.0

    for value, color, label in needles:
        frac = max(0, min(1, (value - min_val) / rng))
        angle = math.radians(start_a - frac * (start_a - end_a))
        cos_a, sin_a = math.cos(angle), math.sin(angle)

        needle_len = radius - int(radius * 0.22)
        tail_len = int(radius * 0.12)

        nx = cx + needle_len * cos_a
        ny = cy - needle_len * sin_a
        tx = cx - tail_len * cos_a
        ty = cy + tail_len * sin_a
        canvas.create_line(tx, ty, nx, ny, fill=color, width=3,
                           capstyle="round", tags="needle")

        # Arrow tip
        tip = max(3, int(radius * 0.04))
        px, py = -sin_a * tip, -cos_a * tip
        canvas.create_polygon(
            nx, ny,
            nx - cos_a * tip * 2 + px, ny + sin_a * tip * 2 + py,
            nx - cos_a * tip * 2 - px, ny + sin_a * tip * 2 - py,
            fill=color, outline="", tags="needle")

    # Center cap (on top)
    cap_r = max(3, int(radius * 0.045))
    canvas.create_oval(cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r,
                       fill="#2a2a2a", outline=DIM, width=1, tags="needle")

    # Digital readouts below gauge
    font_size = max(9, int(radius * 0.07))
    y_base = cy + radius * 0.45
    for i, (value, color, label) in enumerate(needles):
        short = label.split("/")[-1].strip() if "/" in label else label
        txt = f"{short}\n{value:.4f}"
        canvas.create_text(cx, y_base + i * (font_size * 2.8),
                           text=txt, fill=color, tags="needle",
                           font=("Menlo", font_size), justify="center")


# ── Gauge Window ─────────────────────────────────────────────────────────────

class GaugeWindow:
    GAUGE_SIZE = 300

    def __init__(self, master, store, dataset_keys, title="Gauge"):
        self.store = store
        self.keys = list(dataset_keys)  # [(key, label, color)]
        self.sweep = 270
        self.zones = []

        # Use project-configured range from first dataset if available
        first_key = dataset_keys[0][0] if dataset_keys else None
        project_range = store.get_range(first_key) if first_key else None
        if project_range:
            self.min_val = project_range[0]
            self.max_val = project_range[1]
            self.auto_range = False
        else:
            self.min_val = -1.0
            self.max_val = 1.0
            self.auto_range = True

        self._dial_dirty = True
        self._last_size = (0, 0)

        size = self.GAUGE_SIZE
        win_w = size + 40
        win_h = size + 140

        self.win = tk.Toplevel(master)
        self.win.title(title)
        self.win.geometry(f"{win_w}x{win_h}")
        self.win.configure(bg=BG)
        self.win.resizable(True, True)
        self.win.minsize(240, 260)
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        # Canvas
        self.canvas = tk.Canvas(self.win, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        # Controls
        ctrl = tk.Frame(self.win, bg=BG)
        ctrl.pack(fill="x", padx=8, pady=(4, 8))

        def make_lbl_btn(parent, text, cmd):
            l = tk.Label(parent, text=f" {text} ", cursor="hand2",
                         bg=BORDER, fg=TEXT, font=("Menlo", 9, "bold"),
                         padx=4, pady=2)
            l.bind("<Button-1>", lambda _: cmd())
            l.bind("<Enter>", lambda _: l.config(bg=ACCENT, fg=BG))
            l.bind("<Leave>", lambda _: l.config(bg=BORDER, fg=TEXT))
            return l

        self.range_lbl = tk.Label(
            ctrl, text="Auto", bg=BG, fg=DIM, font=("Menlo", 9))
        self.range_lbl.pack(side="left")

        make_lbl_btn(ctrl, "SET MIN", self._set_min).pack(side="left", padx=(6, 2))
        make_lbl_btn(ctrl, "SET MAX", self._set_max).pack(side="left", padx=2)
        make_lbl_btn(ctrl, "AUTO", self._auto_range).pack(side="left", padx=2)

        self.sweep_btn = make_lbl_btn(ctrl, "270°", self._cycle_sweep)
        self.sweep_btn.pack(side="right")

        make_lbl_btn(ctrl, "+ DATASET", lambda: self._add_dataset(master)).pack(
            side="right", padx=(0, 6))

        self.alive = True
        self._observed_min = None
        self._observed_max = None
        self._tick()

    def _set_min(self):
        self.auto_range = False
        val = self._prompt("Set minimum value", str(self.min_val))
        if val is not None:
            self.min_val = val
            self._dial_dirty = True

    def _set_max(self):
        self.auto_range = False
        val = self._prompt("Set maximum value", str(self.max_val))
        if val is not None:
            self.max_val = val
            self._dial_dirty = True

    def _auto_range(self):
        self.auto_range = True
        self._observed_min = None
        self._observed_max = None
        self._dial_dirty = True

    def _cycle_sweep(self):
        if self.sweep == 270:
            self.sweep = 180
        elif self.sweep == 180:
            self.sweep = 90
        else:
            self.sweep = 270
        self.sweep_btn.config(text=f" {self.sweep}° ")
        self._dial_dirty = True

    def _prompt(self, title, default=""):
        dlg = tk.Toplevel(self.win)
        dlg.title(title)
        dlg.geometry("280x90")
        dlg.configure(bg=SURFACE)
        dlg.transient(self.win)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text=title, fg=TEXT, bg=SURFACE,
                 font=("Helvetica Neue", 11)).pack(pady=(10, 4))

        entry = tk.Entry(dlg, font=("Menlo", 12), bg=BG, fg=TEXT,
                         insertbackground=ACCENT, relief="flat",
                         highlightthickness=1, highlightcolor=ACCENT,
                         highlightbackground=BORDER)
        entry.pack(padx=16, fill="x")
        entry.insert(0, default)
        entry.select_range(0, tk.END)
        entry.focus_set()

        result = [None]
        def apply(*_):
            try:
                result[0] = float(entry.get())
            except ValueError:
                pass
            dlg.destroy()

        entry.bind("<Return>", apply)
        self.win.wait_window(dlg)
        return result[0]

    def _add_dataset(self, master):
        """Show a dialog to pick an additional dataset for this gauge."""
        dlg = tk.Toplevel(self.win)
        dlg.title("Add Dataset")
        dlg.geometry("360x300")
        dlg.configure(bg=SURFACE)
        dlg.transient(self.win)
        dlg.grab_set()
        dlg.resizable(False, True)

        tk.Label(dlg, text="Select a dataset to add:", fg=TEXT, bg=SURFACE,
                 font=("Helvetica Neue", 11)).pack(pady=(10, 4))

        style = ttk.Style()
        style.configure("GD.Treeview",
                        background=BG, foreground=TEXT,
                        fieldbackground=BG, rowheight=24,
                        borderwidth=0, font=("Menlo", 10))
        style.configure("GD.Treeview.Heading",
                        background=HEADER, foreground=DIM, borderwidth=0)

        tree = ttk.Treeview(dlg, columns=("GROUP", "DATASET"), show="headings",
                             style="GD.Treeview")
        tree.heading("GROUP", text="GROUP")
        tree.heading("DATASET", text="DATASET")
        tree.column("GROUP", width=140)
        tree.column("DATASET", width=180)
        tree.pack(fill="both", expand=True, padx=8, pady=4)

        existing_keys = {k for k, _, _ in self.keys}

        with self.store.lock:
            for key, group, title, units in self.store.fields:
                if key not in existing_keys:
                    tree.insert("", "end", values=(group, title), tags=(key,))

        def on_select(_):
            sel = tree.selection()
            if sel:
                # Get key from tags
                tags = tree.item(sel[0], "tags")
                if tags:
                    key = tags[0]
                    with self.store.lock:
                        for k, g, t, u in self.store.fields:
                            if k == key:
                                color_idx = len(self.keys) % len(NEEDLE_COLORS)
                                label = f"{g}/{t}" if g else t
                                self.keys.append((k, label, NEEDLE_COLORS[color_idx]))
                                break
                dlg.destroy()

        tree.bind("<Double-1>", on_select)

    def to_dict(self):
        return {
            "keys": [{"key": k, "label": l, "color": c} for k, l, c in self.keys],
            "min": self.min_val,
            "max": self.max_val,
            "auto_range": self.auto_range,
            "sweep": self.sweep,
            "title": self.win.title(),
        }

    def _close(self):
        self.alive = False
        self.win.destroy()

    def _tick(self):
        if not self.alive:
            return

        try:
            self._draw()
            self.win.after(100, self._tick)
        except (tk.TclError, RuntimeError):
            self.alive = False

    def _draw(self):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return

        radius = min(w, h) // 2 - 10
        cx = w // 2
        cy = h // 2 + (10 if self.sweep >= 270 else 0)

        # Read values
        needles = []
        with self.store.lock:
            for key, label, color in self.keys:
                val = self.store.current.get(key, 0)
                needles.append((val, color, label))

        # Auto-range
        if self.auto_range and needles:
            old_min, old_max = self.min_val, self.max_val
            for val, _, _ in needles:
                if self._observed_min is None:
                    self._observed_min = val
                    self._observed_max = val
                else:
                    self._observed_min = min(self._observed_min, val)
                    self._observed_max = max(self._observed_max, val)

            rng = (self._observed_max or 0) - (self._observed_min or 0)
            margin = max(abs(rng) * 0.15, 0.001)
            self.min_val = (self._observed_min or 0) - margin
            self.max_val = (self._observed_max or 0) + margin

            if self.min_val != old_min or self.max_val != old_max:
                self._dial_dirty = True

        # Range label
        self.range_lbl.config(
            text=f"{'Auto' if self.auto_range else 'Fixed'}: "
                 f"[{self.min_val:.2f}, {self.max_val:.2f}]")

        # Redraw static dial only when needed (resize, range change, sweep change)
        cur_size = (w, h)
        if self._dial_dirty or cur_size != self._last_size:
            draw_dial(self.canvas, cx, cy, radius, self.sweep,
                      self.min_val, self.max_val, self.zones)
            self._last_size = cur_size
            self._dial_dirty = False

        # Redraw needles every tick (fast, only lines + text)
        draw_needles(self.canvas, cx, cy, radius, self.sweep,
                     needles, self.min_val, self.max_val)


# ── Master Window ────────────────────────────────────────────────────────────

class MasterApp:
    def __init__(self, store, client):
        self.store = store
        self.client = client
        self.gauges = []

        self.root = tk.Tk()
        self.root.title("Custom Gauge Panel")
        self.root.geometry("500x480")
        self.root.minsize(380, 320)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        # Header
        hdr = tk.Frame(self.root, bg=HEADER, height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Custom Gauge Panel", bg=HEADER, fg=TEXT,
                 font=("Helvetica Neue", 13, "bold")).pack(side="left", padx=14)
        self.status = tk.Label(hdr, text="● Connecting", bg=HEADER, fg=DIM,
                               font=("Helvetica Neue", 11))
        self.status.pack(side="right", padx=14)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        tk.Label(self.root,
                 text="Double-click a dataset to create a gauge. Add more needles from the gauge window.",
                 bg=BG, fg=DIM, font=("Helvetica Neue", 10), anchor="w",
                 wraplength=460).pack(fill="x", padx=14, pady=(8, 4))

        # Dataset list
        style = ttk.Style()
        style.theme_use("default")
        style.configure("GG.Treeview",
                        background=SURFACE, foreground=TEXT,
                        fieldbackground=SURFACE, rowheight=26,
                        borderwidth=0, font=("Menlo", 11))
        style.configure("GG.Treeview.Heading",
                        background=HEADER, foreground=DIM,
                        borderwidth=0, relief="flat",
                        font=("Helvetica Neue", 10, "bold"))
        style.map("GG.Treeview",
                  background=[("selected", SELECT)],
                  foreground=[("selected", ACCENT)])
        style.layout("GG.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        tf = tk.Frame(self.root, bg=BG)
        tf.pack(fill="both", expand=True, padx=12, pady=(4, 0))

        cols = ("GROUP", "DATASET", "VALUE", "UNITS")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings",
                                  style="GG.Treeview")
        for col, w in zip(cols, (130, 150, 100, 60)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w,
                             anchor="w" if col in ("GROUP", "DATASET") else "e",
                             minwidth=40)

        self.tree.pack(side="left", fill="both", expand=True)
        if sys.platform != "darwin":
            vsb = tk.Scrollbar(tf, orient="vertical", command=self.tree.yview,
                               bg=SURFACE, troughcolor=BG, highlightthickness=0,
                               borderwidth=0, width=10)
            self.tree.configure(yscrollcommand=vsb.set)
            vsb.pack(side="right", fill="y")

        self.tree.tag_configure("even", background=SURFACE)
        self.tree.tag_configure("odd", background=ROW_ALT)
        self.tree.bind("<Double-1>", self._on_double_click)

        # Footer
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        ftr = tk.Frame(self.root, bg=BG, height=28)
        ftr.pack(fill="x"); ftr.pack_propagate(False)
        self.lbl_fc = tk.Label(ftr, text="0 frames", bg=BG, fg=DIM,
                               font=("Menlo", 10))
        self.lbl_fc.pack(side="left", padx=14)
        self.lbl_gauges = tk.Label(ftr, text="0 gauges", bg=BG, fg=DIM,
                                    font=("Menlo", 10))
        self.lbl_gauges.pack(side="right", padx=14)

        self.iid_map = {}
        self._tick()

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        group, title, _, units = item["values"]

        found = None
        with self.store.lock:
            for key, g, t, u in self.store.fields:
                if g == group and t == title:
                    found = (key, g, t, u)
                    break

        if found:
            key, g, t, u = found
            label = f"{g}/{t}" if g else t
            gauge_title = f"{t} ({u})" if u else t
            gauge = GaugeWindow(
                self.root, self.store,
                [(key, label, NEEDLE_COLORS[0])],
                title=gauge_title,
            )
            self.gauges.append(gauge)

    def _fmt(self, v):
        a = abs(v)
        if a == 0: return "0"
        if a >= 1e6: return f"{v/1e6:.2f}M"
        if a >= 100: return f"{v:.1f}"
        if a >= 1: return f"{v:.3f}"
        if a >= 0.01: return f"{v:.4f}"
        return f"{v:.2e}"

    def _tick(self):
        if not self.client.running:
            self.root.destroy(); return

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
        self.gauges = [g for g in self.gauges if g.alive]
        self.lbl_gauges.config(text=f"{len(self.gauges)} gauges")

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
        gauges = [g.to_dict() for g in self.gauges if g.alive]
        if self.client.connected:
            self.client.save_state("custom-gauge", {"gauges": gauges})

    def _restore_state(self):
        if not self.client.connected:
            return
        self.client.on_state_loaded = self._on_state_loaded
        self.client.load_state_async("custom-gauge")

    def _on_state_loaded(self, state):
        if not state or "gauges" not in state:
            return

        def try_restore():
            with self.store.lock:
                has_fields = len(self.store.fields) > 0
            if not has_fields:
                self.root.after(500, try_restore)
                return

            for gc in state["gauges"]:
                keys = [(d["key"], d["label"], d["color"]) for d in gc.get("keys", [])]
                if not keys:
                    continue
                gauge = GaugeWindow(self.root, self.store, keys,
                                    title=gc.get("title", "Gauge"))
                gauge.min_val = gc.get("min", -1)
                gauge.max_val = gc.get("max", 1)
                gauge.auto_range = gc.get("auto_range", True)
                gauge.sweep = gc.get("sweep", 270)
                self.gauges.append(gauge)

        self.root.after(100, try_restore)

    def _on_event(self, event_name):
        if event_name == "disconnected":
            self._save_state()
        elif event_name == "connected":
            self._restore_state()

    def _quit(self):
        self._save_state()
        for g in self.gauges:
            g.alive = False
            try:
                g.win.destroy()
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
        print("[Gauge] Waiting for API server…", file=sys.stderr)

    threading.Thread(target=client.run_loop, daemon=True).start()

    try:
        app = MasterApp(store, client)
        client.on_event = app._on_event
        app._restore_state()
        app.run()
    except Exception as e:
        print(f"[Gauge] {e}", file=sys.stderr)

    client.running = False
    if client.sock:
        client.sock.close()


if __name__ == "__main__":
    main()
