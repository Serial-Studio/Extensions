/**
 * Binary TLV (Type-Length-Value) Parser
 *
 * Decodes binary frames encoded in TLV format into labeled fields.
 * Each TLV record is: [type:1 byte][length:1 byte][value:N bytes]
 *
 * Supported value types:
 *   0x01 = uint8     0x02 = int8
 *   0x03 = uint16    0x04 = int16    (big-endian)
 *   0x05 = uint32    0x06 = int32    (big-endian)
 *   0x07 = float32                   (big-endian IEEE 754)
 *   0x08 = string                    (UTF-8)
 *
 * INPUT FORMAT: Binary TLV bytes (hex string from Serial Studio)
 * OUTPUT ARRAY: Array of decoded numeric/string values
 *
 * Note: Frame delimiters are automatically removed by Serial Studio.
 *       Enable "Hexadecimal Delimiters" in your project if framing
 *       uses binary delimiters.
 */

//------------------------------------------------------------------------------
// Frame Parser Function
//------------------------------------------------------------------------------

/**
 * Parses a binary TLV frame into an array of decoded values.
 *
 * @param {string} frame - Hex-encoded binary data from the data source
 * @returns {array} Array of decoded values (numbers and strings)
 */
function parse(frame) {
  var bytes = [];
  var hex = frame.replace(/\s/g, '');
  for (var i = 0; i < hex.length; i += 2)
    bytes.push(parseInt(hex.substr(i, 2), 16));

  var values = [];
  var pos = 0;

  while (pos + 2 <= bytes.length) {
    var type = bytes[pos];
    var len = bytes[pos + 1];
    pos += 2;

    if (pos + len > bytes.length)
      break;

    var chunk = bytes.slice(pos, pos + len);
    pos += len;

    if (type === 0x01 && len >= 1)
      values.push(chunk[0]);
    else if (type === 0x02 && len >= 1)
      values.push(chunk[0] > 127 ? chunk[0] - 256 : chunk[0]);
    else if (type === 0x03 && len >= 2)
      values.push((chunk[0] << 8) | chunk[1]);
    else if (type === 0x04 && len >= 2) {
      var u16 = (chunk[0] << 8) | chunk[1];
      values.push(u16 > 32767 ? u16 - 65536 : u16);
    }
    else if (type === 0x05 && len >= 4)
      values.push(((chunk[0] << 24) | (chunk[1] << 16) | (chunk[2] << 8) | chunk[3]) >>> 0);
    else if (type === 0x06 && len >= 4) {
      var u32 = ((chunk[0] << 24) | (chunk[1] << 16) | (chunk[2] << 8) | chunk[3]) >>> 0;
      values.push(u32 > 2147483647 ? u32 - 4294967296 : u32);
    }
    else if (type === 0x07 && len >= 4) {
      var buf = new ArrayBuffer(4);
      var view = new DataView(buf);
      for (var b = 0; b < 4; b++)
        view.setUint8(b, chunk[b]);
      values.push(view.getFloat32(0, false).toFixed(4));
    }
    else if (type === 0x08) {
      var str = '';
      for (var c = 0; c < chunk.length; c++)
        str += String.fromCharCode(chunk[c]);
      values.push(str);
    }
    else
      values.push(0);
  }

  return values;
}
