"""Restart the background Window Switcher so it picks up the current code."""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import time
from pathlib import Path

from install_startup import pythonw_path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "windowswitcher.py"

CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008
PROCESS_TERMINATE = 0x0001
SYNCHRONIZE = 0x00100000

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def running_instances() -> list[int]:
    """Return the pids of every Python process running windowswitcher.py.

    One instance shows up as two pids: the venv launcher re-executes the base
    interpreter, and both keep the script on their command line.
    """
    import win32com.client

    wmi = win32com.client.GetObject("winmgmts:")
    query = (
        "SELECT ProcessId, CommandLine FROM Win32_Process "
        "WHERE Name = 'python.exe' OR Name = 'pythonw.exe'"
    )
    own = os.getpid()
    needle = SCRIPT.name.lower()
    return [
        int(process.ProcessId)
        for process in wmi.ExecQuery(query)
        if int(process.ProcessId) != own and needle in (process.CommandLine or "").lower()
    ]


def stop_instances(timeout_s: float = 5.0) -> tuple[list[int], list[int]]:
    """Kill the running instances. Windows releases the hotkey and hook for us.

    Returns the pids that are gone and the ones that survived. A process can
    exit on its own between the query and the kill, so the outcome is decided
    by looking again rather than by the return code of a single call.
    """
    targets = running_instances()
    for pid in targets:
        handle = kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
        if not handle:
            continue
        try:
            if kernel32.TerminateProcess(handle, 0):
                kernel32.WaitForSingleObject(handle, int(timeout_s * 1000))
        finally:
            kernel32.CloseHandle(handle)
    alive = set(running_instances())
    return (
        [pid for pid in targets if pid not in alive],
        [pid for pid in targets if pid in alive],
    )


def start_instance(hotkey: str | None = None) -> int:
    pythonw = pythonw_path(ROOT)
    if not SCRIPT.is_file():
        raise SystemExit(f"找不到 {SCRIPT}")
    if not pythonw.is_file():
        raise SystemExit(f"找不到 {pythonw}，请先创建虚拟环境")
    command = [str(pythonw), str(SCRIPT)]
    if hotkey:
        command.append(hotkey)
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    return process.pid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="重启后台运行的 windowswitcher.py")
    parser.add_argument("--stop", action="store_true", help="只停止，不重新启动")
    parser.add_argument("hotkey", nargs="?", help="可选快捷键，例如 ctrl+alt+space")
    args = parser.parse_args(argv)

    stopped, stubborn = stop_instances()
    if stopped:
        print(f"已停止 {len(stopped)} 个进程：" + "、".join(str(pid) for pid in stopped))
    if stubborn:
        print(
            "无法结束（可能以管理员身份运行）："
            + "、".join(str(pid) for pid in stubborn)
        )
    if not stopped and not stubborn:
        print("没有正在运行的实例")
    if args.stop:
        return 1 if stubborn else 0

    pid = start_instance(args.hotkey)
    # The hotkey is registered during startup; a dead process here means it clashed.
    time.sleep(2.0)
    if pid not in running_instances():
        print(f"进程 {pid} 启动后立即退出，请用 python windowswitcher.py 查看报错")
        return 1
    print(f"已启动：{pid}（快捷键 {args.hotkey or 'alt+q'}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
