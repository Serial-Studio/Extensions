# Artemis

Deep-space dark theme inspired by the NASA Orion crew module flight software displays. Near-black backgrounds with cool cyan-blue instrument accents evoke the cockpit of a crewed lunar mission.

## Color Palette

| Role           | Color                                                        |
|----------------|--------------------------------------------------------------|
| Background     | `#080C12` - near-black with blue undertone                   |
| Surface        | `#0C1118` - slightly lifted panels                           |
| Border         | `#1E2A35` - subtle blue-steel dividers                       |
| Text           | `#8A9BB0` - muted instrument readout blue-gray               |
| Accent         | `#4DA8DA` - primary cyan-blue (indicators, links, highlights)|
| Highlight      | `#1A6E9E` - deeper selection/focus blue                      |
| Console        | `#4DA8DA` - cyan telemetry readout                           |
| Error          | `#E05555` - caution red                                      |
| Success        | `#50C878` - nominal green                                    |
| Warning        | `#E0A030` - advisory amber                                   |

## Design Notes

- Backgrounds are in the `#06-#14` range to simulate unlit cockpit panels
- Borders are barely visible blue-steel lines, like instrument bezels
- Text uses muted blue-gray rather than pure white to reduce glare
- The accent cyan matches the characteristic glow of modern glass-cockpit displays
- Console text is cyan rather than green, matching the flight software aesthetic
