"""Window discovery, DPI-aware capture, and multi-monitor mouse helpers for Epic Seven."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import random
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import mss
import numpy as np
import win32con
import win32gui
import win32ui


def enable_dpi_awareness() -> None:
    """Enable Per-Monitor DPI Awareness v2/v1 so coordinates match across monitors."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


@dataclass(frozen=True)
class WindowRegion:
    """Screen-space client rectangle of a window."""

    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int

    def as_mss_monitor(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


def find_game_window(title_substring: str = "Epic Seven") -> Optional[WindowRegion]:
    """Find the first visible, non-minimized window whose title contains title_substring."""
    matches: list[WindowRegion] = []
    needle = title_substring.lower()

    def _enum_cb(hwnd: int, _: int) -> bool:
        if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if needle in title.lower():
            cr = win32gui.GetClientRect(hwnd)
            width = cr[2] - cr[0]
            height = cr[3] - cr[1]
            if width > 100 and height > 100:
                left, top = win32gui.ClientToScreen(hwnd, (0, 0))
                matches.append(WindowRegion(hwnd, title, left, top, width, height))
        return True

    win32gui.EnumWindows(_enum_cb, 0)
    return matches[0] if matches else None


_PW_CLIENTONLY = 0x00000001
_PW_RENDERFULLCONTENT = 0x00000002


def capture_region(region: WindowRegion) -> np.ndarray:
    """Capture the game client area via PrintWindow (works even when covered), with mss fallback."""
    hwnd_dc = win32gui.GetWindowDC(region.hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(mfc_dc, region.width, region.height)
        save_dc.SelectObject(bitmap)

        ok = ctypes.windll.user32.PrintWindow(
            region.hwnd, save_dc.GetSafeHdc(), _PW_CLIENTONLY | _PW_RENDERFULLCONTENT
        )
        if ok:
            bmp_bits = bitmap.GetBitmapBits(True)
            img = np.frombuffer(bmp_bits, dtype=np.uint8).reshape((region.height, region.width, 4))
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(region.hwnd, hwnd_dc)

    with mss.MSS() as sct:
        shot = sct.grab(region.as_mss_monitor())
        frame = np.array(shot, dtype=np.uint8)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)


# Win32 SendInput mouse constants
_INPUT_MOUSE = 0
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("mi", _MOUSEINPUT)]


def _send_mouse_flag(flag: int) -> None:
    inp = _INPUT(
        type=_INPUT_MOUSE,
        mi=_MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flag, time=0, dwExtraInfo=None),
    )
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def click_screen(x: int, y: int, hold_seconds: float = 0.05) -> None:
    """Move cursor to (x, y) across any monitor and perform a left click."""
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    time.sleep(random.uniform(0.03, 0.07))
    _send_mouse_flag(_MOUSEEVENTF_LEFTDOWN)
    time.sleep(max(0.02, hold_seconds))
    _send_mouse_flag(_MOUSEEVENTF_LEFTUP)


def click_background(hwnd: int, rel_x: int, rel_y: int, hold_seconds: float = 0.06) -> None:
    """Send a background left click to hwnd at client coordinates (rel_x, rel_y) without moving the cursor."""
    lparam = ((int(rel_y) & 0xFFFF) << 16) | (int(rel_x) & 0xFFFF)
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
    time.sleep(random.uniform(0.02, 0.04))
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(max(0.02, hold_seconds))
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)


def click_box_in_region(
    region: WindowRegion,
    box: tuple[int, int, int, int],
    hold_seconds: Optional[float] = None,
    padding_ratio: float = 0.2,
    background: bool = True,
) -> tuple[int, int]:
    """Click a randomized point inside (x, y, w, h) relative to region."""
    bx, by, bw, bh = box
    pad_x = max(1, int(bw * padding_ratio))
    pad_y = max(1, int(bh * padding_ratio))

    rel_x = random.randint(bx + pad_x, max(bx + pad_x, bx + bw - pad_x))
    rel_y = random.randint(by + pad_y, max(by + pad_y, by + bh - pad_y))
    hold = hold_seconds if hold_seconds is not None else random.uniform(0.05, 0.11)

    if background:
        click_background(region.hwnd, rel_x, rel_y, hold_seconds=hold)
        return rel_x, rel_y

    abs_x = region.left + rel_x
    abs_y = region.top + rel_y
    click_screen(abs_x, abs_y, hold_seconds=hold)
    return abs_x, abs_y
