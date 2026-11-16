"""Test whether Epic Seven can be captured via Win32 PrintWindow even when covered."""

from __future__ import annotations

import ctypes
import cv2
import numpy as np
import win32gui
import win32ui

from window_utils import enable_dpi_awareness, find_game_window

PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002


def capture_printwindow(hwnd: int, width: int, height: int) -> np.ndarray:
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)

    # PW_CLIENTONLY | PW_RENDERFULLCONTENT captures client area of DWM/DirectX windows
    ok = ctypes.windll.user32.PrintWindow(
        hwnd, save_dc.GetSafeHdc(), PW_CLIENTONLY | PW_RENDERFULLCONTENT
    )
    if not ok:
        ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_CLIENTONLY)

    bmp_bits = bitmap.GetBitmapBits(True)
    img = np.frombuffer(bmp_bits, dtype=np.uint8).reshape((height, width, 4))
    bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    return bgr


def main() -> None:
    enable_dpi_awareness()
    region = find_game_window("Epic Seven")
    if region is None:
        print("[ERROR] 'Epic Seven' window not found.")
        return

    input(
        "Drag another window OVER the Epic Seven window (do NOT minimize it), "
        "then press Enter to capture..."
    )
    frame = capture_printwindow(region.hwnd, region.width, region.height)
    out = "test_printwindow.png"
    cv2.imwrite(out, frame)
    mean_val = float(frame.mean())
    print(f"[OK] Saved {out} ({region.width}x{region.height}), mean brightness={mean_val:.1f}")
    if mean_val < 5.0:
        print("[WARN] Image looks black (DirectX window may not support PrintWindow).")
    else:
        print("Open test_printwindow.png to verify the game screen was captured cleanly!")


if __name__ == "__main__":
    main()
