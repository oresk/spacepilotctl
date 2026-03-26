# SpacePilot LCD

Python library and CLI for controlling the 240x64 monochrome LCD on a 3Dconnexion SpacePilot HP (Logitech `046d:c625`).

## Hardware

- **Display**: 240x64 pixels, monochrome
- **Interface**: USB HID (single interface, `usage_page=0x0001`)
- **Note**: avoid running multiple processes against the device simultaneously — interleaved
  HID writes corrupt the display state

## Ring light

4 blue LEDs below the mushroom, controlled via HID output report `0x04` (1 byte bitmask).

| Bit | Position |
|-----|----------|
| 0 (0x01) | 12 o'clock |
| 1 (0x02) | 3 o'clock |
| 2 (0x04) | 6 o'clock |
| 3 (0x08) | 9 o'clock |

Note: sent via raw `write()` to the hidraw device — HIDAPI's `hid_write()` fails on this device
because it has no interrupt OUT endpoint and the hidraw driver doesn't fall back to SET_REPORT.

## Protocol

All communication is via HID feature reports on the single HID interface.

### Report `0x0C` — LCD position (3 bytes)

Sets the write cursor before sending pixel data.

```
[row, column, 0]
```

- `row`: 0–7, selects an 8-pixel-tall horizontal band (8 bands × 8px = 64px)
- `column`: starting pixel column (0–239). The cursor auto-advances after each data report,
  so only one position report per row is needed.

**Firmware bug**: early SpacePilot firmware has an off-by-one for column ≥ 120. Avoided by
always starting at column 0 and letting the cursor auto-advance.

### Report `0x0D` — LCD data, unpacked (7 bytes)

Writes 7 columns of pixel data at the current cursor position, then advances the cursor by 7.

Each byte represents one pixel column. Within a byte, bit 0 is the top pixel of the band
and bit 7 is the bottom pixel (LSB = top).

### Report `0x0E` — LCD data, packed (6 bytes)

RLE-compressed data: `[count0, bits0, count1, bits1, count2, bits2]`

Writes `count0` bytes of `bits0`, then `count1` of `bits1`, then `count2` of `bits2`.
Up to 3 patterns per report, each count 0–255. Far fewer USB transfers for images with
repeated byte patterns. Used in preference to `0x0D` for all writes.

### Report `0x10` — Display control register (1 byte, write-only)

| Bit | Effect |
|-----|--------|
| 0   | Invert display |
| 1   | Backlight off |
| 2   | Enable firmware clock/timer |
| 3–7 | No visible effect |

Write-only — cannot be read back. All bits must be fully specified on each write.

## Performance

Each HID feature report is a USB control transfer (~4ms on USB full-speed). Throughput
depends entirely on report count, not data size.

| Image type | Reports | Time |
|------------|---------|------|
| Solid color | 16 | ~100ms |
| Typical image | ~90–100 | ~400ms |

## Linux notes

- The device exposes a **single HID interface** (unlike Windows). The LCD reports are
  embedded alongside the 6DoF motion reports.
- `spacenavd` can run concurrently — it does not hold an exclusive lock on the hidraw device.
- When the HID connection is closed, the firmware takes over (shows built-in clock, resets backlight).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install easyhid opencv-python
```

## Usage

```bash
# All ring LEDs on
.venv/bin/python lcd.py -r 15

# Just 12 and 6 o'clock
.venv/bin/python lcd.py -r 0b0101

# Ring off
.venv/bin/python lcd.py -r 0

# Backlight on, clear display, show image
.venv/bin/python lcd.py -b on -c -m images/test.png

# Backlight off
.venv/bin/python lcd.py -b off

# Invert display
.venv/bin/python lcd.py -b on -i on

# Show firmware clock
.venv/bin/python lcd.py --clock

# Verbose timing output
.venv/bin/python lcd.py -m images/test.png -v

# Full help
.venv/bin/python lcd.py --help
```

All display control flags (`-b`, `-i`, `--clock`) must be fully specified each invocation
since the register is write-only and state cannot be read back from the device.

## Image format

- Size: exactly 240×64 pixels
- Mode: grayscale (any non-zero pixel = white on LCD)
- Format: PNG (read via OpenCV)
- Sample images in `images/`

## Files

| File | Description |
|------|-------------|
| `lcd.py` | Library + CLI |
| `images/` | Sample and test images |
