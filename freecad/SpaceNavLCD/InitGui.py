"""SpaceNavLCD — FreeCAD plugin for spacenavlcdd.

Shows the FreeCAD logo on startup, then updates the LCD with the
active workbench name whenever the workbench changes.
"""

import socket
from pathlib import Path

SOCKET_PATH = "/run/spacenavlcdd.sock"
_cache_dir = Path.home() / ".cache" / "spacenavlcd"
_tmp_image = _cache_dir / "freecad.png"


def _send(cmd: str) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(SOCKET_PATH)
            s.sendall((cmd + "\n").encode())
            s.recv(256)
    except Exception:
        pass  # daemon not running or device not connected — ignore silently


def _render_logo() -> str:
    """Render the FreeCAD window icon centered on a 240x64 grayscale image."""
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QColor, QImage, QPainter
    import FreeCADGui

    img = QImage(240, 64, QImage.Format.Format_Grayscale8)
    img.fill(QColor(0, 0, 0))

    icon = FreeCADGui.getMainWindow().windowIcon()
    pixmap = icon.pixmap(QSize(60, 60))

    painter = QPainter(img)
    x = (240 - pixmap.width()) // 2
    y = (64 - pixmap.height()) // 2
    painter.drawPixmap(x, y, pixmap)
    painter.end()

    _cache_dir.mkdir(parents=True, exist_ok=True)
    img.save(str(_tmp_image))
    return str(_tmp_image)


def _render_workbench(text: str) -> str:
    """Render workbench name centered on a 240x64 grayscale image."""
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

    _cache_dir.mkdir(parents=True, exist_ok=True)
    img.save(str(_tmp_image))
    return str(_tmp_image)


def _on_workbench_activated(name: str) -> None:
    import FreeCADGui
    try:
        wb = FreeCADGui.getWorkbench(name)
        display = getattr(wb, "MenuText", name) if wb else name
    except Exception:
        display = name
    _send(f"IMAGE {_render_workbench(display)}")


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

    # Show FreeCAD logo on startup
    _send(f"IMAGE {_render_logo()}")


def _init() -> None:
    from PySide6.QtCore import QTimer
    QTimer.singleShot(500, _setup)


_init()
