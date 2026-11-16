"""Test whether Epic Seven (Steam) accepts background mouse clicks without moving the cursor."""

from __future__ import annotations

import time
import win32api
import win32con
import win32gui

from window_utils import enable_dpi_awareness, find_game_window


def make_lparam(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def send_bg_click(hwnd: int, rel_x: int, rel_y: int) -> None:
    lparam = make_lparam(rel_x, rel_y)
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
    time.sleep(0.02)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(0.06)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)


def main() -> None:
    enable_dpi_awareness()
    region = find_game_window("Epic Seven")
    if region is None:
        print("[ERROR] 'Epic Seven' window not found.")
        return

    print(f"[OK] Found '{region.title}' ({region.width}x{region.height})")
    print("Keep another window (e.g. PowerShell) active without focusing the game.")
    input("Press Enter to send a background click (PostMessage) to the Ready button (bottom-right)...")

    # Ready button center in 1920x991 is roughly (1705, 922); scale proportionally
    rel_x = int(region.width * 0.888)
    rel_y = int(region.height * 0.930)
    print(f"Sending PostMessage at client coords ({rel_x}, {rel_y}) - cursor will NOT move...")
    send_bg_click(region.hwnd, rel_x, rel_y)
    print("Done! Check if the game responded (clicked Ready).")


if __name__ == "__main__":
    main()
