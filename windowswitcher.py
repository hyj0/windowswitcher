from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import os
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable, Sequence

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from pywinauto import Desktop


LOG = logging.getLogger("windowswitcher")

KEY_ORDER = "fjdklghrueiovwnbzpqcmxy"
CWP_SKIPINVISIBLE = 0x0001
DWMWA_CLOAKED = 14
GA_ROOT = 2
GA_ROOTOWNER = 3
GWL_EXSTYLE = -20
MARKER_PROBE_SIZE = 30
MONITOR_DEFAULTTONEAREST = 2
SW_RESTORE = 9
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080

HC_ACTION = 0
HOTKEY_ID = 1
HWND_TOPMOST = -1
INJECTED_TAG = 0x57535731
KEYEVENTF_KEYUP = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOSIZE = 0x0001
VK_CONTROL = 0x11
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_BACK = 0x08
VK_ESCAPE = 0x1B
VK_F1 = 0x70
WH_KEYBOARD_LL = 13
WM_HOTKEY = 0x0312
WM_KEYDOWN = 0x0100
WM_QUIT = 0x0012
WM_SYSKEYDOWN = 0x0104

# Letting modifiers through keeps the host application from seeing them stuck down.
MODIFIER_KEYS = frozenset(
    {0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}
)
MODIFIER_TOKENS = {
    "alt": MOD_ALT,
    "control": MOD_CONTROL,
    "ctrl": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "super": MOD_WIN,
    "win": MOD_WIN,
}
NAMED_KEYS = {
    "backspace": VK_BACK,
    "delete": 0x2E,
    "down": 0x28,
    "end": 0x23,
    "enter": 0x0D,
    "esc": VK_ESCAPE,
    "escape": VK_ESCAPE,
    "home": 0x24,
    "insert": 0x2D,
    "left": 0x25,
    "pagedown": 0x22,
    "pageup": 0x21,
    "return": 0x0D,
    "right": 0x27,
    "space": 0x20,
    "tab": 0x09,
    "up": 0x26,
}

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
kernel32 = ctypes.windll.kernel32

user32.EnumWindows.argtypes = [ctypes.c_void_p, wt.LPARAM]
user32.EnumWindows.restype = wt.BOOL
user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
user32.GetWindow.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetAncestor.restype = wt.HWND
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.AttachThreadInput.restype = wt.BOOL
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.GetDesktopWindow.restype = wt.HWND
user32.ChildWindowFromPointEx.argtypes = [wt.HWND, wt.POINT, wt.UINT]
user32.ChildWindowFromPointEx.restype = wt.HWND
user32.WindowFromPoint.argtypes = [wt.POINT]
user32.WindowFromPoint.restype = wt.HWND
user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.RegisterHotKey.restype = wt.BOOL
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wt.BOOL
user32.GetKeyState.argtypes = [ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_short
user32.UnhookWindowsHookEx.argtypes = [wt.HHOOK]
user32.UnhookWindowsHookEx.restype = wt.BOOL
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE
kernel32.GetCurrentThreadId.restype = wt.DWORD
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.PostThreadMessageW.restype = wt.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wt.DWORD),
        ("scanCode", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


user32.keybd_event.argtypes = [wt.BYTE, wt.BYTE, wt.DWORD, ctypes.c_size_t]


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM
)
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    LowLevelKeyboardProc,
    wt.HMODULE,
    wt.DWORD,
]
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t


def parse_hotkey(text: str) -> tuple[int, int]:
    """Translate a string such as ``alt+q`` into RegisterHotKey arguments."""
    modifiers = 0
    key: int | None = None
    for raw in text.split("+"):
        token = raw.strip().lower()
        if not token:
            raise ValueError(f"快捷键格式错误：{text}")
        if token in MODIFIER_TOKENS:
            modifiers |= MODIFIER_TOKENS[token]
            continue
        if key is not None:
            raise ValueError(f"快捷键只能包含一个主键：{text}")
        if len(token) == 1 and token.isalnum() and token.isascii():
            key = ord(token.upper())
        elif token in NAMED_KEYS:
            key = NAMED_KEYS[token]
        elif token.startswith("f") and token[1:].isdigit() and 1 <= int(token[1:]) <= 24:
            key = VK_F1 + int(token[1:]) - 1
        else:
            raise ValueError(f"不支持的按键：{raw}")
    if key is None:
        raise ValueError(f"快捷键缺少主键：{text}")
    return modifiers, key


