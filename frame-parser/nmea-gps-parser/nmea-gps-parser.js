/**
 * NMEA 0183 GPS Sentence Parser
 *
 * Parses standard NMEA GGA and RMC sentences into numeric fields suitable
 * for Serial Studio dashboards. Handles both sentence types and outputs
 * a consistent set of GPS telemetry values.
 *
 * INPUT FORMAT: "$GPGGA,..." or "$GPRMC,..." (with or without checksum)
 * OUTPUT ARRAY: [lat, lon, alt, speed_knots, course, satellites, fix_quality, hdop]
 *
 * Latitude/Longitude are output in decimal degrees (negative for S/W).
 * Missing fields output 0.
 *
 * Note: Frame delimiters are automatically removed by Serial Studio.
 *       Use line-based frame detection (QuickPlot mode) for NMEA.
 */

//------------------------------------------------------------------------------
// State (persisted across frames)
//------------------------------------------------------------------------------

var lastLat = 0;
var lastLon = 0;
var lastAlt = 0;
var lastSpeed = 0;
var lastCourse = 0;
var lastSats = 0;
var lastFix = 0;
var lastHdop = 0;

//------------------------------------------------------------------------------
// Helpers
//------------------------------------------------------------------------------

function nmeaToDecimal(raw, hemisphere) {
  if (!raw || raw.length === 0)
    return 0;

  var deg, min;
  if (hemisphere === 'N' || hemisphere === 'S') {
    deg = parseInt(raw.substr(0, 2), 10);
    min = parseFloat(raw.substr(2));
  }
  else {
    deg = parseInt(raw.substr(0, 3), 10);
    min = parseFloat(raw.substr(3));
  }

  var decimal = deg + (min / 60.0);
  if (hemisphere === 'S' || hemisphere === 'W')
    decimal = -decimal;

  return parseFloat(decimal.toFixed(6));
}

//------------------------------------------------------------------------------
// Frame Parser Function
//------------------------------------------------------------------------------

/**
 * Parses an NMEA sentence into GPS telemetry values.
 *
 * @param {string} frame - NMEA sentence string
 * @returns {array} [lat, lon, alt, speed, course, sats, fix, hdop]
 */
function parse(frame) {
  var line = frame.replace(/\r|\n/g, '');
  var star = line.indexOf('*');
  if (star > 0)
    line = line.substring(0, star);

  var fields = line.split(',');
  var id = fields[0];

  if (id === '$GPGGA' || id === '$GNGGA') {
    lastLat  = nmeaToDecimal(fields[2], fields[3]);
    lastLon  = nmeaToDecimal(fields[4], fields[5]);
    lastFix  = parseInt(fields[6], 10) || 0;
    lastSats = parseInt(fields[7], 10) || 0;
    lastHdop = parseFloat(fields[8]) || 0;
    lastAlt  = parseFloat(fields[9]) || 0;
  }
  else if (id === '$GPRMC' || id === '$GNRMC') {
    lastLat    = nmeaToDecimal(fields[3], fields[4]);
    lastLon    = nmeaToDecimal(fields[5], fields[6]);
    lastSpeed  = parseFloat(fields[7]) || 0;
    lastCourse = parseFloat(fields[8]) || 0;
  }

  return [lastLat, lastLon, lastAlt, lastSpeed, lastCourse, lastSats, lastFix, lastHdop];
}
