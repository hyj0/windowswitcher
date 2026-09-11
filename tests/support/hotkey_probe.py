"""In-process probe: confirm the hotkey reaches RegisterHotKey and installs the hook."""

from __future__ import annotations

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
from tests.support.send_keys import send_combo

HOTKEY = sys.argv[1] if len(sys.argv) > 1 else "alt+f9"
results: list[tuple[str, object]] = []


def press_hotkey() -> None:
    time.sleep(2.0)
    send_combo(HOTKEY)


app = QApplication([])
app.setQuitOnLastWindowClosed(False)
switcher = w.Switcher(HOTKEY)
threading.Thread(target=press_hotkey, daemon=True).start()


def check() -> None:
    results.append(("active", switcher._active))
    results.append(("markers", sum(len(group) for group in switcher.markers.values())))
    results.append(("hook", switcher.hook.installed))
    switcher.cancel()
    results.append(("active_after_cancel", switcher._active))
    results.append(("hook_after_cancel", switcher.hook.installed))
    switcher.shutdown()
    app.quit()


QTimer.singleShot(5000, check)
app.exec()
for name, value in results:
    print(f"{name}={value}")
