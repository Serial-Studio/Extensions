#!/usr/bin/env python3
"""
Threshold Alerts

Real-time field monitor with per-field high/low thresholds. Breaches trigger
color-coded row highlighting, a timestamped event log, and a system bell.
Double-click Low/High cells to configure. Thresholds persist to a JSON file
in the plugin directory. Auto-reconnects to the API server.

Requirements: Serial Studio API server on port 7777, Python 3.6+, tkinter.
"""

import json, os, signal, socket, sys, threading, time
from datetime import datetime
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    sys.exit("[Alerts] tkinter required")

# ── Theme ────────────────────────────────────────────────────────────────────

BG       = "#0d1117"
SURFACE  = "#161b22"
HEADER   = "#2d1520"
HDR_TXT  = "#ff7b72"
BORDER   = "#30363d"
TEXT     = "#e6edf3"
DIM      = "#8b949e"
ACCENT   = "#58a6ff"
GREEN    = "#3fb950"
ORANGE   = "#d29922"
RED      = "#f85149"
ROW_ALT  = "#111820"
LOG_BG   = "#0a0e14"
BADGE_OK = "#238636"

# Platform-aware font families
MONO_FONT = MONO_FONT if sys.platform == "darwin" else "Consolas" if sys.platform == "win32" else "Monospace"
SANS_FONT = SANS_FONT if sys.platform == "darwin" else "Segoe UI" if sys.platform == "win32" else "Sans"

# ── Threshold persistence ────────────────────────────────────────────────────

THRESH_FILE = Path(__file__).parent / "thresholds.json"

def load_thresholds():
    if THRESH_FILE.exists():
        try:
            data = json.loads(THRESH_FILE.read_text())
            return {k: tuple(v) for k, v in data.items()}
        except Exception:
            pass
    return {}

def save_thresholds(thresholds):
    try:
        THRESH_FILE.write_text(json.dumps(
            {k: list(v) for k, v in thresholds.items()}, indent=2))
    except Exception:
        pass

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
            self._send("initialize", {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "Threshold Alerts", "version": "2.0.0"},
                "capabilities": {},
            })
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


# ── Data store ───────────────────────────────────────────────────────────────

INF = float("inf")
IDLE_SEC = 3

class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.fields = []           # [(key, label)]
        self.field_set = set()
        self.current = {}
        self.thresholds = load_thresholds()
        self.alert_log = []
        self.alert_counts = {}
        self.frame_count = 0
        self.last_frame_time = None

    @property
    def is_active(self):
        return self.last_frame_time is not None and (time.time() - self.last_frame_time) < IDLE_SEC

    def ingest(self, frame):
        with self.lock:
            self.frame_count += 1
            self.last_frame_time = time.time()
            idx = 0
            for g in frame.get("groups", []):
                gt = g.get("title", "")
                for ds in g.get("datasets", []):
                    title = ds.get("title", f"Field {idx}")
                    try:
                        val = float(ds.get("value", ""))
                    except (ValueError, TypeError):
                        idx += 1; continue

                    key = f"f{idx}"
                    self.current[key] = val

                    if key not in self.field_set:
                        self.field_set.add(key)
                        lbl = f"{gt} / {title}" if gt else title
                        self.fields.append((key, lbl))

                    if key in self.thresholds:
                        lo, hi = self.thresholds[key]
                        if val > hi or val < lo:
                            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            d = "HIGH" if val > hi else "LOW"
                            label = next((l for k, l in self.fields if k == key), key)
                            self.alert_log.append((ts, label, val, d))
                            self.alert_counts[key] = self.alert_counts.get(key, 0) + 1
                            if len(self.alert_log) > 1000:
                                self.alert_log = self.alert_log[-500:]
                    idx += 1


# ── GUI ──────────────────────────────────────────────────────────────────────

