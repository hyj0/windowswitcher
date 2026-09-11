"""In-process probe: confirm Alt+Q reaches RegisterHotKey and installs the hook."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import windowswitcher as w

user32 = ctypes.windll.user32
KEYEVENTF_KEYUP = 0x0002
results: list[tuple[str, object]] = []


def send_alt_q() -> None:
    time.sleep(2.0)
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(ord("Q"), 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(ord("Q"), 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(0x12, 0, KEYEVENTF_KEYUP, 0)


app = QApplication([])
app.setQuitOnLastWindowClosed(False)
switcher = w.Switcher("alt+q")
threading.Thread(target=send_alt_q, daemon=True).start()


def check() -> None:
    results.append(("active", switcher._active))
    results.append(("markers", sum(len(group) for group in switcher.markers.values())))
    results.append(("hook", switcher._hook is not None))
    switcher.cancel()
    results.append(("active_after_cancel", switcher._active))
    results.append(("hook_after_cancel", switcher._hook is not None))
    switcher.shutdown()
    app.quit()


QTimer.singleShot(5000, check)
app.exec()
for name, value in results:
    print(f"{name}={value}")
