# CLAUDE.md - Serial Studio Extensions Repository

## Purpose

Extensions for Serial Studio: themes, frame parsers, project templates, and plugins.

## Repository Structure

```
manifest.json                           ← lists all info.json paths (version: 1)
theme/<id>/info.json                   ← theme metadata
theme/<id>/<name>.json                  ← theme color palette
theme/<id>/code-editor/<name>.xml       ← code editor syntax colors
theme/<id>/README.md                    ← theme description
frame-parser/<id>/info.json            ← parser metadata
frame-parser/<id>/<name>.js             ← JavaScript parse(frame) function
project-template/<id>/info.json        ← template metadata
project-template/<id>/<name>.ssproj     ← Serial Studio project file
plugin/<id>/info.json                  ← plugin metadata
plugin/<id>/<script>.py                 ← plugin entry point
plugin/<id>/run.sh                      ← Unix launcher wrapper
plugin/<id>/run.cmd                     ← Windows launcher wrapper
plugin/<id>/icon.svg                    ← plugin icon for toolbar/start menu
plugin/<id>/README.md                   ← plugin description
```

## Conventions

- Extension IDs: lowercase-hyphenated (e.g., `solarized-dark`, `digital-indicator`)
- Each extension is self-contained in its own directory
- info.json carries all metadata. manifest.json only references paths.
- File paths in info.json are relative to the info.json location
- All versions are `0.0.1` during development
- Themes must include a color palette JSON, code-editor XML, and README.md
- Frame parsers must export `function parse(frame)` returning an array
- Plugins communicate via Serial Studio's MCP/JSON-RPC API on port 7777
- Plugins should handle SIGTERM gracefully for clean shutdown

## Plugin Architecture

### API Connection

Plugins connect to the Serial Studio API server on TCP port 7777. The API uses JSON-RPC 2.0 over newline-delimited JSON.

**Initialization handshake:**
```python
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2024-11-05",
    "clientInfo": {"name": "Plugin Name", "version": "1.0.0"},
    "capabilities": {}
}}
```

### Frame Data Format

The API broadcasts two types of data:

**Parsed frames** (when dashboard is active):
```json
{"frames": [{"data": {"title": "...", "groups": [
    {"title": "Group", "datasets": [
        {"title": "Field", "value": "1.234", "units": "V"}
    ]}
]}}]}
```

**Raw device data** (always, base64-encoded):
```json
{"data": "base64encodedstring"}
```

Plugins should listen for `"frames"` key for structured data. The protocol analyzer also handles `"data"` for raw mode when no dashboard is active.

### Lifecycle Events

The API server broadcasts lifecycle events so plugins can save/restore state:
```json
{"event": "connected"}
{"event": "disconnected"}
```

### Plugin State Persistence

Plugin state is saved in the project file's `widgetSettings` under `__plugin__:<pluginId>` keys. This ties plugin configuration to the project, so different projects can have different plugin setups.

**Save state:**
```python
self._send("extensions.saveState", {
    "pluginId": "my-plugin",
    "state": {"windows": [...], "settings": {...}}
})
```

**Load state (on startup or after "connected" event):**
```python
resp = self._send("extensions.loadState", {"pluginId": "my-plugin"})
state = resp["result"]["state"]  # {} if no saved state
```

**Recommended lifecycle flow:**
1. Plugin starts → `extensions.loadState` → restore windows/config
2. User modifies settings → `extensions.saveState` periodically
3. `{"event": "disconnected"}` received → `extensions.saveState` (final save)
4. `{"event": "connected"}` received → `extensions.loadState` (may have changed project)

### Dataset Range Metadata

Datasets in the frame JSON may include configured ranges:
```json
{"title": "RPM", "value": "3500", "widgetMin": 0, "widgetMax": 8000, "plotMin": 0, "plotMax": 10000}
```

Plugins (especially gauges) should use `widgetMin`/`widgetMax` as default range, falling back to `plotMin`/`plotMax`, then auto-range if both are 0.

### Recommended Plugin Structure

```python
class APIClient:       # Socket connection, auto-reconnect, message dispatch
class DataStore:       # Thread-safe data model with lock
class App:             # tkinter GUI with periodic _tick() updates
```

