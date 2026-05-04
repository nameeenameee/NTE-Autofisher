import cv2
import numpy as np
import mss
import pydirectinput
import time
import keyboard
import tkinter as tk
from tkinter import ttk
import threading
from PIL import Image, ImageTk

# --- CONFIGURATION ---
DEFAULT_REGION = {"top": 50, "left": 610, "width": 710, "height": 40}

YELLOW_LOWER = np.array([20, 150, 150]) 
YELLOW_UPPER = np.array([40, 255, 255])
SAFEZONE_LOWER = np.array([80, 150, 150]) 
SAFEZONE_UPPER = np.array([100, 255, 255])

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
        self.root.title("NTE Fisher v2.1")
        self.root.geometry("400x350")
        self.root.attributes('-topmost', True) 
        
        self.bot_running = False
        self.bot_thread = None

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both')

        self.main_tab = tk.Frame(self.notebook)
        self.settings_tab = tk.Frame(self.notebook)

        self.notebook.add(self.main_tab, text="Main")
        self.notebook.add(self.settings_tab, text="Settings")

        self.setup_main_tab()
        self.setup_settings_tab()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.sct = mss.MSS()
        self.root.after(100, self.update_preview_loop)

    def setup_main_tab(self):
        self.status_label = tk.Label(self.main_tab, text="Status: IDLE", font=("Helvetica", 14, "bold"), fg="grey")
        self.status_label.pack(pady=30)

        self.start_btn = tk.Button(self.main_tab, text="START BOT", bg="green", fg="white", font=("Helvetica", 12, "bold"), command=self.start_bot)
        self.start_btn.pack(fill=tk.X, padx=40, pady=5)

        self.stop_btn = tk.Button(self.main_tab, text="STOP BOT (or F8)", bg="red", fg="white", font=("Helvetica", 12, "bold"), command=self.stop_bot, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, padx=40, pady=5)

    def setup_settings_tab(self):
        self.region_vars = {
            "top": tk.IntVar(value=DEFAULT_REGION["top"]),
            "left": tk.IntVar(value=DEFAULT_REGION["left"]),
            "width": tk.IntVar(value=DEFAULT_REGION["width"]),
            "height": tk.IntVar(value=DEFAULT_REGION["height"])
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
        preview_lbl.pack(pady=(10, 0))

        self.preview_canvas = tk.Label(self.settings_tab, bg="black", text="Loading...", fg="white")
        self.preview_canvas.pack(pady=5, padx=10, expand=True, fill=tk.BOTH)

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
                img_bgra = np.array(self.sct.grab(region))
                
                target_width = 360
                aspect_ratio = region["height"] / region["width"]
                target_height = max(10, int(target_width * aspect_ratio))
                
                # OPTIMIZATION 2: Use OpenCV for resizing instead of PIL Lanczos (Much faster)
                resized_bgra = cv2.resize(img_bgra, (target_width, target_height), interpolation=cv2.INTER_NEAREST)
                img_rgb = cv2.cvtColor(resized_bgra, cv2.COLOR_BGRA2RGB)
                
                pil_img = Image.fromarray(img_rgb)
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
        # 1. Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
                    
        # 2. Calculate the exact center
        center_x = screen_width // 2
        center_y = screen_height // 2
                    
        # 3. Teleport the mouse
        pydirectinput.moveTo(center_x, center_y)

    def bot_loop(self):
        state = "BEFORE_FISHING"
        sct = mss.mss()
        last_f_press = 0
        frames_lost = 0
        
        try:
            while self.bot_running:
                if keyboard.is_pressed('f8'): 
                    self.root.after(0, self.stop_bot)
                    break

                region = self.get_current_region()
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
                            state = "REWARD"

                elif state == "REWARD":
                    if self.smart_sleep(2.0): break
                    
                    self.move_cursor()
                    time.sleep(1)
                    pydirectinput.keyDown('escape')
                    pydirectinput.keyUp('escape')
                    
                    if self.smart_sleep(2.0): break
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