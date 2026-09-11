from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.support.send_keys import send_sequence

SUPPORT = Path(__file__).resolve().parent / "support"
PYTHON = sys.executable
# The app itself may already be running from the Startup folder, so the tests
# drive a second instance on a hotkey nobody else registers. Alt stays the only
# modifier so the menu-bar suppression is still exercised.
TEST_HOTKEY = "alt+f9"


def _skip_reason() -> str | None:
    if sys.platform != "win32":
        return "仅 Windows 可测按键隔离"
    if os.environ.get("SKIP_INPUT_TESTS"):
        return "SKIP_INPUT_TESTS 已设置"
    return None


class _Process:
    def __init__(self, args: list[str], *, cwd: Path | None = None) -> None:
        self.proc = subprocess.Popen(
            args,
            cwd=str(cwd) if cwd is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def wait_alive(self, seconds: float = 6.0) -> None:
        time.sleep(seconds)
        if self.proc.poll() is not None:
            output = self.proc.stdout.read() if self.proc.stdout else ""
            raise RuntimeError(f"进程提前退出，代码 {self.proc.returncode}\n{output}")

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if self.proc.stdout is not None:
            self.proc.stdout.close()


def _wait_for_log(path: Path, needle: str, timeout: float = 10.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if needle in text:
                return text
        time.sleep(0.1)
    raise TimeoutError(f"{path} 在 {timeout} 秒内未出现 {needle!r}")


@unittest.skipIf(_skip_reason(), _skip_reason() or "")
class KeyIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.switcher = _Process(
            [PYTHON, str(ROOT / "windowswitcher.py"), TEST_HOTKEY], cwd=ROOT
        )
        self.addCleanup(self.switcher.stop)
        self.switcher.wait_alive()

    def test_letters_do_not_reach_the_foreground_app(self) -> None:
        log = Path(tempfile.gettempdir()) / "windowswitcher-keylog.txt"
        log.unlink(missing_ok=True)
        target = _Process([PYTHON, str(SUPPORT / "keylog_target.py"), str(log)])
        self.addCleanup(target.stop)
        _wait_for_log(log, "ready")
        time.sleep(1.0)

        send_sequence(TEST_HOTKEY, "a", "esc")
        during = _wait_for_log(log, "ready")
        texts = [line.split(":", 1)[1] for line in during.splitlines() if line.startswith("key ")]
        self.assertNotIn("'q'", texts)
        self.assertNotIn("'Q'", texts)
        self.assertNotIn("'a'", texts)
        self.assertNotIn("'A'", texts)

        send_sequence("b")
        after = _wait_for_log(log, "'b'")
        self.assertIn("'b'", after)

    def test_the_hotkey_does_not_open_the_menu_bar(self) -> None:
        log = Path(tempfile.gettempdir()) / "windowswitcher-menu.txt"
        log.unlink(missing_ok=True)
        target = _Process([PYTHON, str(SUPPORT / "menu_target.py"), str(log)])
        self.addCleanup(target.stop)
        _wait_for_log(log, "ready")
        time.sleep(1.0)

        send_sequence(TEST_HOTKEY, "esc")
        time.sleep(1.5)
        text = log.read_text(encoding="utf-8")
        focuses = [line.split(" ", 1)[1] for line in text.splitlines() if line.startswith("focus ")]
        self.assertEqual(focuses, ["QPlainTextEdit"])


@unittest.skipIf(_skip_reason(), _skip_reason() or "")
class HotkeyDeliveryTests(unittest.TestCase):
    def test_hotkey_installs_hook_and_shows_markers(self) -> None:
        probe = subprocess.run(
            [PYTHON, str(SUPPORT / "hotkey_probe.py"), TEST_HOTKEY],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)
        lines = dict(
            line.split("=", 1) for line in probe.stdout.splitlines() if "=" in line
        )
        self.assertEqual(lines.get("active"), "True")
        self.assertGreater(int(lines.get("markers", "0")), 0)
        self.assertEqual(lines.get("hook"), "True")
        self.assertEqual(lines.get("active_after_cancel"), "False")
        self.assertEqual(lines.get("hook_after_cancel"), "False")
