"""SpaceNavLCD — FreeCAD plugin for spacenavlcdd.

Watches the active workbench and sends the workbench name to the
SpacePilot LCD via the spacenavlcdd daemon socket.
"""

import socket
import tempfile
from pathlib import Path

SOCKET_PATH = "/run/spacenavlcdd.sock"
_tmp_image = Path(tempfile.gettempdir()) / "spacenavlcd_freecad.png"


def _send(cmd: str) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(SOCKET_PATH)
            s.sendall((cmd + "\n").encode())
            s.recv(256)
    except Exception:
        pass  # daemon not running or device not connected — ignore silently


def _render(text: str) -> str:
    """Render text centered on a 240x64 grayscale PNG using PySide6."""
    from PySide6.QtCore import Qt, QRect
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    img = QImage(240, 64, QImage.Format.Format_Grayscale8)
    img.fill(QColor(0, 0, 0))

    painter = QPainter(img)
    font = QFont("Sans Serif", 16, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(QRect(0, 0, 240, 64), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()

    img.save(str(_tmp_image))
    return str(_tmp_image)


def _on_workbench_activated(name: str) -> None:
    import FreeCADGui
    try:
        wb = FreeCADGui.getWorkbench(name)
        display = getattr(wb, "MenuText", name) if wb else name
    except Exception:
        display = name
    _send(f"IMAGE {_render(display)}")


def _setup() -> None:
    import FreeCAD
    import FreeCADGui

    mw = FreeCADGui.getMainWindow()
    if mw is None:
        return

    try:
        mw.workbenchActivated.connect(_on_workbench_activated)
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"SpaceNavLCD: failed to connect signal: {e}\n")
        return

    # Show the current workbench immediately
    wb = FreeCADGui.activeWorkbench()
    if wb:
        _on_workbench_activated(type(wb).__name__)


def _init() -> None:
    from PySide6.QtCore import QTimer
    # Defer until the main window is fully initialised
    QTimer.singleShot(500, _setup)


_init()
