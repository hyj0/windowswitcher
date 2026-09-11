from __future__ import annotations

import ctypes
import time

user32 = ctypes.windll.user32
user32.keybd_event.argtypes = [
    ctypes.c_ubyte,
    ctypes.c_ubyte,
    ctypes.c_ulong,
    ctypes.c_size_t,
]

KEYEVENTF_KEYUP = 0x0002
VIRTUAL_KEYS = {
    "alt": 0x12,
    "ctrl": 0x11,
    "control": 0x11,
    "esc": 0x1B,
    "escape": 0x1B,
    "shift": 0x10,
    "win": 0x5B,
}


def send_combo(step: str, hold_s: float = 0.05) -> None:
    """Send a chord such as ``alt+q`` or a single key such as ``a``."""
    parts = [part.strip().lower() for part in step.split("+") if part.strip()]
    if not parts:
        raise ValueError("empty key combo")
    *modifiers, name = parts
    for modifier in modifiers:
        user32.keybd_event(VIRTUAL_KEYS[modifier], 0, 0, 0)
    if name in VIRTUAL_KEYS:
        vk = VIRTUAL_KEYS[name]
    elif len(name) == 1 and name.isascii():
        vk = ord(name.upper())
    else:
        raise ValueError(f"不支持的按键：{name!r}")
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(hold_s)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    for modifier in reversed(modifiers):
        user32.keybd_event(VIRTUAL_KEYS[modifier], 0, KEYEVENTF_KEYUP, 0)


def send_sequence(*steps: str, pause_s: float = 1.0) -> None:
    for step in steps:
        send_combo(step)
        time.sleep(pause_s)
