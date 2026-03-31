"""spacenavlcdd — SpacePilot LCD daemon.

Owns the HID device and serves commands over a Unix socket.

Socket protocol (line-based text):
  CLEAR
  IMAGE <path>
  LEDS <mask>
  BACKLIGHT on|off
  INVERT on|off
  CLOCK on|off

Each command returns OK or ERROR <message>.
"""

import asyncio
import os
import sys
import tomllib
from pathlib import Path

from spacepilotctl import (
    set_ring_light, set_display_mode, clear, write_png,
    DISPLAY_NORMAL, DISPLAY_BL_OFF, DISPLAY_INVERTED, DISPLAY_CLOCK,
    VENDOR_ID, PRODUCT_ID,
)
from easyhid import Enumeration

SOCKET_PATH = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "spacenavlcdd.sock"
CONFIG_PATH = Path.home() / ".config" / "spacenavlcdd.toml"

DEFAULT_CONFIG = {
    "on_connect": {
        "backlight": "on",
        "action": "clear",  # "clear", "image", or "nothing"
        "image": "",
    }
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    return DEFAULT_CONFIG


class SpaceNavLCDDaemon:
    def __init__(self, config: dict):
        self.config = config
        self.dev = None
        self._lock = asyncio.Lock()
        self._display_mode = DISPLAY_NORMAL

    def open_device(self) -> bool:
        en = Enumeration()
        devices = en.find(vid=VENDOR_ID, pid=PRODUCT_ID)
        if not devices:
            return False
        self.dev = devices[0]
        self.dev.open()
        return True

    def _apply_display_mode(self, mode: int) -> None:
        self._display_mode = mode
        set_display_mode(self.dev, mode)

    def apply_on_connect(self) -> None:
        cfg = self.config.get("on_connect", {})

        mode = DISPLAY_NORMAL
        if cfg.get("backlight", "on") == "off":
            mode |= DISPLAY_BL_OFF
        self._apply_display_mode(mode)

        action = cfg.get("action", "clear")
        if action == "clear":
            clear(self.dev)
        elif action == "image":
            img = cfg.get("image", "")
            if img:
                write_png(self.dev, img)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                parts = line.decode().strip().split(None, 1)
                if not parts:
                    continue
                verb = parts[0].upper()
                arg = parts[1] if len(parts) > 1 else ""

                async with self._lock:
                    try:
                        if verb == "CLEAR":
                            clear(self.dev)
                        elif verb == "IMAGE":
                            if not write_png(self.dev, arg):
                                raise ValueError(f"failed to load image: {arg}")
                        elif verb == "LEDS":
                            set_ring_light(self.dev, int(arg, 0))
                        elif verb == "BACKLIGHT":
                            if arg == "off":
                                self._display_mode |= DISPLAY_BL_OFF
                            else:
                                self._display_mode &= ~DISPLAY_BL_OFF
                            self._apply_display_mode(self._display_mode)
                        elif verb == "INVERT":
                            if arg == "on":
                                self._display_mode |= DISPLAY_INVERTED
                            else:
                                self._display_mode &= ~DISPLAY_INVERTED
                            self._apply_display_mode(self._display_mode)
                        elif verb == "CLOCK":
                            if arg == "on":
                                self._display_mode |= DISPLAY_CLOCK
                            else:
                                self._display_mode &= ~DISPLAY_CLOCK
                            self._apply_display_mode(self._display_mode)
                        else:
                            raise ValueError(f"unknown command: {verb}")
                        writer.write(b"OK\n")
                    except OSError as e:
                        # HID write failed — device likely disconnected
                        print(f"spacenavlcdd: device error: {e}", file=sys.stderr)
                        writer.write(b"ERROR device disconnected\n")
                        await writer.drain()
                        sys.exit(1)
                    except Exception as e:
                        writer.write(f"ERROR {e}\n".encode())
                    await writer.drain()
        finally:
            writer.close()


async def run() -> None:
    config = load_config()
    daemon = SpaceNavLCDDaemon(config)

    if not daemon.open_device():
        print("spacenavlcdd: device not found, will retry", file=sys.stderr)
        sys.exit(1)

    try:
        daemon.apply_on_connect()
    except OSError as e:
        print(f"spacenavlcdd: device error on connect: {e}", file=sys.stderr)
        sys.exit(1)

    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()

    server = await asyncio.start_unix_server(daemon.handle_client, path=str(SOCKET_PATH))
    SOCKET_PATH.chmod(0o600)
    print(f"spacenavlcdd: listening on {SOCKET_PATH}", flush=True)

    async with server:
        await server.serve_forever()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
