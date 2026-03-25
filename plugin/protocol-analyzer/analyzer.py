#!/usr/bin/env python3
"""
Protocol Analyzer — Serial Studio Plugin

Captures parsed frames with hex dumps, decoded field tables, inter-frame
timing, throughput stats, and a frame-rate graph. Features auto-scroll
toggle, copy-to-clipboard, packet limit control, and auto-reconnect.

Requirements: Serial Studio API server on port 7777, Python 3.6+, tkinter.
"""

import base64, json, signal, socket, sys, threading, time
from collections import deque
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    sys.exit("[Analyzer] tkinter required")

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
DET_BG   = "#0a0e14"
HEX_CLR  = "#7d8590"
FIELD_CLR= "#d2a8ff"
UNITS_CLR= "#7ee787"
TAG_CLR  = "#79c0ff"

MAX_FRAMES = 1000
RATE_W, RATE_H = 200, 40

# ── API Client ───────────────────────────────────────────────────────────────

class APIClient:
    def __init__(self, host="localhost", port=7777):
        self.host, self.port = host, port
        self.sock = None
        self.buffer = b""
        self.req_id = 0
        self.running = True
        self.connected = False
        self.has_dashboard = False
        self.on_frame = None
        self.on_raw = None

    def connect(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((self.host, self.port))
            self.sock, self.buffer, self.connected = s, b"", True
            self._send("initialize", {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "Protocol Analyzer", "version": "2.0.0"},
                "capabilities": {},
            })
            self._detect_dashboard()
            return True
        except (ConnectionRefusedError, OSError):
            self.connected = False
            return False

    def _send(self, method, params=None):
        self.req_id += 1
        try:
            self.sock.sendall((json.dumps({
                "jsonrpc": "2.0", "id": self.req_id,
                "method": method, "params": params or {}
            }) + "\n").encode())
        except OSError:
            self.connected = False

    def _detect_dashboard(self):
        """Auto-detect dashboard from first broadcast type in run_loop."""
        pass  # Detection now happens inline in run_loop

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

                # Parsed frame broadcasts (when dashboard is active)
                if "frames" in msg and self.on_frame:
                    self.has_dashboard = True
                    for fw in msg["frames"]:
                        d = fw.get("data")
                        if d:
                            self.on_frame(d)

                # Raw data broadcasts (when no dashboard / always available)
                elif "data" in msg and "jsonrpc" not in msg and self.on_raw:
                    if not self.has_dashboard:
                        self.on_raw(msg["data"])


# ── Data model ───────────────────────────────────────────────────────────────

class FrameRecord:
    __slots__ = ("num", "timestamp", "raw", "fields", "size", "delta_ms")
    def __init__(self, num, timestamp, raw, fields, size, delta_ms):
        self.num = num
        self.timestamp = timestamp
        self.raw = raw
        self.fields = fields
        self.size = size
        self.delta_ms = delta_ms


IDLE_SEC = 3