- `APIClient.on_frame` callback → `DataStore.ingest(frame_data)`
- `App._tick()` reads from `DataStore` under lock, updates GUI, schedules next tick
- **Never create GUI widgets while holding the data lock.** This causes deadlocks.

### Activity Detection

Track `last_frame_time` in the data store. Define `is_active` as:
```python
@property
def is_active(self):
    return self.last_frame_time is not None and (time.time() - self.last_frame_time) < 3
```

Use this for:
- Status indicator: "Live" (green) when active, "Idle" (gray) when not
- FPS display: only show rate while active, show "Xs total" when idle
- Prevents showing stale fps after device disconnects

### Duration and FPS

Compute duration as `last_frame_time - start_time` (not `time.time() - start_time`), so fps reflects actual data throughput, not wall clock:
```python
@property
def duration(self):
    if self.start_time is None or self.last_frame_time is None:
        return 0
    return self.last_frame_time - self.start_time
```

## Plugin GUI Rules (tkinter on macOS)

These are hard-won lessons from macOS tkinter behavior. Violating them causes invisible widgets, white artifacts, or crashes.

### Use ttk.Treeview for data tables, NEVER tk.Canvas with embedded Frames

The `tk.Canvas` + `create_window()` + `tk.Frame` row pattern **does not work on macOS**. Rows are invisible. The only reliable approach for dark-themed scrollable tables is `ttk.Treeview` with custom styling:

```python
style = ttk.Style()
style.theme_use("default")
style.configure("XX.Treeview",
                background=SURFACE, foreground=TEXT,
                fieldbackground=SURFACE, rowheight=26,
                borderwidth=0, font=("Menlo", 11))
style.configure("XX.Treeview.Heading",
                background=HEADER, foreground=DIM,
                borderwidth=0, relief="flat",
                font=("Helvetica Neue", 10, "bold"))
style.map("XX.Treeview",
          background=[("selected", SELECT)],
          foreground=[("selected", ACCENT)])
style.layout("XX.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
```

Use unique style names per plugin (e.g., `"LT.Treeview"`, `"ST.Treeview"`) to avoid conflicts.

### Hide scrollbars on macOS

macOS ignores `tk.Scrollbar` color styling, so scrollbars are always white. Hide them on macOS. Users scroll with trackpad gestures:

```python
tree.pack(side="left", fill="both", expand=True)
if sys.platform != "darwin":
    vsb = tk.Scrollbar(parent, orient="vertical", command=tree.yview,
                       bg=SURFACE, troughcolor=BG, highlightthickness=0,
                       borderwidth=0, width=10)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
```

### Use tk.Label for buttons, NEVER tk.Button

macOS ignores `tk.Button` background/foreground styling. Buttons always render with white system chrome. Use `tk.Label` with click/hover bindings instead:

```python
lbl = tk.Label(parent, text="  HOLD  ", cursor="hand2",
               bg=colors["dim"], fg=colors["label"],
               font=("Menlo", 9, "bold"), padx=6, pady=4)
lbl.bind("<Button-1>", lambda _: command())
lbl.bind("<Enter>", lambda _: lbl.config(bg=highlight, fg=bg))
lbl.bind("<Leave>", lambda _: lbl.config(bg=normal_bg, fg=normal_fg))
```

### Avoid ttk.Combobox in dark themes

`ttk.Combobox` dropdown is always white on macOS. Use cycling `tk.Label` buttons instead:
```python
def _cycle_option(self):
    self._idx = (self._idx + 1) % len(self._options)
    self.btn.config(text=self._options[self._idx])
```

### Thread safety

- All data writes happen in the background `run_loop` thread
- All GUI updates happen in the main thread via `root.after(ms, callback)`
- **Never hold the data lock while creating tkinter widgets.** The widget constructor may trigger tkinter callbacks that try to acquire the same lock, leading to a deadlock.
- Pattern: find data under lock, release lock, then create widgets:
  ```python
  found = None
  with store.lock:
      for key, g, t, u in store.fields:
          if match:
              found = (key, g, t, u)
              break
  if found:
      IndicatorWindow(root, store, *found)  # outside lock!
  ```

### Wrap tick methods in try/except

Toplevel windows can be destroyed between `after()` scheduling and execution:
```python
def _tick(self):
    if not self.alive:
        return
    try:
        self._update_display()
        self.win.after(100, self._tick)
    except (tk.TclError, RuntimeError):
        self.alive = False
```

