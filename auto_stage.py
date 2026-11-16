"""State-machine auto-clicker for Epic Seven story stages on Steam."""

from __future__ import annotations

import argparse
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
    resize_game_window,
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


def click_center_safe_area(region: WindowRegion) -> tuple[int, int]:
    """Click center area (e.g., Act banner) to reveal Skip or advance."""
    box = (
        int(region.width * 0.42),
        int(region.height * 0.42),
        int(region.width * 0.16),
        int(region.height * 0.16),
    )
    return click_box_in_region(region, box)


def click_enemy_area(region: WindowRegion) -> tuple[int, int]:
    """Click enemy side of the battlefield after selecting a manual skill."""
    box = (
        int(region.width * 0.72),
        int(region.height * 0.44),
        int(region.width * 0.08),
        int(region.height * 0.12),
    )
    return click_box_in_region(region, box)


def click_right_portal(region: WindowRegion) -> tuple[int, int]:
    """Click the blue >>> portal arrows on the right side of walk-out stages."""
    box = (
        int(region.width * 0.90),
        int(region.height * 0.55),
        int(region.width * 0.07),
        int(region.height * 0.08),
    )
    return click_box_in_region(region, box)


def _skill_slots(work_w: int) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Return skill slots (S3 rightmost -> S2 middle -> S1 leftmost) in BASE_HEIGHT space."""
    return [
        ("S3", (work_w - 150, 845, 132, 132)),
        ("S2", (work_w - 293, 845, 132, 132)),
        ("S1", (work_w - 436, 845, 132, 132)),
    ]


def _is_skill_on_cooldown(slot_img: np.ndarray, templates: dict[str, np.ndarray]) -> bool:
    tmpl = templates.get("cooldown_turns")
    if tmpl is None:
        return False
    return match_template(slot_img, tmpl, threshold=0.52) is not None


def _is_passive_s2(slot_img: np.ndarray, templates: dict[str, np.ndarray]) -> bool:
    tmpl = templates.get("passive_corner")
    if tmpl is None:
        return False
    return match_template(slot_img, tmpl, threshold=0.90) is not None


def _handle_battle(
    region: WindowRegion,
    work_screen: np.ndarray,
    scale: float,
    templates: dict[str, np.ndarray],
) -> Optional[str]:
    """Handle battle auto-toggle (if active & not spinning) or manual skills (if dimmed)."""
    a_tmpl = templates.get("auto_battle_icon")
    if a_tmpl is None:
        return None

    wh, ww = work_screen.shape[:2]
    roi_x = max(0, ww - 420)
    top_right = work_screen[0:110, roi_x:ww]
    m = match_template(top_right, a_tmpl, threshold=0.45)
    if m is None:
        return None

    ax, ay, aw, ah = m.box
    abs_a_box = (roi_x + ax, ay, aw, ah)
    a_patch1 = work_screen[ay : ay + ah, roi_x + ax : roi_x + ax + aw]
    p95 = float(np.percentile(cv2.cvtColor(a_patch1, cv2.COLOR_BGR2GRAY), 95))

    # Case 1: Auto-battle icon is bright/active -> check if spinning across 0.25s
    if p95 >= 180.0:
        time.sleep(0.25)
        screen2 = capture_region(region)
        work2, _ = _prepare_work_screen(screen2)
        if work2.shape[:2] == work_screen.shape[:2]:
            a_patch2 = work2[ay : ay + ah, roi_x + ax : roi_x + ax + aw]
            diff = float(cv2.absdiff(a_patch1, a_patch2).mean())
            if diff < 4.0:
                x, y = click_box_in_region(region, _scale_box(abs_a_box, scale))
                return f"enable_auto_battle (diff={diff:.2f}) -> ({x}, {y})"
        return None

    # Case 2: Auto-battle icon is dimmed -> manual-only fight; check if our turn (S1 visible)
    slots = _skill_slots(ww)
    _, (s1x, s1y, s1w, s1h) = slots[-1]
    if s1x < 0 or s1y + s1h > wh:
        return None
    s1_patch = work_screen[s1y : s1y + s1h, s1x : s1x + s1w]
    if float(np.percentile(cv2.cvtColor(s1_patch, cv2.COLOR_BGR2GRAY), 95)) < 185.0:
        return None

    for name, (sx, sy, sw, sh) in slots:
        patch = work_screen[sy : sy + sh, sx : sx + sw]
        if _is_skill_on_cooldown(patch, templates):
            continue
        if name == "S2" and _is_passive_s2(patch, templates):
            continue

        x, y = click_box_in_region(region, _scale_box((sx, sy, sw, sh), scale))
        time.sleep(random.uniform(0.30, 0.45))
        tx, ty = click_enemy_area(region)
        return f"manual_skill {name} -> ({x}, {y}), target -> ({tx}, {ty})"

    return None


def _prepare_work_screen(screen: np.ndarray) -> tuple[np.ndarray, float]:
    """Scale screen uniformly by height to match BASE_HEIGHT without aspect distortion."""
    sh, sw = screen.shape[:2]
    if sh == BASE_HEIGHT:
        return screen, 1.0
    scale = sh / BASE_HEIGHT
    work_w = max(1, int(round(sw / scale)))
    interp = cv2.INTER_AREA if sh > BASE_HEIGHT else cv2.INTER_LINEAR
    work_screen = cv2.resize(screen, (work_w, BASE_HEIGHT), interpolation=interp)
    return work_screen, scale


def _scale_box(
    box: tuple[int, int, int, int], scale: float
) -> tuple[int, int, int, int]:
    x, y, w, h = box
    return (
        int(round(x * scale)),
        int(round(y * scale)),
        max(1, int(round(w * scale))),
        max(1, int(round(h * scale))),
    )


def step_once(
    region: WindowRegion,
    screen: np.ndarray,
    templates: dict[str, np.ndarray],
    threshold: float,
) -> Optional[str]:
    """Check UI states by priority and perform one action if matched."""
    work_screen, scale = _prepare_work_screen(screen)

    def find(name: str, thr: float = threshold) -> Optional[MatchResult]:
        tmpl = templates.get(name)
        if tmpl is None:
            return None
        return match_template(work_screen, tmpl, threshold=thr)

    def click_scaled(m: MatchResult, hold_seconds: Optional[float] = None) -> tuple[int, int]:
        real_box = _scale_box(m.box, scale)
        return click_box_in_region(region, real_box, hold_seconds=hold_seconds)

    # 1. Popup: Tap to close (Story Clear / Received Reward / etc.)
    if m := find("tap_to_close", 0.80):
        x, y = click_scaled(m)
        return f"tap_to_close ({m.score:.2f}) -> ({x}, {y})"

    # 1b. Rank Up screen -> click anywhere on screen
    if m := find("rank_up", 0.78):
        x, y = click_clear_safe_area(region)
        return f"rank_up ({m.score:.2f}) -> click ({x}, {y})"

    # 2. Popup: Skip Story / Auto Assign -> Confirm (verified by prompt/header)
    if find("skip_story_prompt", 0.80) and (m := find("skip_confirm", 0.82)):
        x, y = click_scaled(m)
        return f"skip_confirm ({m.score:.2f}) -> ({x}, {y})"

    if find("auto_assign_header", 0.80) and (m := find("skip_confirm", 0.80)):
        x, y = click_scaled(m)
        return f"auto_assign_confirm ({m.score:.2f}) -> ({x}, {y})"

    # 3. Popup: Friend Request -> Cancel (verified by friend header)
    if find("friend_header", 0.80) and (m := find("friend_cancel", 0.82)):
        x, y = click_scaled(m)
        return f"friend_cancel ({m.score:.2f}) -> ({x}, {y})"

    # 4. Dialogue: Skip > (restricted to top-right corner) or Act banner
    if (skip_tmpl := templates.get("skip_btn")) is not None:
        wh, ww = work_screen.shape[:2]
        roi_x = max(0, ww - 220)
        top_right_skip = work_screen[0:100, roi_x:ww]
        if m := match_template(top_right_skip, skip_tmpl, threshold=0.72):
            mx, my, mw, mh = m.box
            real_box = _scale_box((roi_x + mx, my, mw, mh), scale)
            x, y = click_box_in_region(region, real_box)
            return f"skip_btn ({m.score:.2f}) -> ({x}, {y})"

    if m := find("act_banner", 0.78):
        x, y = click_center_safe_area(region)
        return f"act_banner ({m.score:.2f}) -> click ({x}, {y})"

    # 5. Cutscene anime: hold >>| if template provided
    if m := find("cutscene_skip", 0.80):
        x, y = click_scaled(m, hold_seconds=3.0)
        return f"cutscene_skip hold 3s ({m.score:.2f}) -> ({x}, {y})"

    # 6. Abyss Next Floor (must run before generic CLEAR), Battle CLEAR, or walk-out >>> portal
    if m := find("abyss_next_floor", 0.82):
        x, y = click_scaled(m)
        return f"abyss_next_floor ({m.score:.2f}) -> ({x}, {y})"

    if m := find("clear_logo", 0.78):
        x, y = click_clear_safe_area(region)
        return f"clear_logo ({m.score:.2f}) -> click ({x}, {y})"

    if m := find("clear_logo_single", 0.78):
        x, y = click_clear_safe_area(region)
        return f"clear_logo_single ({m.score:.2f}) -> click ({x}, {y})"

    if m := find("walk_leave_lobby", 0.82):
        x, y = click_right_portal(region)
        return f"walk_portal ({m.score:.2f}) -> click ({x}, {y})"

    # 7. MVP screen -> Confirm >
    if m := find("mvp_confirm", 0.82):
        x, y = click_scaled(m)
        return f"mvp_confirm ({m.score:.2f}) -> ({x}, {y})"

    # 8. Team screen -> Start Quest or Side Story Start
    if m := find("start_quest", 0.82):
        x, y = click_scaled(m)
        return f"start_quest ({m.score:.2f}) -> ({x}, {y})"

    if m := find("side_start", 0.82):
        x, y = click_scaled(m)
        return f"side_start ({m.score:.2f}) -> ({x}, {y})"

    # 9. Supporter screen -> Select Team >
    if m := find("select_team", 0.82):
        x, y = click_scaled(m)
        return f"select_team ({m.score:.2f}) -> ({x}, {y})"

    # 10. Episode / Side Story screen -> Ready / View Story / View
    if m := find("ready", 0.84):
        x, y = click_scaled(m)
        return f"ready ({m.score:.2f}) -> ({x}, {y})"

    if m := find("side_ready", 0.82):
        x, y = click_scaled(m)
        return f"side_ready ({m.score:.2f}) -> ({x}, {y})"

    if m := find("view_story", 0.82):
        x, y = click_scaled(m)
        return f"view_story ({m.score:.2f}) -> ({x}, {y})"

    if m := find("side_view", 0.82):
        x, y = click_scaled(m)
        return f"side_view ({m.score:.2f}) -> ({x}, {y})"

    # 11. In-battle: enable Auto if not spinning, or cast manual skills if Auto is dimmed
    if battle_action := _handle_battle(region, work_screen, scale, templates):
        return battle_action

    return None


def get_top_scores(
    screen: np.ndarray, templates: dict[str, np.ndarray]
) -> list[tuple[str, float]]:
    work_screen, _ = _prepare_work_screen(screen)
    wh, ww = work_screen.shape[:2]

    scores: list[tuple[str, float]] = []
    for name, tmpl in templates.items():
        th, tw = tmpl.shape[:2]
        if th <= wh and tw <= ww:
            res = cv2.matchTemplate(work_screen, tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            scores.append((name, float(max_val)))
    scores.sort(key=lambda item: item[1], reverse=True)
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description="Epic Seven Steam background auto-stage.")
    parser.add_argument(
        "--no-resize",
        action="store_true",
        help="Do not automatically resize the game window to 1280x720.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print capture brightness and top template match scores when idle.",
    )
    args = parser.parse_args()

    enable_dpi_awareness()
    templates = load_templates(Path("templates"))
    if not templates:
        print("[ERROR] templates/ is empty. Run capture_helper.py and crop_helper.py first.")
        return

    print(f"[INFO] Loaded {len(templates)} templates: {', '.join(sorted(templates.keys()))}")
    print("[INFO] Hotkeys: F8 = Pause / Resume | F10 = Exit")

    paused = False
    f8_was_down = False
    resized_once = False

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

        if not resized_once and not args.no_resize:
            resize_game_window(region.hwnd, target_width=1280, client_aspect=16 / 9)
            region = find_game_window("Epic Seven") or region
            print(f"[INFO] Resized game client to {region.width}x{region.height}")
            resized_once = True

        screen = capture_region(region)
        action = step_once(region, screen, templates, threshold=0.82)
        if action:
            print(f"[CLICK] {action}")
            is_popup = action.startswith(
                ("tap_to_close", "skip_confirm", "auto_assign_confirm", "friend_cancel")
            )
            delay = random.uniform(1.15, 1.50) if is_popup else random.uniform(0.75, 1.25)
            time.sleep(delay)
        else:
            if args.debug:
                top3 = ", ".join(f"{n}={s:.3f}" for n, s in get_top_scores(screen, templates)[:3])
                print(
                    f"[DEBUG] size={region.width}x{region.height} "
                    f"mean={screen.mean():.1f} | top: {top3}"
                )
            time.sleep(random.uniform(0.45, 0.70))


if __name__ == "__main__":
    main()
