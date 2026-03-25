# Binary TLV Parser

Type-Length-Value parser for binary serial protocols.

## Protocol Format

Each TLV record consists of:
- **Type** (1 byte): Identifies the value type.
- **Length** (1 byte): Number of value bytes.
- **Value** (N bytes): The actual data.

## Supported Types

| Type ID | Name | Size |
|---------|------|------|
| `0x01` | uint8 | 1 byte |
| `0x02` | int8 | 1 byte |
| `0x03` | uint16 | 2 bytes (big-endian) |
| `0x04` | int16 | 2 bytes (big-endian) |
| `0x05` | uint32 | 4 bytes (big-endian) |
| `0x06` | int32 | 4 bytes (big-endian) |
| `0x07` | float32 | 4 bytes (IEEE 754, big-endian) |
| `0x08` | string | N bytes (UTF-8) |

## Usage

1. Install this extension
2. In the Project Editor, set the frame parser to use this script
3. Enable "Hexadecimal Delimiters" if your frame delimiters are binary
4. The parser will decode each TLV field into the corresponding value

## Example Input

Hex: `01 01 2A 07 04 41 C8 00 00` → Decoded: `[42, 25.0000]`
