from pathlib import Path
import sys
import time
import cv2

VENDOR_ID = 0x046d  # Logitech vendor ID
PRODUCT_ID = 0xC625  # SpacePilot product ID

LCD_USAGE_PAGE = 0xFF00
LCD_USAGE = 0x01
REPORT_ID_RING_LIGHT    = 0x04  # output report
# Ring light LED positions (bits):
RING_12 = 0x01  # 12 o'clock
RING_3  = 0x02  # 3 o'clock
RING_6  = 0x04  # 6 o'clock
RING_9  = 0x08  # 9 o'clock
RING_ALL = 0x0F
REPORT_ID_LCD_POS       = 0x0C
REPORT_ID_LCD_DATA      = 0x0D
REPORT_ID_LCD_DATA_PACK = 0x0E  # packed: [count0, bits0, count1, bits1, count2, bits2]
REPORT_ID_DISPLAY_CTRL  = 0x10
# Display control register bits:
#   bit 0: invert display
#   bit 1: backlight off
#   bit 2: firmware clock/timer on
DISPLAY_NORMAL    = 0x00
DISPLAY_INVERTED  = 0x01
DISPLAY_BL_OFF    = 0x02
DISPLAY_CLOCK     = 0x04

# Firmware bug: on early SpacePilot firmware, starting at column >= 120 is off by one.
def _lcd_col(column: int) -> int:
    return column - 1 if column >= 120 else column

from easyhid import Enumeration
from easyhid import HIDDevice

en = Enumeration()
devices = en.find(vid=VENDOR_ID, pid=PRODUCT_ID)
if not devices:
    print("SpacePilot LCD device not found", file=sys.stderr)
    sys.exit(1)

lcd_device = devices[0]
lcd_device.open()


def set_ring_light(dev: HIDDevice, mask: int) -> None:
    """Set ring light LEDs. Use RING_* constants or combine with |."""
    with open(dev.path, "wb", buffering=0) as f:
        f.write(bytes([REPORT_ID_RING_LIGHT, mask & 0x0F]))


def set_display_mode(dev: HIDDevice, mode: int) -> None:
    """Set display control register (DISPLAY_* constants)."""
    dev.send_feature_report(bytes([mode]), REPORT_ID_DISPLAY_CTRL)


def clear(dev: HIDDevice) -> None:
    """Clear the LCD (all pixels off) using packed data for speed."""
    for row in range(8):
        dev.send_feature_report(bytes([row, 0, 0]), REPORT_ID_LCD_POS)
        dev.send_feature_report(bytes([85, 0x00, 85, 0x00, 70, 0x00]), REPORT_ID_LCD_DATA_PACK)


def _rle(data: bytes) -> list[tuple[int, int]]:
    """RLE-encode bytes into (count, value) runs, splitting runs > 255."""
    runs = []
    i = 0
    while i < len(data):
        val = data[i]
        j = i
        while j < len(data) and data[j] == val:
            j += 1
        length = j - i
        while length > 255:
            runs.append((255, val))
            length -= 255
        runs.append((length, val))
        i = j
    return runs


def write_png(dev: HIDDevice, png_path: Path | str, verbose: bool = False) -> bool:
    """Write a 240x64 PNG image to the SpacePilot LCD using packed reports."""
    img = cv2.imread(str(png_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"Failed to read image: {png_path}", file=sys.stderr)
        return False

    if img.shape != (64, 240):
        print(f"Image has wrong shape: {img.shape}, expected (64, 240)", file=sys.stderr)
        return False

    t0 = time.perf_counter()
    n_reports = 0
    for row in range(8):
        row_bytes = bytearray(240)
        for col in range(240):
            byte = 0
            for bit in range(8):
                if img[row * 8 + bit, col] != 0:
                    byte |= (1 << bit)
            row_bytes[col] = byte

        dev.send_feature_report(bytes([row, 0, 0]), REPORT_ID_LCD_POS)
        n_reports += 1
        runs = _rle(bytes(row_bytes))
        for i in range(0, len(runs), 3):
            group = runs[i:i+3]
            while len(group) < 3:
                group.append((0, 0))
            data = bytearray(6)
            for k, (count, val) in enumerate(group):
                data[k * 2]     = count
                data[k * 2 + 1] = val
            dev.send_feature_report(bytes(data), REPORT_ID_LCD_DATA_PACK)
            n_reports += 1

    if verbose:
        elapsed = time.perf_counter() - t0
        print(f"{Path(png_path).name}: {elapsed*1000:.0f}ms  {n_reports} reports", file=sys.stderr)

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SpacePilot LCD controller")
    parser.add_argument("--ring", "-r", type=lambda x: int(x, 0), metavar="0-15",
                        help="Ring light bitmask: 1=12h, 2=3h, 4=6h, 8=9h (0=off, 15=all)")
    parser.add_argument("--backlight", "-b", choices=["on", "off"],
                        help="Turn backlight on or off")
    parser.add_argument("--invert", "-i", choices=["on", "off"],
                        help="Invert the display")
    parser.add_argument("--clock", action="store_true",
                        help="Show firmware clock/timer")
    parser.add_argument("--image", "-m", type=Path, metavar="FILE",
                        help="Display a 240x64 PNG image")
    parser.add_argument("--clear", "-c", action="store_true",
                        help="Clear the display")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print timing info")
    args = parser.parse_args()

    if not any([args.ring is not None, args.backlight, args.invert, args.clock, args.image, args.clear]):
        parser.print_help()
        lcd_device.close()
        sys.exit(0)

    if args.ring is not None:
        set_ring_light(lcd_device, args.ring)

    if args.backlight or args.invert or args.clock:
        mode = DISPLAY_NORMAL
        if args.backlight == "off":
            mode |= DISPLAY_BL_OFF
        if args.invert == "on":
            mode |= DISPLAY_INVERTED
        if args.clock:
            mode |= DISPLAY_CLOCK
        set_display_mode(lcd_device, mode)

    if args.clear:
        clear(lcd_device)

    if args.image:
        ok = write_png(lcd_device, args.image, verbose=args.verbose)
        if not ok:
            lcd_device.close()
            sys.exit(1)

    lcd_device.close()
