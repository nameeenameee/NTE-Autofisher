 # NTE Auto-Fisher



A simple, lightweight Python pixel-bot for automated fishing in NTE.

Built with Python, OpenCV, MSS, PyDirectInput, and Tkinter.



 ## Highlights



 *  Lightweight GUI: Simple Tkinter interface to start and stop the bot.

 *  Vision-Based: Uses OpenCV and HSV color masking to track the fishing safe zone and cursor.

 *  Hardware Inputs: `PyDirectInput` sends reliable, game-friendly keystrokes.

 *  Emergency Stop: Press `F8` to kill the bot

 *  Visual Debugging: Built-in OpenCV window to help calibrate screen capture and masks.



 ## Getting Started



 ### Option 1: Prebuilt Executable



1 . Download the latest `.exe` from  [Releases](../../releases).

2 . Run it as  Administrator so simulated inputs can reach the game.

3 . Click "START BOT" and tab back into NTE. Press F8 to stop at any time.



 ### Option 2: Run From Source



```bash

git clone  [https://github.com/YourUsername/NTE-Fisher.git](https://github.com/YourUsername/NTE-Fisher.git)

cd NTE-Fisher

pip install opencv-python numpy mss pydirectinput keyboard

```



Launch the bot:

```bash

python main.py

```



 ## Configuration



If the bot isn't tracking properly, open `main.py` and adjust the configuration block at the top:

 * `BAR _REGION`: Update the `top`, `left`, `width`, and `height` coordinates to match your specific monitor resolution and UI scale.

 * Keep `DEBUG _MODE = True` while configuring. This opens a visual window showing exactly what the bot sees, allowing you to easily align the bounding box with the minigame bar.



 ## Notes



 * Run as Admin: Always run your terminal or the `.exe` as an Administrator on Windows, otherwise `pydirectinput` will be blocked by the game.

 * Window Mode: Borderless window or windowed fullscreen at resolution 1920x1080 provides the most reliable screen capture behavior.

 * Disclaimer: Automating gameplay violates the TOS of most games. This is a basic memory-safe pixel bot, but use it entirely at your own risk.

