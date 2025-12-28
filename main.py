import customtkinter as ctk
import json
import threading
import time
import ctypes
import random
import os
import winsound
from tkinter import filedialog, messagebox, Canvas
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController
from pynput.mouse import Button
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key
from pynput.keyboard import Listener as KeyboardListener
from pynput.mouse import Listener as MouseListener

# --- إعدادات المظهر ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# --- ثوابت Win32 API ---
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# ثوابت النافذة الشفافة
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

class IntegratedApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Calm Hub - v5")
        self.geometry("480x950") # زدت العرض قليلاً لاستيعاب القوائم
        self.resizable(False, False)

        # ===========================
        # إعدادات القفل
        # ===========================
        self.valid_codes = ["2710", "ali", "omega", "hoto"]
        self.is_authenticated = False 

        # --- المتغيرات العامة ---
        self.running_app = True
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        
        # القيم الافتراضية للمفاتيح
        self.key_recoil_toggle = keyboard.Key.f1
        self.key_overlay_toggle = keyboard.Key.f2
        self.key_next_weapon = keyboard.Key.f3 # تعديل الاسم
        self.key_prev_weapon = keyboard.Key.f4 # تعديل الاسم
        
        self.binding_target = None
        self.is_binding_key = False

        # Recoil Vars
        self.recoil_enabled = True
        self.overlay_visible = True
        self.left_pressed = False
        self.right_pressed = False
        self.is_locked = False
        
        # --- هيكل البيانات الجديد (لعبة -> أسلحة) ---
        self.games_library = {
            "Global Settings": {
                "Default Weapon": {"x": 0, "x2": 0, "y": 0, "human": 0, "cps": 10}
            },
            "CS2": {
                "AK-47": {"x": 2, "x2": 0, "y": 15, "human": 2, "cps": 9},
                "M4A1-S": {"x": 0, "x2": 1, "y": 10, "human": 1, "cps": 10},
                "Deagle": {"x": 0, "x2": 0, "y": 25, "human": 0, "cps": 5}
            },
            "Valorant": {
                "Vandal": {"x": 1, "x2": -1, "y": 12, "human": 1, "cps": 10},
                "Phantom": {"x": 0, "x2": 0, "y": 9, "human": 1, "cps": 11}
            }
        }
        
        self.current_game = "CS2"
        self.current_weapon = "AK-47"

        # Clicker Vars
        self.clicker_running = False
        self.cps = 10
        self.clicker_key = keyboard.Key.f6
        self.binding_mode_clicker = False
        self.click_mode = "Toggle"

        # Movement Vars
        self.strafe_enabled = False
        self.bhop_enabled = False
        self.strafe_speed = 0.1
        self.space_held = False

        # Crosshair Vars
        self.crosshair_window = None
        self.show_crosshair = False
        self.crosshair_color = "Red"
        self.crosshair_shape = "Cross"
        self.crosshair_size = 10

        # --- تحميل الإعدادات ---
        self.load_config()

        # --- التأكد من صحة البيانات المحملة ---
        if self.current_game not in self.games_library:
            self.current_game = list(self.games_library.keys())[0]
        if self.current_weapon not in self.games_library[self.current_game]:
            self.current_weapon = list(self.games_library[self.current_game].keys())[0]

        # --- بناء الواجهة ---
        self.build_main_ui()
        self.build_login_screen()

    # =====================================================
    # نظام الحفظ والاسترجاع (محدث للهيكل الجديد)
    # =====================================================
    def get_key_str(self, key):
        if isinstance(key, mouse.Button): return f"mouse.{key.name}"
        try: return f"char.{key.char}"
        except: return f"key.{key.name}"

    def parse_key_str(self, key_str):
        try:
            if key_str.startswith("mouse."): return getattr(mouse.Button, key_str.split(".")[1])
            if key_str.startswith("key."): return getattr(keyboard.Key, key_str.split(".")[1])
            if key_str.startswith("char."): return keyboard.KeyCode(char=key_str.split(".")[1])
        except: return keyboard.Key.f1

    def save_config(self):
        # حفظ القيم الحالية قبل الكتابة
        self.update_current_weapon_data()
        
        data = {
            "library": self.games_library, # الهيكل الجديد
            "last_game": self.current_game,
            "last_weapon": self.current_weapon,
            "keys": {
                "recoil": self.get_key_str(self.key_recoil_toggle),
                "overlay": self.get_key_str(self.key_overlay_toggle),
                "next": self.get_key_str(self.key_next_weapon),
                "prev": self.get_key_str(self.key_prev_weapon),
                "clicker": self.get_key_str(self.clicker_key)
            },
            "crosshair": {
                "enabled": self.show_crosshair,
                "color": self.crosshair_color,
                "shape": self.crosshair_shape,
                "size": self.crosshair_size
            },
            "clicker": {
                # CPS يتم حفظه داخل السلاح الآن، لكن يمكن حفظ وضع التشغيل هنا
                "mode": self.click_mode
            },
            "movement": {
                "strafe_enabled": self.strafe_enabled,
                "bhop_enabled": self.bhop_enabled,
                "strafe_speed": self.strafe_speed
            }
        }
        try:
            with open("config.json", "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def load_config(self):
        if not os.path.exists("config.json"): return

        try:
            with open("config.json", "r") as f:
                data = json.load(f)
            
            if "library" in data: self.games_library = data["library"]
            if "last_game" in data: self.current_game = data["last_game"]
            if "last_weapon" in data: self.current_weapon = data["last_weapon"]

            keys = data.get("keys", {})
            if "recoil" in keys: self.key_recoil_toggle = self.parse_key_str(keys["recoil"])
            if "overlay" in keys: self.key_overlay_toggle = self.parse_key_str(keys["overlay"])
            if "next" in keys: self.key_next_weapon = self.parse_key_str(keys["next"])
            if "prev" in keys: self.key_prev_weapon = self.parse_key_str(keys["prev"])
            if "clicker" in keys: self.clicker_key = self.parse_key_str(keys["clicker"])

            ch = data.get("crosshair", {})
            self.show_crosshair = ch.get("enabled", False)
            self.crosshair_color = ch.get("color", "Red")
            self.crosshair_shape = ch.get("shape", "Cross")
            self.crosshair_size = ch.get("size", 10)

            cl = data.get("clicker", {})
            self.click_mode = cl.get("mode", "Toggle")
            
            mv = data.get("movement", {})
            self.strafe_enabled = mv.get("strafe_enabled", False)
            self.bhop_enabled = mv.get("bhop_enabled", False)
            self.strafe_speed = mv.get("strafe_speed", 0.1)

        except Exception as e:
            print(f"Error loading config: {e}")

    # =====================================================
    # UI Building
    # =====================================================
    def build_login_screen(self):
        self.login_frame = ctk.CTkFrame(self, fg_color="#101010", corner_radius=0)
        self.login_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(self.login_frame, text="SECURITY ACCESS", font=("Orbitron", 24, "bold"), text_color="#cf1b1b").pack(pady=(200, 20))
        self.entry_code = ctk.CTkEntry(self.login_frame, placeholder_text="Enter Passcode", show="*", width=200, font=("Arial", 14), justify="center")
        self.entry_code.pack(pady=10)
        self.entry_code.bind("<Return>", self.check_passcode)
        self.btn_login = ctk.CTkButton(self.login_frame, text="Unlock", command=self.check_passcode, fg_color="#cf1b1b", hover_color="#8a0f0f", width=200)
        self.btn_login.pack(pady=10)
        self.lbl_error = ctk.CTkLabel(self.login_frame, text="", text_color="red")
        self.lbl_error.pack(pady=5)

    def check_passcode(self, event=None):
        if self.entry_code.get() in self.valid_codes:
            self.unlock_app()
        else:
            self.lbl_error.configure(text="Access Denied")
            self.entry_code.delete(0, 'end')

    def unlock_app(self):
        self.login_frame.place_forget()
        self.is_authenticated = True
        threading.Thread(target=lambda: winsound.Beep(1000, 200)).start()
        self.create_overlay()
        if self.show_crosshair: self.create_crosshair_window()
        self.start_listeners()

    def build_main_ui(self):
        self.tabview = ctk.CTkTabview(self, width=450, height=880)
        self.tabview.pack(padx=10, pady=10, fill="both")
        self.tab_recoil = self.tabview.add("Recoil & Library")
        self.tab_macro = self.tabview.add("Clicker")
        self.tab_move = self.tabview.add("Movement")
        self.tab_crosshair = self.tabview.add("Crosshair")

        self.build_library_ui() # تم تغيير الاسم ليعكس الوظيفة الجديدة
        self.build_clicker_ui()
        self.build_movement_ui()
        self.build_crosshair_ui()

    def open_keybinds_window(self):
        if self.is_binding_key: return
        self.win_binds = ctk.CTkToplevel(self)
        self.win_binds.title("Configure Hotkeys")
        self.win_binds.geometry("350x450")
        self.win_binds.attributes('-topmost', True)
        self.win_binds.grab_set()
        
        ctk.CTkLabel(self.win_binds, text="Hotkey Configuration", font=("Orbitron", 18, "bold")).pack(pady=20)
        
        def create_row(label_text, current_key, bind_cmd):
            frame = ctk.CTkFrame(self.win_binds, fg_color="transparent")
            frame.pack(fill="x", padx=20, pady=10)
            ctk.CTkLabel(frame, text=label_text, font=("Roboto", 12)).pack(side="left")
            btn = ctk.CTkButton(frame, text=self.format_trigger_name(current_key), width=100, command=bind_cmd, fg_color="#333")
            btn.pack(side="right")
            return btn

        self.btn_bind_recoil = create_row("Toggle Recoil:", self.key_recoil_toggle, lambda: self.start_global_binding("recoil", self.btn_bind_recoil))
        self.btn_bind_overlay = create_row("Toggle Overlay:", self.key_overlay_toggle, lambda: self.start_global_binding("overlay", self.btn_bind_overlay))
        # تغيير المسميات
        self.btn_bind_next = create_row("Next Weapon:", self.key_next_weapon, lambda: self.start_global_binding("next", self.btn_bind_next))
        self.btn_bind_prev = create_row("Prev Weapon:", self.key_prev_weapon, lambda: self.start_global_binding("prev", self.btn_bind_prev))

    def start_global_binding(self, target, btn_widget):
        self.is_binding_key = True
        self.binding_target = target
        self.current_binding_btn = btn_widget
        btn_widget.configure(text="Waiting...", fg_color="#FFA500", text_color="black")

    def apply_new_bind(self, trigger):
        if self.binding_target == "recoil": self.key_recoil_toggle = trigger
        elif self.binding_target == "overlay": self.key_overlay_toggle = trigger
        elif self.binding_target == "next": self.key_next_weapon = trigger
        elif self.binding_target == "prev": self.key_prev_weapon = trigger
        
        trigger_name = self.format_trigger_name(trigger)
        self.current_binding_btn.configure(text=trigger_name, fg_color="#333", text_color="white")
        self.is_binding_key = False
        self.binding_target = None
        self.save_config()

    # =====================================================
    # Recoil & Library UI (المعدل بالكامل)
    # =====================================================
    def build_library_ui(self):
        ctk.CTkLabel(self.tab_recoil, text="Game Library Hub", font=("Orbitron", 20, "bold"), text_color="#3a7ebf").pack(pady=10)
        
        # --- قسم اختيار اللعبة ---
        self.frame_game_select = ctk.CTkFrame(self.tab_recoil, fg_color="#202020", border_color="#3a7ebf", border_width=1)
        self.frame_game_select.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(self.frame_game_select, text="ACTIVE GAME", font=("Roboto", 10, "bold"), text_color="gray").pack(pady=(5,0))
        self.cmb_games = ctk.CTkOptionMenu(self.frame_game_select, values=list(self.games_library.keys()), command=self.on_game_change, height=30, fg_color="#1f6aa5")
        self.cmb_games.set(self.current_game)
        self.cmb_games.pack(pady=5, padx=10, fill="x")
        
        self.btn_add_game = ctk.CTkButton(self.frame_game_select, text="+ New Game", width=80, height=20, command=self.add_new_game, fg_color="#333")
        self.btn_add_game.pack(pady=(0, 5))

        # --- قسم اختيار السلاح ---
        self.frame_weapon_select = ctk.CTkFrame(self.tab_recoil, fg_color="#202020")
        self.frame_weapon_select.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(self.frame_weapon_select, text="ACTIVE WEAPON PROFILE", font=("Roboto", 10, "bold"), text_color="gray").pack(pady=(5,0))
        
        # استخراج أسلحة اللعبة الحالية
        current_weapons = list(self.games_library[self.current_game].keys())
        self.cmb_weapons = ctk.CTkOptionMenu(self.frame_weapon_select, values=current_weapons, command=self.on_weapon_change, height=30, fg_color="#2b2b2b")
        self.cmb_weapons.set(self.current_weapon)
        self.cmb_weapons.pack(pady=5, padx=10, fill="x")

        self.btn_add_weapon = ctk.CTkButton(self.frame_weapon_select, text="+ New Weapon", width=80, height=20, command=self.add_new_weapon, fg_color="#333")
        self.btn_add_weapon.pack(pady=(0, 5))
        
        # --- أدوات التحكم (Save, Delete) ---
        self.frame_actions = ctk.CTkFrame(self.tab_recoil, fg_color="transparent")
        self.frame_actions.pack(pady=5)
        self.btn_save = ctk.CTkButton(self.frame_actions, text="Save Config", width=100, height=28, command=self.save_config, fg_color="#1f6aa5")
        self.btn_save.grid(row=0, column=0, padx=5)
        self.btn_del_weapon = ctk.CTkButton(self.frame_actions, text="Delete Weapon", width=100, height=28, command=self.delete_current_weapon, fg_color="#8B0000")
        self.btn_del_weapon.grid(row=0, column=1, padx=5)
        
        # --- إعدادات السلاح (Sliders) ---
        self.frame_controls = ctk.CTkFrame(self.tab_recoil)
        self.frame_controls.pack(pady=10, padx=10, fill="x")
        
        # Activation Mode
        ctk.CTkLabel(self.frame_controls, text="Recoil Activation", font=("Roboto", 11, "bold")).pack(pady=4)
        self.trigger_mode = ctk.CTkSegmentedButton(self.frame_controls, values=["Left Click Only", "Right + Left Click"], height=24)
        self.trigger_mode.set("Left Click Only")
        self.trigger_mode.pack(pady=5, padx=10)

        # استدعاء القيم الحالية
        vals = self.games_library[self.current_game][self.current_weapon]
        
        self.lbl_x = ctk.CTkLabel(self.frame_controls, text=f"Main X-Axis: {vals.get('x', 0)}", font=("Roboto", 12, "bold"))
        self.lbl_x.pack(pady=(8, 4))
        self.slider_x = ctk.CTkSlider(self.frame_controls, from_=-20, to=20, number_of_steps=40, command=self.update_labels, height=16)
        self.slider_x.set(vals.get('x', 0))
        self.slider_x.pack(pady=4, padx=15, fill="x")
        
        self.lbl_x2 = ctk.CTkLabel(self.frame_controls, text=f"X2-Axis (Fine Tune): {vals.get('x2', 0)}", font=("Roboto", 12, "bold"), text_color="#AABBCC")
        self.lbl_x2.pack(pady=(8, 4))
        self.slider_x2 = ctk.CTkSlider(self.frame_controls, from_=-10, to=10, number_of_steps=20, command=self.update_labels, progress_color="#888", height=16)
        self.slider_x2.set(vals.get('x2', 0))
        self.slider_x2.pack(pady=4, padx=15, fill="x")
        
        self.lbl_y = ctk.CTkLabel(self.frame_controls, text=f"Y-Axis (Vertical): {vals.get('y', 0)}", font=("Roboto", 12, "bold"))
        self.lbl_y.pack(pady=(12, 4))
        self.slider_y = ctk.CTkSlider(self.frame_controls, from_=0, to=50, number_of_steps=50, command=self.update_labels, height=16)
        self.slider_y.set(vals.get('y', 0))
        self.slider_y.pack(pady=(4, 15), padx=15, fill="x")
        
        self.lbl_human = ctk.CTkLabel(self.frame_controls, text=f"Humanization: {vals.get('human', 0)}", font=("Roboto", 12, "bold"), text_color="#00FF7F")
        self.lbl_human.pack(pady=(12, 4))
        self.slider_human = ctk.CTkSlider(self.frame_controls, from_=0, to=5, number_of_steps=5, command=self.update_labels, height=16, progress_color="#00FF7F")
        self.slider_human.set(vals.get('human', 0))
        self.slider_human.pack(pady=(4, 15), padx=15, fill="x")
        
        # --- Footer ---
        self.frame_bottom = ctk.CTkFrame(self.tab_recoil)
        self.frame_bottom.pack(pady=10, padx=10, fill="x")
        self.btn_keybinds = ctk.CTkButton(self.frame_bottom, text="Hotkeys ⌨️", command=self.open_keybinds_window, fg_color="#444", width=120)
        self.btn_keybinds.pack(pady=5)
        self.switch_lock = ctk.CTkSwitch(self.frame_bottom, text="LOCK EDITING", command=self.toggle_lock, font=("Roboto", 11, "bold"))
        self.switch_lock.pack(pady=5)
        
        self.interactive_elements = [self.cmb_games, self.cmb_weapons, self.btn_add_game, self.btn_add_weapon, self.btn_save, self.btn_del_weapon, self.trigger_mode, self.slider_x, self.slider_x2, self.slider_y, self.slider_human, self.btn_keybinds]

    def build_clicker_ui(self):
        self.label_title_clicker = ctk.CTkLabel(self.tab_macro, text="Auto Clicker", font=("Roboto", 24, "bold"))
        self.label_title_clicker.pack(pady=20)
        
        # تحديث CPS بناءً على السلاح
        current_cps = self.games_library[self.current_game][self.current_weapon].get("cps", 10)
        
        self.label_cps = ctk.CTkLabel(self.tab_macro, text=f"Clicks Per Second (CPS): {current_cps}")
        self.label_cps.pack(pady=(5, 0))
        self.slider_cps = ctk.CTkSlider(self.tab_macro, from_=1, to=50, number_of_steps=49, command=self.update_cps)
        self.slider_cps.set(current_cps) 
        self.slider_cps.pack(pady=5)
        self.lbl_mode_clicker = ctk.CTkLabel(self.tab_macro, text="Trigger Mode:", font=("Roboto", 14))
        self.lbl_mode_clicker.pack(pady=(15, 0))
        self.mode_selector = ctk.CTkSegmentedButton(self.tab_macro, values=["Toggle", "Hold"], command=self.change_clicker_mode)
        self.mode_selector.set(self.click_mode)
        self.mode_selector.pack(pady=5)
        self.lbl_bind = ctk.CTkLabel(self.tab_macro, text="Activation Key/Button:", font=("Roboto", 14))
        self.lbl_bind.pack(pady=(15, 0))
        
        key_name = self.format_trigger_name(self.clicker_key)
        self.btn_bind = ctk.CTkButton(self.tab_macro, text=f"Current: {key_name}", command=self.start_binding_clicker, fg_color="#555555", hover_color="#333333")
        self.btn_bind.pack(pady=5)
        
        self.btn_status = ctk.CTkButton(self.tab_macro, text="Ready", state="disabled", fg_color="transparent", border_width=2, text_color_disabled="white", height=50)
        self.btn_status.pack(pady=20)
        self.label_status = ctk.CTkLabel(self.tab_macro, text="Status: STOPPED", text_color="gray")
        self.label_status.pack(pady=5)

    def build_movement_ui(self):
        ctk.CTkLabel(self.tab_move, text="Movement Assistant", font=("Orbitron", 20, "bold"), text_color="#FF8C00").pack(pady=15)
        self.frame_strafe = ctk.CTkFrame(self.tab_move)
        self.frame_strafe.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(self.frame_strafe, text="Auto Strafe (Dodge)", font=("Roboto", 14, "bold")).pack(pady=5)
        ctk.CTkLabel(self.frame_strafe, text="Moves A/D when shooting", font=("Roboto", 10), text_color="gray").pack(pady=0)
        
        self.switch_strafe = ctk.CTkSwitch(self.frame_strafe, text="Enable Auto Strafe", command=self.toggle_strafe)
        if self.strafe_enabled: self.switch_strafe.select()
        self.switch_strafe.pack(pady=10)
        
        self.lbl_strafe_speed = ctk.CTkLabel(self.frame_strafe, text=f"Strafe Delay: {self.strafe_speed}s")
        self.lbl_strafe_speed.pack(pady=5)
        self.slider_strafe = ctk.CTkSlider(self.frame_strafe, from_=0.05, to=1.0, number_of_steps=19, command=self.update_movement_settings)
        self.slider_strafe.set(self.strafe_speed)
        self.slider_strafe.pack(pady=5)

        self.frame_bhop = ctk.CTkFrame(self.tab_move)
        self.frame_bhop.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(self.frame_bhop, text="Bunny Hop (Bhop)", font=("Roboto", 14, "bold")).pack(pady=5)
        self.switch_bhop = ctk.CTkSwitch(self.frame_bhop, text="Enable Bhop (Hold SPACE)", command=self.toggle_bhop)
        if self.bhop_enabled: self.switch_bhop.select()
        self.switch_bhop.pack(pady=10)

    # =====================================================
    # Library Logic (New)
    # =====================================================
    def on_game_change(self, selected_game):
        self.update_current_weapon_data() # Save old weapon data first
        self.current_game = selected_game
        
        # Load weapons for this game
        weapons = list(self.games_library[self.current_game].keys())
        self.cmb_weapons.configure(values=weapons)
        
        # Select first weapon by default
        self.current_weapon = weapons[0]
        self.cmb_weapons.set(self.current_weapon)
        self.on_weapon_change(self.current_weapon)

    def on_weapon_change(self, selected_weapon):
        self.update_current_weapon_data() # Save previous weapon data
        self.current_weapon = selected_weapon
        
        # Load data to sliders
        data = self.games_library[self.current_game][self.current_weapon]
        self.slider_x.set(data.get("x", 0))
        self.slider_x2.set(data.get("x2", 0))
        self.slider_y.set(data.get("y", 0))
        self.slider_human.set(data.get("human", 0))
        
        # Update Clicker CPS too
        cps_val = data.get("cps", 10)
        self.slider_cps.set(cps_val)
        self.label_cps.configure(text=f"Clicks Per Second (CPS): {cps_val}")
        
        self.update_labels()
        self.update_overlay()
        self.save_config()

    def update_current_weapon_data(self):
        # حفظ بيانات السلايدرز في الذاكرة
        self.games_library[self.current_game][self.current_weapon]["x"] = self.slider_x.get()
        self.games_library[self.current_game][self.current_weapon]["x2"] = self.slider_x2.get()
        self.games_library[self.current_game][self.current_weapon]["y"] = self.slider_y.get()
        self.games_library[self.current_game][self.current_weapon]["human"] = self.slider_human.get()
        self.games_library[self.current_game][self.current_weapon]["cps"] = int(self.slider_cps.get())

    def add_new_game(self):
        name = ctk.CTkInputDialog(text="Game Name (e.g., Apex Legends):", title="New Game").get_input()
        if name and name not in self.games_library:
            self.games_library[name] = {"Default Gun": {"x": 0, "x2": 0, "y": 0, "human": 0, "cps": 10}}
            self.cmb_games.configure(values=list(self.games_library.keys()))
            self.cmb_games.set(name)
            self.on_game_change(name)

    def add_new_weapon(self):
        name = ctk.CTkInputDialog(text="Weapon Name (e.g., MP5):", title="New Weapon").get_input()
        if name and name not in self.games_library[self.current_game]:
            self.games_library[self.current_game][name] = {"x": 0, "x2": 0, "y": 0, "human": 0, "cps": 10}
            self.cmb_weapons.configure(values=list(self.games_library[self.current_game].keys()))
            self.cmb_weapons.set(name)
            self.on_weapon_change(name)

    def delete_current_weapon(self):
        weapons = list(self.games_library[self.current_game].keys())
        if len(weapons) <= 1:
            messagebox.showwarning("Warning", "Cannot delete the last weapon in a game profile!")
            return
        
        confirm = messagebox.askyesno("Confirm", f"Delete weapon '{self.current_weapon}'?")
        if confirm:
            del self.games_library[self.current_game][self.current_weapon]
            # Switch to another weapon
            new_weapons = list(self.games_library[self.current_game].keys())
            self.cmb_weapons.configure(values=new_weapons)
            self.current_weapon = new_weapons[0]
            self.cmb_weapons.set(self.current_weapon)
            self.on_weapon_change(self.current_weapon)

    def cycle_weapon(self, direction):
        # Cycle through weapons of the CURRENT GAME only
        weapons = list(self.games_library[self.current_game].keys())
        try:
            curr_idx = weapons.index(self.current_weapon)
            new_idx = (curr_idx + direction) % len(weapons)
            new_weapon = weapons[new_idx]
            self.cmb_weapons.set(new_weapon)
            self.on_weapon_change(new_weapon)
        except: pass

    # =====================================================
    # Movement, Logic & Listeners
    # =====================================================
    def toggle_strafe(self):
        self.strafe_enabled = self.switch_strafe.get()
        self.save_config()

    def toggle_bhop(self):
        self.bhop_enabled = self.switch_bhop.get()
        self.save_config()

    def update_movement_settings(self, value=None):
        self.strafe_speed = round(self.slider_strafe.get(), 2)
        self.lbl_strafe_speed.configure(text=f"Strafe Delay: {self.strafe_speed}s")
        self.save_config()

    def movement_loop(self):
        strafe_direction = 0 
        while self.running_app:
            if not self.is_authenticated:
                time.sleep(0.5); continue

            # Auto Strafe
            if self.strafe_enabled and self.left_pressed and self.right_pressed: 
                try:
                    if strafe_direction == 0:
                        self.keyboard_controller.press('a'); time.sleep(self.strafe_speed)
                        self.keyboard_controller.release('a'); strafe_direction = 1
                    else:
                        self.keyboard_controller.press('d'); time.sleep(self.strafe_speed)
                        self.keyboard_controller.release('d'); strafe_direction = 0
                except: pass
            
            # Bhop
            if self.bhop_enabled and self.space_held:
                try:
                    self.keyboard_controller.press(Key.space); time.sleep(0.01)
                    self.keyboard_controller.release(Key.space)
                    time.sleep(0.02 + random.uniform(0.01, 0.03))
                except: pass
            else: time.sleep(0.01)

    def recoil_move_loop(self):
        while self.running_app:
            if self.is_authenticated and self.recoil_enabled:
                should_activate = False
                mode = self.trigger_mode.get()
                if mode == "Left Click Only": should_activate = self.left_pressed
                elif mode == "Right + Left Click": should_activate = self.right_pressed and self.left_pressed

                if should_activate:
                    base_x = int(self.slider_x.get()) + int(self.slider_x2.get())
                    base_y = int(self.slider_y.get())
                    human_val = int(self.slider_human.get())
                    final_x = base_x
                    final_y = base_y
                    
                    if human_val > 0:
                        final_x += random.randint(-human_val, human_val)
                        final_y += random.randint(-human_val, human_val)
                        
                    if final_x != 0 or final_y != 0:
                        self.game_move(final_x, final_y)
                        sleep_time = 0.015 + (random.uniform(0, 0.005) if human_val > 0 else 0)
                        time.sleep(sleep_time)
                    else: time.sleep(0.01)
                else: time.sleep(0.01)
            else: time.sleep(0.1)

    def start_listeners(self):
        self.key_listener = KeyboardListener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.key_listener.start()
        self.mouse_listener = MouseListener(on_click=self.on_mouse_click)
        self.mouse_listener.start()
        
        self.recoil_thread = threading.Thread(target=self.recoil_move_loop, daemon=True)
        self.recoil_thread.start()
        self.clicker_thread = threading.Thread(target=self.clicker_loop, daemon=True)
        self.clicker_thread.start()
        self.movement_thread = threading.Thread(target=self.movement_loop, daemon=True)
        self.movement_thread.start()

    def on_key_press(self, key):
        if not self.is_authenticated: return
        
        if self.is_binding_key:
            self.after(0, lambda: self.apply_new_bind(key))
            return
        if self.binding_mode_clicker:
            self.after(0, lambda: self.set_new_trigger(key))
            return

        if key == Key.space: self.space_held = True

        if key == self.key_recoil_toggle:
            self.recoil_enabled = not self.recoil_enabled
            if self.recoil_enabled: winsound.Beep(800, 150)
            else: winsound.Beep(400, 150)
            self.update_overlay()

        elif key == self.key_overlay_toggle:
            self.overlay_visible = not self.overlay_visible
            if self.overlay_visible: self.overlay.deiconify()
            else: self.overlay.withdraw()
        
        elif key == self.key_next_weapon: self.cycle_weapon(1)
        elif key == self.key_prev_weapon: self.cycle_weapon(-1)

        if key == self.clicker_key:
            if self.click_mode == "Toggle":
                if self.clicker_running: self.after(0, self.stop_clicking)
                else: self.after(0, self.start_clicking)
            elif self.click_mode == "Hold":
                if not self.clicker_running: self.after(0, self.start_clicking)

    def on_key_release(self, key):
        if not self.is_authenticated: return
        if key == Key.space: self.space_held = False
        if self.click_mode == "Hold" and key == self.clicker_key:
            self.after(0, self.stop_clicking)

    def on_mouse_click(self, x, y, button, pressed):
        if not self.is_authenticated: return
        if self.is_binding_key:
            if pressed and button != Button.left:
                self.after(0, lambda: self.apply_new_bind(button))
            return
        if self.binding_mode_clicker:
            if pressed and button != Button.left:
                self.after(0, lambda: self.set_new_trigger(button))
            return

        if button == Button.left: self.left_pressed = pressed
        elif button == Button.right: self.right_pressed = pressed

        if button == self.clicker_key:
            if self.click_mode == "Toggle":
                if pressed:
                    if self.clicker_running: self.after(0, self.stop_clicking)
                    else: self.after(0, self.start_clicking)
            elif self.click_mode == "Hold":
                if pressed: self.after(0, self.start_clicking)
                else: self.after(0, self.stop_clicking)

    def game_move(self, x, y):
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, int(x), int(y), 0, 0)
    def game_click(self):
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.01)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def clicker_loop(self):
        while self.running_app:
            if self.is_authenticated and self.clicker_running:
                # استخدم CPS السلاح الحالي بدلاً من قيمة عامة
                try: current_cps = int(self.slider_cps.get())
                except: current_cps = 10
                
                self.game_click()
                time.sleep(1.0 / max(1, current_cps))
            else: time.sleep(0.01)

    # --- Crosshair & Helper Functions ---
    def build_crosshair_ui(self):
        ctk.CTkLabel(self.tab_crosshair, text="External Crosshair", font=("Orbitron", 20, "bold"), text_color="#3a7ebf").pack(pady=15)
        self.switch_crosshair = ctk.CTkSwitch(self.tab_crosshair, text="Enable Crosshair", command=self.toggle_crosshair, font=("Roboto", 14, "bold"))
        if self.show_crosshair: self.switch_crosshair.select()
        self.switch_crosshair.pack(pady=20)
        
        ctk.CTkLabel(self.tab_crosshair, text="Shape Style", font=("Roboto", 12)).pack(pady=(10, 5))
        self.seg_shape = ctk.CTkSegmentedButton(self.tab_crosshair, values=["Dot", "Cross", "Circle"], command=self.update_crosshair_settings)
        self.seg_shape.set(self.crosshair_shape)
        self.seg_shape.pack(pady=5)
        
        ctk.CTkLabel(self.tab_crosshair, text="Color", font=("Roboto", 12)).pack(pady=(15, 5))
        self.seg_color = ctk.CTkSegmentedButton(self.tab_crosshair, values=["Red", "Green", "Cyan", "White"], command=self.update_crosshair_settings)
        self.seg_color.set(self.crosshair_color)
        self.seg_color.pack(pady=5)
        
        ctk.CTkLabel(self.tab_crosshair, text="Size", font=("Roboto", 12)).pack(pady=(15, 5))
        self.slider_size = ctk.CTkSlider(self.tab_crosshair, from_=2, to=30, number_of_steps=28, command=self.update_crosshair_settings)
        self.slider_size.set(self.crosshair_size)
        self.slider_size.pack(pady=5)

    def toggle_crosshair(self):
        self.show_crosshair = self.switch_crosshair.get()
        if self.show_crosshair: self.create_crosshair_window()
        else:
            if self.crosshair_window: self.crosshair_window.destroy(); self.crosshair_window = None
        self.save_config()

    def update_crosshair_settings(self, value=None):
        self.crosshair_shape = self.seg_shape.get()
        self.crosshair_color = self.seg_color.get()
        self.crosshair_size = int(self.slider_size.get())
        if self.show_crosshair and self.crosshair_window: self.draw_crosshair()
        self.save_config()

    def create_crosshair_window(self):
        if self.crosshair_window: return
        self.crosshair_window = ctk.CTkToplevel(self)
        self.crosshair_window.overrideredirect(True)
        self.crosshair_window.attributes('-topmost', True)
        self.crosshair_window.attributes('-transparentcolor', 'black')
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        size = 100
        x = (screen_w // 2) - (size // 2)
        y = (screen_h // 2) - (size // 2)
        self.crosshair_window.geometry(f"{size}x{size}+{x}+{y}")
        self.crosshair_window.configure(bg='black')
        self.canvas = Canvas(self.crosshair_window, width=size, height=size, bg='black', highlightthickness=0)
        self.canvas.pack()
        try:
            hwnd = ctypes.windll.user32.GetParent(self.crosshair_window.winfo_id())
            if hwnd == 0: hwnd = self.crosshair_window.winfo_id()
            styles = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            styles = styles | WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, styles)
        except: pass
        self.draw_crosshair()

    def draw_crosshair(self):
        self.canvas.delete("all")
        center = 50
        s = self.crosshair_size
        c = self.crosshair_color.lower()
        if c == "cyan": c = "#00FFFF"
        if self.crosshair_shape == "Dot":
            self.canvas.create_oval(center-s/2, center-s/2, center+s/2, center+s/2, fill=c, outline="")
        elif self.crosshair_shape == "Circle":
             self.canvas.create_oval(center-s, center-s, center+s, center+s, outline=c, width=2)
        elif self.crosshair_shape == "Cross":
            self.canvas.create_line(center-s, center, center+s, center, fill=c, width=2)
            self.canvas.create_line(center, center-s, center, center+s, fill=c, width=2)

    def create_overlay(self):
        if not self.is_authenticated: return
        self.overlay = ctk.CTkToplevel(self)
        self.overlay.geometry("200x50+10+10")
        self.overlay.overrideredirect(True)
        self.overlay.attributes('-topmost', True)
        self.overlay.configure(fg_color="#1a1a1a")
        self.overlay_frame = ctk.CTkFrame(self.overlay, fg_color="green", corner_radius=8)
        self.overlay_frame.pack(expand=True, fill="both", padx=2, pady=2)
        self.overlay_label = ctk.CTkLabel(self.overlay_frame, text=f"{self.current_game}\n{self.current_weapon}", font=("Arial", 11, "bold"), text_color="white")
        self.overlay_label.pack(expand=True)

    def update_overlay(self):
        try:
            if self.recoil_enabled:
                self.overlay_frame.configure(fg_color="green")
                self.overlay_label.configure(text=f"ON | {self.current_game}\n{self.current_weapon}")
            else:
                self.overlay_frame.configure(fg_color="#8B0000")
                self.overlay_label.configure(text=f"OFF | {self.current_game}\n{self.current_weapon}")
        except: pass

    def update_labels(self, value=None):
        self.lbl_x.configure(text=f"Main X-Axis: {int(self.slider_x.get())}")
        self.lbl_x2.configure(text=f"X2-Axis (Fine Tune): {int(self.slider_x2.get())}")
        self.lbl_y.configure(text=f"Y-Axis (Vertical): {int(self.slider_y.get())}")
        self.lbl_human.configure(text=f"Humanization: {int(self.slider_human.get())}")
        self.save_config()

    def update_cps(self, value):
        self.cps = int(value)
        self.label_cps.configure(text=f"Clicks Per Second (CPS): {self.cps}")
        self.save_config()

    def change_clicker_mode(self, value):
        self.click_mode = value
        if self.clicker_running: self.stop_clicking()
        self.save_config()

    def start_binding_clicker(self):
        self.binding_mode_clicker = True
        self.btn_bind.configure(text="Press any button...", fg_color="#FFA500", text_color="black")
        self.btn_status.configure(text="Waiting for input...")

    def set_new_trigger(self, trigger):
        self.clicker_key = trigger
        self.binding_mode_clicker = False
        name = self.format_trigger_name(trigger)
        self.btn_bind.configure(text=f"Current: {name}", fg_color="#555555", text_color="white")
        self.btn_status.configure(text=f"Ready (Press {name})")
        self.save_config()

    def format_trigger_name(self, trigger):
        if isinstance(trigger, mouse.Button): return str(trigger).replace("Button.", "").upper()
        try: return trigger.char.upper()
        except: return str(trigger).replace("Key.", "").upper()

    def start_clicking(self):
        if not self.clicker_running:
            self.clicker_running = True
            self.label_status.configure(text="Status: CLICKING...", text_color="#00FF00")
            self.btn_status.configure(text="RUNNING", fg_color="green", text_color="white")

    def stop_clicking(self):
        if self.clicker_running:
            self.clicker_running = False
            self.label_status.configure(text="Status: STOPPED", text_color="gray")
            trigger_name = self.format_trigger_name(self.clicker_key)
            self.btn_status.configure(text=f"Ready (Press {trigger_name})", fg_color="transparent", text_color="white")

    def toggle_lock(self):
        self.is_locked = self.switch_lock.get()
        state = "disabled" if self.is_locked else "normal"
        for widget in self.interactive_elements:
            try: widget.configure(state=state)
            except: pass
        self.title(f"Calm Hub - {'LOCKED' if self.is_locked else 'UNLOCKED'}")

    def on_closing(self):
        self.save_config()
        self.running_app = False
        self.key_listener.stop()
        self.mouse_listener.stop()
        self.destroy()

if __name__ == "__main__":
    app = IntegratedApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()