from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SUPPORT = Path(__file__).resolve().parent / "support"
PYTHON = sys.executable


def _skip_reason() -> str | None:
    if sys.platform != "win32":
        return "仅 Windows 可测标记定位"
    if os.environ.get("SKIP_INPUT_TESTS"):
        return "SKIP_INPUT_TESTS 已设置"
    return None


@unittest.skipIf(_skip_reason(), _skip_reason() or "")
class MarkerPlacementTests(unittest.TestCase):
    def test_markers_land_on_their_probed_pixel(self) -> None:
        probe = subprocess.run(
            [PYTHON, str(SUPPORT / "marker_placement_probe.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)
        values = dict(
            line.split("=", 1) for line in probe.stdout.splitlines() if "=" in line
        )
        self.assertGreater(int(values.get("markers", "0")), 0, probe.stdout)
        self.assertLessEqual(int(values.get("max_offset", "999")), 1, probe.stdout)