def key_name(vk: int) -> str | None:
    """Name the marker-mode action a virtual key stands for."""
    if vk == VK_ESCAPE:
        return "escape"
    if vk == VK_BACK:
        return "backspace"
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    return None


def _break_modifier_tap() -> None:
    """Keep the still held Alt/Win from reaching the app as a lone tap.

    Windows opens the menu bar or the start menu when a modifier is pressed and
    released on its own. Tapping Ctrl while the hotkey modifier is still down
    ends that lone press without meaning anything to the application. The tag
    lets the low level hook pass the injected key through.
    """
    user32.keybd_event(VK_CONTROL, 0, 0, INJECTED_TAG)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, INJECTED_TAG)


def _pressed_modifiers() -> int:
    modifiers = 0
    if user32.GetKeyState(0x12) < 0:
        modifiers |= MOD_ALT
    if user32.GetKeyState(0x11) < 0:
        modifiers |= MOD_CONTROL
    if user32.GetKeyState(0x10) < 0:
        modifiers |= MOD_SHIFT
    if user32.GetKeyState(0x5B) < 0 or user32.GetKeyState(0x5C) < 0:
        modifiers |= MOD_WIN
    return modifiers
dwmapi.DwmGetWindowAttribute.argtypes = [
    wt.HWND,
    wt.DWORD,
    ctypes.c_void_p,
    wt.DWORD,
]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


def label_for(index: int) -> str:
    """Return the same prefix-friendly labels used by FastWindowSwitcher."""
    if index < 0:
        raise ValueError("index must be non-negative")
    base = len(KEY_ORDER)
    if index < base:
        return KEY_ORDER[index]
    index -= base
    if index < base:
        return "a" + KEY_ORDER[index]
    index -= base
    if index < base:
        return "s" + KEY_ORDER[index]
    return f"#{index + base * 3}"


def labels(count: int) -> list[str]:
    if count < 0:
        raise ValueError("count must be non-negative")
    return [label_for(index) for index in range(count)]


@dataclass(frozen=True)
class MarkerPosition:
    x: int
    y: int


@dataclass
class Target:
    title: str
    positions: list[MarkerPosition]
    activate: Callable[[], None] = field(repr=False)
    label: str = ""


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wt.LONG),
        ("top", wt.LONG),
        ("right", wt.LONG),
        ("bottom", wt.LONG),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wt.DWORD),
    ]


user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
user32.MonitorFromWindow.restype = wt.HMONITOR
user32.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wt.BOOL
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wt.BOOL
user32.SetWindowPos.argtypes = [
    wt.HWND,
    wt.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wt.UINT,
]
user32.SetWindowPos.restype = wt.BOOL


def clamp_to_work_area(rect: RECT, work: RECT | None) -> RECT:
    """Trim a window rect down to the part of the monitor the user can see.

    Maximized windows report a rect that includes the invisible resize border,
    so the top edge can sit above the screen. Markers placed there would land
    outside the virtual desktop and be treated as covered.
    """
    if work is None:
        return rect
    left = max(rect.left, work.left)
    top = max(rect.top, work.top)
    right = min(rect.right, work.right)
    bottom = min(rect.bottom, work.bottom)
    if right - left < MARKER_PROBE_SIZE or bottom - top < MARKER_PROBE_SIZE:
        return rect
    return RECT(left, top, right, bottom)


def _window_work_area(hwnd: int) -> RECT | None:
    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor:
        return None
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    return info.rcWork


def _window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value.strip()


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _window_rect(hwnd: int) -> RECT | None:
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    if rect.right - rect.left < 10 or rect.bottom - rect.top < 10:
        return None
    return rect


def _is_cloaked(hwnd: int) -> bool:
    cloaked = wt.DWORD()
    result = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return result == 0 and bool(cloaked.value)


def _is_selectable_window(hwnd: int, own_pid: int) -> bool:
    if not user32.IsWindowVisible(hwnd) or not user32.IsWindowEnabled(hwnd):
        return False
    if user32.IsIconic(hwnd) or _is_cloaked(hwnd):
        return False

    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == own_pid:
        return False

    title = _window_text(hwnd)
    if not title:
        return False

    class_name = _class_name(hwnd)
    if class_name in {
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "Progman",
        "WorkerW",
    }:
        return False

    ex_style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    if ex_style & WS_EX_TOOLWINDOW and not ex_style & WS_EX_APPWINDOW:
        return False

    owner = user32.GetWindow(hwnd, 4)  # GW_OWNER
    if owner and not ex_style & WS_EX_APPWINDOW:
        root_owner = user32.GetAncestor(hwnd, GA_ROOTOWNER)
        if root_owner != hwnd:
            return False
    return _window_rect(hwnd) is not None


