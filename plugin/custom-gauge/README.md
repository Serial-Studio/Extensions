# Custom Gauge Panel

Multi-needle analog gauge with Canvas-drawn dials for real-time dataset monitoring. Overlay multiple datasets on a single gauge to compare channels, much like an aircraft instrument cluster or industrial process display.

## Features

- **Canvas-rendered analog dial.** Tick marks, labels, needle with arrow tip, and center cap.
- **Multi-needle.** Add 2+ datasets to one gauge, each with a distinct color (10 colors available).
- **Auto-ranging.** Gauge min/max automatically tracks observed data with 15% margin.
- **Manual range.** Click SET MIN / SET MAX to lock the scale.
- **3 sweep styles.** 270° (full), 180° (half-circle), 90° (quarter). Cycle with the button.
- **Digital readout.** Numeric values shown below the dial with needle color coding.
- **Resizable.** Drag the window to resize; the gauge scales proportionally.
- **60fps update.** Smooth needle movement.

## Usage

1. Launch from the Extension Manager or Start Menu
2. The master window shows all available datasets
3. Double-click a dataset to create a gauge window
4. In the gauge window:
   - **+ DATASET.** Add another needle (different color).
   - **SET MIN / SET MAX.** Manually set the scale range.
   - **AUTO.** Return to auto-ranging mode.
   - **270° / 180° / 90°.** Cycle the sweep angle.
5. The gauge resizes with the window

## Multi-Needle Example

Double-click "Temperature" to create a gauge. Then click "+ DATASET" and select "Pressure." Both values now display as colored needles on the same dial, with digital readouts below showing which color is which.
