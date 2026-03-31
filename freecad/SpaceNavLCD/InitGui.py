"""SpaceNavLCD — FreeCAD plugin for spacenavlcdd.

Shows the FreeCAD logo on startup, then updates the LCD with the
active workbench name whenever the workbench changes.
"""


def _init():
    import os
    import socket
    import traceback

    SOCKET = "/run/spacenavlcdd.sock"
    LOG    = os.path.join(os.path.expanduser("~"), ".cache", "spacenavlcd", "debug.log")

    def log(msg):
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(msg + "\n")

    def send(cmd):
        log(f"send: {cmd}")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect(SOCKET)
                s.sendall((cmd + "\n").encode())
                log(f"response: {s.recv(256)}")
        except Exception as e:
            log(f"send error: {e}\n{traceback.format_exc()}")

    def send_image(img):
        try:
            from PySide6.QtCore import QBuffer, QByteArray, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buf, "PNG")
            data = bytes(buf.data())
            log(f"send_image: {len(data)} bytes")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect(SOCKET)
                s.sendall(f"BIMAGE {len(data)}\n".encode())
                s.sendall(data)
                log(f"response: {s.recv(256)}")
        except Exception as e:
            log(f"send_image error: {e}\n{traceback.format_exc()}")

    def render_logo():
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QColor, QImage, QPainter
        import FreeCADGui

        src = QImage(240, 64, QImage.Format.Format_ARGB32)
        src.fill(QColor(0, 0, 0, 0))
        pixmap = FreeCADGui.getMainWindow().windowIcon().pixmap(QSize(60, 60))
        painter = QPainter(src)
        painter.drawPixmap((240 - 60) // 2, (64 - 60) // 2, pixmap)
        painter.end()

        out = QImage(240, 64, QImage.Format.Format_Grayscale8)
        out.fill(QColor(0, 0, 0))
        for y in range(64):
            for x in range(240):
                c = src.pixelColor(x, y)
                lum = 255 if c.alpha() < 64 else (c.red() * 299 + c.green() * 587 + c.blue() * 114) // 1000
                if lum > 160:
                    out.setPixelColor(x, y, QColor(255, 255, 255))
        return out

    def render_workbench(text):
        from PySide6.QtCore import Qt, QRect
        from PySide6.QtGui import QColor, QFont, QImage, QPainter

        img = QImage(240, 64, QImage.Format.Format_Grayscale8)
        img.fill(QColor(0, 0, 0))
        painter = QPainter(img)
        painter.setFont(QFont("Sans Serif", 16, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRect(0, 0, 240, 64), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        return img

    def show_current_workbench():
        import FreeCADGui
        wb = FreeCADGui.activeWorkbench()
        if wb:
            on_workbench_activated(type(wb).__name__)

    def on_workbench_activated(name):
        import FreeCADGui
        try:
            wb = FreeCADGui.getWorkbench(name)
            display = getattr(wb, "MenuText", name) if wb else name
        except Exception:
            display = name
        send_image(render_workbench(display))

    def setup():
        import FreeCAD
        import FreeCADGui

        log("setup called")
        mw = FreeCADGui.getMainWindow()
        if mw is None:
            log("main window is None")
            return

        try:
            mw.workbenchActivated.connect(on_workbench_activated)
            log("signal connected")
        except Exception as e:
            log(f"signal connect failed: {e}\n{traceback.format_exc()}")
            FreeCAD.Console.PrintWarning(f"SpaceNavLCD: {e}\n")

        class DocObserver:
            def slotActivatedDocument(self, doc):
                show_current_workbench()
            def slotCreatedDocument(self, doc):
                show_current_workbench()
            def slotOpenedDocument(self, doc):
                show_current_workbench()

        observer = DocObserver()
        FreeCAD.addDocumentObserver(observer)
        log("document observer added")

        try:
            send_image(render_logo())
        except Exception as e:
            log(f"render failed: {e}\n{traceback.format_exc()}")

    log("loading")
    from PySide6.QtCore import QTimer
    QTimer.singleShot(500, setup)


_init()
