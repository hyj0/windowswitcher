"""Foreground window that records every key press it receives."""

from __future__ import annotations

import pathlib
import sys

from PySide6.QtWidgets import QApplication, QPlainTextEdit

LOG = pathlib.Path(sys.argv[1])
LOG.write_text("ready\n", encoding="utf-8")


class Catcher(QPlainTextEdit):
    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"key {event.key()}:{event.text()!r}\n")
            handle.flush()
        super().keyPressEvent(event)


app = QApplication(sys.argv)
window = Catcher()
window.setWindowTitle("windowswitcher-keylog-target")
window.resize(700, 350)
window.show()
window.raise_()
window.activateWindow()
sys.exit(app.exec())
