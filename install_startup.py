"""Install or remove a Windows logon shortcut for windowswitcher.py."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

NAME = "WindowSwitcher.lnk"


def startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("找不到 APPDATA，无法定位启动文件夹")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def shortcut_path() -> Path:
    return startup_dir() / NAME


def pythonw_path(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "pythonw.exe"
    if candidate.is_file():
        return candidate
    return Path(sys.executable).with_name("pythonw.exe")


def create_shortcut() -> Path:
    root = Path(__file__).resolve().parent
    script = root / "windowswitcher.py"
    pythonw = pythonw_path(root)
    if not script.is_file():
        raise SystemExit(f"找不到 {script}")
    if not pythonw.is_file():
        raise SystemExit(f"找不到 {pythonw}，请先创建虚拟环境")

    target = shortcut_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    from win32com.client import Dispatch

    shortcut = Dispatch("WScript.Shell").CreateShortcut(str(target))
    shortcut.TargetPath = str(pythonw)
    shortcut.Arguments = f'"{script}"'
    shortcut.WorkingDirectory = str(root)
    shortcut.WindowStyle = 7
    shortcut.Description = "Python Window Switcher"
    shortcut.Save()
    return target


def remove_shortcut() -> bool:
    path = shortcut_path()
    if path.exists():
        path.unlink()
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 windowswitcher.py 加入或移出当前用户启动项")
    parser.add_argument("--remove", action="store_true", help="从启动项中移除")
    args = parser.parse_args(argv)
    if args.remove:
        if remove_shortcut():
            print(f"已移除 {shortcut_path()}")
        else:
            print("启动项中没有 WindowSwitcher")
        return 0
    path = create_shortcut()
    print(f"已加入启动项：{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