class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.frames = deque(maxlen=MAX_FRAMES)
        self.frame_count = 0
        self.total_bytes = 0
        self.start_time = None
        self.last_time = None
        self.deltas = deque(maxlen=200)
        self.rate_history = deque(maxlen=RATE_W)  # fps samples for graph
        self._rate_frames = 0
        self._rate_t = None

    @property
    def is_active(self):
        return self.last_time is not None and (time.time() - self.last_time) < IDLE_SEC

    @property
    def duration(self):
        if self.start_time is None or self.last_time is None:
            return 0
        return self.last_time - self.start_time

    @property
    def fps(self):
        d = self.duration
        return self.frame_count / d if d > 0 else 0

    def ingest(self, frame_data):
        now = time.time()
        with self.lock:
            self.frame_count += 1
            if self.start_time is None:
                self.start_time = now
                self._rate_t = now

            delta = 0.0
            if self.last_time is not None:
                delta = (now - self.last_time) * 1000
                self.deltas.append(delta)
            self.last_time = now

            # per-second rate sampling
            self._rate_frames += 1
            if now - (self._rate_t or now) >= 1.0:
                self.rate_history.append(self._rate_frames)
                self._rate_frames = 0
                self._rate_t = now

            decoded = []
            raw_vals = []
            for g in frame_data.get("groups", []):
                gt = g.get("title", "")
                for ds in g.get("datasets", []):
                    title = ds.get("title", "?")
                    value = ds.get("value", "")
                    units = ds.get("units", "")
                    label = f"{gt}/{title}" if gt else title
                    decoded.append((label, value, units))
                    raw_vals.append(value)

            raw_str = ",".join(raw_vals)
            self.total_bytes += len(raw_str)

            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.frames.append(FrameRecord(
                self.frame_count, ts, raw_str, decoded, len(raw_str), delta))

    def ingest_raw(self, b64_data):
        """Ingest raw device data (base64-encoded) when no dashboard is active."""
        try:
            raw_bytes = base64.b64decode(b64_data)
        except Exception:
            return

        if not raw_bytes:
            return

        now = time.time()
        with self.lock:
            self.frame_count += 1
            if self.start_time is None:
                self.start_time = now
                self._rate_t = now

            delta = 0.0
            if self.last_time is not None:
                delta = (now - self.last_time) * 1000
                self.deltas.append(delta)
            self.last_time = now

            self._rate_frames += 1
            if now - (self._rate_t or now) >= 1.0:
                self.rate_history.append(self._rate_frames)
                self._rate_frames = 0
                self._rate_t = now

            # Build raw string and decoded fields from raw bytes
            raw_str = raw_bytes.decode("utf-8", errors="replace").strip()
            self.total_bytes += len(raw_bytes)

            # Try to split as CSV for field display
            decoded = []
            parts = raw_str.split(",")
            for i, part in enumerate(parts):
                part = part.strip()
                decoded.append((f"[{i}]", part, ""))

            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.frames.append(FrameRecord(
                self.frame_count, ts, raw_str, decoded, len(raw_bytes), delta))


# ── Helpers ──────────────────────────────────────────────────────────────────

def hex_dump(data, width=16):
    raw = data.encode("utf-8", errors="replace")
    lines = []
    for off in range(0, len(raw), width):
        c = raw[off:off + width]
        hx = " ".join(f"{b:02X}" for b in c)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in c)
        lines.append(f"{off:04X}  {hx:<{width*3}}  {asc}")
    return "\n".join(lines)


# ── Rate graph ───────────────────────────────────────────────────────────────

class RateGraph(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, width=RATE_W, height=RATE_H,
                         bg=DET_BG, highlightthickness=0, **kw)

    def draw(self, values):
        self.delete("all")
        n = len(values)
        if n < 2:
            return
        hi = max(values) or 1
        w, h = RATE_W, RATE_H
        pad = 2

        # grid lines
        for frac in (0.25, 0.5, 0.75):
            y = h - pad - (h - 2*pad) * frac
            self.create_line(pad, y, w - pad, y, fill=BORDER, dash=(2, 4))

        # line
        pts = []
        for i, v in enumerate(values):
            x = pad + (w - 2*pad) * i / (n - 1)
            y = h - pad - (h - 2*pad) * min(v / hi, 1.0)
            pts.extend((x, y))
        self.create_line(pts, fill=GREEN, width=1.5, smooth=True)

        # label
        self.create_text(w - pad, pad, text=f"{values[-1]} fps",
                         fill=GREEN, anchor="ne", font=("Menlo", 8))


# ── GUI ──────────────────────────────────────────────────────────────────────

