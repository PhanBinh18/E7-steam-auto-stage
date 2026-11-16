# Epic Seven Steam Auto Stage

A Python auto-clicker for clearing **Epic Seven (Steam / Windows)** story and episode stages in the background.

## Features
- **True Background Operation:**
  - Captures the game window via Win32 `PrintWindow` (works even when other windows cover the game, as long as the game window is **not minimized**).
  - Sends background mouse clicks via `PostMessage` (`WM_LBUTTONDOWN` / `WM_LBUTTONUP`) without moving your physical cursor or stealing focus from your active window.
- **Priority-Based State Machine:** Automatically handles the full loop:
  `Ready` → `Select Team` → `Start Quest` → dialogue skip (`Skip >` + `Confirm`) → battle wait → `CLEAR` → dismiss `Friend` prompt (`Cancel`) → `MVP Confirm` → close `Tap to close` popups (`Story Clear`, `Received Reward`).
- **Multi-Monitor & Auto-Resize / Scaling:** Enables Per-Monitor DPI Awareness, automatically resizes and centers the game window to **1280x720** (pass `--no-resize` to disable), and scales templates cleanly across resolutions.
- **Hotkeys:** `F8` to Pause / Resume, `F10` to Exit.

## Installation
Requirements: Windows + Python 3.10+.

```powershell
pip install -r requirements.txt
```

## Usage
1. Launch **Epic Seven** on Steam in **Windowed** mode (maximizing the window is recommended).
2. Make sure **AUTO** battle is enabled in-game.
3. Run the script:
   ```powershell
   python auto_stage.py
   ```
   *(Optional: `python auto_stage.py --no-resize` to keep your current window size.)*
4. Do not minimize the game window (you can cover it with other windows).
5. Press **`F8`** to pause/resume, or **`F10`** to exit.

## Re-cropping Templates (Optional)
If you play in a non-English language, an ultrawide aspect ratio (e.g. 21:9), or want to add extra buttons:
1. Run `python capture_helper.py`, play through one stage manually, and press **`F9`** on each screen (`F10` to exit).
2. Run `python crop_helper.py` to drag-select and save the button templates into `templates/`.

## Diagnostic Tools
- `python test_click.py`: Verify `Epic Seven` window detection, capture, and foreground click.
- `python test_background_click.py`: Verify background `PostMessage` clicking.
- `python test_printwindow.py`: Verify `PrintWindow` capture while covered by another window.
