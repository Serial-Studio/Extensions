#!/usr/bin/env python3
"""
Data Statistics Logger

Computes running statistics (Welford's algorithm) for every numeric field:
min, max, mean, standard deviation, sample count. Features Canvas-drawn
distribution bars, auto-reconnect, freeze/resume, and generates a styled
HTML report on exit.

Requirements: Serial Studio API server on port 7777, Python 3.6+, tkinter.
"""

import json, math, os, re, signal, sys, threading, time, webbrowser
from datetime import datetime
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    sys.exit("[StatsLogger] tkinter required")

# ── Theme ────────────────────────────────────────────────────────────────────

BG       = "#0d1117"
SURFACE  = "#161b22"
HEADER   = "#1a2332"
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
MONO_FONT = "Menlo" if sys.platform == "darwin" else "Consolas" if sys.platform == "win32" else "Monospace"
SANS_FONT = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI" if sys.platform == "win32" else "Sans"

# ── Helpers ──────────────────────────────────────────────────────────────────

def fmt(v):
    a = abs(v)
    if a == 0: return "0"
    if a >= 1e6:  return f"{v/1e6:.2f}M"
    if a >= 1e4:  return f"{v/1e3:.1f}k"
    if a >= 100:  return f"{v:.1f}"
    if a >= 1:    return f"{v:.3f}"
    if a >= 0.01: return f"{v:.4f}"
    return f"{v:.2e}"


class RunningStats:
    __slots__ = ("n", "mean", "m2", "min_val", "max_val")
    def __init__(self):
        self.n, self.mean, self.m2 = 0, 0.0, 0.0
        self.min_val, self.max_val = float("inf"), float("-inf")

    def update(self, x):
        self.n += 1
        d1 = x - self.mean
        self.mean += d1 / self.n
        self.m2 += d1 * (x - self.mean)
        if x < self.min_val: self.min_val = x
        if x > self.max_val: self.max_val = x

    @property
    def stdev(self):
        return math.sqrt(self.m2 / self.n) if self.n > 1 else 0.0


from grpc_client import GRPCClient


# ── Data store ───────────────────────────────────────────────────────────────

IDLE_SEC = 3

class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.fields = []          # [(key, label)]
        self.field_set = set()
        self.stats = {}           # key → RunningStats
        self.frame_count = 0
        self.start_time = None
        self.last_frame_time = None
        self.project_title = None

    @property
    def is_active(self):
        return self.last_frame_time is not None and (time.time() - self.last_frame_time) < IDLE_SEC

    @property
    def duration(self):
        if self.start_time is None or self.last_frame_time is None:
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
            if self.project_title is None and frame.get("title"):
                self.project_title = frame["title"]
            idx = 0
            for g in frame.get("groups", []):
                gt = g.get("title", "")
                for ds in g.get("datasets", []):
                    title = ds.get("title", f"Field {idx}")
                    units = ds.get("units", "")
                    try:
                        val = float(ds.get("value", ""))
                    except (ValueError, TypeError):
                        idx += 1
                        continue
                    key = f"f{idx}"
                    if key not in self.field_set:
                        self.field_set.add(key)
                        lbl = f"{gt} / {title}" if gt else title
                        if units:
                            lbl += f" ({units})"
                        self.fields.append((key, lbl))
                        self.stats[key] = RunningStats()
                    self.stats[key].update(val)
                    idx += 1


# ── GUI ──────────────────────────────────────────────────────────────────────