class App:
    def __init__(self, store, client):
        self.store, self.client = store, client
        self.prev_log_len = 0

        self.root = tk.Tk()
        self.root.title("Threshold Alerts")
        self.root.geometry("820x640")
        self.root.minsize(620, 420)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        # header
        hdr = tk.Frame(self.root, bg=HEADER, height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Threshold Alerts", bg=HEADER, fg=HDR_TXT,
                 font=(SANS_FONT, 13, "bold")).pack(side="left", padx=14)

        self.badge = tk.Label(hdr, text=" 0 alerts ", bg=BADGE_OK, fg=TEXT,
                              font=(MONO_FONT, 10, "bold"), padx=6)
        self.badge.pack(side="right", padx=14, pady=10)

        self.status = tk.Label(hdr, text="● Connecting", bg=HEADER, fg=DIM,
                               font=(SANS_FONT, 11))
        self.status.pack(side="right", padx=(0, 8))

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # paned
        pane = tk.PanedWindow(self.root, orient="vertical", bg=BG,
                               sashwidth=6, sashrelief="flat")
        pane.pack(fill="both", expand=True, padx=12, pady=8)

        # top: field table
        top = tk.Frame(pane, bg=BG)
        pane.add(top, height=320)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("AL.Treeview",
                        background=SURFACE, foreground=TEXT,
                        fieldbackground=SURFACE, rowheight=26,
                        borderwidth=0, font=(MONO_FONT, 11))
        style.configure("AL.Treeview.Heading",
                        background="#1c2633", foreground=DIM,
                        borderwidth=0, relief="flat",
                        font=(SANS_FONT, 10, "bold"))
        style.map("AL.Treeview",
                  background=[("selected", "#1f3a5f")],
                  foreground=[("selected", ACCENT)])
        style.layout("AL.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        self.tcols = ("FIELD", "VALUE", "LOW", "HIGH", "STATUS", "ALERTS")
        self.tree = ttk.Treeview(top, columns=self.tcols, show="headings",
                                  style="AL.Treeview")
        ws = (180, 90, 80, 80, 70, 65)
        ancs = ("w", "e", "e", "e", "center", "e")
        for col, w, a in zip(self.tcols, ws, ancs):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor=a, minwidth=40)

        self.tree.pack(fill="both", expand=True)

        self.tree.tag_configure("ok", foreground=GREEN)
        self.tree.tag_configure("alert", foreground=RED)
        self.tree.tag_configure("even", background=SURFACE)
        self.tree.tag_configure("odd", background=ROW_ALT)
        self.tree.bind("<Double-1>", self._on_double_click)

        tk.Label(top, text="Double-click Low / High to set thresholds",
                 bg=BG, fg=DIM, font=(SANS_FONT, 10)).pack(anchor="w", pady=(4, 0))

        # bottom: log
        bot = tk.Frame(pane, bg=LOG_BG)
        pane.add(bot)

        log_hdr = tk.Frame(bot, bg=LOG_BG, height=22)
        log_hdr.pack(fill="x"); log_hdr.pack_propagate(False)
        tk.Label(log_hdr, text="EVENT LOG", bg=LOG_BG, fg=DIM,
                 font=(SANS_FONT, 9, "bold")).pack(side="left", padx=8)

        self.log_text = tk.Text(
            bot, bg=LOG_BG, fg="#ff9492", font=(MONO_FONT, 10),
            state="disabled", wrap="none", highlightthickness=0,
            borderwidth=0, padx=8, pady=4)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("ts", foreground=DIM)
        self.log_text.tag_configure("hi", foreground=RED)
        self.log_text.tag_configure("lo", foreground=ORANGE)

        # footer
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        ftr = tk.Frame(self.root, bg=BG, height=28)
        ftr.pack(fill="x"); ftr.pack_propagate(False)
        self.lbl_fc = tk.Label(ftr, text="0 frames", bg=BG, fg=DIM, font=(MONO_FONT, 10))
        self.lbl_fc.pack(side="left", padx=14)

        self.iid_map = {}
        self._tick()

    def _on_double_click(self, event):
        """Handle double-click on LOW/HIGH columns to edit thresholds."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        col_id = self.tree.identify_column(event.x)
        col_idx = int(col_id.replace("#", "")) - 1
        col_name = self.tcols[col_idx] if 0 <= col_idx < len(self.tcols) else ""
        if col_name not in ("LOW", "HIGH"):
            return

        # Find the key for this row
        values = self.tree.item(item, "values")
        field_name = values[0]
        key = None
        with self.store.lock:
            for k, label in self.store.fields:
                if label == field_name:
                    key = k
                    break
        if key:
            self._edit_thresh(key, col_name)

    def _edit_thresh(self, key, col):
        cur_lo, cur_hi = self.store.thresholds.get(key, (-INF, INF))
        current = cur_lo if col == "LOW" else cur_hi
        label = next((l for k, l in self.store.fields if k == key), key)

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Set {col.lower()} threshold")
        dlg.geometry("320x100")
        dlg.configure(bg=SURFACE)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text=f"{col} for {label}:", fg=TEXT, bg=SURFACE,
                 font=(SANS_FONT, 11)).pack(pady=(12, 6))

        entry = tk.Entry(dlg, font=(MONO_FONT, 12), bg=BG, fg=TEXT,
                         insertbackground=ACCENT, relief="flat",
                         highlightthickness=1, highlightcolor=ACCENT,
                         highlightbackground=BORDER)
        entry.pack(padx=20, fill="x")
        if current not in (-INF, INF):
            entry.insert(0, f"{current:.4f}")
        entry.select_range(0, tk.END)
        entry.focus_set()

        def apply(*_):
            try:
                val = float(entry.get())
            except ValueError:
                dlg.destroy(); return
            with self.store.lock:
                lo, hi = self.store.thresholds.get(key, (-INF, INF))
                if col == "LOW":
                    self.store.thresholds[key] = (val, hi)
                else:
                    self.store.thresholds[key] = (lo, val)
                save_thresholds(self.store.thresholds)
            dlg.destroy()

        entry.bind("<Return>", apply)

    def _clear_thresh(self, key, col):
        with self.store.lock:
            lo, hi = self.store.thresholds.get(key, (-INF, INF))
            if col == "LOW":
                self.store.thresholds[key] = (-INF, hi)
            else:
                self.store.thresholds[key] = (lo, INF)
            if self.store.thresholds[key] == (-INF, INF):
                self.store.thresholds.pop(key, None)
            save_thresholds(self.store.thresholds)

    def _tick(self):
        if not self.client.running:
            self.root.destroy(); return

        # status
        with self.store.lock:
            active = self.store.is_active
            fc = self.store.frame_count

        if not self.client.connected:
            self.status.config(text="● Reconnecting…", fg=RED)
        elif active:
            self.status.config(text="● Monitoring", fg=GREEN)
        elif fc > 0:
            self.status.config(text="● Idle", fg=DIM)
        else:
            self.status.config(text="● Connected", fg=ACCENT)

        total_alerts = 0
        with self.store.lock:
            self.lbl_fc.config(text=f"{self.store.frame_count:,} frames")

            for i, (key, label) in enumerate(self.store.fields):
                val = self.store.current.get(key, 0)
                lo, hi = self.store.thresholds.get(key, (-INF, INF))
                count = self.store.alert_counts.get(key, 0)
                total_alerts += count

                lo_s = f"{lo:.2f}" if lo != -INF else "-"
                hi_s = f"{hi:.2f}" if hi != INF else "-"

                if lo != -INF and val < lo:
                    status, tag = "LOW", "alert"
                elif hi != INF and val > hi:
                    status, tag = "HIGH", "alert"
                else:
                    status, tag = "OK", "ok"

                row_tag = "even" if i % 2 == 0 else "odd"
                values = (label, f"{val:.4f}", lo_s, hi_s, status, str(count))

                if key in self.iid_map:
                    self.tree.item(self.iid_map[key], values=values, tags=(tag, row_tag))
                else:
                    iid = self.tree.insert("", "end", values=values, tags=(tag, row_tag))
                    self.iid_map[key] = iid

            # log
            log_len = len(self.store.alert_log)
            if log_len != self.prev_log_len:
                self.log_text.config(state="normal")
                self.log_text.delete("1.0", "end")
                for ts, label, val, direction in self.store.alert_log[-200:]:
                    tag = "hi" if direction == "HIGH" else "lo"
                    self.log_text.insert("end", f"[{ts}]  ", "ts")
                    self.log_text.insert("end", f"{label}: {val:.4f} ({direction})\n", tag)
                self.log_text.see("end")
                self.log_text.config(state="disabled")
                self.prev_log_len = log_len
                try:
                    self.root.bell()
                except tk.TclError:
                    pass

        self.badge.config(
            text=f" {total_alerts} alerts ",
            bg=RED if total_alerts > 0 else BADGE_OK)

        self.root.after(200, self._tick)

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
        print("[Alerts] Waiting for API server…", file=sys.stderr)

    threading.Thread(target=client.run_loop, daemon=True).start()

    try:
        App(store, client).run()
    except Exception as e:
        print(f"[Alerts] {e}", file=sys.stderr)

    client.running = False
    if client.sock:
        client.sock.close()


if __name__ == "__main__":
    main()
