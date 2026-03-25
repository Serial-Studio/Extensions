# NMEA GPS Sentence Parser

Parses standard NMEA 0183 GGA and RMC sentences into GPS telemetry values.

## Supported Sentences

- **$GPGGA / $GNGGA** — Fix data: latitude, longitude, altitude, fix quality, satellite count, HDOP
- **$GPRMC / $GNRMC** — Recommended minimum: latitude, longitude, speed, course

## Output Fields

| Index | Field | Units |
|-------|-------|-------|
| 0 | Latitude | Decimal degrees (negative = South) |
| 1 | Longitude | Decimal degrees (negative = West) |
| 2 | Altitude | Meters |
| 3 | Speed | Knots |
| 4 | Course | Degrees |
| 5 | Satellites | Count |
| 6 | Fix Quality | 0=Invalid, 1=GPS, 2=DGPS |
| 7 | HDOP | Horizontal dilution of precision |

## Usage

1. Install this extension
2. Use **Quick Plot** mode with line-based frame detection
3. Or set it as the frame parser in a Project File
4. Connect to your GPS module (typically 9600 or 115200 baud)

The parser maintains state across frames — GGA updates position/altitude/satellites, RMC updates speed/course. Both always output all 8 fields.