## Plugin Platform Support

### Shell wrappers (required for Python plugins)

Python plugins need `run.sh` / `run.cmd` wrappers to avoid tkinter issues when launched from QProcess without a terminal:

**run.sh:**
```sh
#!/bin/sh
cd "$(dirname "$0")"
exec python3 plugin.py "$@"
```

**run.cmd:**
```cmd
@echo off
cd /d "%~dp0"
python plugin.py %*
```

### Platform keys in info.json

```json
"platforms": {
    "darwin/*":  { "entry": "run.sh", "runtime": "", "files": ["run.sh"] },
    "linux/*":   { "entry": "run.sh", "runtime": "", "files": ["run.sh"] },
    "windows/*": { "entry": "run.cmd", "runtime": "", "files": ["run.cmd"] }
}
```

- macOS: always `darwin/*` (universal builds)
- Linux: `linux/x86_64`, `linux/arm64`, or `linux/*`
- `runtime: ""` means the entry is a native executable / shell script
- Fallback order: exact `os/arch`, then `os/*`, then `*`, then top-level fields

### Plugin icons

Plugins should include an `icon.svg` for display in the start menu and toolbar. Add to info.json:
```json
"icon": "icon.svg"
```

## Theme Development

### Required files

- `<id>.json`: full color palette (see any built-in theme for key list)
- `code-editor/<id>.xml`: syntax highlighting for the JavaScript editor
- `info.json`: metadata with `"type": "theme"`
- `README.md`: description with color table

### Theme JSON structure

```json
{
  "title": "Theme Name",
  "parameters": {
    "code-editor-theme": "theme-id",
    "start-icon": "qrc:/rcc/logo/start-dark.svg"
  },
  "translations": { "en_US": "Theme Name", ... },
  "colors": { ... },
}
```

- `start-icon`: use `start-dark.svg` for dark themes, `start.svg` for light themes
- `code-editor-theme`: must match the XML filename (without extension)
- The code editor theme path is automatically rewritten to an absolute path by the ThemeManager

### Color keys

Full palette requires ~80 color keys plus `widget_colors` (20 colors) and `device_colors` (10 gradient pairs). Reference: `app/rcc/themes/default.json` in the Serial Studio repo.

Key groups:
- `groupbox_*`: panel borders and backgrounds
- `pane_*`: content area and section headers
- `toolbar_*`: main toolbar gradient and buttons
- `console_*`: terminal/console widget
- `widget_*`: dashboard widget controls
- `window_*`: window chrome and title bars
- `taskbar_*`: dashboard taskbar
- `start_menu_*`: dashboard start menu
- `table_*`: data grid tables
- `plot3d_*`: 3D visualization
- `polar_*`: polar/compass widgets

### Dark theme tips

- Separators/borders need enough contrast against both `groupbox_background` and `pane_background` to be visible. Typically 15-20% lighter than the darker surface.
- Console text should NOT be the same color as code editor keywords
- Pane caption gradient: darker top → lighter bottom gives "pressed in" depth

### Light theme tips

- Toolbar gradient should be noticeably darker than content area
- Pane caption gradient: darker top → lighter bottom
- Borders around `#B8B098` range (warm gray) for Solarized-family palettes
- Widget borders need to be darker than widget backgrounds to be visible

## Testing Locally

1. Clone this repo next to the Serial Studio repo
2. In Serial Studio Pro, open Extensions → Repos → Browse → select this folder
3. Extensions appear immediately, so you can install and test right away
4. For GPL builds, the default extension repo is used (repo settings are Pro-only)
5. Extensions auto-update when a newer version is detected in the repository

## Seven-Segment Display Notes (Digital Indicator)

- Decimal points are zero-width. They are drawn as circles in the gap between digits, not as separate columns.
- Never use scientific notation (e.g., `1.0e-03`). Real panel meters don't. Use fixed decimal with auto-selected precision.
- `format_7seg()` must guarantee exactly `width` non-dot characters
- Character set: `0-9`, `-`, ` `, `.`, `E`/`e`, `F`, `r`, `o`, `L`, `H`, `d`, `P`, `n`, `t`
- Canvas `create_rectangle` for segments, `create_oval` for decimal points
- Use `canvas.delete("seg")` + full redraw each tick (simpler than tracking individual items)
