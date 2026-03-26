#!/usr/bin/env python3
"""
Live Data Table

Real-time tabular view of every dataset field with sparkline history,
smart value formatting, min/max tracking, search filtering, freeze/resume,
column sorting, and automatic reconnection.

Requirements: Serial Studio API server on port 7777, Python 3.6+, tkinter.
"""

import json, math, signal, socket, sys, threading, time
from collections import deque

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    sys.exit("[LiveTable] tkinter required")

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

# Platform-aware font families
MONO_FONT = MONO_FONT if sys.platform == "darwin" else "Consolas" if sys.platform == "win32" else "Monospace"
SANS_FONT = SANS_FONT if sys.platform == "darwin" else "Segoe UI" if sys.platform == "win32" else "Sans"

SPARK    = "▁▂▃▄▅▆▇█"
HISTORY  = 60
IDLE_SEC = 3

# ── Helpers ──────────────────────────────────────────────────────────────────

def fmt(v):
    a = abs(v)
    if a == 0:     return "0"
    if a >= 1e6:   return f"{v/1e6:.2f}M"
    if a >= 1e4:   return f"{v/1e3:.1f}k"
    if a >= 100:   return f"{v:.1f}"
    if a >= 1:     return f"{v:.3f}"
    if a >= 0.01:  return f"{v:.4f}"
    return f"{v:.2e}"

def sparkline(vals):
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    r = hi - lo
    if r == 0:
        return SPARK[3] * len(vals)
    return "".join(SPARK[min(7, int((v - lo) / r * 7.99))] for v in vals)


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

    def connect(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((self.host, self.port))
            self.sock, self.buffer, self.connected = s, b"", True
            self.req_id += 1
            self.sock.sendall((json.dumps({
                "jsonrpc": "2.0", "id": self.req_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "Live Data Table", "version": "2.0.0"},
                    "capabilities": {},
                },
            }) + "\n").encode())
            return True
        except (ConnectionRefusedError, OSError):
            self.connected = False
            return False

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


# ── Data model ───────────────────────────────────────────────────────────────

class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.fields = []           # [(key, label, units)]
        self.field_keys = set()
        self.current = {}
        self.history = {}
        self.mins = {}
        self.maxs = {}
        self.frame_count = 0
        self.start_time = None
        self.last_frame_time = None

    @property
    def is_active(self):
        if self.last_frame_time is None:
            return False
        return (time.time() - self.last_frame_time) < IDLE_SEC

    @property
    def duration(self):
        if self.start_time is None:
            return 0
        if self.last_frame_time is None:
            return 0
        return self.last_frame_time - self.start_time

    @property
    def fps(self):
        d = self.duration
        return self.frame_count / d if d > 0 else 0

    def ingest(self, frame):
        now = time.time()
        with self.lock:
            self.frame_count += 1
            if self.start_time is None:
                self.start_time = now
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
                        label = f"{gt} / {title}" if gt else title
                        self.fields.append((key, label, units))
                        self.history[key] = deque(maxlen=HISTORY)
                        self.mins[key] = val
                        self.maxs[key] = val

                    self.history[key].append(val)
                    if val < self.mins[key]: self.mins[key] = val
                    if val > self.maxs[key]: self.maxs[key] = val
                    idx += 1


# ── GUI ──────────────────────────────────────────────────────────────────────

