"""Quick diagnostic: verify Epic Seven window detection, screen capture, and mouse click."""

from __future__ import annotations

import sys
import cv2

from window_utils import (
    capture_region,
    click_screen,
    enable_dpi_awareness,
    find_game_window,
)


def main() -> int:
    enable_dpi_awareness()
    region = find_game_window("Epic Seven")
    if region is None:
        print("[ERROR] 'Epic Seven' window not found (or it is minimized).")
        return 1

    print(
        f"[OK] Found window: '{region.title}' | "
        f"Pos=({region.left}, {region.top}) | "
        f"Client size={region.width}x{region.height}"
    )

    frame = capture_region(region)
    out_path = "test_capture.png"
    cv2.imwrite(out_path, frame)
    print(f"[OK] Saved game window screenshot to: {out_path}")

    ans = input("Test clicking the center of the game window? (y/n): ").strip().lower()
    if ans == "y":
        cx = region.left + region.width // 2
        cy = region.top + region.height // 2
        print(f"Clicking at ({cx}, {cy})...")
        click_screen(cx, cy)
        print("[OK] Click sent. Check if the game responded.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
