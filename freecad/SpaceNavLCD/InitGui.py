"""SpaceNavLCD — FreeCAD plugin for spacenavlcdd.

Shows the FreeCAD logo on startup, then a split layout:
  - Upper 40px: active workbench name
  - Lower 24px: 6 button labels read from Spaceball preferences
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

    def send_image(img):
        try:
            from PySide6.QtCore import QBuffer, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buf, "PNG")
            data = bytes(buf.data())
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect(SOCKET)
                s.sendall(f"BIMAGE {len(data)}\n".encode())
                s.sendall(data)
                s.recv(256)
        except Exception as e:
            log(f"send_image error: {e}\n{traceback.format_exc()}")

    def get_button_labels():
        """Read button mappings from FreeCAD Spaceball preferences.

        Format: groups named "0".."5", each with Command and Description fields.
        """
        import FreeCAD
        try:
            params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Spaceball/Buttons")
            labels = []
            for i in range(6):
                group = params.GetGroup(str(i))
                cmd = group.GetString("Command", "")
                if cmd:
                    # "Std_ViewFront" → "Front", "PartDesign_Pad" → "Pad"
                    # "Sketcher_CreateRectangle_Center" → "Rect" (last meaningful part)
                    part = cmd.split("_")[-1]
                    if part.startswith("View"):
                        part = part[4:]
                    labels.append(part[:7])
                else:
                    labels.append("")
            return labels
        except Exception as e:
            log(f"get_button_labels error: {e}")
            return [""] * 6

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

    def render_layout(workbench, button_labels):
        """Render split layout: workbench name top, 6 button labels bottom."""
        from PySide6.QtCore import Qt, QRect
        from PySide6.QtGui import QColor, QFont, QImage, QPainter

        img = QImage(240, 64, QImage.Format.Format_Grayscale8)
        img.fill(QColor(0, 0, 0))
        painter = QPainter(img)
        white = QColor(255, 255, 255)

        # Upper section: workbench name (40px tall)
        painter.setFont(QFont("Sans Serif", 14, QFont.Weight.Bold))
        painter.setPen(white)
        painter.drawText(QRect(0, 0, 240, 40), Qt.AlignmentFlag.AlignCenter, workbench)

        # Divider line
        painter.drawLine(0, 40, 239, 40)

        # Lower section: 6 button cells (40px wide, 23px tall each)
        btn_font = QFont("Sans Serif", 6)
        num_font = QFont("Sans Serif", 5)
        cell_w = 40

        for i, label in enumerate(button_labels[:6]):
            x = i * cell_w
            # Vertical divider (skip leftmost)
            if i > 0:
                painter.drawLine(x, 41, x, 63)
            # Button number (top-left of cell)
            painter.setFont(num_font)
            painter.drawText(QRect(x + 2, 42, 10, 10), Qt.AlignmentFlag.AlignLeft, str(i + 1))
            # Label (centered in cell)
            painter.setFont(btn_font)
            painter.drawText(QRect(x, 51, cell_w, 12), Qt.AlignmentFlag.AlignCenter, label)

        painter.end()
        return img

    def show_layout(workbench_display):
        labels = get_button_labels()
        send_image(render_layout(workbench_display, labels))

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
        show_layout(display)

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

        FreeCAD.addDocumentObserver(DocObserver())
        log("document observer added")

        try:
            send_image(render_logo())
        except Exception as e:
            log(f"render failed: {e}\n{traceback.format_exc()}")

    log("loading")
    from PySide6.QtCore import QTimer
    QTimer.singleShot(500, setup)


_init()
