# NTE Auto-Fisher

A simple, lightweight Python pixel-bot for automated fishing in NTE.
Built with Python, OpenCV, MSS, PyDirectInput, Pillow, and Tkinter.

## Highlights

* **Lightweight Tabbed GUI:** Simple interface with a dedicated control center and a live settings panel.
* **In-App Calibration:** No more editing code! Use sliders in the "Settings" tab to adjust the screen capture region on the fly.
* **Live Vision Preview:** See exactly what the bot sees directly inside the app to perfectly align your capture box.
* **Smart CPU Usage:** Idles at near 0% CPU while waiting for a fish, but ramps up to maximum speed during the minigame for zero input lag.
* **Hardware Inputs:** `PyDirectInput` sends reliable, game-friendly keystrokes.
* **Emergency Stop:** Global **F8** kill switch halts the bot instantly.

## Getting Started

### Option 1: Prebuilt Executable

1. Download the latest `.exe` from [Releases](../../releases).
2. Run it as **Administrator** so simulated inputs can reach the game.
3. Configure your capture area in the **Settings** tab (Default resolution is 16x9).
   Settings Example:
   <img width="400" height="205" alt="image" src="https://github.com/user-attachments/assets/3c26fd4c-e371-4d88-a806-46ee71b84e86" />

   *Try to keep the height boxes tight to prevent trees from interfering with the bot's vision during Minigame*
5. Go to the **Main** tab, click "START BOT," and tab back into NTE. Press F8 to stop at any time.

### Option 2: Run From Source

```bash
git clone [https://github.com/YourUsername/NTE-Fisher.git](https://github.com/YourUsername/NTE-Fisher.git)
cd NTE-Fisher
pip install opencv-python numpy mss pydirectinput keyboard Pillow
```

Launch the bot:
```bash
python main.py
```

## Configuration

Setting up the bot is now entirely visual:
1. Open the **Settings** tab in the bot interface.
2. Adjust the `Top`, `Left`, `Width`, and `Height` sliders.
3. Watch the **Live Vision Preview** box at the bottom. Adjust the sliders until the preview perfectly outlines the fishing minigame bar in your game. 

## Notes

* **Run as Admin:** Always run your terminal or the `.exe` as an Administrator on Windows, otherwise `pydirectinput` will be blocked by the game.
* **Window Mode:** Borderless window or windowed fullscreen provides the most reliable screen capture behavior.
* **Disclaimer:** Automating gameplay violates the TOS of most games. This is a basic memory-safe pixel bot, but use it entirely at your own risk.
