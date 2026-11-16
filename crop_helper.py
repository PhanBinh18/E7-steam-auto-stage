"""Interactive template cropper for screenshots/*.png -> templates/*.png."""

from __future__ import annotations

from pathlib import Path
import cv2

TEMPLATE_GUIDE = [
    ("tap_to_close", "'Tap to close' label (Story Clear / Received Reward popups)"),
    ("rank_up", "'Energy for Ranking up' text on the Rank Up screen"),
    ("skip_story_prompt", "'Are you sure you want to skip the story?' prompt text"),
    ("auto_assign_header", "'Auto Assign' popup title"),
    ("skip_confirm", "Blue 'Confirm' button in the Skip Story / Auto Assign popup"),
    ("friend_header", "'Friend' title (or 'Would you like to send a friend request?')"),
    ("friend_cancel", "'Cancel' button in the Friend popup"),
    ("skip_btn", "'Skip >' button at the top-right"),
    ("act_banner", "Top gold ornament of the Side Story Act banner"),
    ("cutscene_skip", "(Optional) Circular '>>|' icon during animated cutscenes"),
    ("clear_logo", "'CLEAR' text after winning a stage"),
    ("walk_leave_lobby", "'Leave' + 'Lobby' buttons on walk-out portal screens"),
    ("mvp_confirm", "Green 'Confirm >' button on the MVP screen"),
    ("start_quest", "'Start Quest' button"),
    ("side_start", "'Start' button on Side Story team screen"),
    ("select_team", "'Select Team >' button"),
    ("ready", "'Ready' button"),
    ("side_ready", "'Ready' button on Side Story"),
    ("view_story", "'View Story' button on story-only stages"),
    ("side_view", "'View' button on Side Story"),
    ("auto_battle_icon", "Top-right Auto-battle 'A' icon"),
    ("cooldown_turns", "'turn(s)' text on a skill cooldown"),
    ("passive_corner", "Top-left notched corner of a passive S2 skill"),
]


def main() -> None:
    shots_dir = Path("screenshots")
    tmpl_dir = Path("templates")
    tmpl_dir.mkdir(exist_ok=True)

    shots = sorted(shots_dir.glob("*.png"))
    if not shots:
        print("No images found in screenshots/. Run capture_helper.py first.")
        return

    print("=== Captured Screenshots ===")
    for i, p in enumerate(shots, 1):
        print(f"  {i}. {p.name}")

    print("\n=== Template Names ===")
    for i, (name, desc) in enumerate(TEMPLATE_GUIDE, 1):
        exists = "[EXISTS]" if (tmpl_dir / f"{name}.png").exists() else "[MISSING]"
        print(f"  {i:2d}. {name:18s} {exists} - {desc}")

    while True:
        choice = input("\nSelect screenshot number (or 'q' to quit): ").strip().lower()
        if choice == "q":
            break
        if not choice.isdigit() or not (1 <= int(choice) <= len(shots)):
            print("Invalid screenshot number.")
            continue

        img_path = shots[int(choice) - 1]
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"Failed to read image: {img_path}")
            continue

        t_choice = input("Select template number to crop from this screenshot: ").strip()
        if not t_choice.isdigit() or not (1 <= int(t_choice) <= len(TEMPLATE_GUIDE)):
            print("Invalid template number.")
            continue

        tmpl_name, _ = TEMPLATE_GUIDE[int(t_choice) - 1]
        print("Drag to select the button region -> Press ENTER/SPACE to save, or ESC to cancel.")
        roi = cv2.selectROI(f"Crop: {tmpl_name}", img, showCrosshair=True, fromCenter=False)
        cv2.destroyAllWindows()

        x, y, w, h = [int(v) for v in roi]
        if w > 0 and h > 0:
            crop = img[y : y + h, x : x + w]
            out_path = tmpl_dir / f"{tmpl_name}.png"
            cv2.imwrite(str(out_path), crop)
            print(f"[SAVED] {out_path} ({w}x{h})")
        else:
            print("Crop cancelled.")


if __name__ == "__main__":
    main()
