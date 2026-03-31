"""spacenavlcdctl — CLI client for spacenavlcdd."""

import os
import socket
import sys
from pathlib import Path

SOCKET_PATH = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "spacenavlcdd.sock"


def send(command: str) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        try:
            s.connect(str(SOCKET_PATH))
        except FileNotFoundError:
            print(f"error: socket not found at {SOCKET_PATH} — is spacenavlcdd running?", file=sys.stderr)
            sys.exit(1)
        s.sendall((command + "\n").encode())
        return s.recv(1024).decode().strip()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="spacenavlcdd client")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("clear", help="Clear the display")

    p = sub.add_parser("image", help="Show image on display")
    p.add_argument("path", help="Path to 240x64 PNG")

    p = sub.add_parser("leds", help="Set ring LEDs")
    p.add_argument("mask", help="Bitmask: 1=12h 2=3h 4=6h 8=9h (0=off, 15=all)")

    p = sub.add_parser("backlight", help="Backlight on or off")
    p.add_argument("state", choices=["on", "off"])

    p = sub.add_parser("invert", help="Invert display on or off")
    p.add_argument("state", choices=["on", "off"])

    p = sub.add_parser("clock", help="Firmware clock on or off")
    p.add_argument("state", choices=["on", "off"])

    args = parser.parse_args()

    if args.cmd == "clear":
        print(send("CLEAR"))
    elif args.cmd == "image":
        print(send(f"IMAGE {Path(args.path).resolve()}"))
    elif args.cmd == "leds":
        print(send(f"LEDS {args.mask}"))
    elif args.cmd == "backlight":
        print(send(f"BACKLIGHT {args.state}"))
    elif args.cmd == "invert":
        print(send(f"INVERT {args.state}"))
    elif args.cmd == "clock":
        print(send(f"CLOCK {args.state}"))


if __name__ == "__main__":
    main()
