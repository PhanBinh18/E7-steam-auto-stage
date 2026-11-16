"""State-machine auto-clicker for Epic Seven story stages on Steam."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import keyboard
import numpy as np

from window_utils import (
    WindowRegion,
    capture_region,
    click_box_in_region,
    enable_dpi_awareness,
    find_game_window,
)


BASE_WIDTH = 1920
BASE_HEIGHT = 991


@dataclass(frozen=True)
class MatchResult:
    score: float
    box: tuple[int, int, int, int]  # (x, y, w, h) relative to client region


def load_templates(tmpl_dir: Path) -> dict[str, np.ndarray]:
    templates: dict[str, np.ndarray] = {}
    if not tmpl_dir.exists():
        return templates
    for path in sorted(tmpl_dir.glob("*.png")):
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is not None:
            templates[path.stem] = img
    return templates


def match_template(
    screen: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.84,
) -> Optional[MatchResult]:
    sh, sw = screen.shape[:2]
    th, tw = template.shape[:2]
    if th > sh or tw > sw:
        return None

    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold:
        return MatchResult(score=float(max_val), box=(max_loc[0], max_loc[1], tw, th))
    return None


def click_clear_safe_area(region: WindowRegion) -> tuple[int, int]:
    """Click lower-center area on CLEAR screen to advance."""
    box = (
        int(region.width * 0.40),
        int(region.height * 0.70),
        int(region.width * 0.20),
        int(region.height * 0.15),
    )
    return click_box_in_region(region, box)


def _scale_box(
    box: tuple[int, int, int, int], scale_x: float, scale_y: float
) -> tuple[int, int, int, int]:
    x, y, w, h = box
    return (
        int(round(x * scale_x)),
        int(round(y * scale_y)),
        max(1, int(round(w * scale_x))),
        max(1, int(round(h * scale_y))),
    )


def step_once(
    region: WindowRegion,
    screen: np.ndarray,
    templates: dict[str, np.ndarray],
    threshold: float,
) -> Optional[str]:
    """Check UI states by priority and perform one action if matched."""
    sh, sw = screen.shape[:2]
    scale_x = sw / BASE_WIDTH
    scale_y = sh / BASE_HEIGHT

    if sw != BASE_WIDTH or sh != BASE_HEIGHT:
        interp = cv2.INTER_AREA if sw > BASE_WIDTH else cv2.INTER_LINEAR
        work_screen = cv2.resize(screen, (BASE_WIDTH, BASE_HEIGHT), interpolation=interp)
    else:
        work_screen = screen

    def find(name: str, thr: float = threshold) -> Optional[MatchResult]:
        tmpl = templates.get(name)
        if tmpl is None:
            return None
        return match_template(work_screen, tmpl, threshold=thr)

    def click_scaled(m: MatchResult, hold_seconds: Optional[float] = None) -> tuple[int, int]:
        real_box = _scale_box(m.box, scale_x, scale_y)
        return click_box_in_region(region, real_box, hold_seconds=hold_seconds)

    # 1. Popup: Tap to close (Story Clear / Received Reward / etc.)
    if m := find("tap_to_close", 0.80):
        x, y = click_scaled(m)
        return f"tap_to_close ({m.score:.2f}) -> ({x}, {y})"

    # 2. Popup: Skip Story -> Confirm (verified by prompt text)
    if find("skip_story_prompt", 0.80) and (m := find("skip_confirm", 0.82)):
        x, y = click_scaled(m)
        return f"skip_confirm ({m.score:.2f}) -> ({x}, {y})"

    # 3. Popup: Friend Request -> Cancel (verified by friend header)
    if find("friend_header", 0.80) and (m := find("friend_cancel", 0.82)):
        x, y = click_scaled(m)
        return f"friend_cancel ({m.score:.2f}) -> ({x}, {y})"

    # 4. Dialogue: Skip >
    if m := find("skip_btn", 0.80):
        x, y = click_scaled(m)
        return f"skip_btn ({m.score:.2f}) -> ({x}, {y})"

    # 5. Cutscene anime: hold >>| if template provided
    if m := find("cutscene_skip", 0.80):
        x, y = click_scaled(m, hold_seconds=3.0)
        return f"cutscene_skip hold 3s ({m.score:.2f}) -> ({x}, {y})"

    # 6. Battle CLEAR screen
    if m := find("clear_logo", 0.78):
        x, y = click_clear_safe_area(region)
        return f"clear_logo ({m.score:.2f}) -> click ({x}, {y})"

    # 7. MVP screen -> Confirm >
    if m := find("mvp_confirm", 0.82):
        x, y = click_scaled(m)
        return f"mvp_confirm ({m.score:.2f}) -> ({x}, {y})"

    # 8. Team screen -> Start Quest
    if m := find("start_quest", 0.82):
        x, y = click_scaled(m)
        return f"start_quest ({m.score:.2f}) -> ({x}, {y})"

    # 9. Supporter screen -> Select Team >
    if m := find("select_team", 0.82):
        x, y = click_scaled(m)
        return f"select_team ({m.score:.2f}) -> ({x}, {y})"

    # 10. Episode screen -> Ready
    if m := find("ready", 0.84):
        x, y = click_scaled(m)
        return f"ready ({m.score:.2f}) -> ({x}, {y})"

    return None


def main() -> None:
    enable_dpi_awareness()
    templates = load_templates(Path("templates"))
    if not templates:
        print("[ERROR] templates/ is empty. Run capture_helper.py and crop_helper.py first.")
        return

    print(f"[INFO] Loaded {len(templates)} templates: {', '.join(sorted(templates.keys()))}")
    print("[INFO] Hotkeys: F8 = Pause / Resume | F10 = Exit")

    paused = False
    f8_was_down = False

    while True:
        if keyboard.is_pressed("f10"):
            print("\n[EXIT] F10 pressed. Stopping.")
            break

        f8_down = keyboard.is_pressed("f8")
        if f8_down and not f8_was_down:
            paused = not paused
            print(f"\n[{'PAUSED' if paused else 'RESUMED'}]")
        f8_was_down = f8_down

        if paused:
            time.sleep(0.15)
            continue

        region = find_game_window("Epic Seven")
        if region is None:
            print("[WAIT] Waiting for 'Epic Seven' window...", end="\r")
            time.sleep(1.0)
            continue

        screen = capture_region(region)
        action = step_once(region, screen, templates, threshold=0.82)
        if action:
            print(f"[CLICK] {action}")
            time.sleep(random.uniform(0.75, 1.25))
        else:
            time.sleep(random.uniform(0.45, 0.70))


if __name__ == "__main__":
    main()
