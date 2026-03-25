# Digital Indicator Panel

Industrial seven-segment display panel for real-time dataset monitoring. Inspired by panel meters from Omega, Laurel, and Red Lion — the kind of displays you see on strain gauge indicators, process controllers, and lab instruments.

## Features

- **Canvas-rendered seven-segment digits** — authentic segment geometry, not a font hack
- **Multi-window** — open a separate indicator for each dataset you want to monitor
- **6 color themes** — Blue, Green, Amber, Red, Cyan, White — switchable per display
- **Hold** — freeze the display to read a value without it changing
- **Tare** — zero-offset the display (like a scale tare button)
- **Peak tracking** — capture and display min/max peaks since last reset
- **Reset** — clear tare, peaks, and hold state
- **Configurable decimals** — Auto, 0–5 fixed decimal places
- **Smart formatting** — auto-scales from µV to MV, uses scientific notation for extremes
- **Auto-reconnect** — reconnects to the API server if the connection drops

## Usage

1. Launch the plugin from the Extension Manager or Start Menu
2. The master window shows all available datasets with live values
3. Double-click any dataset to open a dedicated indicator display
4. Use the buttons on each display:
   - **HOLD** — freeze the current reading (amber highlight when active)
   - **TARE** — set the current value as the zero reference
   - **PEAK** — enable min/max peak tracking
   - **RESET** — clear all offsets and return to normal display
5. Change the color theme or decimal places using the dropdowns

## Color Themes

| Theme | Digit Color | Use Case |
|-------|------------|----------|
| Blue | `#58a6ff` | Default, cool-toned instrumentation |
| Green | `#39ff14` | Classic panel meter, general purpose |
| Amber | `#ffbf00` | Caution/warning channels, high visibility |
| Red | `#ff3030` | Alarm channels, critical values |
| Cyan | `#00e5ff` | Temperature, flow, cool-toned data |
| White | `#e0e0e0` | Neutral, high contrast |

## Screenshots

Each indicator window shows:
- Large seven-segment display (8 digits)
- Dataset name and units
- Live min/max tracking
- Control buttons (Hold, Tare, Peak, Reset)
- Color and decimal configuration
