"""Main window with a menu bar; records which widget currently has focus."""

from __future__ import annotations

import pathlib
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit

LOG = pathlib.Path(sys.argv[1])
LOG.write_text("ready\n", encoding="utf-8")

app = QApplication(sys.argv)
window = QMainWindow()
menu = window.menuBar().addMenu("文件(&F)")
menu.addAction("打开(&O)")
editor = QPlainTextEdit()
window.setCentralWidget(editor)
window.setWindowTitle("windowswitcher-menu-target")
window.resize(700, 350)
window.show()
window.raise_()
window.activateWindow()
editor.setFocus()

seen: set[str] = set()


def sample() -> None:
    focused = app.focusWidget()
    name = type(focused).__name__ if focused else "None"
    if name not in seen:
        seen.add(name)
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"focus {name}\n")
            handle.flush()


timer = QTimer()
timer.timeout.connect(sample)
timer.start(200)
sys.exit(app.exec())
