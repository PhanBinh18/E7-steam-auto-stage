"""Capture native-resolution screenshots of the Epic Seven window using F9."""

from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
import keyboard

from window_utils import capture_region, enable_dpi_awareness, find_game_window


def main() -> None:
    enable_dpi_awareness()
    out_dir = Path("screenshots")
    out_dir.mkdir(exist_ok=True)

    existing = sorted(out_dir.glob("shot_*.png"))
    index = len(existing) + 1

    print("=== Epic Seven Screenshot Helper ===")
    print("Press F9  to capture the 'Epic Seven' window")
    print("Press F10 to exit")

    while True:
        if keyboard.is_pressed("f10"):
            print("Exited.")
            break

        if keyboard.is_pressed("f9"):
            region = find_game_window("Epic Seven")
            if region is None:
                print("[WARN] 'Epic Seven' window not found!")
            else:
                frame = capture_region(region)
                file_path = out_dir / f"shot_{index:03d}.png"
                cv2.imwrite(str(file_path), frame)
                print(f"[SAVED] {file_path} ({region.width}x{region.height})")
                index += 1
            time.sleep(0.4)

        time.sleep(0.05)


if __name__ == "__main__":
    main()