class App:
    def __init__(self, store, client):
        self.store = store
        self.client = client
        self.frozen = False
        self.sort_col = None
        self.sort_rev = False

        self.root = tk.Tk()
        self.root.title("Live Data Table")
        self.root.geometry("920x580")
        self.root.minsize(700, 360)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        # ── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=HEADER, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="Live Data Table", bg=HEADER, fg=TEXT,
                 font=(SANS_FONT, 13, "bold")).pack(side="left", padx=14)

        self.status_lbl = tk.Label(hdr, text="● Connecting", bg=HEADER,
                                   fg=DIM, font=(SANS_FONT, 11))
        self.status_lbl.pack(side="right", padx=14)

        self.freeze_btn = tk.Label(
            hdr, text="  Freeze  ", bg=BORDER, fg=TEXT, cursor="hand2",
            font=(SANS_FONT, 10), padx=8, pady=2)
        self.freeze_btn.pack(side="right", padx=(0, 8))
        self.freeze_btn.bind("<Button-1>", lambda _: self._toggle_freeze())

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # ── Search ───────────────────────────────────────────────────────
        sf = tk.Frame(self.root, bg=BG, height=30)
        sf.pack(fill="x", padx=12, pady=(6, 2))
        sf.pack_propagate(False)

        tk.Label(sf, text="Filter:", bg=BG, fg=DIM,
                 font=(SANS_FONT, 10)).pack(side="left")

        self.search_var = tk.StringVar()
        tk.Entry(
            sf, textvariable=self.search_var, bg=SURFACE, fg=TEXT,
            insertbackground=ACCENT, font=(MONO_FONT, 11), relief="flat",
            highlightthickness=1, highlightcolor=ACCENT,
            highlightbackground=BORDER,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

        # ── Table ────────────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("LT.Treeview",
                        background=SURFACE, foreground=TEXT,
                        fieldbackground=SURFACE, rowheight=26,
                        borderwidth=0, font=(MONO_FONT, 11))
        style.configure("LT.Treeview.Heading",
                        background=HEADER, foreground=DIM,
                        borderwidth=0, relief="flat",
                        font=(SANS_FONT, 10, "bold"))
        style.map("LT.Treeview",
                  background=[("selected", SELECT)],
                  foreground=[("selected", ACCENT)])
        style.layout("LT.Treeview", [
            ("Treeview.treearea", {"sticky": "nswe"})
        ])

        tf = tk.Frame(self.root, bg=BG)
        tf.pack(fill="both", expand=True, padx=12, pady=(2, 0))

        self.cols = ("FIELD", "VALUE", "UNITS", "MIN", "MAX", "TREND")
        self.tree = ttk.Treeview(tf, columns=self.cols, show="headings",
                                  style="LT.Treeview")
        widths  = (180, 100, 55, 95, 95, 280)
        anchors = ("w", "e", "center", "e", "e", "w")
        for col, w, a in zip(self.cols, widths, anchors):
            self.tree.heading(col, text=col, command=lambda c=col: self._sort(c))
            self.tree.column(col, width=w, anchor=a, minwidth=40)

        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.tag_configure("even", background=SURFACE)
        self.tree.tag_configure("odd", background=ROW_ALT)

        # ── Footer ───────────────────────────────────────────────────────
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        ftr = tk.Frame(self.root, bg=BG, height=28)
        ftr.pack(fill="x")
        ftr.pack_propagate(False)

        self.lbl_fc = tk.Label(ftr, text="0 frames", bg=BG, fg=DIM,
                               font=(MONO_FONT, 10))
        self.lbl_fc.pack(side="left", padx=14)

        self.lbl_rate = tk.Label(ftr, text="", bg=BG, fg=DIM,
                                 font=(MONO_FONT, 10))
        self.lbl_rate.pack(side="right", padx=14)

        self.iid_map = {}
        self._tick()

    def _sort(self, col):
        if col == "TREND":
            return
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col = col
            self.sort_rev = False

    def _toggle_freeze(self):
        self.frozen = not self.frozen
        self.freeze_btn.config(
            text="  Resume  " if self.frozen else "  Freeze  ",
            bg=ORANGE if self.frozen else BORDER,
            fg=BG if self.frozen else TEXT)

    def _get_sorted_fields(self):
        filt = self.search_var.get().lower()
        with self.store.lock:
            fields = list(self.store.fields)
        if filt:
            fields = [(k, l, u) for k, l, u in fields
                      if filt in l.lower() or filt in u.lower()]
        if self.sort_col:
            key_fn = {
                "FIELD": lambda f: f[1].lower(),
                "VALUE": lambda f: self.store.current.get(f[0], 0),
                "UNITS": lambda f: f[2].lower(),
                "MIN":   lambda f: self.store.mins.get(f[0], 0),
                "MAX":   lambda f: self.store.maxs.get(f[0], 0),
            }.get(self.sort_col)
            if key_fn:
                fields.sort(key=key_fn, reverse=self.sort_rev)
        return fields

    def _tick(self):
        if not self.client.running:
            self.root.destroy()
            return

        # Status
        with self.store.lock:
            fc = self.store.frame_count
            active = self.store.is_active
            fps = self.store.fps
            dur = self.store.duration

        if not self.client.connected:
            self.status_lbl.config(text="● Reconnecting…", fg=RED)
        elif active:
            if self.frozen:
                self.status_lbl.config(text="● Frozen", fg=ORANGE)
            else:
                self.status_lbl.config(text="● Live", fg=GREEN)
        elif fc > 0:
            self.status_lbl.config(text="● Idle", fg=DIM)
        else:
            self.status_lbl.config(text="● Connected", fg=ACCENT)

        # Footer: only show fps when active
        self.lbl_fc.config(text=f"{fc:,} frames")
        if active:
            self.lbl_rate.config(text=f"{fps:.1f} fps  •  {dur:.0f}s")
        elif fc > 0:
            self.lbl_rate.config(text=f"{dur:.0f}s total")
        else:
            self.lbl_rate.config(text="")

        # Table update
        if not self.frozen:
            fields = self._get_sorted_fields()
            with self.store.lock:
                for i, (key, label, units) in enumerate(fields):
                    val = self.store.current.get(key, 0)
                    lo = self.store.mins.get(key, 0)
                    hi = self.store.maxs.get(key, 0)
                    hist = list(self.store.history.get(key, []))
                    tag = "even" if i % 2 == 0 else "odd"

                    values = (label, fmt(val), units,
                              fmt(lo), fmt(hi), sparkline(hist))

                    if key in self.iid_map:
                        self.tree.item(self.iid_map[key], values=values, tags=(tag,))
                    else:
                        iid = self.tree.insert("", "end", values=values, tags=(tag,))
                        self.iid_map[key] = iid

        self.root.after(150, self._tick)

    def _quit(self):
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
        print("[LiveTable] Waiting for API server…", file=sys.stderr)

    threading.Thread(target=client.run_loop, daemon=True).start()

    try:
        App(store, client).run()
    except Exception as e:
        print(f"[LiveTable] {e}", file=sys.stderr)

    client.running = False
    if client.sock:
        client.sock.close()


if __name__ == "__main__":
    main()
