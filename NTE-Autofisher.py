import cv2
import numpy as np
import mss
import pydirectinput
import time
import keyboard
import tkinter as tk
from tkinter import ttk
import threading
import ctypes # NEW: Added to bypass Windows display scaling
from PIL import Image, ImageTk
from collections import deque

# --- FIX WINDOWS SCALING ---
# This forces Windows to give us the TRUE pixel resolution of the monitor
# instead of a zoomed-in version if the user has 125% or 150% scaling enabled.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- CONFIGURATION ---
# Note: DEFAULT_REGION has been removed here. It is now calculated dynamically inside the GUI!

YELLOW_LOWER = np.array([20, 150, 150]) 
YELLOW_UPPER = np.array([40, 255, 255])
SAFEZONE_LOWER = np.array([80, 150, 150]) 
SAFEZONE_UPPER = np.array([100, 255, 255])

TINT_THRESHOLD = 50
TINT_DROP_FACTOR = 0.7

DEADZONE_PIXELS = 15 
pydirectinput.PAUSE = 0 

def get_positions(sct, region):
    img_bgra = np.array(sct.grab(region))
    
    # We MUST slice off the Alpha channel before converting to HSV
    img_bgr = img_bgra[:, :, :3] 
    hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    mask_yellow = cv2.inRange(hsv_img, YELLOW_LOWER, YELLOW_UPPER)
    mask_safezone = cv2.inRange(hsv_img, SAFEZONE_LOWER, SAFEZONE_UPPER)

    MIN_PIXEL_AREA = 50 

    cursor_x = None
    M_yellow = cv2.moments(mask_yellow)
    if M_yellow["m00"] > MIN_PIXEL_AREA:
        cursor_x = int(M_yellow["m10"] / M_yellow["m00"])

    safezone_x = None
    M_safe = cv2.moments(mask_safezone)
    if M_safe["m00"] > MIN_PIXEL_AREA:
        safezone_x = int(M_safe["m10"] / M_safe["m00"])

    return cursor_x, safezone_x

def release_keys():
    pydirectinput.keyUp('a')
    pydirectinput.keyUp('d')

class FishingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NTE Fisher v3.0")
        self.root.geometry("400x420") 
        self.root.attributes('-topmost', True) 
        
        self.bot_running = False
        self.bot_thread = None

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both')

        self.main_tab = tk.Frame(self.notebook)
        self.settings_tab = tk.Frame(self.notebook)

        self.notebook.add(self.main_tab, text="Main")
        self.notebook.add(self.settings_tab, text="Settings")

        # Dynamically calculate region BEFORE setting up tabs
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.dynamic_region = self.calculate_dynamic_region(screen_w, screen_h)

        self.setup_main_tab()
        self.setup_settings_tab()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.sct = mss.MSS()
        self.root.after(100, self.update_preview_loop)

    def calculate_dynamic_region(self, screen_w, screen_h):
        # 1. Base the UI scale strictly off the screen height (assuming 1080p is scale 1.0)
        scale_factor = screen_h / 1080.0
        
        # 2. We pad the capture box to be slightly larger than the raw 1080p values.
        # This guarantees it catches the bar even if 16:10 shifts it vertically by a few pixels.
        # Since our bot relies on strict HSV color filters, grabbing extra background is 100% safe!
        base_w = 710  # Padded wider than original 710
        base_h = 30   # Padded taller than original 22
        base_top = 60 # Started slightly higher than original 64
        
        calc_w = int(base_w * scale_factor)
        calc_h = int(base_h * scale_factor)
        calc_top = int(base_top * scale_factor)
        
        # 3. Perfectly center it horizontally on the screen
        calc_left = (screen_w // 2) - (calc_w // 2)
        
        return {"top": calc_top, "left": calc_left, "width": calc_w, "height": calc_h}

    def setup_main_tab(self):
        self.status_label = tk.Label(self.main_tab, text="Status: IDLE", font=("Helvetica", 14, "bold"), fg="grey")
        self.status_label.pack(pady=30)

        self.start_btn = tk.Button(self.main_tab, text="START BOT", bg="green", fg="white", font=("Helvetica", 12, "bold"), command=self.start_bot)
        self.start_btn.pack(fill=tk.X, padx=40, pady=5)

        self.stop_btn = tk.Button(self.main_tab, text="STOP BOT (or F8)", bg="red", fg="white", font=("Helvetica", 12, "bold"), command=self.stop_bot, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, padx=40, pady=5)

    def setup_settings_tab(self):
        # Load the dynamic values into the sliders
        self.region_vars = {
            "top": tk.IntVar(value=self.dynamic_region["top"]),
            "left": tk.IntVar(value=self.dynamic_region["left"]),
            "width": tk.IntVar(value=self.dynamic_region["width"]),
            "height": tk.IntVar(value=self.dynamic_region["height"])
        }

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        limits = {
            "top": screen_height,
            "left": screen_width,
            "width": screen_width,
            "height": 500 
        }

        for key in ["top", "left", "width", "height"]:
            frame = tk.Frame(self.settings_tab)
            frame.pack(fill=tk.X, padx=10, pady=2)
            lbl = tk.Label(frame, text=key.capitalize(), width=6, anchor="w")
            lbl.pack(side=tk.LEFT)
            scale = tk.Scale(frame, from_=1, to=limits[key], orient=tk.HORIZONTAL, variable=self.region_vars[key])
            scale.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        preview_lbl = tk.Label(self.settings_tab, text="Live Vision Preview:", font=("Helvetica", 10, "bold"))
        preview_lbl.pack(pady=(5, 0))

        self.preview_canvas = tk.Label(self.settings_tab, bg="black", text="Loading...", fg="white")
        self.preview_canvas.pack(pady=5, padx=10, expand=True, fill=tk.BOTH)

        self.instruction_lbl = tk.Label(self.settings_tab, text="Make sure the fishing circles icons during minigame are in the blacked areas", font=("Helvetica", 8, "italic"))
        self.instruction_lbl.pack(pady=(0, 10))

    def get_current_region(self):
        return {
            "top": max(1, self.region_vars["top"].get()),
            "left": max(1, self.region_vars["left"].get()),
            "width": max(1, self.region_vars["width"].get()),
            "height": max(1, self.region_vars["height"].get())
        }

    def update_preview_loop(self):
        if self.notebook.index(self.notebook.select()) == 1: 
            region = self.get_current_region()
            
            try:
                screen_w = self.root.winfo_screenwidth()
                screen_h = self.root.winfo_screenheight()
                pad = 150
                
                grab_top = max(0, region["top"] - pad)
                grab_left = max(0, region["left"] - pad)
                grab_bottom = min(screen_h, region["top"] + region["height"] + pad)
                grab_right = min(screen_w, region["left"] + region["width"] + pad)
                
                grab_region = {
                    "top": grab_top,
                    "left": grab_left,
                    "width": grab_right - grab_left,
                    "height": grab_bottom - grab_top
                }
                
                inner_y1 = region["top"] - grab_top
                inner_x1 = region["left"] - grab_left
                inner_y2 = inner_y1 + region["height"]
                inner_x2 = inner_x1 + region["width"]

                img_bgra = np.array(self.sct.grab(grab_region))
                img_rgb = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2RGB)
                
                composite = (img_rgb * 0.4).astype(np.uint8)
                composite[inner_y1:inner_y2, inner_x1:inner_x2] = img_rgb[inner_y1:inner_y2, inner_x1:inner_x2]
                
                cv2.rectangle(composite, (inner_x1, inner_y1), (inner_x2, inner_y2), (0, 255, 0), 2)
                
                target_width = 360
                aspect_ratio = grab_region["height"] / grab_region["width"]
                target_height = max(10, int(target_width * aspect_ratio))
                
                resized = cv2.resize(composite, (target_width, target_height), interpolation=cv2.INTER_NEAREST)
                
                pil_img = Image.fromarray(resized)
                self.tk_image = ImageTk.PhotoImage(pil_img)
                self.preview_canvas.config(image=self.tk_image, text="")
            except Exception as e:
                self.preview_canvas.config(image='', text="Invalid Region")
        
        self.root.after(100, self.update_preview_loop)

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
            if not self.bot_running or keyboard.is_pressed('f8'): 
                self.bot_running = False
                return True 
            time.sleep(0.05)
        return False

    def move_cursor(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = screen_width // 2
        center_y = screen_height // 2
        pydirectinput.moveTo(center_x, center_y)

    def bot_loop(self):
        state = "BEFORE_FISHING"
        sct = mss.MSS()
        last_f_press = 0
        frames_lost = 0
        
        brightness_history = deque(maxlen=4)
        
        try:
            while self.bot_running:
                if keyboard.is_pressed('f8'): 
                    self.root.after(0, self.stop_bot)
                    break

                region = self.get_current_region()
                # 1. Grab current frame and calculate average brightness
                img_bgra = np.array(sct.grab(region))
                img_bgr = img_bgra[:, :, :3]
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                avg_brightness = np.mean(gray)
                
                # 2. Update history
                brightness_history.append(avg_brightness)
                
                # 3. Standard cursor/safezone detection
                c_x, s_x = get_positions(sct, region)

                if state == "BEFORE_FISHING":
                    self.move_cursor()
                    if time.time() - last_f_press > 1.5:
                        pydirectinput.click()
                        pydirectinput.press('f')
                        last_f_press = time.time()
                    
                    if s_x is not None and c_x is not None:
                        state = "MINIGAME"
                        frames_lost = 0
                    else:
                        time.sleep(0.05) 

                elif state == "MINIGAME":
                    if c_x is not None and s_x is not None:
                        frames_lost = 0
                        distance = abs(c_x - s_x)
                        
                        if c_x < (s_x - DEADZONE_PIXELS):
                            pydirectinput.keyUp('a')
                            pydirectinput.keyDown('d')
                            if distance < 40: 
                                time.sleep(0.01)
                                pydirectinput.keyUp('d')
                                
                        elif c_x > (s_x + DEADZONE_PIXELS):
                            pydirectinput.keyUp('d')
                            pydirectinput.keyDown('a')
                            if distance < 40:
                                time.sleep(0.01)
                                pydirectinput.keyUp('a')
                        else:
                            release_keys()
                                                    
                    else:
                        frames_lost += 1
                        if frames_lost > 10: 
                            release_keys()
                            
                            # Compare current frame to the one 3 frames ago (index 0)
                            if len(brightness_history) == 4:
                                baseline = brightness_history[0]
                                current = brightness_history[-1]
                                
                                # Condition: Screen is dark AND brightness dropped significantly compared to baseline
                                if current < TINT_THRESHOLD and current < (baseline * TINT_DROP_FACTOR):
                                    print(f"Reward detected! Brightness: {current:.1f} (Baseline: {baseline:.1f})")
                                    state = "REWARD"
                                else:
                                    print("Minigame failed (no tint detected). Retrying...")
                                    state = "BEFORE_FISHING"
                                    last_f_press = time.time() + 1.0 # Short delay before next cast
                            else:
                                state = "BEFORE_FISHING"

                elif state == "REWARD":
                    if self.smart_sleep(3.0): break
                    
                    self.move_cursor()
                    pydirectinput.press('escape')
                    
                    if self.smart_sleep(1.5): break
                    state = "BEFORE_FISHING"
                    last_f_press = time.time()
                    
        finally:
            release_keys()
            self.root.after(0, lambda: self.update_ui_state(False))

    def on_closing(self):
        self.bot_running = False
        release_keys()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FishingBotGUI(root)
    root.mainloop()