class App:
    def __init__(self, store, client):
        self.store, self.client = store, client
        self.frozen = False

        self.root = tk.Tk()
        self.root.title("Data Statistics")
        self.root.geometry("880x540")
        self.root.minsize(640, 340)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        # header
        hdr = tk.Frame(self.root, bg=HEADER, height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Data Statistics Logger", bg=HEADER, fg=TEXT,
                 font=(SANS_FONT, 13, "bold")).pack(side="left", padx=14)

        self.status = tk.Label(hdr, text="● Connecting", bg=HEADER, fg=DIM,
                               font=(SANS_FONT, 11))
        self.status.pack(side="right", padx=14)

        self.freeze_btn = tk.Label(
            hdr, text="  Freeze  ", bg=BORDER, fg=TEXT, cursor="hand2",
            font=(SANS_FONT, 10), padx=8, pady=2)
        self.freeze_btn.pack(side="right", padx=(0, 8))
        self.freeze_btn.bind("<Button-1>", lambda _: self._toggle_freeze())

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # table
        tf = tk.Frame(self.root, bg=BG)
        tf.pack(fill="both", expand=True, padx=12, pady=(6, 0))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("ST.Treeview",
                        background=SURFACE, foreground=TEXT,
                        fieldbackground=SURFACE, rowheight=26,
                        borderwidth=0, font=(MONO_FONT, 11))
        style.configure("ST.Treeview.Heading",
                        background=HEADER, foreground=DIM,
                        borderwidth=0, relief="flat",
                        font=(SANS_FONT, 10, "bold"))
        style.map("ST.Treeview",
                  background=[("selected", "#1f3a5f")],
                  foreground=[("selected", ACCENT)])
        style.layout("ST.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        self.cols = ("FIELD", "SAMPLES", "MIN", "MAX", "MEAN", "STD DEV")
        self.tree = ttk.Treeview(tf, columns=self.cols, show="headings",
                                  style="ST.Treeview")
        widths = (200, 80, 95, 95, 95, 95)
        for col, w in zip(self.cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="e" if col != "FIELD" else "w",
                             minwidth=40)

        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.tag_configure("even", background=SURFACE)
        self.tree.tag_configure("odd", background=ROW_ALT)

        # footer
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        ftr = tk.Frame(self.root, bg=BG, height=28)
        ftr.pack(fill="x"); ftr.pack_propagate(False)
        self.lbl_fc = tk.Label(ftr, text="0 frames", bg=BG, fg=DIM, font=(MONO_FONT, 10))
        self.lbl_fc.pack(side="left", padx=14)
        self.lbl_rate = tk.Label(ftr, text="", bg=BG, fg=DIM, font=(MONO_FONT, 10))
        self.lbl_rate.pack(side="right", padx=14)

        self.iid_map = {}
        self._tick()

    def _toggle_freeze(self):
        self.frozen = not self.frozen
        self.freeze_btn.config(
            text="  Resume  " if self.frozen else "  Freeze  ",
            bg=ORANGE if self.frozen else BORDER,
            fg=BG if self.frozen else TEXT)

    def _tick(self):
        if not self.client.running:
            self.root.destroy()
            return

        # status
        with self.store.lock:
            fc = self.store.frame_count
            active = self.store.is_active
            fps = self.store.fps
            dur = self.store.duration

        if not self.client.connected:
            self.status.config(text="● Reconnecting…", fg=RED)
        elif active:
            self.status.config(
                text="● Frozen" if self.frozen else "● Recording",
                fg=ORANGE if self.frozen else GREEN)
        elif fc > 0:
            self.status.config(text="● Idle", fg=DIM)
        else:
            self.status.config(text="● Connected", fg=ACCENT)

        self.lbl_fc.config(text=f"{fc:,} frames")
        if active:
            self.lbl_rate.config(text=f"{fps:.1f} fps  •  {dur:.0f}s")
        elif fc > 0:
            self.lbl_rate.config(text=f"{dur:.0f}s total")
        else:
            self.lbl_rate.config(text="")

        if not self.frozen:
            with self.store.lock:
                for i, (key, label) in enumerate(self.store.fields):
                    s = self.store.stats[key]
                    tag = "even" if i % 2 == 0 else "odd"
                    values = (label, f"{s.n:,}", fmt(s.min_val),
                              fmt(s.max_val), fmt(s.mean), fmt(s.stdev))

                    if key in self.iid_map:
                        self.tree.item(self.iid_map[key], values=values, tags=(tag,))
                    else:
                        iid = self.tree.insert("", "end", values=values, tags=(tag,))
                        self.iid_map[key] = iid

        self.root.after(200, self._tick)

    def _quit(self):
        self.client.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ── HTML report ──────────────────────────────────────────────────────────────

def generate_report(store):
    dur = time.time() - store.start_time if store.start_time else 0
    rate = store.frame_count / dur if dur > 0 else 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = ""
    with store.lock:
        for key, label in store.fields:
            s = store.stats[key]
            rows += (f"<tr><td>{label}</td><td>{s.n:,}</td>"
                     f"<td>{s.min_val:.4f}</td><td>{s.max_val:.4f}</td>"
                     f"<td>{s.mean:.4f}</td><td>{s.stdev:.4f}</td></tr>\n")

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Data Statistics Report</title><style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;margin:40px;background:#0d1117;color:#e6edf3}}
h1{{color:#58a6ff;font-size:22px}}
.meta{{color:#8b949e;font-size:14px;margin-bottom:24px}}
table{{border-collapse:collapse;width:100%;background:#161b22;border-radius:8px;
       overflow:hidden;border:1px solid #30363d}}
th{{background:#1c2633;color:#8b949e;padding:12px 16px;text-align:left;font-size:12px;
    text-transform:uppercase;letter-spacing:.5px}}
td{{padding:10px 16px;border-bottom:1px solid #21262d;font-variant-numeric:tabular-nums}}
tr:hover td{{background:#1c2d41}}
</style></head><body>
<h1>Data Statistics Report</h1>
<div class="meta">Generated: {now}<br>
Frames: {store.frame_count:,} &middot; Duration: {dur:.1f}s &middot; {rate:.1f} fps</div>
<table><tr><th>Field</th><th>Samples</th><th>Min</th><th>Max</th>
<th>Mean</th><th>Std Dev</th></tr>
{rows}</table></body></html>"""

    workspace = Path.home() / "Documents" / "Serial Studio"
    project_name = store.project_title or "Untitled Project"
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', project_name).strip()
    out = workspace / "Stats" / safe_name
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"stats-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"
    path.write_text(html)
    return str(path)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    store = DataStore()
    client = GRPCClient()
    client.on_frame = store.ingest

    signal.signal(signal.SIGTERM, lambda *_: setattr(client, "running", False))
    signal.signal(signal.SIGINT, lambda *_: setattr(client, "running", False))

    if not client.connect():
        print("[StatsLogger] Waiting for API server…", file=sys.stderr)

    threading.Thread(target=client.run_loop, daemon=True).start()

    try:
        App(store, client).run()
    except Exception as e:
        print(f"[StatsLogger] {e}", file=sys.stderr)

    client.running = False
    if store.frame_count > 0:
        path = generate_report(store)
        print(f"[StatsLogger] Report: {path}", file=sys.stderr)
        try:
            webbrowser.open(f"file://{path}")
        except Exception:
            pass

    client.stop()


if __name__ == "__main__":
    main()
