"""Check that every marker lands on the physical spot it was assigned.

Qt positions widgets in device independent pixels, so on a monitor scaled to
anything other than 100% a raw Win32 coordinate would put the marker somewhere
else, possibly on a different screen.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import windowswitcher as w

w.enable_dpi_awareness()
app = QApplication([])
app.setQuitOnLastWindowClosed(False)

markers: list[tuple[w.MarkerPosition, w.Marker]] = []
for target in w.collect_targets():
    for position in target.positions:
        marker = w.Marker(target.label, position)
        marker.show_marker()
        markers.append((position, marker))


def check() -> None:
    worst = 0
    for position, marker in markers:
        rect = w.RECT()
        w.user32.GetWindowRect(int(marker.winId()), ctypes.byref(rect))
        center_x = (rect.left + rect.right) // 2
        worst = max(worst, abs(center_x - position.x), abs(rect.top - position.y))
        marker.close()
    scales = sorted({screen.devicePixelRatio() for screen in app.screens()})
    print(f"markers={len(markers)}")
    print(f"scales={','.join(str(scale) for scale in scales)}")
    print(f"max_offset={worst}")
    app.quit()


QTimer.singleShot(1500, check)
app.exec()