def _marker_positions(rect: RECT) -> list[MarkerPosition]:
    width = rect.right - rect.left
    y = rect.top + 8
    if width <= 160:
        return [MarkerPosition(rect.left + width // 2, y)]
    count = max(1, width // 180)
    step = width / (count + 1)
    return [
        MarkerPosition(round(rect.left + step * (index + 1)), y)
        for index in range(count)
    ]


def _top_level_window_at(x: int, y: int) -> int:
    """Return the top level window the user actually sees at a screen point."""
    point = wt.POINT(x, y)
    found = user32.ChildWindowFromPointEx(
        user32.GetDesktopWindow(), point, CWP_SKIPINVISIBLE
    )
    if not found:
        found = user32.WindowFromPoint(point)
    if not found:
        return 0
    return int(user32.GetAncestor(found, GA_ROOT) or found)


def _is_marker_visible(
    hwnd: int,
    rect: RECT,
    position: MarkerPosition,
    probe: Callable[[int, int], int],
) -> bool:
    half = MARKER_PROBE_SIZE // 2
    left = max(rect.left + 1, position.x - half)
    right = min(rect.right - 2, position.x + half)
    top = max(rect.top + 1, position.y)
    bottom = min(rect.bottom - 2, position.y + MARKER_PROBE_SIZE)
    if right < left or bottom < top:
        return False
    return probe(left, top) == hwnd and probe(right, bottom) == hwnd


def visible_marker_positions(
    hwnd: int,
    rect: RECT,
    probe: Callable[[int, int], int] | None = None,
) -> list[MarkerPosition]:
    """Keep only the marker spots that are not obscured by another window."""
    hit_test = probe if probe is not None else _top_level_window_at
    return [
        position
        for position in _marker_positions(rect)
        if _is_marker_visible(hwnd, rect, position, hit_test)
    ]


def _activate_window(hwnd: int) -> None:
    if not user32.IsWindow(hwnd):
        return
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    foreground = user32.GetForegroundWindow()
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
    current_thread = kernel32.GetCurrentThreadId()
    attached = False
    if foreground_thread and foreground_thread != current_thread:
        attached = bool(
            user32.AttachThreadInput(current_thread, foreground_thread, True)
        )
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(current_thread, foreground_thread, False)


def enumerate_window_targets() -> list[Target]:
    targets: list[Target] = []
    own_pid = os.getpid()
    callback_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    @callback_type
    def callback(hwnd: int, _lparam: int) -> bool:
        if _is_selectable_window(hwnd, own_pid):
            rect = _window_rect(hwnd)
            if rect is not None:
                placement = clamp_to_work_area(rect, _window_work_area(hwnd))
                positions = visible_marker_positions(hwnd, placement)
                if positions:
                    targets.append(
                        Target(
                            title=_window_text(hwnd),
                            positions=positions,
                            activate=lambda handle=hwnd: _activate_window(handle),
                        )
                    )
        return True

    user32.EnumWindows(callback, 0)
    return targets


def _rect_center(rect: object) -> MarkerPosition | None:
    left = int(getattr(rect, "left", 0))
    top = int(getattr(rect, "top", 0))
    right = int(getattr(rect, "right", 0))
    bottom = int(getattr(rect, "bottom", 0))
    if right <= left or bottom <= top:
        return None
    return MarkerPosition((left + right) // 2, (top + bottom) // 2)


def _invoke_taskbar_button(button: object) -> None:
    try:
        button.invoke()
    except Exception:
        button.click_input()


def enumerate_taskbar_targets() -> list[Target]:
    """Enumerate visible taskbar buttons through Microsoft UI Automation."""
    targets: list[Target] = []
    seen: set[tuple[int, int, int, int, str]] = set()
    try:
        desktop = Desktop(backend="uia")
        taskbars = [
            window
            for window in desktop.windows()
            if window.class_name() in {"Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
        ]
        for taskbar in taskbars:
            taskbar_handle = int(taskbar.handle or 0)
            for button in taskbar.descendants(control_type="Button"):
                try:
                    if not button.is_visible():
                        continue
                    title = button.window_text().strip()
                    center = _rect_center(button.rectangle())
                    rect = button.rectangle()
                    key = (
                        int(rect.left),
                        int(rect.top),
                        int(rect.right),
                        int(rect.bottom),
                        title,
                    )
                    if center is None or key in seen:
                        continue
                    if (
                        taskbar_handle
                        and _top_level_window_at(center.x, center.y) != taskbar_handle
                    ):
                        continue
                    seen.add(key)
                    targets.append(
                        Target(
                            title=title or "任务栏按钮",
                            positions=[center],
                            activate=lambda item=button: _invoke_taskbar_button(item),
                        )
                    )
                except Exception:
                    LOG.debug("忽略无法读取的任务栏元素", exc_info=True)
    except Exception:
        LOG.warning("无法读取任务栏按钮；窗口切换仍可使用", exc_info=True)
    return targets


def collect_targets() -> list[Target]:
    result = enumerate_window_targets()
    result.extend(enumerate_taskbar_targets())
    for target, text in zip(result, labels(len(result)), strict=True):
        target.label = text
    return result


class Marker(QLabel):
    def __init__(self, text: str, position: MarkerPosition) -> None:
        super().__init__(text)
        self._full_text = text
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.setStyleSheet(
            "QLabel { color: #111; background: #ffd43b; "
            "border: 2px solid #111; border-radius: 5px; padding: 2px 5px; }"
        )
        self._position = position
        self._resize_to_text()

    def _resize_to_text(self) -> None:
        self.adjustSize()
        size = max(self.width(), self.height(), 30)
        self.resize(size, max(self.height(), 30))

    def place(self) -> None:
        """Position the marker in physical pixels.

        Qt lays widgets out in device independent pixels, so on a monitor with
        a scale factor other than 100% a Win32 coordinate would land somewhere
        else entirely, possibly on another screen. Moving the native window
        keeps the marker exactly on the spot that was probed.
        """
        hwnd = int(self.winId())
        rect = RECT()
        # Two passes: the first move can cross a DPI boundary and resize us.
        for _ in range(2):
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return
            width = rect.right - rect.left
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                self._position.x - width // 2,
                self._position.y,
                0,
                0,
                SWP_NOSIZE | SWP_NOACTIVATE,
            )

    def show_marker(self) -> None:
        self.show()
        self.place()

    def update_prefix(self, prefix: str) -> bool:
        if not self._full_text.startswith(prefix):
            self.hide()
            return False
        remaining = self._full_text[len(prefix) :]
        self.setText(remaining or self._full_text)
        self._resize_to_text()
        self.show()
        self.place()
        return True


class HotkeyFilter(QAbstractNativeEventFilter):
    """Turn the WM_HOTKEY message delivered by Windows into a callback."""

    def __init__(self, hotkey_id: int, on_hotkey: Callable[[], None]) -> None:
        super().__init__()
        self._hotkey_id = hotkey_id
        self._on_hotkey = on_hotkey

    def nativeEventFilter(self, event_type, message):  # type: ignore[override]
        if event_type == b"windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(wt.MSG)).contents
            if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                self._on_hotkey()
                return True, 0
        return False, 0


class KeyboardHook:
    """A low level keyboard hook running on its own message pumping thread.

    Windows stops calling a hook that does not answer within
    ``LowLevelHooksTimeout`` (300 ms by default) and lets the keystroke reach
    the focused application instead. Enumerating windows and taskbar buttons
    easily takes longer than that, so the hook cannot share the UI thread.
    """

    def __init__(self, on_key: Callable[[int, int], None]) -> None:
        self._on_key = on_key
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._handle = 0
        self._proc: LowLevelKeyboardProc | None = None
        self._ready = threading.Event()

    @property
    def installed(self) -> bool:
        return self._thread is not None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._ready.clear()
        thread = threading.Thread(target=self._run, name="keyboard-hook", daemon=True)
        thread.start()
        self._ready.wait(2.0)
        self._thread = thread if self._handle else None

    def stop(self) -> None:
        thread, thread_id = self._thread, self._thread_id
        self._thread = None
        self._thread_id = 0
        if thread is None:
            return
        if thread_id:
            user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
        thread.join(2.0)

    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        self._proc = LowLevelKeyboardProc(self._callback)
        self._handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0
        )
        self._ready.set()
        if not self._handle:
            LOG.error(
                "无法安装键盘钩子（错误码 %d），标记模式下的按键会传给其他程序",
                ctypes.GetLastError(),
            )
            self._proc = None
            return
        message = wt.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        user32.UnhookWindowsHookEx(self._handle)
        self._handle = 0
        self._proc = None

    def _callback(self, code: int, wparam: int, lparam: int) -> int:
        if code == HC_ACTION:
            info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if info.vkCode not in MODIFIER_KEYS and info.dwExtraInfo != INJECTED_TAG:
                self._on_key(info.vkCode, wparam)
                # Swallow the whole key so the focused application never sees it.
                return 1
        return user32.CallNextHookEx(None, code, wparam, lparam)


class Switcher(QObject):
    activation_requested = Signal()
    key_received = Signal(str)

    def __init__(self, hotkey: str) -> None:
        super().__init__()
        self.hotkey = hotkey
        self.modifiers, self.key = parse_hotkey(hotkey)
        self.targets: list[Target] = []
        self.markers: dict[str, list[Marker]] = {}
        self.prefix = ""
        self.hook = KeyboardHook(self._on_hook_key)
        self._active = False
        self.activation_requested.connect(self.activate_mode)
        # Queued so the low level hook returns before any window work starts.
        self.key_received.connect(
            self.process_key, Qt.ConnectionType.QueuedConnection
        )

        self._host = QWidget()
        self._hwnd = int(self._host.winId())
        self._filter = HotkeyFilter(HOTKEY_ID, self.activation_requested.emit)
        QApplication.instance().installNativeEventFilter(self._filter)
        if not user32.RegisterHotKey(
            self._hwnd, HOTKEY_ID, self.modifiers | MOD_NOREPEAT, self.key
        ):
            raise RuntimeError(f"快捷键 {hotkey} 已被其他程序占用，无法注册")

    @Slot()
    def activate_mode(self) -> None:
        if self.modifiers & (MOD_ALT | MOD_WIN):
            _break_modifier_tap()
        if self._active:
            self.cancel()
            return
        # Hook first: enumerating windows and taskbar buttons takes a moment,
        # and anything typed in the meantime would reach the focused app.
        self.hook.start()
        self.targets = collect_targets()
        if not self.targets:
            self.hook.stop()
            return
        self.prefix = ""
        self._active = True
        for target in self.targets:
            target_markers = [
                Marker(target.label, position) for position in target.positions
            ]
            self.markers[target.label] = target_markers
            for marker in target_markers:
                marker.show_marker()
                marker.raise_()

    def _on_hook_key(self, vk: int, wparam: int) -> None:
        if wparam not in (WM_KEYDOWN, WM_SYSKEYDOWN):
            return
        if vk == self.key and _pressed_modifiers() == self.modifiers:
            self.key_received.emit("escape")
            return
        name = key_name(vk)
        if name is not None:
            self.key_received.emit(name)

    @Slot(str)
    def process_key(self, key: str) -> None:
        if not self._active:
            return
        if key == "escape":
            self.cancel()
            return
        if key == "backspace":
            self.prefix = self.prefix[:-1]
        else:
            self.prefix += key

        exact = next(
            (target for target in self.targets if target.label == self.prefix), None
        )
        if exact is not None:
            action = exact.activate
            self._finish()
            try:
                action()
            except Exception:
                LOG.exception("无法激活目标：%s", exact.title)
            return

        matches = 0
        for label, marker_list in self.markers.items():
            visible = label.startswith(self.prefix)
            if visible:
                matches += 1
            for marker in marker_list:
                marker.update_prefix(self.prefix)
        if not matches:
            QApplication.beep()
            self.prefix = self.prefix[:-1]
            for marker_list in self.markers.values():
                for marker in marker_list:
                    marker.update_prefix(self.prefix)

    @Slot()
    def cancel(self) -> None:
        self._finish()

    def _finish(self) -> None:
        self.hook.stop()
        for marker_list in self.markers.values():
            for marker in marker_list:
                marker.close()
                marker.deleteLater()
        self.markers.clear()
        self.targets.clear()
        self.prefix = ""
        self._active = False

    def shutdown(self) -> None:
        self._finish()
        user32.UnregisterHotKey(self._hwnd, HOTKEY_ID)
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self._filter)


def enable_dpi_awareness() -> None:
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            LOG.debug("无法设置 DPI awareness", exc_info=True)


DEFAULT_HOTKEY = "alt+q"


def main(argv: Sequence[str] | None = None) -> int:
    if sys.platform != "win32":
        raise SystemExit("此程序仅支持 Windows")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args = list(argv if argv is not None else sys.argv)
    hotkey = args[1] if len(args) > 1 else DEFAULT_HOTKEY
    enable_dpi_awareness()
    app = QApplication(args[:1])
    app.setQuitOnLastWindowClosed(False)
    switcher = Switcher(hotkey)
    app.aboutToQuit.connect(switcher.shutdown)
    LOG.info("窗口切换器已启动：按 %s 显示字母标记", hotkey)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
