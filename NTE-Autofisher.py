import cv2
import numpy as np
import mss
import pydirectinput
import time
import keyboard
import tkinter as tk
from tkinter import ttk
import threading
import ctypes 
import math # NEW: Added for easing functions
from PIL import Image, ImageTk
from collections import deque

# --- FIX WINDOWS SCALING ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- CONFIGURATION ---
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

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.dynamic_region = self.calculate_dynamic_region(screen_w, screen_h)

        self.setup_main_tab()
        self.setup_settings_tab()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.sct = mss.MSS()
        self.root.after(100, self.update_preview_loop)

    def calculate_dynamic_region(self, screen_w, screen_h):
        scale_factor = screen_h / 1080.0
        base_w = 710  
        base_h = 30   
        base_top = 60 
        
        calc_w = int(base_w * scale_factor)
        calc_h = int(base_h * scale_factor)
        calc_top = int(base_top * scale_factor)
        
        calc_left = (screen_w // 2) - (calc_w // 2)
        
        return {"top": calc_top, "left": calc_left, "width": calc_w, "height": calc_h}

    def setup_main_tab(self):
        self.status_label = tk.Label(self.main_tab, text="Status: IDLE", font=("Helvetica", 14, "bold"), fg="grey")
        self.status_label.pack(pady=20) # Reduced padding to fit the new buttons

        self.do_selling = tk.BooleanVar(value=True) # Defaulting to True
        self.do_buying = tk.BooleanVar(value=False)

        self.sell_check = tk.Checkbutton(self.main_tab, text="Enable Auto-Selling", variable=self.do_selling, font=("Helvetica", 10))
        self.sell_check.pack(pady=2)

        self.buy_check = tk.Checkbutton(self.main_tab, text="Enable Auto-Buying", variable=self.do_buying, font=("Helvetica", 10))
        self.buy_check.pack(pady=(2, 10))

        self.start_btn = tk.Button(self.main_tab, text="START BOT", bg="green", fg="white", font=("Helvetica", 12, "bold"), command=self.start_bot)
        self.start_btn.pack(fill=tk.X, padx=40, pady=5)

        self.stop_btn = tk.Button(self.main_tab, text="STOP BOT (or F8)", bg="red", fg="white", font=("Helvetica", 12, "bold"), command=self.stop_bot, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, padx=40, pady=5)

    def setup_settings_tab(self):
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

    # --- NEW: Humanized Mouse Movement ---
    def human_move(self, dest_x, dest_y, duration=0.6):
        """Moves the mouse to coordinates using a Cubic Ease-In-Out curve."""
        start_x, start_y = pydirectinput.position()
        steps = int(duration * 60) # Assume ~60 fps update rate
        
        for i in range(1, steps + 1):
            if not self.bot_running: return
            
            t = i / steps
            # Cubic Ease-In-Out Formula
            ease_t = 4 * t**3 if t < 0.5 else 1 - math.pow(-2 * t + 2, 3) / 2
            
            cur_x = int(start_x + (dest_x - start_x) * ease_t)
            cur_y = int(start_y + (dest_y - start_y) * ease_t)
            
            pydirectinput.moveTo(cur_x, cur_y)
            time.sleep(duration / steps)

    # --- NEW: Selling Template ---
    def execute_selling_phase(self):
        """Executes the sell rotation template. Fill the coordinates below."""
        print("Executing selling phase...")
        
        pydirectinput.press('q')
        if self.smart_sleep(1.0): return # Wait for menu
        
        # 4 Clicks Template
        coords_1 = [(158, 385), (1049, 982), (1086, 707), (1848, 71)] # TODO: Set these 4 coordinates
        for x, y in coords_1:
            self.human_move(x, y)
            pydirectinput.click()
            if self.smart_sleep(0.2): return
        self.smart_sleep(5)
        pydirectinput.click()

    def execute_buying_phase(self):
        print("Executing buying phase...")
        self.smart_sleep(0.5)
        pydirectinput.press('r')
        if self.smart_sleep(0.5): return

        # Move & Click once
        # TODO: Set coordinate
        self.human_move(607, 254) 
        pydirectinput.click()
        if self.smart_sleep(0.2): return

        # Loop 6 times: move->click, move->click, move->click, click
        coords_loop = [(1823, 941), (1773, 1027), (1225, 709)] # TODO: Set the 3 looping coordinates
        for _ in range(6):
            if not self.bot_running: break

            # Step 1
            self.human_move(coords_loop[0][0], coords_loop[0][1])
            pydirectinput.click()
            if _ > 0:
                self.smart_sleep(0.5)
                pydirectinput.click()
                self.smart_sleep(0.5)
                pydirectinput.click()
            
            # Step 2
            self.human_move(coords_loop[1][0], coords_loop[1][1])
            pydirectinput.click()
            if self.smart_sleep(0.5): return
            
            # Step 3
            self.human_move(coords_loop[2][0], coords_loop[2][1])
            pydirectinput.click()
            if self.smart_sleep(2): return
            

        # Final Move and Click
        # TODO: Set final coordinate
        self.human_move(1848, 71)
        pydirectinput.click()
        self.smart_sleep(0.5)
        pydirectinput.click()
        if self.smart_sleep(0.5): return

    def bot_loop(self):
        state = "BEFORE_FISHING"
        sct = mss.MSS()
        last_f_press = 0
        frames_lost = 0
        wait_start_time = time.time() # NEW: Track stuck time
        
        brightness_history = deque(maxlen=4)
        
        try:
            while self.bot_running:
                if keyboard.is_pressed('f8'): 
                    self.root.after(0, self.stop_bot)
                    break

                region = self.get_current_region()
                img_bgra = np.array(sct.grab(region))
                img_bgr = img_bgra[:, :, :3]
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                avg_brightness = np.mean(gray)
                
                brightness_history.append(avg_brightness)
                c_x, s_x = get_positions(sct, region)

                if state == "BEFORE_FISHING":
                    self.move_cursor()
                    
                    # NEW: Timeout check with Toggles
                    if time.time() - wait_start_time > 40:
                        if self.do_selling.get() or self.do_buying.get():
                            print("Stuck waiting for over 40 seconds. Initiating trade phases.")
                            state = "TRADING"
                        else:
                            print("Stuck waiting... retrying fishing since trading is toggled off.")
                            last_f_press = time.time() - 2 # Force a new 'f' press immediately
                            wait_start_time = time.time() # Reset wait timer
                        continue

                    if time.time() - last_f_press > 1.5:
                        pydirectinput.click()
                        pydirectinput.press('f')
                        last_f_press = time.time()
                    
                    if s_x is not None and c_x is not None:
                        state = "MINIGAME"
                        frames_lost = 0
                        wait_start_time = time.time() # Reset wait timer
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
                            
                            if len(brightness_history) == 4:
                                baseline = brightness_history[0]
                                current = brightness_history[-1]
                                
                                if current < TINT_THRESHOLD and current < (baseline * TINT_DROP_FACTOR):
                                    print(f"Reward detected! Brightness: {current:.1f} (Baseline: {baseline:.1f})")
                                    state = "REWARD"
                                else:
                                    print("Minigame failed (no tint detected). Retrying...")
                                    state = "BEFORE_FISHING"
                                    last_f_press = time.time() + 1.0 
                                    wait_start_time = time.time() # Reset wait timer
                            else:
                                state = "BEFORE_FISHING"
                                wait_start_time = time.time() # Reset wait timer

                elif state == "REWARD":
                    if self.smart_sleep(3.0): break
                    
                    self.move_cursor()
                    pydirectinput.press('escape')
                    
                    if self.smart_sleep(1.5): break
                    state = "BEFORE_FISHING"
                    last_f_press = time.time()
                    wait_start_time = time.time() # Reset wait timer

                # --- NEW: Trading State (Handles Selling and Buying) ---
                elif state == "TRADING":
                    # Check the toggle variables before executing
                    if self.do_selling.get():
                        self.execute_selling_phase()
                        
                    if self.do_buying.get():
                        self.execute_buying_phase()
                    
                    # Return to fishing logic
                    state = "BEFORE_FISHING"
                    last_f_press = time.time()
                    wait_start_time = time.time() # Reset wait timer

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