class App:
    def __init__(self, store, client):
        self.store, self.client = store, client
        self.auto_scroll = True
        self.prev_count = 0

        self.root = tk.Tk()
        self.root.title("Protocol Analyzer — Serial Studio")
        self.root.geometry("960x680")
        self.root.minsize(720, 450)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        # header
        hdr = tk.Frame(self.root, bg=HEADER, height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Protocol Analyzer", bg=HEADER, fg=TEXT,
                 font=("Helvetica Neue", 13, "bold")).pack(side="left", padx=14)

        self.stats_lbl = tk.Label(hdr, text="", bg=HEADER, fg=DIM,
                                  font=("Menlo", 10))
        self.stats_lbl.pack(side="right", padx=14)

        # auto-scroll toggle
        self.scroll_btn = tk.Label(
            hdr, text="  Auto-scroll ✓  ", bg=GREEN, fg=BG, cursor="hand2",
            font=("Helvetica Neue", 10), padx=6, pady=2)
        self.scroll_btn.pack(side="right", padx=(0, 8))
        self.scroll_btn.bind("<Button-1>", lambda _: self._toggle_scroll())

        # rate graph
        self.rate_graph = RateGraph(hdr)
        self.rate_graph.pack(side="right", padx=(0, 8), pady=6)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # paned
        pane = tk.PanedWindow(self.root, orient="vertical", bg=BG,
                               sashwidth=6, sashrelief="flat")
        pane.pack(fill="both", expand=True, padx=12, pady=8)

        # frame list
        top = tk.Frame(pane, bg=BG)
        pane.add(top, height=360)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("PA.Treeview",
                        background=SURFACE, foreground=TEXT,
                        fieldbackground=SURFACE, rowheight=24,
                        borderwidth=0, font=("Menlo", 10))
        style.configure("PA.Treeview.Heading",
                        background=HEADER, foreground=DIM,
                        borderwidth=0, relief="flat",
                        font=("Helvetica Neue", 10, "bold"))
        style.map("PA.Treeview",
                  background=[("selected", "#1f3a5f")],
                  foreground=[("selected", ACCENT)])
        style.layout("PA.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        cols = ("#", "TIME", "SIZE", "DELTA", "FIELDS", "PREVIEW")
        self.tree = ttk.Treeview(top, columns=cols, show="headings", style="PA.Treeview")
        ws = (55, 95, 55, 75, 50, 540)
        for col, w in zip(cols, ws):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w" if col == "PREVIEW" else "e", minwidth=30)

        self.tree.pack(side="left", fill="both", expand=True)
        if sys.platform != "darwin":
            vsb = tk.Scrollbar(top, orient="vertical",
                               command=self.tree.yview,
                               bg=SURFACE, troughcolor=BG, highlightthickness=0,
                               borderwidth=0, width=10)
            self.tree.configure(yscrollcommand=vsb.set)
            vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.tree.tag_configure("even", background=SURFACE)
        self.tree.tag_configure("odd", background=ROW_ALT)

        # detail view
        bot_frame = tk.Frame(pane, bg=DET_BG)
        pane.add(bot_frame)

        # copy button
        det_hdr = tk.Frame(bot_frame, bg=DET_BG, height=22)
        det_hdr.pack(fill="x"); det_hdr.pack_propagate(False)
        tk.Label(det_hdr, text="FRAME DETAIL", bg=DET_BG, fg=DIM,
                 font=("Helvetica Neue", 9, "bold")).pack(side="left", padx=8)

        copy_btn = tk.Label(det_hdr, text="  Copy  ", bg=BORDER, fg=TEXT,
                            cursor="hand2", font=("Helvetica Neue", 9), padx=4)
        copy_btn.pack(side="right", padx=8)
        copy_btn.bind("<Button-1>", lambda _: self._copy_detail())

        self.detail = tk.Text(
            bot_frame, bg=DET_BG, fg=DIM, font=("Menlo", 10),
            state="disabled", wrap="none", highlightthickness=0,
            borderwidth=0, padx=8, pady=4)
        self.detail.pack(fill="both", expand=True)

        self.detail.tag_configure("hdr", foreground=ACCENT, font=("Menlo", 10, "bold"))
        self.detail.tag_configure("hex", foreground=HEX_CLR)
        self.detail.tag_configure("fld", foreground=FIELD_CLR)
        self.detail.tag_configure("val", foreground=TEXT)
        self.detail.tag_configure("unt", foreground=UNITS_CLR)
        self.detail.tag_configure("dim", foreground=DIM)

        # footer
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        ftr = tk.Frame(self.root, bg=BG, height=28)
        ftr.pack(fill="x"); ftr.pack_propagate(False)
        self.lbl_total = tk.Label(ftr, text="", bg=BG, fg=DIM, font=("Menlo", 10))
        self.lbl_total.pack(side="left", padx=14)
        self.lbl_avg = tk.Label(ftr, text="", bg=BG, fg=DIM, font=("Menlo", 10))
        self.lbl_avg.pack(side="right", padx=14)

        self._tick()

    def _toggle_scroll(self):
        self.auto_scroll = not self.auto_scroll
        if self.auto_scroll:
            self.scroll_btn.config(text="  Auto-scroll ✓  ", bg=GREEN, fg=BG)
        else:
            self.scroll_btn.config(text="  Auto-scroll ✗  ", bg=BORDER, fg=TEXT)

    def _copy_detail(self):
        text = self.detail.get("1.0", "end").strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

    def _on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        num = int(self.tree.item(sel[0])["values"][0])

        with self.store.lock:
            frames = list(self.store.frames)

        fr = None
        for f in frames:
            if f.num == num:
                fr = f
                break
        if not fr:
            return

        d = self.detail
        d.config(state="normal")
        d.delete("1.0", "end")

        d.insert("end", f"Frame #{fr.num}  ", "hdr")
        d.insert("end", f"{fr.timestamp}   {fr.size} bytes   ", "dim")
        d.insert("end", f"\u0394 {fr.delta_ms:.1f} ms\n\n", "dim")

        d.insert("end", "HEX DUMP\n", "hdr")
        d.insert("end", hex_dump(fr.raw) + "\n\n", "hex")

        d.insert("end", "DECODED FIELDS\n", "hdr")
        for i, (label, val, units) in enumerate(fr.fields):
            d.insert("end", f"  {i:>2d}  ", "dim")
            d.insert("end", f"{label}  ", "fld")
            d.insert("end", val, "val")
            if units:
                d.insert("end", f" {units}", "unt")
            d.insert("end", "\n")

        d.config(state="disabled")

    def _tick(self):
        if not self.client.running:
            self.root.destroy(); return

        with self.store.lock:
            frames = list(self.store.frames)
            count = self.store.frame_count
            total = self.store.total_bytes
            active = self.store.is_active
            dur = self.store.duration
            fps = self.store.fps
            bps = total / dur if dur > 0 else 0
            avg_d = (sum(self.store.deltas) / len(self.store.deltas)
                     if self.store.deltas else 0)
            rates = list(self.store.rate_history)

        mode = "Parsed" if self.client.has_dashboard else "Raw"
        if active:
            self.stats_lbl.config(
                text=f"[{mode}]  {count:,} frames  •  {fps:.1f} fps  •  {bps/1024:.1f} KB/s")
        elif count > 0:
            self.stats_lbl.config(text=f"[{mode}]  {count:,} frames  •  {dur:.0f}s  •  Idle")
        else:
            self.stats_lbl.config(text=f"[{mode}]  Waiting for data…")

        self.lbl_total.config(text=f"{total:,} bytes captured")
        self.lbl_avg.config(text=f"avg \u0394 {avg_d:.1f} ms" if count > 0 else "")

        # rate graph
        if rates:
            self.rate_graph.draw(rates)

        # new frames
        if count > self.prev_count:
            new = [f for f in frames if f.num > self.prev_count]
            for f in new:
                preview = f.raw[:55] + ("\u2026" if len(f.raw) > 55 else "")
                tag = "even" if f.num % 2 == 0 else "odd"
                self.tree.insert("", "end", values=(
                    f.num, f.timestamp, f.size,
                    f"{f.delta_ms:.1f}", len(f.fields), preview
                ), tags=(tag,))

            if self.auto_scroll:
                children = self.tree.get_children()
                if children:
                    self.tree.see(children[-1])

            # prune old rows to avoid memory bloat
            children = self.tree.get_children()
            if len(children) > MAX_FRAMES:
                for iid in children[:len(children) - MAX_FRAMES]:
                    self.tree.delete(iid)

            self.prev_count = count

        self.root.after(100, self._tick)

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
    client.on_raw = store.ingest_raw

    signal.signal(signal.SIGTERM, lambda *_: setattr(client, "running", False))
    signal.signal(signal.SIGINT, lambda *_: setattr(client, "running", False))

    if not client.connect():
        print("[Analyzer] Waiting for API server…", file=sys.stderr)

    threading.Thread(target=client.run_loop, daemon=True).start()

    try:
        App(store, client).run()
    except Exception as e:
        print(f"[Analyzer] {e}", file=sys.stderr)

    client.running = False
    if client.sock:
        client.sock.close()


if __name__ == "__main__":
    main()
