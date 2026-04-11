# Serial Studio Extensions

Extensions for [Serial Studio](https://serial-studio.com). Themes and plugins that extend the application without modifying its core.

## Available Extensions

### Themes

| Extension | Style | Description |
|-----------|-------|-------------|
| [Solarized Dark](theme/solarized-dark/) | Dark | Ethan Schoonover's iconic palette with calibrated contrast |
| [Solarized Light](theme/solarized-light/) | Light | Warm cream variant of Solarized for bright environments |
| [Aether Dark](theme/aether-dark/) | Dark | GitHub-inspired deep space dark with cool blue accents |
| [Aether Light](theme/aether-light/) | Light | Clean GitHub light mode with bold blue accents |
| [Classic](theme/classic/) | Dark | The original Serial Studio look with teal and mint green |
| [Gunmetal](theme/gunmetal/) | Dark | Industrial charcoal with warm gold accents |
| [Iron](theme/iron/) | Light | Polished white surface with gold highlights |
| [Midday](theme/midday/) | Light | Slate-blue toolbars with amber accents |
| [Midnight](theme/midnight/) | Dark | Ultra-dark with muted indigo for late-night sessions |
| [Rust](theme/rust/) | Dark | Warm earthy browns with gold accents |

### Plugins

| Extension | Category | Description |
|-----------|----------|-------------|
| [Live Data Table](plugin/live-data-table/) | Visualization | Sortable table with sparklines, search, freeze/resume |
| [Data Statistics Logger](plugin/data-stats-logger/) | Analysis | Running stats (min/max/mean/stdev) with HTML export |
| [Threshold Alerts](plugin/threshold-alerts/) | Monitoring | Per-field alert thresholds with event log |
| [Protocol Analyzer](plugin/protocol-analyzer/) | Debugging | Frame capture with hex dumps and timing analysis |
| [Digital Indicator](plugin/digital-indicator/) | Visualization | Seven-segment displays with hold, tare, peak tracking |
| [Custom Gauge](plugin/custom-gauge/) | Visualization | Multi-needle analog gauges with auto-ranging |

## Installation

1. Open Serial Studio and click **Extensions** in the toolbar
2. Browse the catalog. Extensions are grouped by type
3. Click a card to see details, then click **Install**

Installed extensions auto-update when a newer version is detected in the repository.

## Plugin Features

All plugins in this repository share a common set of capabilities:

- **Auto-reconnect** to the Serial Studio API server
- **State persistence**: plugin windows and settings are saved to the project file
- **Auto-launch**: plugins that were running are relaunched on next startup
- **Start Menu integration**: launch plugins from the dashboard Start Menu
- **Cross-platform**: separate entry points for macOS, Linux, and Windows

## Contributing

### Development Setup

1. Clone this repository
2. In Serial Studio, open **Extensions** > **Repos** > **Browse** and select the cloned folder
3. Extensions appear immediately, so you can install and test right away
4. Make changes, reload, and iterate

### Creating Extensions

See the [doc/](doc/) folder for detailed guides:

1. [Getting Started](doc/01-getting-started.md): extension types, info.json structure, local testing
2. [Creating Themes](doc/02-creating-themes.md): color palettes, code editor XML, design tips
3. [Creating Plugins](doc/03-creating-plugins.md): API connection, frame data, tkinter patterns
4. [Plugin State Persistence](doc/04-plugin-state.md): save/restore plugin state in project files
5. [Platform Support](doc/05-platform-support.md): platform keys, shell wrappers, native binaries

### Repository Structure

```
manifest.json                    Extension index (references all info.json paths)
theme/<id>/                      Color themes (palette JSON + code editor XML)
plugin/<id>/                     External plugins (Python + shell wrappers)
doc/                             Development guides
```

### Conventions

- Extension IDs use `lowercase-hyphenated` format
- Each extension is self-contained in its own directory
- `info.json` carries all metadata; `manifest.json` only references paths
- File paths in `info.json` are relative to the `info.json` location

## License

This repository is licensed under the [MIT License](LICENSE). Copyright (c) 2025 Alex Spataru.
