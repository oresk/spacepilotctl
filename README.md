# spacepilotctl

Python library and CLI for controlling the 3Dconnexion SpacePilot HP (Logitech `046d:c625`).

## What you can control

- **LCD** — 240×64 monochrome display: show images, clear, invert
- **Backlight** — turn on or off
- **Ring light** — 4 blue LEDs around the mushroom button, individually addressable
- **Firmware clock** — enable the built-in clock/timer shown on the LCD

## Install

Install the tools system-wide:

```bash
sudo pip install --break-system-packages .
```

Install the daemon as a system service:

```bash
sudo cp spacenavlcdd.service /etc/systemd/system/
sudo cp 99-spacenavlcdd.rules /etc/udev/rules.d/
sudo cp spacenavlcdd.toml /etc/spacenavlcdd.toml   # edit as needed
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
```

The daemon starts automatically when the device is plugged in.

For direct HID access (`spacepilotctl`) without the daemon, install via pipx:

```bash
pipx install .
```

## FreeCAD plugin

The plugin watches the active workbench and displays its name on the LCD.

**Install (Flatpak FreeCAD):**

```bash
# Copy plugin into FreeCAD's Mod directory
cp -r freecad/SpaceNavLCD ~/.var/app/org.freecad.FreeCAD/data/FreeCAD/Mod/

# Allow FreeCAD to access the daemon socket
flatpak override --user --filesystem=/run org.freecad.FreeCAD
```

**Install (native FreeCAD):**

```bash
cp -r freecad/SpaceNavLCD ~/.local/share/FreeCAD/Mod/
```

Restart FreeCAD. The LCD will update automatically when you switch workbenches.

## Usage

```bash
# Show image
spacepilotctl -m images/test.png

# Backlight on, clear display, show image
spacepilotctl -b on -c -m images/test.png

# Backlight off
spacepilotctl -b off

# Invert display
spacepilotctl -b on -i on

# Show firmware clock
spacepilotctl --clock

# All ring LEDs on
spacepilotctl -r 15

# Individual LEDs: 1=12h, 2=3h, 4=6h, 8=9h — combine with |
spacepilotctl -r 0b0101   # 12 and 6 o'clock

# Ring off
spacepilotctl -r 0

# Verbose timing output
spacepilotctl -m images/test.png -v

# Full help
spacepilotctl --help
```

Display control flags (`-b`, `-i`, `--clock`) must be fully specified on each invocation — the register is write-only and cannot be read back.

## Image format

- Size: exactly 240×64 pixels
- Mode: grayscale (any non-zero pixel = white on LCD)
- Format: PNG
- Sample images in `images/`

## Protocol

All communication is via HID feature reports.

### Report `0x0C` — LCD position (3 bytes)

Sets the write cursor before sending pixel data: `[row, column, 0]`

- `row`: 0–7, selects an 8-pixel-tall horizontal band
- `column`: starting pixel column (0–239), auto-advances after each data report

### Report `0x0D` — LCD data, unpacked (7 bytes)

Writes 7 columns at the current cursor. Each byte is one pixel column; bit 0 = top pixel (LSB = top).

### Report `0x0E` — LCD data, packed (6 bytes)

RLE: `[count0, bits0, count1, bits1, count2, bits2]` — up to 3 runs per report, count 0–255.
Preferred over `0x0D` for all writes; significantly reduces USB transfers for images with repeated patterns.

### Report `0x10` — Display control register (1 byte, write-only)

| Bit | Effect |
|-----|--------|
| 0   | Invert display |
| 1   | Backlight off |
| 2   | Enable firmware clock/timer |

### Report `0x04` — Ring light (output report, 1 byte bitmask)

| Bit | Position |
|-----|----------|
| 0 (0x01) | 12 o'clock |
| 1 (0x02) | 3 o'clock |
| 2 (0x04) | 6 o'clock |
| 3 (0x08) | 9 o'clock |

## Performance

Each HID feature report is a USB control transfer (~4ms on USB full-speed).

| Image type | Reports | Time |
|------------|---------|------|
| Solid color | 16 | ~100ms |
| Typical image | ~90–100 | ~400ms |

## Linux notes

- `spacenavd` can run concurrently — it does not hold an exclusive lock on the hidraw device.
- When the HID connection is closed, the firmware takes over (shows built-in clock, resets backlight).
