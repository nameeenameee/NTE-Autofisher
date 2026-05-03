import cv2
import numpy as np
import mss
import pydirectinput
import time
import keyboard
import tkinter as tk
import threading

# --- CONFIGURATION ---
BAR_REGION = {"top": 50, "left": 610, "width": 710, "height": 40}

# STRICTOR COLORS: High Saturation and Value to ignore sky/water and only see neon UI
YELLOW_LOWER = np.array([20, 150, 150]) 
YELLOW_UPPER = np.array([40, 255, 255])
SAFEZONE_LOWER = np.array([80, 150, 150]) 
SAFEZONE_UPPER = np.array([100, 255, 255])

DEADZONE_PIXELS = 10 
DEBUG_MODE = False 
pydirectinput.PAUSE = 0

def get_positions(sct):
    img_bgra = np.array(sct.grab(BAR_REGION))
    img_bgr = img_bgra[:, :, :3]

    hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    mask_yellow = cv2.inRange(hsv_img, YELLOW_LOWER, YELLOW_UPPER)
    mask_safezone = cv2.inRange(hsv_img, SAFEZONE_LOWER, SAFEZONE_UPPER)

    # LOWERED: 50 is small enough to see the thin cursor, but big enough to ignore 1-pixel noise
    MIN_PIXEL_AREA = 50 

    cursor_x = None
    M_yellow = cv2.moments(mask_yellow)
    if M_yellow["m00"] > MIN_PIXEL_AREA:
        cursor_x = int(M_yellow["m10"] / M_yellow["m00"])

    safezone_x = None
    M_safe = cv2.moments(mask_safezone)
    if M_safe["m00"] > MIN_PIXEL_AREA:
        safezone_x = int(M_safe["m10"] / M_safe["m00"])

    debug_img = img_bgr.copy()
    if cursor_x:
        cv2.line(debug_img, (cursor_x, 0), (cursor_x, 40), (0, 255, 255), 2)
    if safezone_x:
        cv2.line(debug_img, (safezone_x, 0), (safezone_x, 40), (255, 255, 0), 2)

    return cursor_x, safezone_x, debug_img

def release_keys():
    pydirectinput.keyUp('a')
    pydirectinput.keyUp('d')

class FishingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NTE Fisher")
        self.root.geometry("250x150")
        self.root.attributes('-topmost', True) 
        
        self.bot_running = False
        self.bot_thread = None

        self.status_label = tk.Label(root, text="Status: IDLE", font=("Helvetica", 12, "bold"), fg="grey")
        self.status_label.pack(pady=10)

        self.start_btn = tk.Button(root, text="START BOT", bg="green", fg="white", font=("Helvetica", 10, "bold"), command=self.start_bot)
        self.start_btn.pack(fill=tk.X, padx=20, pady=5)

        # CHANGED KILL SWITCH TO F8
        self.stop_btn = tk.Button(root, text="STOP BOT (or press F8)", bg="red", fg="white", font=("Helvetica", 10, "bold"), command=self.stop_bot, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, padx=20, pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def start_bot(self):
        if not self.bot_running:
            self.bot_running = True
            self.update_ui_state(running=True)
            self.bot_thread = threading.Thread(target=self.bot_loop, daemon=True)
            self.bot_thread.start()

    def stop_bot(self):
        self.bot_running = False
        self.update_ui_state(running=False)

    def update_ui_state(self, running):
        if running:
            self.status_label.config(text="Status: RUNNING", fg="green")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
        else:
            self.status_label.config(text="Status: IDLE", fg="grey")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def smart_sleep(self, duration):
        end_time = time.time() + duration
        while time.time() < end_time:
            if not self.bot_running or keyboard.is_pressed('f8'): # Changed to f8
                self.bot_running = False
                return True 
            time.sleep(0.05)
        return False

    def bot_loop(self):
        state = "BEFORE_FISHING"
        sct = mss.MSS()
        last_f_press = 0
        frames_lost = 0
        
        try:
            while self.bot_running:
                if keyboard.is_pressed('f8'): # Changed to f8
                    print("F8 pressed. Stopping bot.")
                    self.root.after(0, self.stop_bot)
                    break

                c_x, s_x, debug_img = get_positions(sct)
                
                if DEBUG_MODE:
                    cv2.imshow("Bot Vision", debug_img)
                    cv2.waitKey(1)

                if state == "BEFORE_FISHING":
                    if time.time() - last_f_press > 1.5:
                        print("Pressing F...")
                        pydirectinput.press('f')
                        last_f_press = time.time()
                    
                    if s_x is not None and c_x is not None:
                        print("Minigame detected!")
                        state = "MINIGAME"
                        frames_lost = 0

                elif state == "MINIGAME":
                    if c_x is not None and s_x is not None:
                        frames_lost = 0
                        distance = abs(c_x - s_x)
                        
                        if c_x < (s_x - DEADZONE_PIXELS):
                            pydirectinput.keyUp('a')
                            pydirectinput.keyDown('d')
                            
                            # ANTI-MOMENTUM: If we are getting close, release the key immediately
                            # to 'tap' it instead of holding it down.
                            if distance < 40: 
                                time.sleep(0.01)
                                pydirectinput.keyUp('d')
                                
                        elif c_x > (s_x + DEADZONE_PIXELS):
                            pydirectinput.keyUp('d')
                            pydirectinput.keyDown('a')
                            
                            # ANTI-MOMENTUM
                            if distance < 40:
                                time.sleep(0.01)
                                pydirectinput.keyUp('a')
                                
                        else:
                            release_keys()
                    else:
                        frames_lost += 1
                        if frames_lost > 10: 
                            release_keys()
                            print("Bar lost. Transitioning to Reward.")
                            state = "REWARD"

                elif state == "REWARD":
                    print("Collecting loot...")
                    if self.smart_sleep(2.0): break
                    
                    # Double click just to ensure the game registers it to close the UI
                    pydirectinput.click()
                    time.sleep(0.2)
                    pydirectinput.click()
                    
                    if self.smart_sleep(2.0): break
                    state = "BEFORE_FISHING"
                    last_f_press = time.time()
                    
        finally:
            release_keys()
            if DEBUG_MODE:
                cv2.destroyAllWindows()
            print("Bot thread cleanly stopped.")
            self.root.after(0, lambda: self.update_ui_state(False))

    def on_closing(self):
        self.bot_running = False
        release_keys()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FishingBotGUI(root)
    root.mainloop()