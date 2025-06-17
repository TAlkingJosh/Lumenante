# lumenante_main.py
import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
import time
import math
import shlex
import asyncio
from aiohttp import web
from collections import deque
import uuid
import importlib.util
import random

# Helper to determine the application's root directory
def get_base_path():
    """Gets the base path for the application, handling PyInstaller's temp folder."""
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle, the PyInstaller bootloader
        # extends the sys module by a flag frozen=True and sets the app
        # path into sys._MEIPASS.
        return Path(sys._MEIPASS)
    else:
        # If running from source
        return Path(__file__).resolve().parent

# Set a global base path variable
BASE_PATH = get_base_path()

try:
    import inputs
    GAMEPAD_AVAILABLE = True
except ImportError:
    GAMEPAD_AVAILABLE = False
    print("Warning: 'inputs' library not found. Gamepad/joystick support will be disabled.")
    print("         Install it with: pip install inputs")


try:
    from OpenGL.GLUT import glutInit
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False
    print("PyOpenGL not found. 3D features will be unavailable.")
except Exception as e:
    OPENGL_AVAILABLE = False
    print(f"Error importing PyOpenGL: {e}. 3D features may be unstable.")


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QLabel, QSlider, QFrame, QMessageBox, QFileDialog,
    QLineEdit, QSplashScreen, QProgressBar, QComboBox
)

from PyQt6.QtCore import Qt, QSize, QSettings, pyqtSignal, QTimer, QThread, QElapsedTimer, QStandardPaths
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter, QFont, QShortcut, QKeySequence


# New Imports for Plugin System
from plugins.plugin_api import LumenantePlugin, PluginAPI

from tabs.main_tab import MainTab
from tabs.fixtures_tab import FixturesTab
from tabs.timeline_tab import TimelineTab
from tabs.visualization_3d_tab import Visualization3DTab
from tabs.settings_tab import SettingsTab
from tabs.presets_tab import PresetsTab
from tabs.help_tab import HelpTab
from tabs.fixture_groups_tab import FixtureGroupsTab
from tabs.loop_palettes_tab import LoopPalettesTab
from tabs.video_sync_tab import VideoSyncTab
from tabs.plugins_tab import PluginsTab # New Tab

import sqlite3
import theme_manager

def get_app_data_path(file_name: str) -> Path:
    """Returns the full path to a file in the application's persistent data directory."""
    app_data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    app_data_dir.mkdir(parents=True, exist_ok=True)
    return app_data_dir / file_name

class RobloxHTTPManager(QThread):
    """Manages an asynchronous HTTP server to provide fixture updates to Roblox."""
    status_updated = pyqtSignal(str)
    positions_reported = pyqtSignal(dict) # New signal for reporting positions

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings = main_window.settings
        self.db_connection = main_window.db_connection
        self.data_buffer = {}
        self.loop = None
        self.shutdown_event = None

    async def get_updates(self, request):
        """Web handler for Roblox to poll for changes."""
        updates_to_send = self.data_buffer.copy()
        self.data_buffer.clear()
        return web.json_response(updates_to_send)
        
    async def handle_report_positions(self, request):
        """Web handler to receive position data from Roblox."""
        try:
            data = await request.json()
            if isinstance(data, dict):
                self.positions_reported.emit(data)
                return web.Response(text="Positions received.", status=200)
            else:
                return web.Response(text="Invalid data format.", status=400)
        except Exception as e:
            print(f"Error handling reported positions: {e}")
            return web.Response(text=f"Server error: {e}", status=500)

    async def _server_main(self):
        """Initializes and runs the web server."""
        self.status_updated.emit("Server Starting...")
        app = web.Application()
        app.router.add_get("/get_updates", self.get_updates)
        app.router.add_post("/report_positions", self.handle_report_positions) # New route
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        host = '127.0.0.1'
        port = 25000 
        site = web.TCPSite(runner, host, port)
        
        try:
            await site.start()
            self.status_updated.emit(f"Listening on http://{host}:{port}")
            # Wait for the shutdown event instead of using a while loop
            if self.shutdown_event:
                await self.shutdown_event.wait()
        except asyncio.CancelledError:
            print("Server main task was cancelled.")
        except OSError as e:
            print(f"CRITICAL: Could not start HTTP server on {host}:{port}. Is the port in use? Error: {e}")
            self.status_updated.emit(f"Error: Port {port} in use.")
        except Exception as e:
            print(f"CRITICAL: HTTP server failed: {e}")
            self.status_updated.emit(f"Server Error: {e}")
        finally:
            await runner.cleanup()
            print("Roblox HTTP Server: Cleanup complete.")
    
    def run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.shutdown_event = asyncio.Event() # Create the event in the correct loop
            self.loop.run_until_complete(self._server_main())
        except Exception as e:
             print(f"Error in RobloxHTTPManager thread run method: {e}")

    def stop(self):
        if self.loop and self.shutdown_event:
            # Safely set the event from the main thread to signal the asyncio loop to stop
            self.loop.call_soon_threadsafe(self.shutdown_event.set)
        print("Roblox HTTP Server: Stop requested.")

    def add_update(self, fixture_fid: int, params: dict):
        """
        Thread-safe way for the main GUI to add data to the buffer.
        Uses the Fixture ID (FID) as the key, which matches Roblox model names.
        """
        if self._live_mode_enabled:
            # Use string representation of FID as JSON keys must be strings
            fid_str = str(fixture_fid)
            if fid_str not in self.data_buffer:
                self.data_buffer[fid_str] = {}
            self.data_buffer[fid_str].update(params)

    def set_live_mode(self, enabled: bool):
        self._live_mode_enabled = enabled
        if not enabled:
            self.data_buffer.clear()
            self.status_updated.emit("Live Mode OFF")
        else:
            # When enabling live mode, trigger an update for all fixtures.
            # The update function will calculate the correct state and add it to the buffer.
            for fixture_id in list(self.main_window.live_fixture_states.keys()):
                self.main_window.update_fixture_data_and_notify(fixture_id, {})
            self.status_updated.emit("Live Mode ON - Awaiting ROBLOX connection")

class PluginManager:
    """Discovers, loads, and manages application plugins."""
    def __init__(self, main_window: 'Lumenante'):
        self.main_window = main_window
        self.settings = main_window.settings
        self.plugins_dir = BASE_PATH / "plugins"
        
        self.discovered_plugins = {} # {plugin_id: {info_dict}}
        self.loaded_plugins = {} # {plugin_id: plugin_instance}
        
    def discover_plugins(self):
        """Scans the plugins directory for valid plugins."""
        self.discovered_plugins.clear()
        if not self.plugins_dir.exists():
            print(f"Creating plugins directory: {self.plugins_dir}")
            self.plugins_dir.mkdir()
            return

        for path_item in self.plugins_dir.iterdir():
            if path_item.is_dir() and (path_item / "plugin.py").exists():
                plugin_id = path_item.name
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"plugins.{plugin_id}.plugin", path_item / "plugin.py"
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[spec.name] = module
                        spec.loader.exec_module(module)
                        
                        if hasattr(module, 'get_plugin_class'):
                            plugin_class = module.get_plugin_class()
                            if issubclass(plugin_class, LumenantePlugin):
                                self.discovered_plugins[plugin_id] = {
                                    'id': plugin_id,
                                    'name': getattr(plugin_class, 'name', 'Unnamed Plugin'),
                                    'author': getattr(plugin_class, 'author', 'Unknown'),
                                    'version': getattr(plugin_class, 'version', '0.0.0'),
                                    'description': getattr(plugin_class, 'description', 'No description.'),
                                    'class': plugin_class,
                                    'path': path_item
                                }
                                print(f"Discovered plugin: '{plugin_class.name}'")
                            else:
                                print(f"Warning: Class in {plugin_id} does not inherit from LumenantePlugin.")
                        else:
                            print(f"Warning: Plugin module {plugin_id} is missing get_plugin_class() function.")
                except Exception as e:
                    print(f"Error discovering plugin in '{path_item.name}': {e}")

    def load_enabled_plugins(self):
        """Initializes all plugins marked as enabled in settings."""
        api = PluginAPI(self.main_window)
        for plugin_id, plugin_info in self.discovered_plugins.items():
            if self.is_plugin_enabled(plugin_id):
                try:
                    plugin_class = plugin_info['class']
                    plugin_instance = plugin_class()
                    if plugin_instance.initialize(api):
                        self.loaded_plugins[plugin_id] = plugin_instance
                    else:
                        print(f"Plugin '{plugin_info['name']}' failed to initialize.")
                except Exception as e:
                    print(f"Error loading plugin '{plugin_info['name']}': {e}")
                    QMessageBox.critical(self.main_window, "Plugin Load Error",
                                         f"Failed to load the plugin '{plugin_info['name']}'.\n\nError: {e}")

    def shutdown_plugins(self):
        """Calls the shutdown method on all loaded plugins."""
        for plugin_id, plugin_instance in self.loaded_plugins.items():
            try:
                plugin_instance.shutdown()
            except Exception as e:
                print(f"Error shutting down plugin '{plugin_instance.name}': {e}")
        self.loaded_plugins.clear()

    def is_plugin_enabled(self, plugin_id: str) -> bool:
        return self.settings.value(f"Plugins/{plugin_id}/enabled", False, type=bool)

    def set_plugin_enabled(self, plugin_id: str, enabled: bool):
        self.settings.setValue(f"Plugins/{plugin_id}/enabled", enabled)

class GamepadManager(QThread):
    """Manages listening for gamepad/joystick input in a separate thread."""
    joystick_moved = pyqtSignal(str, float)
    button_pressed = pyqtSignal(str)
    dpad_pressed = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True
        self.DEADZONE = 0.15
        self.daemon = True # Set thread as daemon

    def run(self):
        """Main loop to poll for gamepad events."""
        if not GAMEPAD_AVAILABLE:
            return

        while self._is_running:
            try:
                events = inputs.get_gamepad()
                for event in events:
                    if not self._is_running: break
                    
                    if event.ev_type == 'Absolute':
                        if event.code in ['ABS_RX', 'ABS_RY', 'ABS_X', 'ABS_Y']:
                            raw_val = event.state
                            normalized_val = raw_val / 32768.0
                            if abs(normalized_val) < self.DEADZONE:
                                normalized_val = 0.0
                            self.joystick_moved.emit(event.code, normalized_val)
                        elif event.code in ['ABS_HAT0X', 'ABS_HAT0Y']:
                            # D-pad often reports as an absolute axis.
                            # State is -1 (up/left), 0 (released), or 1 (down/right).
                            if event.state != 0:
                                self.dpad_pressed.emit(event.code, event.state)
                    
                    elif event.ev_type == 'Key':
                        # Buttons report on press (state 1) and release (state 0)
                        if event.state == 1: # Only emit on press
                            self.button_pressed.emit(event.code)
                            
            except inputs.UnpluggedError:
                if not self._is_running: break
                print("Gamepad unplugged. Will re-check in 3 seconds.")
                time.sleep(3)
            except Exception as e:
                if not self._is_running: break
                print(f"Error in GamepadManager: {e}. Disabling for this session.")
                self._is_running = False
                break
    
    def stop(self):
        """Stops the event loop."""
        self._is_running = False

class BaseEffect:
    def __init__(self, name:str, loop_palette_db_id: int, start_time_msec: float,
                 phase_offset_rad: float = 0.0, group_phase_offset_rad: float = 0.0,
                 source_effect_config: dict = None):
        self.name = name
        self.loop_palette_db_id = loop_palette_db_id
        self.start_time_msec = start_time_msec
        self.is_active = False
        self.phase_offset_rad = phase_offset_rad
        self.group_phase_offset_rad = group_phase_offset_rad
        self.source_effect_config = source_effect_config if source_effect_config else {}


    def get_value(self, current_time_msec: float) -> float | dict:
        raise NotImplementedError("Subclasses must implement get_value")

class SineWaveEffect(BaseEffect):
    def __init__(self, name:str, loop_palette_db_id: int, param_key: str,
                 speed_hz: float, size: float, center: float, direction: str,
                 start_time_msec: float,
                 phase_offset_rad: float = 0.0, group_phase_offset_rad: float = 0.0,
                 source_effect_config: dict = None):
        super().__init__(name, loop_palette_db_id, start_time_msec, phase_offset_rad, group_phase_offset_rad, source_effect_config)
        self.param_key = param_key
        self.speed_hz = max(0.01, speed_hz)
        self.size = size
        self.center = center
        self.direction_multiplier = -1.0 if str(direction).lower() == "backward" else 1.0

    def get_value(self, current_time_msec: float) -> float:
        if not self.is_active:
            return self.center
            
        elapsed_time_sec = (current_time_msec - self.start_time_msec) / 1000.0
        total_phase_offset = self.phase_offset_rad + self.group_phase_offset_rad
        
        value = self.center + self.size * math.sin(
            2 * math.pi * self.speed_hz * (elapsed_time_sec * self.direction_multiplier) + total_phase_offset
        )
        return value

class CircleEffect(BaseEffect):
    def __init__(self, name:str, loop_palette_db_id: int,
                 speed_hz: float, radius_pan: float, radius_tilt: float,
                 center_pan: float, center_tilt: float,
                 start_time_msec: float,
                 phase_offset_rad: float = 0.0, group_phase_offset_rad: float = 0.0,
                 source_effect_config: dict = None):
        super().__init__(name, loop_palette_db_id, start_time_msec, phase_offset_rad, group_phase_offset_rad, source_effect_config)
        self.speed_hz = max(0.01, speed_hz)
        self.radius_pan = radius_pan
        self.radius_tilt = radius_tilt
        self.center_pan = center_pan
        self.center_tilt = center_tilt


    def get_value(self, current_time_msec: float) -> dict:
        if not self.is_active:
            return {'rotation_y': self.center_pan, 'rotation_x': self.center_tilt}
        
        elapsed_time_sec = (current_time_msec - self.start_time_msec) / 1000.0
        angle_rad = 2 * math.pi * self.speed_hz * elapsed_time_sec + self.phase_offset_rad + self.group_phase_offset_rad
        
        pan_value = self.center_pan + self.radius_pan * math.cos(angle_rad)
        tilt_value = self.center_tilt + self.radius_tilt * math.sin(angle_rad)
        
        return {'rotation_y': pan_value, 'rotation_x': tilt_value}

class UShapeEffect(BaseEffect):
    def __init__(self, name: str, loop_palette_db_id: int, speed_hz: float,
                 width: float, height: float, orientation: str, start_time_msec: float,
                 phase_offset_rad: float = 0.0, group_phase_offset_rad: float = 0.0,
                 source_effect_config: dict = None):
        super().__init__(name, loop_palette_db_id, start_time_msec, phase_offset_rad, group_phase_offset_rad, source_effect_config)
        self.speed_hz = max(0.01, speed_hz)
        self.width = width / 2.0  # Use radius
        self.height = height / 2.0 # Use radius
        self.orientation = orientation

    def get_value(self, current_time_msec: float) -> dict:
        if not self.is_active: return {'rotation_y': 0, 'rotation_x': 0}
        
        elapsed_time_sec = (current_time_msec - self.start_time_msec) / 1000.0
        angle = 2 * math.pi * self.speed_hz * elapsed_time_sec

        # Primary axis is a full sine wave
        primary_val = self.width * math.sin(angle)
        # Secondary axis is a half-wave (always positive)
        secondary_val = self.height * abs(math.cos(angle))

        if self.orientation == "Up": pan, tilt = primary_val, secondary_val
        elif self.orientation == "Down": pan, tilt = primary_val, -secondary_val
        elif self.orientation == "Left": pan, tilt = -secondary_val, primary_val
        else: pan, tilt = secondary_val, primary_val # Right

        return {'rotation_y': pan, 'rotation_x': tilt}

class Figure8Effect(BaseEffect):
    def __init__(self, name: str, loop_palette_db_id: int, speed_hz: float,
                 width: float, height: float, start_time_msec: float,
                 phase_offset_rad: float = 0.0, group_phase_offset_rad: float = 0.0,
                 source_effect_config: dict = None):
        super().__init__(name, loop_palette_db_id, start_time_msec, phase_offset_rad, group_phase_offset_rad, source_effect_config)
        self.speed_hz = max(0.01, speed_hz)
        self.width = width / 2.0  # Use radius
        self.height = height / 2.0 # Use radius

    def get_value(self, current_time_msec: float) -> dict:
        if not self.is_active: return {'rotation_y': 0, 'rotation_x': 0}
        
        elapsed_time_sec = (current_time_msec - self.start_time_msec) / 1000.0
        angle = 2 * math.pi * self.speed_hz * elapsed_time_sec
        
        pan = self.width * math.sin(angle)
        tilt = self.height * math.sin(2 * angle)
        
        return {'rotation_y': pan, 'rotation_x': tilt}

class BallyEffect(BaseEffect):
    def __init__(self, name: str, loop_palette_db_id: int, speed_hz: float,
                 width: float, start_time_msec: float,
                 phase_offset_rad: float = 0.0, group_phase_offset_rad: float = 0.0,
                 source_effect_config: dict = None):
        super().__init__(name, loop_palette_db_id, start_time_msec, phase_offset_rad, group_phase_offset_rad, source_effect_config)
        self.speed_hz = max(0.01, speed_hz)
        self.width = width / 2.0 # Use radius

    def get_value(self, current_time_msec: float) -> dict:
        if not self.is_active: return {'rotation_y': 0, 'rotation_x': 0}
        
        elapsed_time_sec = (current_time_msec - self.start_time_msec) / 1000.0
        # Use a cosine wave for smooth start/end. It naturally goes from 1 to -1 and back.
        angle = 2 * math.pi * self.speed_hz * elapsed_time_sec
        wave_val = math.cos(angle)
        
        pan = wave_val * self.width
        
        return {'rotation_y': pan, 'rotation_x': 0}

class StaggerEffect(BaseEffect):
    def __init__(self, name: str, loop_palette_db_id: int, rate_hz: float, start_time_msec: float,
                 phase_offset_rad: float = 0.0, group_phase_offset_rad: float = 0.0,
                 source_effect_config: dict = None):
        super().__init__(name, loop_palette_db_id, start_time_msec, phase_offset_rad, group_phase_offset_rad, source_effect_config)
        self.rate_hz = max(0.1, rate_hz)
        self._last_toggle_time = 0
        self._is_on = True

    def get_value(self, current_time_msec: float) -> dict:
        if not self.is_active: return {'brightness': 0}
        
        elapsed_since_toggle = current_time_msec - self._last_toggle_time
        interval_ms = (1.0 / self.rate_hz) * 1000.0

        if elapsed_since_toggle > interval_ms:
            self._is_on = (random.random() > 0.5)
            self._last_toggle_time = current_time_msec
        
        return {'brightness': 100 if self._is_on else 0}

class Lumenante(QMainWindow):
    fixture_data_globally_changed = pyqtSignal(int, dict)
    theme_change_requires_restart = pyqtSignal(str)
    active_effects_changed = pyqtSignal()

    initialization_progress = pyqtSignal(str, int)


    def __init__(self):
        super().__init__()
        # Use a consistent path for settings file
        settings_path = str(get_app_data_path("settings.ini"))
        self.settings = QSettings(settings_path, QSettings.Format.IniFormat)
        self.registered_shortcuts = [] 
        self.keybind_map = {} # New registry for keybinds

        self.db_connection = None
        self.initialization_progress.emit("Initializing Database...", 10)
        self.init_database()
        self.initialization_progress.emit("Database Initialized.", 20)

        self.live_fixture_states = {}
        self.executor_fader_levels = {} 
        self._initialize_live_fixture_states_from_db()
        self.initialization_progress.emit("Live State Initialized.", 25)

        self.http_manager = RobloxHTTPManager(self, self)
        self.http_manager.status_updated.connect(self._update_roblox_status_label)
        self.http_manager.positions_reported.connect(self._on_roblox_positions_reported)
        self.http_manager.start()
        self.initialization_progress.emit("Network Server Started.", 30)

        _success, _preferred_pos = theme_manager.apply_theme_to_app(QApplication.instance(), theme_manager.get_saved_theme_name())
        if not _success:
            print("CRITICAL: No theme could be applied during pre-init. Application might look unstyled.")
            QApplication.instance().setStyleSheet("")
        self.initialization_progress.emit("Theme Applied.", 40)

        # Initialize Plugin Manager before UI so UI can access it
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.discover_plugins()
        self.initialization_progress.emit("Plugins Discovered.", 50)

        self.init_ui()
        self.initialization_progress.emit("UI Initialized.", 70)
        
        # Start Gamepad Manager
        self.gamepad_manager = GamepadManager(self)
        if GAMEPAD_AVAILABLE and self.settings.value('gamepad/enabled', True, type=bool):
            self.gamepad_manager.start()
            self.initialization_progress.emit("Gamepad Support Enabled.", 75)
        else:
            self.initialization_progress.emit("Gamepad Support Disabled.", 75)
        
        # Load enabled plugins AFTER UI is fully initialized
        self.plugin_manager.load_enabled_plugins()
        self.initialization_progress.emit("Plugins Loaded.", 80)
        
        self.load_app_settings()
        self.initialization_progress.emit("Settings Loaded.", 85)

        self.setup_signal_connections()
        self.theme_change_requires_restart.connect(self.handle_theme_restart_request)
        self.init_effect_engine()
        self.pre_blackout_brightness_states = {}
        self._load_and_register_keybinds()
        self.initialization_progress.emit("Keybinds Loaded.", 90)

        # --- Gamepad state ---
        self.gamepad_control_modes = ['intensity', 'zoom', 'focus', 'speed']
        self.gamepad_mode_index = 0
        self.joystick_pan_velocity = 0.0
        self.joystick_tilt_velocity = 0.0
        self.gamepad_pan_tilt_timer = QTimer(self)
        self.gamepad_pan_tilt_timer.setInterval(16) # ~60fps
        self.gamepad_pan_tilt_timer.timeout.connect(self._tick_gamepad_pan_tilt)
        
        # --- Selection resend timer ---
        self.selection_refresh_timer = QTimer(self)
        self.selection_refresh_timer.setInterval(1000) # 1 second
        self.selection_refresh_timer.timeout.connect(self._resend_current_selection)
        self.selection_refresh_timer.start()
        
        self._update_gamepad_status_label()
        self.initialization_progress.emit("Ready.", 100)
    
    def init_database(self):
        try:
            db_path = get_app_data_path("lumenante_v1_show.db")
            print(f"Database path: {db_path}")
            self.db_connection = sqlite3.connect(str(db_path))
            cursor = self.db_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            # --- Fixture Profile Table (with default) ---
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fixture_profiles'")
            if cursor.fetchone() is None:
                 cursor.execute('''
                    CREATE TABLE fixture_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        creator TEXT,
                        attributes_json TEXT NOT NULL
                    )
                ''')
            
            cursor.execute("SELECT COUNT(*) FROM fixture_profiles")
            profile_count = cursor.fetchone()[0]
            if profile_count == 0:
                print("No fixture profiles found. Creating default profiles.")
                default_moving_head = [
                    {"name": "Dimmer", "type": "continuous", "dmx_channel": 1},
                    {"name": "Pan", "type": "continuous", "dmx_channel": 2},
                    {"name": "Tilt", "type": "continuous", "dmx_channel": 3},
                    {"name": "Color_Red", "type": "continuous", "dmx_channel": 4},
                    {"name": "Color_Green", "type": "continuous", "dmx_channel": 5},
                    {"name": "Color_Blue", "type": "continuous", "dmx_channel": 6},
                    {"name": "Zoom", "type": "continuous", "dmx_channel": 7},
                    {"name": "Focus", "type": "continuous", "dmx_channel": 8},
                    {"name": "Gobo_Spin", "type": "continuous", "dmx_channel": 9},
                    {"name": "Strobe", "type": "continuous", "dmx_channel": 10}
                ]
                default_par = [
                    {"name": "Dimmer", "type": "continuous"},
                    {"name": "Color_Red", "type": "continuous"},
                    {"name": "Color_Green", "type": "continuous"},
                    {"name": "Color_Blue", "type": "continuous"},
                    {"name": "Zoom", "type": "continuous"}
                ]
                default_blinder = [
                    {"name": "Dimmer", "type": "continuous"},
                    {"name": "Strobe", "type": "continuous"}
                ]
                default_led_bar = [
                    {"name": "Dimmer", "type": "continuous"},
                    {"name": "Color_Red", "type": "continuous"},
                    {"name": "Color_Green", "type": "continuous"},
                    {"name": "Color_Blue", "type": "continuous"}
                ]
                default_profiles = [
                    ("Moving Head", "Lumenante", json.dumps(default_moving_head)),
                    ("PAR Can", "Lumenante", json.dumps(default_par)),
                    ("Blinder", "Lumenante", json.dumps(default_blinder)),
                    ("LED Bar", "Lumenante", json.dumps(default_led_bar)),
                ]
                cursor.executemany(
                    "INSERT INTO fixture_profiles (name, creator, attributes_json) VALUES (?, ?, ?)",
                    default_profiles
                )

            # --- Fixture Table Migration ---
            correct_fixture_schema = '''
                CREATE TABLE fixtures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, fid INTEGER NOT NULL, sfi INTEGER NOT NULL,
                    profile_id INTEGER NOT NULL, name TEXT NOT NULL,
                    x_pos REAL DEFAULT 0, y_pos REAL DEFAULT 0, z_pos REAL DEFAULT 0,
                    rotation_x REAL DEFAULT 0, rotation_y REAL DEFAULT 0, rotation_z REAL DEFAULT 0,
                    red INTEGER DEFAULT 255, green INTEGER DEFAULT 255, blue INTEGER DEFAULT 255,
                    brightness INTEGER DEFAULT 100, gobo_spin REAL DEFAULT 128.0,
                    zoom REAL DEFAULT 15.0, focus REAL DEFAULT 50.0,
                    shutter_strobe_rate REAL DEFAULT 0.0,
                    speed REAL DEFAULT 50.0,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(profile_id) REFERENCES fixture_profiles(id) ON DELETE CASCADE, UNIQUE(fid, sfi)
                )
            '''
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fixtures'")
            if cursor.fetchone() is None:
                cursor.execute(correct_fixture_schema)
            else:
                cursor.execute("PRAGMA table_info(fixtures)")
                fixture_cols = {info[1] for info in cursor.fetchall()}
                if 'speed' not in fixture_cols:
                    cursor.execute("ALTER TABLE fixtures ADD COLUMN speed REAL DEFAULT 50.0")

            # --- Other tables ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, preset_number TEXT NOT NULL UNIQUE, name TEXT,
                    data TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'All', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, cue_number TEXT NOT NULL UNIQUE, name TEXT,
                    trigger_time_s REAL NOT NULL, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS timeline_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, start_time REAL NOT NULL,
                    duration REAL DEFAULT 0, event_type TEXT NOT NULL, data TEXT NOT NULL,
                    target_type TEXT, target_id INTEGER, cue_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(cue_id) REFERENCES cues(id) ON DELETE SET NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fixture_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fixture_group_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, fixture_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(group_id) REFERENCES fixture_groups(id) ON DELETE CASCADE,
                    FOREIGN KEY(fixture_id) REFERENCES fixtures(id) ON DELETE CASCADE,
                    UNIQUE(group_id, fixture_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS loop_palettes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, config_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            self.db_connection.commit()
            print("Database initialized/updated successfully.")
        except sqlite3.Error as e:
            print(f"CRITICAL: Database initialization error: {e}")
            QMessageBox.critical(self, "Database Error", f"Could not initialize/update database: {e}\nThe application might not function correctly.")
            if self.db_connection: self.db_connection.rollback()
        except Exception as e:
            print(f"CRITICAL: Unexpected error during database initialization: {e}")
            if self.db_connection: self.db_connection.rollback()
            
    def _initialize_live_fixture_states_from_db(self):
        """Initializes the live state tracker from the database at startup."""
        self.live_fixture_states.clear()
        if not self.db_connection: return
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT * FROM fixtures")
            all_fixtures_data = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            for data_row in all_fixtures_data:
                fixture_dict = dict(zip(column_names, data_row))
                fixture_id = fixture_dict.get('id')
                if fixture_id is not None:
                    self.live_fixture_states[fixture_id] = fixture_dict
            print(f"Live fixture state tracker initialized with {len(self.live_fixture_states)} fixtures.")
        except Exception as e:
            QMessageBox.critical(self, "Live State Error", f"Could not initialize live fixture states from database: {e}")
            print(f"CRITICAL: Failed to init live fixture states: {e}")


    def init_effect_engine(self):
        self.active_effects = {}
        self.effect_timer = QTimer(self)
        self.EFFECT_TICK_INTERVAL_MS = 16 # Approx 60 FPS
        self.effect_timer.timeout.connect(self.tick_effects)
        self.elapsed_timer = QElapsedTimer()

    def start_effect_engine_if_needed(self):
        if self.active_effects and not (self.effect_timer and self.effect_timer.isActive()):
            self.elapsed_timer.start()
            self.effect_timer.start(self.EFFECT_TICK_INTERVAL_MS)
            print("Effect engine started.")

    def stop_effect_engine_if_idle(self):
        if not self.active_effects and self.effect_timer and self.effect_timer.isActive():
            self.effect_timer.stop()
            print("Effect engine stopped (idle).")

    def is_live_mode_active(self) -> bool:
        if self.settings_tab and hasattr(self.settings_tab, 'roblox_live_mode_checkbox'):
            return self.settings_tab.roblox_live_mode_checkbox.isChecked()
        return False

    def _update_roblox_status_label(self, message: str):
        if not hasattr(self, 'roblox_status_label'): return
        
        self.roblox_status_label.setText(f"ROBLOX: {message}")
        if "Listening" in message or "Connected" in message:
            self.roblox_status_label.setStyleSheet("color: #4CAF50;") # Green
        elif "OFF" in message:
            self.roblox_status_label.setStyleSheet("") # Default color
        else:
            self.roblox_status_label.setStyleSheet("color: #E57373;") # Red


    def tick_effects(self):
        if not self.active_effects:
            self.stop_effect_engine_if_idle()
            return

        current_time_msec = self.elapsed_timer.elapsed()
        effects_to_remove_for_fixture = {}

        for fixture_id, param_effects in list(self.active_effects.items()):
            for param_key, effect_instance in list(param_effects.items()):
                if not effect_instance.is_active:
                    if fixture_id not in effects_to_remove_for_fixture:
                        effects_to_remove_for_fixture[fixture_id] = []
                    effects_to_remove_for_fixture[fixture_id].append(param_key)
                    continue

                new_value_or_dict = effect_instance.get_value(current_time_msec)
                
                if isinstance(new_value_or_dict, dict):
                    updates_for_fixture = {}
                    for sub_param_key, sub_param_value in new_value_or_dict.items():
                        if sub_param_key in ["rotation_x", "rotation_y", "rotation_z"]:
                            sub_param_value = max(-180.0, min(180.0, sub_param_value))
                        elif sub_param_key == "brightness":
                            sub_param_value = max(0, min(100, int(sub_param_value)))
                        elif sub_param_key == "zoom":
                            sub_param_value = max(5.0, min(90.0, float(sub_param_value)))
                        elif sub_param_key == "focus":
                            sub_param_value = max(0.0, min(100.0, float(sub_param_value)))
                        updates_for_fixture[sub_param_key] = sub_param_value
                    if updates_for_fixture:
                        self.update_fixture_data_and_notify(fixture_id, updates_for_fixture)
                else:
                    new_value = new_value_or_dict
                    if param_key in ["rotation_x", "rotation_y", "rotation_z"]:
                        new_value = max(-180.0, min(180.0, new_value))
                    elif param_key == "brightness":
                        new_value = max(0, min(100, int(new_value)))
                    elif param_key == "zoom":
                        new_value = max(5.0, min(90.0, float(new_value)))
                    elif param_key == "focus":
                        new_value = max(0.0, min(100.0, float(new_value)))
                    self.update_fixture_data_and_notify(fixture_id, {param_key: new_value})


        for fix_id, params_to_clear in effects_to_remove_for_fixture.items():
            for p_key in params_to_clear:
                if fix_id in self.active_effects and p_key in self.active_effects[fix_id]:
                    del self.active_effects[fix_id][p_key]
            if fix_id in self.active_effects and not self.active_effects[fix_id]:
                del self.active_effects[fix_id]
        
        if not self.active_effects:
            self.stop_effect_engine_if_idle()


    def apply_loop_effect_to_fixtures(self, fixture_ids: list[int], loop_palette_db_id: int):
        if not fixture_ids:
            return

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name, config_json FROM loop_palettes WHERE id = ?", (loop_palette_db_id,))
            row = cursor.fetchone()
            if not row:
                QMessageBox.warning(self, "Loop Error", f"Loop Palette ID {loop_palette_db_id} not found in database.")
                return
            
            loop_name, config_json_str = row
            effect_configs_list = json.loads(config_json_str)

        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Error loading loop palette {loop_palette_db_id} for application: {e}")
            return

        current_time_msec = self.elapsed_timer.elapsed()
        num_fixtures = len(fixture_ids)

        for i, fixture_id in enumerate(fixture_ids):
            for effect_config_item in effect_configs_list:
                effect_type_str = effect_config_item.get("effect_type")
                db_target_param_key = effect_config_item.get("target_parameter")
                specific_config = effect_config_item.get("config", {})

                if not effect_type_str or not db_target_param_key:
                    print(f"Skipping invalid effect configuration in Loop Palette {loop_name} (ID: {loop_palette_db_id})")
                    continue

                active_effect_storage_key = db_target_param_key
                if effect_type_str in ["circle", "u_shape", "figure_8", "bally"]:
                    active_effect_storage_key = "pan_tilt_shape"
                elif effect_type_str == "stagger":
                    active_effect_storage_key = "dimmer_stagger"

                if fixture_id in self.active_effects and active_effect_storage_key in self.active_effects[fixture_id]:
                    existing_effect = self.active_effects[fixture_id][active_effect_storage_key]
                    if hasattr(existing_effect, 'loop_palette_db_id') and existing_effect.loop_palette_db_id == loop_palette_db_id and \
                       hasattr(existing_effect, 'source_effect_config') and existing_effect.source_effect_config == effect_config_item:
                        existing_effect.start_time_msec = current_time_msec
                        existing_effect.is_active = True
                        continue
                    else:
                        self.stop_effects_on_fixtures([fixture_id], param_key_to_stop=active_effect_storage_key)

                elif effect_type_str in ["circle", "u_shape", "figure_8", "bally"]:
                    self.stop_effects_on_fixtures([fixture_id], param_key_to_stop="rotation_y")
                    self.stop_effects_on_fixtures([fixture_id], param_key_to_stop="rotation_x")
                elif active_effect_storage_key == "pan_tilt_shape": # Current effect is Sine, but a Shape effect was active on this key
                    self.stop_effects_on_fixtures([fixture_id], param_key_to_stop="pan_tilt_shape")


                group_mode_str = specific_config.get("group_mode", "all_same_phase")
                wing_style_str = specific_config.get("wing_style", "none")
                
                calculated_fixture_specific_phase_offset_rad = 0.0
                
                if wing_style_str != "none" and wing_style_str is not None:
                    if wing_style_str == "symmetrical_2_wings" and num_fixtures > 1:
                        center_idx_float = (num_fixtures - 1) / 2.0
                        distance_from_center = abs(i - center_idx_float)
                        normalized_distance_to_end = distance_from_center / center_idx_float if center_idx_float > 0 else 0.0
                        calculated_fixture_specific_phase_offset_rad = normalized_distance_to_end * math.pi
                    
                    elif wing_style_str == "asymmetrical_2_wings" and num_fixtures > 1:
                        wing_center_percent = specific_config.get("wing_center_percent", 50.0)
                        center_idx_float = (num_fixtures - 1) * (wing_center_percent / 100.0)
                        distance_from_center = abs(i - center_idx_float)
                        # Normalize distance based on which side of the center it is on
                        if i < center_idx_float and center_idx_float > 0:
                            normalized_distance = distance_from_center / center_idx_float
                        elif i > center_idx_float and center_idx_float < (num_fixtures - 1):
                            normalized_distance = distance_from_center / ((num_fixtures - 1) - center_idx_float)
                        else:
                            normalized_distance = 0.0
                        calculated_fixture_specific_phase_offset_rad = normalized_distance * math.pi


                    elif wing_style_str == "symmetrical_3_wings" and num_fixtures >= 1:
                        if num_fixtures < 3:
                            calculated_fixture_specific_phase_offset_rad = 0.0
                        else:
                            parts = [num_fixtures // 3] * 3
                            remainder = num_fixtures % 3
                            for r_idx in range(remainder): parts[r_idx] += 1
                            n1, n2, n3 = parts[0], parts[1], parts[2]

                            if i < n1: 
                                norm_pos = i / (n1 - 1.0) if n1 > 1 else 0.0
                                calculated_fixture_specific_phase_offset_rad = norm_pos * math.pi 
                            elif i < n1 + n2: 
                                idx_in_part2 = i - n1
                                norm_pos = idx_in_part2 / (n2 - 1.0) if n2 > 1 else 0.0
                                calculated_fixture_specific_phase_offset_rad = (1.0 - norm_pos) * math.pi 
                            else: 
                                idx_in_part3 = i - (n1 + n2)
                                norm_pos = idx_in_part3 / (n3 - 1.0) if n3 > 1 else 0.0
                                calculated_fixture_specific_phase_offset_rad = norm_pos * math.pi
                else: # Handle group_mode if wing_style is "none"
                    if group_mode_str.startswith("block_"):
                        try:
                            block_size = int(group_mode_str.split('_')[1])
                            if block_size > 0:
                                block_index = i // block_size
                                num_blocks = math.ceil(num_fixtures / block_size)
                                phase_spread_per_block = (2 * math.pi) / num_blocks if num_blocks > 1 else 0
                                calculated_fixture_specific_phase_offset_rad = block_index * phase_spread_per_block
                        except (ValueError, IndexError):
                            print(f"Warning: Could not parse block size from group_mode '{group_mode_str}'. Defaulting.")
                            calculated_fixture_specific_phase_offset_rad = 0.0
                    elif group_mode_str == "spread_phase" and num_fixtures > 1:
                        calculated_fixture_specific_phase_offset_rad = (i / num_fixtures) * (2 * math.pi)

                effect_instance = None
                if effect_type_str == "sine_wave":
                    effect_instance = SineWaveEffect(
                        name=f"{loop_name}/{effect_type_str[:4]}@{db_target_param_key[:3]}",
                        loop_palette_db_id=loop_palette_db_id,
                        param_key=db_target_param_key,
                        speed_hz=specific_config.get("speed_hz", 0.2),
                        size=specific_config.get("size", 45.0),
                        center=specific_config.get("center", 0.0),
                        direction=specific_config.get("direction", "Forward"),
                        start_time_msec=current_time_msec,
                        phase_offset_rad=math.radians(specific_config.get("phase_degrees", 0.0)),
                        group_phase_offset_rad=calculated_fixture_specific_phase_offset_rad,
                        source_effect_config=effect_config_item
                    )
                elif effect_type_str == "circle":
                    circle_group_phase_offset = 0.0
                    if group_mode_str == "spread_phase" and num_fixtures > 1 : 
                        circle_group_phase_offset = (i / num_fixtures) * (2 * math.pi)

                    effect_instance = CircleEffect(
                        name=f"{loop_name}/{effect_type_str[:3]}",
                        loop_palette_db_id=loop_palette_db_id,
                        speed_hz=specific_config.get("speed_hz", 0.2),
                        radius_pan=specific_config.get("radius_pan", 45.0),
                        radius_tilt=specific_config.get("radius_tilt", 30.0),
                        center_pan=specific_config.get("center_pan", 0.0),
                        center_tilt=specific_config.get("center_tilt", 0.0),
                        start_time_msec=current_time_msec,
                        phase_offset_rad=math.radians(specific_config.get("phase_degrees", 0.0)),
                        group_phase_offset_rad=circle_group_phase_offset,
                        source_effect_config=effect_config_item
                    )
                elif effect_type_str == "u_shape":
                    effect_instance = UShapeEffect(
                        name=f"{loop_name}/{effect_type_str[:3]}",
                        loop_palette_db_id=loop_palette_db_id,
                        speed_hz=specific_config.get("speed_hz", 0.5),
                        width=specific_config.get("width", 90.0),
                        height=specific_config.get("height", 45.0),
                        orientation=specific_config.get("orientation", "Up"),
                        start_time_msec=current_time_msec
                    )
                elif effect_type_str == "figure_8":
                    effect_instance = Figure8Effect(
                        name=f"{loop_name}/{effect_type_str[:3]}",
                        loop_palette_db_id=loop_palette_db_id,
                        speed_hz=specific_config.get("speed_hz", 0.5),
                        width=specific_config.get("width", 90.0),
                        height=specific_config.get("height", 45.0),
                        start_time_msec=current_time_msec
                    )
                elif effect_type_str == "bally":
                     effect_instance = BallyEffect(
                        name=f"{loop_name}/{effect_type_str[:3]}",
                        loop_palette_db_id=loop_palette_db_id,
                        speed_hz=specific_config.get("speed_hz", 1.0),
                        width=specific_config.get("width", 90.0),
                        start_time_msec=current_time_msec
                    )
                elif effect_type_str == "stagger":
                     effect_instance = StaggerEffect(
                        name=f"{loop_name}/{effect_type_str[:3]}",
                        loop_palette_db_id=loop_palette_db_id,
                        rate_hz=specific_config.get("rate_hz", 10.0),
                        start_time_msec=current_time_msec
                    )

                if effect_instance:
                    if fixture_id not in self.active_effects:
                        self.active_effects[fixture_id] = {}
                    self.active_effects[fixture_id][active_effect_storage_key] = effect_instance
                    effect_instance.is_active = True

        self.start_effect_engine_if_needed()
        self.active_effects_changed.emit()


    def stop_effects_on_fixtures(self, fixture_ids: list[int],
                                 loop_palette_db_id_to_stop: int | None = None,
                                 param_key_to_stop: str | None = None):
        if not fixture_ids: return

        palettes_stopped_on_any_fixture = False

        for fixture_id in fixture_ids:
            if fixture_id not in self.active_effects:
                continue

            params_actually_cleared_this_fixture = []
            
            effects_to_iterate = list(self.active_effects[fixture_id].items())

            for p_key, effect_instance in effects_to_iterate:
                should_stop_this_effect = False
                if loop_palette_db_id_to_stop is not None:
                    if hasattr(effect_instance, 'loop_palette_db_id') and \
                       effect_instance.loop_palette_db_id == loop_palette_db_id_to_stop:
                        should_stop_this_effect = True
                elif param_key_to_stop:
                    if p_key == param_key_to_stop:
                        should_stop_this_effect = True
                    elif param_key_to_stop in ["rotation_x", "rotation_y"] and p_key == "pan_tilt_shape":
                        should_stop_this_effect = True
                    elif param_key_to_stop == "pan_tilt_shape" and isinstance(effect_instance, (CircleEffect, UShapeEffect, Figure8Effect, BallyEffect, StaggerEffect)):
                        should_stop_this_effect = True

                else: # If no specific loop or param key, stop all for this fixture_id
                    should_stop_this_effect = True

                if should_stop_this_effect:
                    effect_instance.is_active = False
                    params_actually_cleared_this_fixture.append(p_key)
            
            if params_actually_cleared_this_fixture:
                palettes_stopped_on_any_fixture = True

            for p_key_cleared in params_actually_cleared_this_fixture:
                effect_to_clear = self.active_effects[fixture_id].get(p_key_cleared)
                
                if effect_to_clear:
                    if isinstance(effect_to_clear, SineWaveEffect):
                        restored_value = effect_to_clear.center # Use the effect's defined center
                        # Clamp to valid ranges for specific parameters
                        if effect_to_clear.param_key == "brightness": restored_value = max(0, min(100, int(restored_value)))
                        elif effect_to_clear.param_key == "zoom": restored_value = max(5.0, min(90.0, float(restored_value)))
                        elif effect_to_clear.param_key == "focus": restored_value = max(0.0, min(100.0, float(restored_value)))
                        # For pan/tilt, ensure it's within typical -180 to 180
                        elif effect_to_clear.param_key in ["rotation_x", "rotation_y", "rotation_z"]:
                            restored_value = max(-180.0, min(180.0, float(restored_value)))
                        self.update_fixture_data_and_notify(fixture_id, {effect_to_clear.param_key: restored_value})
                    elif isinstance(effect_to_clear, StaggerEffect):
                        self.update_fixture_data_and_notify(fixture_id, {'brightness': 100})
                    elif isinstance(effect_to_clear, (CircleEffect, UShapeEffect, Figure8Effect, BallyEffect)):
                        center_pan = getattr(effect_to_clear, 'center_pan', 0.0)
                        center_tilt = getattr(effect_to_clear, 'center_tilt', 0.0)
                        restore_pan = max(-180.0, min(180.0, center_pan))
                        restore_tilt = max(-180.0, min(180.0, center_tilt))
                        self.update_fixture_data_and_notify(fixture_id, {
                            "rotation_y": restore_pan,
                            "rotation_x": restore_tilt
                        })
        
        if not self.active_effects: # check if any effects are active globally
            self.stop_effect_engine_if_idle()
        
        if palettes_stopped_on_any_fixture:
            self.active_effects_changed.emit()


    def handle_theme_restart_request(self, new_theme_name: str):
        QMessageBox.information(self, "Theme Change Applied",
                                f"The theme '{new_theme_name.replace('_', ' ').title()}' has been applied.\n"
                                "A restart is required for all changes (like tab positions) to take full effect.")

    def init_ui(self):
        self.setWindowTitle("Lumenante V1.1"); self.setMinimumSize(1200, 720); self.resize(1500, 850)
        script_dir = Path(__file__).resolve().parent
        app_icon_path = script_dir / "app_icon.ico"
        if app_icon_path.exists(): self.setWindowIcon(QIcon(str(app_icon_path)))
        
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget); root_layout.setContentsMargins(0, 0, 0, 0); root_layout.setSpacing(0)

        self.main_tab = MainTab(self)
        self.fixtures_tab = FixturesTab(self)
        self.fixture_groups_tab = FixtureGroupsTab(self)
        self.presets_tab = PresetsTab(self)
        self.loop_palettes_tab = LoopPalettesTab(self)
        self.timeline_tab = TimelineTab(self)
        self.video_sync_tab = VideoSyncTab(self)
        self.visualization_3d_tab = Visualization3DTab(self)
        self.settings_tab = SettingsTab(self)
        self.plugins_tab = PluginsTab(self)
        self.help_tab = HelpTab(self)
        
        self.create_main_header_area(root_layout)

        self.current_theme_tab_position = theme_manager.get_saved_theme_tab_position()

        self.tab_widget = QTabWidget(); self.tab_widget.setObjectName("MainTabWidget")
        self.tab_widget.setIconSize(QSize(20, 20))
        self.tab_widget.setTabPosition(self.current_theme_tab_position)


        content_body_widget = QWidget()
        content_body_layout = QHBoxLayout(content_body_widget)
        content_body_layout.setContentsMargins(0,0,0,0)
        content_body_layout.setSpacing(0)

        if self.current_theme_tab_position == QTabWidget.TabPosition.West or \
           self.current_theme_tab_position == QTabWidget.TabPosition.East:
            content_body_layout.addWidget(self.tab_widget, 0)
        else:
            content_body_layout.addWidget(self.tab_widget, 1)

        self.tab_widget.addTab(self.main_tab, "Layouts")
        self.tab_widget.addTab(self.fixtures_tab, "Patch & Fixtures")
        self.tab_widget.addTab(self.fixture_groups_tab, "Groups")
        self.tab_widget.addTab(self.presets_tab, "Presets")
        self.tab_widget.addTab(self.loop_palettes_tab, "Loops")
        self.tab_widget.addTab(self.timeline_tab, "Cues / Timeline")
        self.tab_widget.addTab(self.video_sync_tab, "Video Sync")
        self.tab_widget.addTab(self.visualization_3d_tab, "Stage 3D")
        self.tab_widget.addTab(self.settings_tab, "Setup")
        self.tab_widget.addTab(self.plugins_tab, "Plugins")
        self.tab_widget.addTab(self.help_tab, "Help")
        
        root_layout.addWidget(content_body_widget, 1)
        
        self.create_main_status_bar()
        
    def create_main_header_area(self, parent_layout: QVBoxLayout):
        header_frame = QFrame()
        header_frame.setObjectName("AppHeaderFrame")
        header_frame.setFixedHeight(45)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 0, 10, 0)

        app_title_label = QLabel("Lumenante")
        app_title_label.setObjectName("AppTitleLabel")
        header_layout.addWidget(app_title_label)

        self.layout_lock_button = QPushButton("Lock Layout")
        self.layout_lock_button.setCheckable(True)
        self.layout_lock_button.setChecked(False)
        self.layout_lock_button.toggled.connect(self.on_layout_lock_toggled)
        self.layout_lock_button.setFixedWidth(100)
        header_layout.addWidget(self.layout_lock_button)

        self.clear_selection_button = QPushButton("Clear Sel.")
        self.clear_selection_button.clicked.connect(self.clear_global_fixture_selection)
        self.clear_selection_button.setFixedWidth(80)
        header_layout.addWidget(self.clear_selection_button)

        self.globally_selected_fixture_label = QLabel("Selected Fixture: None")
        self.globally_selected_fixture_label.setObjectName("HeaderSubLabel")
        self.globally_selected_fixture_label.setFixedWidth(300)
        header_layout.addWidget(self.globally_selected_fixture_label)
        
        self.command_line_input = QLineEdit()
        self.command_line_input.setObjectName("MACommandLineInput")
        self.command_line_input.setPlaceholderText("Lumenante>")
        self.command_line_input.setMinimumWidth(200)
        self.command_line_input.returnPressed.connect(self._handle_command_line_input)
        header_layout.addWidget(self.command_line_input, 1)

        # Quick Group Selector
        self.group_selector_combo = QComboBox()
        self.group_selector_combo.setPlaceholderText("Select Group...")
        self.group_selector_combo.setMinimumWidth(150)
        self.group_selector_combo.activated.connect(self._on_group_selector_activated)
        header_layout.addWidget(self.group_selector_combo)
        
        # Quick Fixture Selector
        self.fixture_selector_combo = QComboBox()
        self.fixture_selector_combo.setPlaceholderText("Select Fixture...")
        self.fixture_selector_combo.setMinimumWidth(150)
        self.fixture_selector_combo.activated.connect(self._on_fixture_selector_activated)
        header_layout.addWidget(self.fixture_selector_combo)

        master_intensity_label = QLabel("Master:")
        master_intensity_label.setObjectName("HeaderSubLabel")
        header_layout.addWidget(master_intensity_label)

        self.master_fader = QSlider(Qt.Orientation.Horizontal)
        self.master_fader.setObjectName("MasterIntensityFader")
        self.master_fader.setRange(0, 100)
        self.master_fader.setValue(100)
        self.master_fader.setFixedWidth(160)
        self.master_fader.valueChanged.connect(self.handle_master_fader_change)
        header_layout.addWidget(self.master_fader)

        self.blackout_button = QPushButton("B.O.")
        self.blackout_button.setObjectName("BlackoutButtonHeader")
        self.blackout_button.setCheckable(True)
        self.blackout_button.setFixedWidth(60)
        header_layout.addWidget(self.blackout_button)
        
        parent_layout.addWidget(header_frame)
        
        self.populate_group_selector()
        self.populate_fixture_selector()
        self._update_header_tooltips_with_keybinds()

    def _update_header_tooltips_with_keybinds(self):
        """Sets tooltips for header buttons based on loaded keybinds."""
        base_bo_tooltip = "Toggle Blackout (All Fixtures Off/On)"
        bo_keybind = self.keybind_map.get('global.toggle_blackout', '')
        if bo_keybind:
            self.blackout_button.setToolTip(f"{base_bo_tooltip} ({bo_keybind})")
        else:
            self.blackout_button.setToolTip(base_bo_tooltip)

        base_cs_tooltip = "Clear the current fixture selection"
        cs_keybind = self.keybind_map.get('global.clear_selection', '')
        if cs_keybind:
            self.clear_selection_button.setToolTip(f"{base_cs_tooltip} ({cs_keybind})")
        else:
            self.clear_selection_button.setToolTip(base_cs_tooltip)

    def create_main_status_bar(self):
        self.status_bar = self.statusBar(); self.status_bar.setObjectName("AppStatusBar")
        
        self.gamepad_status_label = QLabel("Gamepad: Off")
        self.gamepad_status_label.setObjectName("StatusBarLabelGamepad")
        self.status_bar.addPermanentWidget(self.gamepad_status_label)
        
        self.roblox_status_label = QLabel("ROBLOX: Disconnected"); self.roblox_status_label.setObjectName("StatusBarLabelRoblox"); self.status_bar.addWidget(self.roblox_status_label)
    
    def _handle_command_line_input(self):
        if not hasattr(self, 'command_line_input') or not self.command_line_input: return
        
        command_text = self.command_line_input.text().strip()
        self.command_line_input.clear()
        if not command_text: return

        print(f"CMD: {command_text}")
        try:
            parts = shlex.split(command_text)
        except ValueError as e:
            QMessageBox.warning(self, "Command Syntax Error", f"Mismatched quotes in command: {e}")
            return
            
        if not parts: return
        cmd = parts[0].lower()

        try:
            if (cmd == "fixture" or cmd == "f") and len(parts) >= 2:
                selection_parts, attribute_parts = [], []
                at_found = False
                for part in parts[1:]:
                    if part.lower() == "at": at_found = True; continue
                    if not at_found: selection_parts.append(part)
                    else: attribute_parts.append(part)
                
                target_fixture_ids = self._parse_fixture_selection_string(selection_parts)

                self._select_fixtures_by_ids_from_cmd(target_fixture_ids)
                if attribute_parts: self._parse_and_apply_attributes(self.main_tab.globally_selected_fixture_ids_for_controls, attribute_parts)

            elif (cmd == "group" or cmd == "g") and len(parts) >= 2:
                self._select_group_by_id_from_cmd(int(parts[1]))
                if len(parts) > 3 and (parts[2].lower() == "at" or parts[2] == "@"):
                     attribute_parts = parts[3:]
                     self._parse_and_apply_attributes(self.main_tab.globally_selected_fixture_ids_for_controls, attribute_parts)

            elif cmd == "clearselection" or cmd == "cs":
                self.clear_global_fixture_selection(); print("CMD: Cleared selection.")
            
            elif cmd == "store" and len(parts) > 1 and parts[1].lower() == "preset" and len(parts) >= 3:
                preset_number = parts[2]
                name_parts = []
                preset_type = 'All'
                type_found = False
                
                # Iterate from part after preset_number
                for part in parts[3:]:
                    if part.lower().startswith('/type='):
                        preset_type = part.split('=', 1)[1]
                        type_found = True
                    elif not type_found:
                        name_parts.append(part)
                preset_name = " ".join(name_parts)
                
                selected_fixture_ids = self.main_tab.globally_selected_fixture_ids_for_controls
                self.store_preset(preset_number, preset_name, selected_fixture_ids, preset_type)


            elif cmd == "go" and len(parts) > 1 and parts[1].lower() == "cue" and len(parts) >= 3:
                cue_number = parts[2]
                self.timeline_tab.go_to_cue_by_number(cue_number)
            
            elif cmd == "label" and len(parts) > 2:
                label_type = parts[1].lower()
                item_number = parts[2]
                new_name = " ".join(parts[3:]) if len(parts) > 3 else ""
                if label_type == "preset":
                    self._label_preset_from_cmd(item_number, new_name)
                elif label_type == "cue":
                    self._label_cue_from_cmd(item_number, new_name)
                else:
                    QMessageBox.warning(self, "Command Error", f"Unknown label type: '{label_type}'. Use 'preset' or 'cue'.")
            
            else:
                QMessageBox.warning(self, "Command Error", f"Unrecognized command or incorrect parameters: '{command_text}'")
        
        except (ValueError, IndexError) as e:
            QMessageBox.warning(self, "Command Syntax Error", f"Invalid command syntax: '{command_text}'\nError: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Command Execution Error", f"Error processing command '{command_text}':\n{e}")
            print(f"Command error: {e}")

    def _parse_fixture_selection_string(self, selection_parts: list[str]) -> list[int]:
        """Parses a fixture selection string (e.g., ['1.1', 'thru', '1.8', '+', '2']) and returns a list of primary key IDs."""
        final_ids = set()
        i = 0
        while i < len(selection_parts):
            part = selection_parts[i]
            if part == '+':
                i += 1
                continue

            # Handle 'thru' ranges
            if i + 2 < len(selection_parts) and selection_parts[i+1].lower() == 'thru':
                start_str, end_str = part, selection_parts[i+2]
                
                start_fid, start_sfi = (int(p) for p in start_str.split('.')) if '.' in start_str else (int(start_str), None)
                end_fid, end_sfi = (int(p) for p in end_str.split('.')) if '.' in end_str else (int(end_str), None)

                if start_fid != end_fid:
                    QMessageBox.warning(self, "Command Error", "Range selections ('thru') must be within the same base Fixture ID (e.g., '1.1 thru 1.8').")
                    return []
                
                start_sfi_val = start_sfi if start_sfi is not None else 1
                end_sfi_val = end_sfi if end_sfi is not None else 9999 # A large number to get all

                query = "SELECT id FROM fixtures WHERE fid = ? AND sfi >= ? AND sfi <= ?"
                params = (start_fid, start_sfi_val, end_sfi_val)
                
                cursor = self.db_connection.cursor()
                cursor.execute(query, params)
                ids_in_range = {row[0] for row in cursor.fetchall()}
                final_ids.update(ids_in_range)
                
                i += 3 # Move past 'start thru end'
                continue

            # Handle single fixture or sub-fixture
            if '.' in part:
                fid, sfi = (int(p) for p in part.split('.'))
                query = "SELECT id FROM fixtures WHERE fid = ? AND sfi = ?"
                params = (fid, sfi)
            else:
                fid = int(part)
                query = "SELECT id FROM fixtures WHERE fid = ?"
                params = (fid,)

            cursor = self.db_connection.cursor()
            cursor.execute(query, params)
            ids_for_part = {row[0] for row in cursor.fetchall()}
            final_ids.update(ids_for_part)
            
            i += 1
        
        return sorted(list(final_ids))

            
    def get_params_for_preset_type(self, preset_type: str) -> list[str]:
        preset_type = preset_type.lower()
        params = {
            "dimmer": ["brightness"],
            "color": ["red", "green", "blue"],
            "position": ["rotation_x", "rotation_y", "rotation_z"],
            "gobo": ["gobo_spin"],
            "beam": ["zoom", "focus", "shutter_strobe_rate", "speed"],
        }
        if preset_type in params:
            return params[preset_type]
        # 'All' or unknown type returns all valid params
        return [
            "rotation_x", "rotation_y", "rotation_z", "red", "green", "blue", 
            "brightness", "gobo_spin", "zoom", "focus", "shutter_strobe_rate", "speed"
        ]

    def _insert_or_overwrite_preset(self, preset_number, preset_name, fixture_ids, preset_type):
        try:
            params_to_store = self.get_params_for_preset_type(preset_type)
            if not params_to_store:
                QMessageBox.warning(self, "Preset Error", f"Could not determine parameters for preset type '{preset_type}'.")
                return

            cols_to_select_str = ", ".join(['id'] + params_to_store)
            placeholders = ','.join(['?'] * len(fixture_ids))
            
            cursor = self.db_connection.cursor()
            cursor.execute(f"SELECT {cols_to_select_str} FROM fixtures WHERE id IN ({placeholders})", tuple(fixture_ids))
            fixtures_raw = cursor.fetchall()
            fixture_columns = [desc[0] for desc in cursor.description]

            preset_data_for_json = {
                str(row[fixture_columns.index('id')]): {
                    col: val for col, val in zip(fixture_columns, row) if col != 'id'
                } for row in fixtures_raw
            }

            if not preset_data_for_json:
                QMessageBox.warning(self, "Command Error", "Could not gather data from selected fixtures.")
                return

            cursor.execute("INSERT OR REPLACE INTO presets (id, preset_number, name, data, type) VALUES ((SELECT id FROM presets WHERE preset_number = ?), ?, ?, ?, ?)",
                           (preset_number, preset_number, preset_name, json.dumps(preset_data_for_json), preset_type))
            self.db_connection.commit()
            self.presets_tab.load_presets_from_db()
            print(f"CMD: Stored/Overwrote '{preset_type}' preset {preset_number} '{preset_name}' for {len(fixture_ids)} fixture(s).")
            return True # Indicate success
        except sqlite3.Error as e:
            QMessageBox.critical(self, "DB Error", f"Failed to store preset {preset_number}: {e}")
        except Exception as e_gen:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while storing the preset: {e_gen}")
        return False # Indicate failure

    def store_preset(self, preset_number: str, preset_name: str, fixture_ids: list[int], preset_type: str = 'All'):
        if not fixture_ids:
            QMessageBox.warning(self, "Command Error", "Cannot store preset: No fixtures selected.")
            return

        cursor = self.db_connection.cursor()
        cursor.execute("SELECT id, name FROM presets WHERE preset_number = ?", (preset_number,))
        existing_preset = cursor.fetchone()

        if existing_preset:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Preset Exists")
            msg_box.setText(f"Preset {preset_number} ('{existing_preset[1]}') already exists.")
            msg_box.setInformativeText("What would you like to do?")
            msg_box.setIcon(QMessageBox.Icon.Question)
            
            overwrite_btn = msg_box.addButton("Overwrite", QMessageBox.ButtonRole.YesRole)
            merge_btn = msg_box.addButton("Merge", QMessageBox.ButtonRole.ActionRole)
            create_new_btn = msg_box.addButton("Create New...", QMessageBox.ButtonRole.ActionRole)
            cancel_btn = msg_box.addButton(QMessageBox.StandardButton.Cancel)
            
            merge_btn.setEnabled(False) # Not implemented yet

            msg_box.setDefaultButton(cancel_btn)
            msg_box.exec()

            clicked_button = msg_box.clickedButton()
            if clicked_button == overwrite_btn:
                self._insert_or_overwrite_preset(preset_number, preset_name, fixture_ids, preset_type)
            elif clicked_button == merge_btn:
                QMessageBox.information(self, "Not Implemented", "Merge functionality is not yet available.")
            elif clicked_button == create_new_btn:
                self.presets_tab.create_new_preset()
        else:
            self._insert_or_overwrite_preset(preset_number, preset_name, fixture_ids, preset_type)

    def update_preset(self, preset_number: str, fixture_ids: list[int]):
        """Updates an existing preset with new values, preserving its name and type."""
        if not fixture_ids:
            QMessageBox.warning(self, "Command Error", "Cannot update preset: No fixtures selected.")
            return

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name, type FROM presets WHERE preset_number = ?", (preset_number,))
            existing_preset = cursor.fetchone()
            if not existing_preset:
                QMessageBox.warning(self, "Error", f"Preset {preset_number} not found for updating.")
                return
            
            original_name, original_type = existing_preset
            
            if self._insert_or_overwrite_preset(preset_number, original_name, fixture_ids, original_type):
                QMessageBox.information(self, "Preset Updated", f"Preset {preset_number} ('{original_name}') has been updated.")
        
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"An error occurred while updating preset {preset_number}: {e}")

    def _label_preset_from_cmd(self, preset_number, new_name):
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("UPDATE presets SET name = ? WHERE preset_number = ?", (new_name, preset_number))
            if cursor.rowcount == 0:
                QMessageBox.warning(self, "Command Error", f"Preset with number '{preset_number}' not found.")
                return
            self.db_connection.commit()
            self.presets_tab.load_presets_from_db()
            print(f"CMD: Labeled preset {preset_number} as '{new_name}'.")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "DB Error", f"Failed to label preset {preset_number}: {e}")
    
    def _label_cue_from_cmd(self, cue_number, new_name):
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("UPDATE cues SET name = ? WHERE cue_number = ?", (new_name, cue_number))
            if cursor.rowcount == 0:
                QMessageBox.warning(self, "Command Error", f"Cue with number '{cue_number}' not found.")
                return
            self.db_connection.commit()
            self.timeline_tab.refresh_event_list_and_timeline()
            print(f"CMD: Labeled cue {cue_number} as '{new_name}'.")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "DB Error", f"Failed to label cue {cue_number}: {e}")

    def _parse_and_apply_attributes(self, fixture_ids: list[int], attribute_parts: list[str]):
        if not fixture_ids or not attribute_parts:
            return

        params_to_update = {}
        try:
            i = 0
            while i < len(attribute_parts):
                attr_name = attribute_parts[i].lower()
                
                # Check for keyword-value pairs
                if attr_name == 'color' and i + 1 < len(attribute_parts):
                    color_name = attribute_parts[i+1].lower()
                    color_map = {
                        "red": (255,0,0), "green": (0,255,0), "blue": (0,0,255),
                        "yellow": (255,255,0), "cyan": (0,255,255), "magenta": (255,0,255),
                        "white": (255,255,255)
                    }
                    if color_name in color_map:
                        r, g, b = color_map[color_name]
                        params_to_update.update({'red': r, 'green': g, 'blue': b})
                    else:
                        QMessageBox.warning(self, "Command Error", f"Unknown color '{color_name}'.")
                        return
                    i += 2
                elif attr_name == 'speed' and i + 1 < len(attribute_parts):
                    value_str = attribute_parts[i+1].replace('%', '')
                    speed_val = float(value_str)
                    if 0 <= speed_val <= 100:
                        params_to_update['speed'] = speed_val
                    else:
                        QMessageBox.warning(self, "Command Error", "Speed value must be between 0 and 100.")
                        return
                    i += 2
                else: # Default to brightness if no keyword
                    value_str = attribute_parts[i].replace('%', '')
                    brightness = int(value_str)
                    if 0 <= brightness <= 100:
                        params_to_update['brightness'] = brightness
                    else:
                        QMessageBox.warning(self, "Command Error", "Brightness value must be between 0 and 100.")
                        return
                    i += 1
        except (ValueError, IndexError):
            QMessageBox.warning(self, "Command Syntax Error", f"Invalid attribute value in: '{' '.join(attribute_parts)}'")
            return

        if params_to_update:
            for fid in fixture_ids:
                self.update_fixture_data_and_notify(fid, params_to_update)
            print(f"CMD: Applied attributes {params_to_update} to {len(fixture_ids)} fixture(s).")


    def _select_fixtures_by_ids_from_cmd(self, fixture_ids: list[int]):
        if not fixture_ids:
            self.clear_global_fixture_selection()
            return

        try:
            cursor = self.db_connection.cursor()
            placeholders = ','.join(['?'] * len(fixture_ids))
            cursor.execute(f"SELECT id, name FROM fixtures WHERE id IN ({placeholders})", tuple(fixture_ids))
            valid_fixtures = cursor.fetchall()
            valid_ids = [row[0] for row in valid_fixtures]

            if not valid_ids:
                QMessageBox.warning(self, "Command Error", f"No valid fixtures found in selection: {fixture_ids}")
                return
            
            if len(valid_ids) < len(fixture_ids):
                 invalid_ids = set(fixture_ids) - set(valid_ids)
                 print(f"CMD Warning: The following fixture IDs were not found and ignored: {sorted(list(invalid_ids))}")

            self.main_tab.clear_all_global_selections()
            self.main_tab.globally_selected_fixture_ids_for_controls = valid_ids
            self.main_tab.global_fixture_selection_changed.emit(valid_ids)
            print(f"CMD: Selected {len(valid_ids)} fixture(s).")
        except Exception as e:
            QMessageBox.critical(self, "Command Error", f"Error selecting fixtures by ID: {e}")


    def _select_group_by_id_from_cmd(self, group_id: int):
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name FROM fixture_groups WHERE id = ?", (group_id,))
            group_row = cursor.fetchone()
            if not group_row:
                QMessageBox.warning(self, "Command Error", f"Group ID {group_id} not found.")
                return
            
            group_name = group_row[0]
            cursor.execute("SELECT fixture_id FROM fixture_group_mappings WHERE group_id = ?", (group_id,))
            fixture_ids_in_group = [row[0] for row in cursor.fetchall()]

            self.main_tab.clear_all_global_selections()
            self.main_tab.globally_selected_fixture_ids_for_controls = sorted(list(set(fixture_ids_in_group)))
            self.main_tab.globally_selected_group_name_for_display = group_name
            self.main_tab.global_fixture_selection_changed.emit(self.main_tab.globally_selected_fixture_ids_for_controls)
            print(f"CMD: Selected Group {group_id} ('{group_name}') with {len(fixture_ids_in_group)} fixtures.")

        except Exception as e:
            QMessageBox.critical(self, "Command Error", f"Error selecting group by ID: {e}")

    # --- Quick Selector Methods ---
    def populate_group_selector(self):
        self.group_selector_combo.blockSignals(True)
        current_data = self.group_selector_combo.currentData()
        self.group_selector_combo.clear()
        self.group_selector_combo.addItem("Select Group...", -1)
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id, name FROM fixture_groups ORDER BY name")
            for gid, name in cursor.fetchall():
                self.group_selector_combo.addItem(f"{name}", gid)
        except Exception as e:
            print(f"Error populating header group selector: {e}")
        
        idx = self.group_selector_combo.findData(current_data)
        self.group_selector_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.group_selector_combo.blockSignals(False)

    def populate_fixture_selector(self):
        self.fixture_selector_combo.blockSignals(True)
        current_data = self.fixture_selector_combo.currentData()
        self.fixture_selector_combo.clear()
        self.fixture_selector_combo.addItem("Select Fixture...", -1)
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id, name, fid, sfi FROM fixtures ORDER BY fid, sfi")
            for pk_id, name, fid, sfi in cursor.fetchall():
                self.fixture_selector_combo.addItem(f"{name} ({fid}.{sfi})", pk_id)
        except Exception as e:
            print(f"Error populating header fixture selector: {e}")

        idx = self.fixture_selector_combo.findData(current_data)
        self.fixture_selector_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.fixture_selector_combo.blockSignals(False)
        
    def _on_group_selector_activated(self, index: int):
        group_id = self.group_selector_combo.itemData(index)
        if group_id is not None and group_id != -1:
            self._select_group_by_id_from_cmd(group_id)
        else:
            self.clear_global_fixture_selection()
            
    def _on_fixture_selector_activated(self, index: int):
        fixture_id = self.fixture_selector_combo.itemData(index)
        if fixture_id is not None and fixture_id != -1:
            self._select_fixtures_by_ids_from_cmd([fixture_id])
        else:
            self.clear_global_fixture_selection()

    def setup_signal_connections(self):
        self.fixtures_tab.fixture_updated.connect(self.on_fixture_updated_from_tab)
        self.fixtures_tab.fixture_added.connect(self.on_fixture_added_from_tab)
        self.fixtures_tab.fixture_deleted.connect(self.on_fixture_deleted_from_tab)

        self.fixtures_tab.fixture_updated.connect(self.populate_fixture_selector)
        self.fixtures_tab.fixture_added.connect(self.populate_fixture_selector)
        self.fixtures_tab.fixture_deleted.connect(self.populate_fixture_selector)

        # Connect fixture changes to refresh layout lists immediately
        self.fixtures_tab.fixture_added.connect(lambda data: self.main_tab.refresh_dynamic_content())
        self.fixtures_tab.fixture_deleted.connect(lambda ids: self.main_tab.refresh_dynamic_content())


        self.fixtures_tab.fixture_updated.connect(lambda fid, data: self.fixture_groups_tab.refresh_all_data_and_ui())
        self.fixtures_tab.fixture_added.connect(lambda data: self.fixture_groups_tab.refresh_all_data_and_ui())
        self.fixtures_tab.fixture_deleted.connect(self.fixture_groups_tab.refresh_all_data_and_ui)

        self.fixture_groups_tab.fixture_groups_changed.connect(self.main_tab.refresh_dynamic_content)
        self.fixture_groups_tab.fixture_groups_changed.connect(self.timeline_tab.refresh_event_list_and_timeline)
        self.fixture_groups_tab.fixture_groups_changed.connect(self.populate_group_selector)

        self.loop_palettes_tab.loop_palettes_changed.connect(self.main_tab.refresh_dynamic_content)
        self.loop_palettes_tab.loop_palettes_changed.connect(lambda: self.settings_tab.populate_keybinds_table())


        self.presets_tab.preset_applied.connect(lambda preset_num: self.on_preset_applied_from_tab(preset_num))
        self.presets_tab.presets_changed.connect(self.main_tab.refresh_dynamic_content)
        self.presets_tab.presets_changed.connect(self.timeline_tab.refresh_event_list_and_timeline)
        self.presets_tab.presets_changed.connect(lambda: self.settings_tab.populate_keybinds_table())

        self.main_tab.preset_triggered.connect(lambda preset_num: self.on_preset_applied_from_tab(preset_num))
        self.main_tab.master_intensity_changed.connect(self.on_main_tab_master_intensity_set)
        self.main_tab.toggle_fixture_power_signal.connect(self.on_main_tab_toggle_fixture_power)
        self.main_tab.flash_fixture_signal.connect(self.on_main_tab_flash_fixture)
        self.main_tab.fixture_parameter_changed_from_area.connect(self.on_fixture_parameter_change_from_main_tab)
        self.main_tab.sequence_go_signal.connect(self.on_main_tab_sequence_go)
        self.main_tab.generic_slider_activated.connect(self.on_main_tab_generic_slider)
        self.main_tab.generic_color_activated.connect(self.on_main_tab_generic_color)
        self.main_tab.loop_palette_triggered.connect(self.on_main_tab_loop_palette_triggered)
        
        # New connection for Executor Faders
        self.main_tab.executor_fader_changed.connect(self._on_executor_fader_updated)

        # The global_fixture_selection_changed signal is handled by the MainTab class itself,
        # which then calls methods on the main_window to update header info. This avoids signal loops.
        self.main_tab.global_fixture_selection_changed.connect(self.main_tab.update_loop_palette_area_button_states)
        self.main_tab.global_fixture_selection_changed.connect(self.visualization_3d_tab.update_selection_visuals)
        self.main_tab.global_fixture_selection_changed.connect(self.main_tab.interactive_canvas.update_all_embedded_view_selections)
        self.main_tab.global_fixture_selection_changed.connect(self._handle_selection_for_roblox) # New connection for Roblox selection box
        self.active_effects_changed.connect(self.main_tab.update_loop_palette_area_button_states)

        self.fixture_data_globally_changed.connect(self.main_tab.on_global_fixture_data_changed)
        self.timeline_tab.event_triggered.connect(self.on_timeline_event_triggered)
        self.timeline_tab.cues_changed.connect(lambda: self.settings_tab.populate_keybinds_table())
        
        if hasattr(self.timeline_tab, 'handle_video_sync_cue_request'):
             self.video_sync_tab.request_add_cue_to_timeline.connect(self.timeline_tab.handle_video_sync_cue_request)
        else:
            print("Warning: TimelineTab does not have 'handle_video_sync_cue_request' slot yet.")
        
        if hasattr(self.settings_tab, 'live_mode_toggled'):
            self.settings_tab.live_mode_toggled.connect(self.http_manager.set_live_mode)
        if hasattr(self.settings_tab, 'keybinds_changed'):
            self.settings_tab.keybinds_changed.connect(self._load_and_register_keybinds)

        if GAMEPAD_AVAILABLE:
            self.gamepad_manager.joystick_moved.connect(self._on_joystick_moved)
            self.gamepad_manager.button_pressed.connect(self._on_gamepad_button_pressed)
            self.gamepad_manager.dpad_pressed.connect(self._on_gamepad_dpad_pressed)

    def _on_executor_fader_updated(self, group_id: int, value: int):
        """Slot to handle value changes from an Executor Fader."""
        self.executor_fader_levels[group_id] = value
        
        try:
            # Get all fixtures in this group
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM fixtures WHERE id IN (SELECT fixture_id FROM fixture_group_mappings WHERE group_id = ?)", (group_id,))
            for (fix_id,) in cursor.fetchall():
                self.update_fixture_data_and_notify(fix_id, {})
        
        except Exception as e:
            print(f"Error updating fixtures for executor fader group {group_id}: {e}")

    def load_app_settings(self):
        try:
            geometry_data = self.settings.value("MainWindow/geometry");
            if geometry_data: self.restoreGeometry(geometry_data)
            
            master_val = self.settings.value("Controls/masterFader", 100, type=int); self.master_fader.setValue(master_val)
            blackout_active = self.settings.value("Controls/blackoutActive", False, type=bool); self.blackout_button.setChecked(blackout_active)
            
            # This line loads the layout data from settings when the app starts
            layout_json_str = self.settings.value("MainTab/Layout_v3.6_Panning", "{}")
            if layout_json_str:
                try:
                    layout_data = json.loads(layout_json_str)
                    if isinstance(layout_data, dict):
                        self.main_tab.load_layout_from_data_dict(layout_data)
                    else:
                        print("Warning: Layout data from settings is not in the expected format (dict).")
                except json.JSONDecodeError:
                    print("Warning: Could not decode layout data from settings. It might be corrupted.")
            
            layout_locked = self.settings.value("Layout/locked", True, type=bool)
            self.layout_lock_button.setChecked(layout_locked)
            self.on_layout_lock_toggled(layout_locked)

            # Set initial state of the HTTP manager from saved settings
            live_mode_enabled = self.settings.value('roblox/live_mode_enabled', False, type=bool)
            self.settings_tab.roblox_live_mode_checkbox.setChecked(live_mode_enabled) # Sync UI
            self.http_manager.set_live_mode(live_mode_enabled) # Sync manager

            print("Application settings loaded.")
        except Exception as e: print(f"Error loading application settings: {e}")

    def save_app_settings(self):
        try:
            self.settings.setValue("MainWindow/geometry", self.saveGeometry())
            self.settings.setValue("Controls/masterFader", self.master_fader.value())
            self.settings.setValue("Controls/blackoutActive", self.blackout_button.isChecked())
            self.settings.setValue("Layout/locked", self.layout_lock_button.isChecked())
            self.settings.setValue("roblox/live_mode_enabled", self.http_manager._live_mode_enabled)

            # This line saves the layout data to settings when the app closes
            if hasattr(self, 'main_tab') and self.main_tab:
                self.main_tab.save_defined_areas_to_settings()

            print("Application settings saved.")
        except Exception as e: print(f"Error saving application settings: {e}")

    def on_layout_lock_toggled(self, checked: bool):
        self.main_tab.toggle_area_creation_mode(not checked)
        if checked:
            self.layout_lock_button.setText("Unlock Layout")
            self.layout_lock_button.setToolTip("Layout is Locked. Click to Unlock and enable area creation.")
        else:
            self.layout_lock_button.setText("Lock Layout")
            self.layout_lock_button.setToolTip("Layout is Unlocked. Click to Lock and disable area creation.")

    def clear_global_fixture_selection(self):
        if self.main_tab.globally_selected_fixture_ids_for_controls:
            self.stop_effects_on_fixtures(self.main_tab.globally_selected_fixture_ids_for_controls)
        self.main_tab.clear_all_global_selections()


    def handle_master_fader_change(self, value):
        if not self.blackout_button.isChecked():
            # When master fader moves, trigger an update for all fixtures
            for fixture_id in list(self.live_fixture_states.keys()):
                # Passing an empty dict is enough, as the function will re-calculate brightness
                self.update_fixture_data_and_notify(fixture_id, {})
            if self.main_tab.isVisible():
                self.main_tab.update_master_intensity_areas(value)

    def handle_blackout_toggle(self, checked):
        # Trigger an update for every fixture, which will apply the new blackout state
        for fixture_id in list(self.live_fixture_states.keys()):
            self.update_fixture_data_and_notify(fixture_id, {})
        
        if self.main_tab.isVisible():
            self.main_tab.update_master_intensity_areas(self.master_fader.value() if not checked else 0)

    def update_fixture_data_and_notify(self, fixture_id: int, partial_update_data: dict):
        if fixture_id not in self.live_fixture_states:
            return

        try:
            # STEP 1: Update the database with the raw, unmodulated values.
            if partial_update_data:
                cursor = self.db_connection.cursor()
                set_clauses = [f"{key} = ?" for key in partial_update_data.keys()]
                values = list(partial_update_data.values()) + [fixture_id]
                sql = f"UPDATE fixtures SET {', '.join(set_clauses)} WHERE id = ?"
                cursor.execute(sql, tuple(values))
                self.db_connection.commit()
            
            # STEP 2: Update the internal "source of truth" state with raw values.
            self.live_fixture_states[fixture_id].update(partial_update_data)
            
            # STEP 3: Create a fresh copy of the full state to calculate the final output.
            final_output_state = self.live_fixture_states[fixture_id].copy()
            
            # STEP 4: Calculate the final, modulated brightness for output.
            base_brightness = float(final_output_state.get('brightness', 0))
            modulated_brightness = base_brightness * (self.master_fader.value() / 100.0)
            
            group_id = self.get_group_for_fixture(fixture_id)
            if group_id and group_id in self.executor_fader_levels:
                modulated_brightness *= (self.executor_fader_levels[group_id] / 100.0)

            if self.blackout_button.isChecked():
                modulated_brightness = 0
                
            final_brightness_int = int(round(modulated_brightness))
            
            # Update the brightness ONLY in our outgoing packet.
            final_output_state['brightness'] = final_brightness_int

            # STEP 5: Send the complete, modulated packet to the HTTP manager.
            # Create a clean dict for Roblox, removing unnecessary keys.
            roblox_packet = {k: v for k, v in final_output_state.items() if k not in ['id', 'created_at', 'comment', 'profile_id']}
            fixture_fid = final_output_state.get('fid')
            if fixture_fid is not None:
                self.http_manager.add_update(fixture_fid, roblox_packet)
            
            # STEP 6: Notify internal UI elements about the change, sending the final *output* state.
            if self.fixtures_tab.isVisible():
                self.fixtures_tab.refresh_fixtures()
            
            self.visualization_3d_tab.update_fixture(fixture_id, final_output_state)
            
            self.fixture_data_globally_changed.emit(fixture_id, final_output_state)

        except sqlite3.Error as e_sql:
            print(f"SQL Error in update_fixture_data_and_notify for fixture {fixture_id}: {e_sql}")
            QMessageBox.critical(self, "DB Update Error", f"Could not update fixture {fixture_id}: {e_sql}")
        except Exception as e_gen:
            print(f"Generic Error in update_fixture_data_and_notify for fixture {fixture_id}: {e_gen}")

    def get_group_for_fixture(self, fixture_id: int) -> int | None:
        """Helper to get the first group a fixture belongs to. Returns None if not in any group."""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT group_id FROM fixture_group_mappings WHERE fixture_id = ? LIMIT 1", (fixture_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error getting group for fixture {fixture_id}: {e}")
            return None

    def on_fixture_updated_from_tab(self, fixture_id: int, data_from_dialog: dict): self.update_fixture_data_and_notify(fixture_id, data_from_dialog)
    def on_fixture_parameter_change_from_main_tab(self, fixture_id: int, params_to_update: dict): self.update_fixture_data_and_notify(fixture_id, params_to_update)
    
    def on_fixture_added_from_tab(self, new_fixture_data_with_id: dict):
        self._initialize_live_fixture_states_from_db() # Re-init to include the new fixture
        self.visualization_3d_tab.update_all_fixtures()
        self.main_tab.refresh_dynamic_content()
        self.fixture_groups_tab.refresh_all_data_and_ui()
        self.timeline_tab.refresh_event_list_and_timeline()

        fixture_id = new_fixture_data_with_id.get('id');
        if fixture_id: 
            self.fixture_data_globally_changed.emit(fixture_id, self.live_fixture_states.get(fixture_id, {}))


    def on_fixture_deleted_from_tab(self, deleted_fixture_ids: list):
        self.stop_effects_on_fixtures(deleted_fixture_ids)
        for fid in deleted_fixture_ids:
            self.live_fixture_states.pop(fid, None)

        self.fixture_groups_tab.refresh_all_data_and_ui()
        self.visualization_3d_tab.update_all_fixtures()
        self.timeline_tab.refresh_event_list_and_timeline()
        self.main_tab.refresh_dynamic_content()

        current_selection = self.main_tab.globally_selected_fixture_ids_for_controls
        new_selection = [fid for fid in current_selection if fid not in deleted_fixture_ids]
        if len(new_selection) < len(current_selection):
            self.main_tab.globally_selected_fixture_ids_for_controls = new_selection
            self.main_tab.global_fixture_selection_changed.emit(new_selection)
            if not new_selection:
                self.main_tab.update_active_group_selection_display(None)


    def on_preset_applied_from_tab(self, preset_number: str, target_type:str = "master", target_id: int | None = None):
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT data, type FROM presets WHERE preset_number = ?", (preset_number,))
            result = cursor.fetchone()
            if not (result and result[0]):
                QMessageBox.warning(self, "Preset Not Found", f"Preset '{preset_number}' could not be loaded.")
                return

            preset_fixture_data_map = json.loads(result[0])
            preset_type = result[1]
            updated_ids_count = 0
            
            params_to_apply_keys = self.get_params_for_preset_type(preset_type)
            
            fixture_ids_to_update_this_call = []
            
            if target_type == "master":
                fixture_ids_to_update_this_call = self.main_tab.globally_selected_fixture_ids_for_controls
                if not fixture_ids_to_update_this_call:
                    fixture_ids_to_update_this_call = [int(fix_id_str) for fix_id_str in preset_fixture_data_map.keys()]
            elif target_type == "fixture" and target_id is not None:
                if str(target_id) in preset_fixture_data_map: fixture_ids_to_update_this_call = [target_id]
            elif target_type == "group" and target_id is not None:
                cursor.execute("SELECT fixture_id FROM fixture_group_mappings WHERE group_id = ?", (target_id,))
                group_fixture_ids = {row[0] for row in cursor.fetchall()}
                fixture_ids_to_update_this_call = [
                    int(fix_id_str) for fix_id_str in preset_fixture_data_map.keys() if int(fix_id_str) in group_fixture_ids
                ]

            for fixture_id_to_process in fixture_ids_to_update_this_call:
                fixture_id_str = str(fixture_id_to_process)
                if fixture_id_str in preset_fixture_data_map:
                    source_params = preset_fixture_data_map[fixture_id_str]
                    params_to_apply_now = {key: source_params[key] for key in params_to_apply_keys if key in source_params}

                    if not params_to_apply_now: continue
                    
                    self.update_fixture_data_and_notify(fixture_id_to_process, params_to_apply_now)
                    updated_ids_count += 1
            
            target_info_str = f"globally to {updated_ids_count} fixture(s)" if target_type == "master" else \
                              f"to fixture ID {target_id}" if target_type == "fixture" else \
                              f"to group ID {target_id} ({updated_ids_count} fixtures)" if target_type == "group" else \
                              "to unknown target"
            
            if updated_ids_count > 0: print(f"Preset '{preset_number}' applied {target_info_str}.")
        except Exception as e: QMessageBox.critical(self, "Preset Error", f"Failed to apply preset '{preset_number}': {e}")


    def on_main_tab_master_intensity_set(self, value: int): self.master_fader.setValue(value)
    def on_main_tab_toggle_fixture_power(self, area_id: str, fixture_id: int, desired_state_is_on: bool = False):
        try:
            cursor = self.db_connection.cursor(); cursor.execute("SELECT brightness, name FROM fixtures WHERE id = ?", (fixture_id,)); result = cursor.fetchone()
            if not result: QMessageBox.warning(self, "Error", f"Fixture ID {fixture_id} not found for toggle."); return
            current_brightness, fixture_name = result; new_brightness = 0; last_on_key = f"FixtureData/{fixture_id}/lastOnBrightness"
            if current_brightness > 0: self.settings.setValue(last_on_key, current_brightness); new_brightness = 0
            else: new_brightness = self.settings.value(last_on_key, 100, type=int)
            self.update_fixture_data_and_notify(fixture_id, {'brightness': new_brightness})
        except Exception as e: QMessageBox.critical(self, "Toggle Error", f"Error toggling fixture {fixture_id}: {e}")

    def on_main_tab_flash_fixture(self, area_id: str, fixture_id: int, is_pressed: bool):
        flash_brightness_on = 100; original_brightness_key = f"FixtureData/{fixture_id}/flashOriginalBrightness"
        try:
            if is_pressed:
                cursor = self.db_connection.cursor(); cursor.execute("SELECT brightness FROM fixtures WHERE id = ?", (fixture_id,)); current_brightness_tuple = cursor.fetchone()
                if not current_brightness_tuple: print(f"Flash Error: Fixture ID {fixture_id} not found for press."); return
                self.settings.setValue(original_brightness_key, current_brightness_tuple[0]); self.update_fixture_data_and_notify(fixture_id, {'brightness': flash_brightness_on})
            else: original_brightness = self.settings.value(original_brightness_key, 0, type=int); self.update_fixture_data_and_notify(fixture_id, {'brightness': original_brightness})
        except Exception as e: print(f"Error during flash for fixture {fixture_id}: {e}")

    def on_main_tab_sequence_go(self, area_id: str): QMessageBox.information(self, "Sequence Control", f"Sequence GO triggered from Area {area_id[:6]}. (Sequencer not yet implemented)")

    def on_main_tab_generic_slider(self, area_id: str, value: object, slider_type_str: str):
        target_fixture_ids = self.main_tab.globally_selected_fixture_ids_for_controls
        if not target_fixture_ids:
            return
            
        param_key = self.main_tab._map_slider_type_to_param_key(slider_type_str.lower())
        if not param_key:
            return

        actual_value = float(value) if isinstance(value, (float, int)) else 0.0
        
        # Apply the value to all selected fixtures.
        for target_fixture_id in target_fixture_ids:
            self.update_fixture_data_and_notify(target_fixture_id, {param_key: actual_value})

    def on_main_tab_generic_color(self, area_id: str, color: QColor, control_type: str):
        target_fixture_ids_to_update = []
        if control_type == "ColorPicker":
            target_fixture_ids_to_update = self.main_tab.globally_selected_fixture_ids_for_controls
        
        if not target_fixture_ids_to_update:
            if control_type == "ColorPicker":
                 QMessageBox.information(self, "No Selection", "No fixtures selected to apply color from Color Picker.")
            return
        
        params_to_update = {'red': color.red(), 'green': color.green(), 'blue': color.blue()}
        for target_fixture_id in target_fixture_ids_to_update:
            self.update_fixture_data_and_notify(target_fixture_id, params_to_update)
        
        if control_type == "ColorPicker":
            for area in self.main_tab.interactive_canvas.defined_areas:
                if area.id == area_id and area.function_type == "Color Picker":
                    area.data['current_color'] = color.name()
                    break
    
    def on_main_tab_loop_palette_triggered(self, area_id: str, loop_palette_db_id: int, is_active: bool):
        selected_fixture_ids = self.main_tab.globally_selected_fixture_ids_for_controls
        if not selected_fixture_ids:
            QMessageBox.information(self, "No Selection", "Select fixtures to apply/stop loop palette.")
            # self.main_tab.revert_loop_palette_button_state(area_id, loop_palette_db_id, not is_active)
            return

        if is_active:
            self.apply_loop_effect_to_fixtures(selected_fixture_ids, loop_palette_db_id)
        else:
            self.stop_effects_on_fixtures(selected_fixture_ids, loop_palette_db_id_to_stop=loop_palette_db_id)
        
    def _handle_selection_for_roblox(self, selected_ids: list[int]):
        """Sends the current selection state to Roblox."""
        if not self.is_live_mode_active():
            return
        
        fids_to_send = []
        for db_id in selected_ids:
            if db_id in self.live_fixture_states:
                fids_to_send.append(self.live_fixture_states[db_id].get('fid'))
        
        payload = {
            "command": "update_selection",
            "selected_ids": list(set(fids_to_send)) # Send unique FIDs
        }
        # Use a special key (-2) to send commands that aren't fixture parameter updates.
        self.http_manager.add_update(-2, payload)

    def _resend_current_selection(self):
        """Periodically called by a timer to keep Roblox selection in sync."""
        if self.is_live_mode_active():
            selected_ids = self.main_tab.globally_selected_fixture_ids_for_controls
            self._handle_selection_for_roblox(selected_ids)

    def update_header_selected_info(self):
        fixture_ids = self.main_tab.globally_selected_fixture_ids_for_controls
        group_name = self.main_tab.globally_selected_group_name_for_display

        if group_name and fixture_ids:
            self.globally_selected_fixture_label.setText(f"Sel Grp: {group_name} ({len(fixture_ids)} Fx)")
            self.globally_selected_fixture_label.setToolTip(f"Group '{group_name}' selected, containing {len(fixture_ids)} fixtures.")
        elif not fixture_ids:
            self.globally_selected_fixture_label.setText("Selected: None")
            self.globally_selected_fixture_label.setToolTip("No fixtures or group currently selected for control.")
        elif len(fixture_ids) == 1:
            fixture_id = fixture_ids[0]
            try:
                cursor = self.db_connection.cursor()
                cursor.execute("SELECT fid, sfi, name FROM fixtures WHERE id = ?", (fixture_id,))
                result = cursor.fetchone()
                fid, sfi, name = result if result else (fixture_id, '?', "N/A")
                display_name = f"{name} ({fid}.{sfi})"
                self.globally_selected_fixture_label.setText(f"Sel Fix: {display_name}")
                self.globally_selected_fixture_label.setToolTip(f"Fixture: {name} ({fid}.{sfi}) - ID: {fixture_id}")
            except Exception as e:
                print(f"Error fetching name for globally selected fixture ID {fixture_id}: {e}")
                self.globally_selected_fixture_label.setText(f"Sel Fix ID: {fixture_id} (Error)")
                self.globally_selected_fixture_label.setToolTip(f"Fixture ID: {fixture_id} (Error fetching name)")
        else:
            self.globally_selected_fixture_label.setText(f"Sel Fix: Multiple ({len(fixture_ids)})")
            self.globally_selected_fixture_label.setToolTip(f"{len(fixture_ids)} fixtures selected.")


    def on_timeline_event_triggered(self, event_data: dict):
        # This now handles instantaneous events. Fades are handled within TimelineTab.
        event_type = event_data.get('type')
        payload = event_data.get('data', {})
        target_type = event_data.get('target_type', 'master')
        target_id = event_data.get('target_id')
        
        if event_type == 'preset':
            preset_number = payload.get('preset_number')
            if preset_number:
                self.on_preset_applied_from_tab(str(preset_number), target_type=target_type, target_id=target_id)
        elif event_type == 'blackout':
            current_blackout_state = self.blackout_button.isChecked()
            action = payload.get('action', 'toggle')
            if action == 'on' and not current_blackout_state:
                self.blackout_button.setChecked(True)
            elif action == 'off' and current_blackout_state:
                self.blackout_button.setChecked(False)
            elif action == 'toggle':
                self.blackout_button.setChecked(not current_blackout_state)
        elif event_type != 'brightness': # Brightness is handled by TimelineTab's internal fade logic
            params_to_update = {}
            if event_type == 'color' and 'color_hex' in payload:
                color = QColor(payload['color_hex'])
                params_to_update = {'red': color.red(), 'green': color.green(), 'blue': color.blue()}
            elif event_type == 'pan' and 'value' in payload:
                params_to_update = {'rotation_y': payload['value']}
            elif event_type == 'tilt' and 'value' in payload:
                params_to_update = {'rotation_x': payload['value']}
            elif event_type == 'zoom' and 'value' in payload:
                params_to_update = {'zoom': payload['value']}
            elif event_type == 'focus' and 'value' in payload:
                params_to_update = {'focus': payload['value']}
            elif event_type == 'gobo' and 'value' in payload:
                params_to_update = {'gobo_spin': payload['value']}
            # ... add other direct parameter events here ...
            
            if params_to_update:
                target_fixture_ids = self.timeline_tab._get_fixture_ids_for_target(target_type, target_id)
                for fid in target_fixture_ids:
                    self.update_fixture_data_and_notify(fid, params_to_update)

    def _on_joystick_moved(self, axis: str, value: float):
        """Handles joystick movements from the GamepadManager."""
        if not self.settings.value('gamepad/enabled', True, type=bool):
            self.joystick_pan_velocity = 0.0
            self.joystick_tilt_velocity = 0.0
            if self.gamepad_pan_tilt_timer.isActive():
                self.gamepad_pan_tilt_timer.stop()
            return
            
        mode = self.settings.value('gamepad/mode', 0, type=int) # 0 for single, 1 for dual
        
        # Dual-joystick mode: Right stick X for Pan, Left stick Y for Tilt
        if mode == 1:
            if axis == 'ABS_RX':
                self.joystick_pan_velocity = value
            elif axis == 'ABS_Y': # Left Stick Y
                self.joystick_tilt_velocity = value
        # Single-joystick mode: Right stick X/Y for Pan/Tilt
        else:
            if axis == 'ABS_RX':
                self.joystick_pan_velocity = value
            elif axis == 'ABS_RY':
                self.joystick_tilt_velocity = value
        
        is_moving = self.joystick_pan_velocity != 0.0 or self.joystick_tilt_velocity != 0.0
        if is_moving and not self.gamepad_pan_tilt_timer.isActive():
            self.gamepad_pan_tilt_timer.start()
        elif not is_moving and self.gamepad_pan_tilt_timer.isActive():
            self.gamepad_pan_tilt_timer.stop()
            
    def _on_gamepad_button_pressed(self, code: str):
        """Handles button presses from the GamepadManager."""
        if not self.settings.value('gamepad/enabled', True, type=bool): return
        
        if code == 'BTN_MODE':
            self.gamepad_mode_index = (self.gamepad_mode_index + 1) % len(self.gamepad_control_modes)
            self._update_gamepad_status_label()

    def _on_gamepad_dpad_pressed(self, axis: str, value: int):
        """Handles D-pad presses for fine control of the selected parameter."""
        if not self.settings.value('gamepad/enabled', True, type=bool): return
        
        selected_ids = self.main_tab.globally_selected_fixture_ids_for_controls
        if not selected_ids: return

        mode_name = self.gamepad_control_modes[self.gamepad_mode_index]
        param_map = {
            'intensity': 'brightness', 'zoom': 'zoom', 'focus': 'focus', 'speed': 'speed'
        }
        param_key = param_map.get(mode_name)
        if not param_key: return

        # Define steps and bounds
        steps = {'intensity': (1, 10), 'zoom': (0.5, 5), 'focus': (1, 10), 'speed': (1, 10)}
        bounds = {'intensity': (0, 100), 'zoom': (5, 90), 'focus': (0, 100), 'speed': (0, 100)}
        small_step, large_step = steps[mode_name]
        min_bound, max_bound = bounds[mode_name]

        delta = 0
        if axis == 'ABS_HAT0X': # Left/Right
            delta = small_step * value # value is -1 or 1
        elif axis == 'ABS_HAT0Y': # Up/Down
            delta = large_step * -value # Y-axis is often inverted, -1 is up

        for fixture_id in selected_ids:
            if fixture_id in self.live_fixture_states:
                current_value = self.live_fixture_states[fixture_id].get(param_key, 0.0)
                new_value = max(min_bound, min(max_bound, current_value + delta))
                self.update_fixture_data_and_notify(fixture_id, {param_key: new_value})

    def _update_gamepad_status_label(self):
        """Updates the status bar to show the current gamepad control mode."""
        if not hasattr(self, 'gamepad_status_label'): return
        
        if not self.settings.value('gamepad/enabled', True, type=bool):
            self.gamepad_status_label.setText("Gamepad: Disabled")
            self.gamepad_status_label.setStyleSheet("color: #999;")
            return
            
        mode_name = self.gamepad_control_modes[self.gamepad_mode_index].capitalize()
        self.gamepad_status_label.setText(f"Gamepad Control: {mode_name}")
        self.gamepad_status_label.setStyleSheet("") # Default color

    def _tick_gamepad_pan_tilt(self):
        """Called by a QTimer to apply continuous pan/tilt movement."""
        selected_ids = self.main_tab.globally_selected_fixture_ids_for_controls
        if not selected_ids:
            return

        sensitivity = self.settings.value('gamepad/sensitivity', 2.0, type=float)
        invert_tilt = self.settings.value('gamepad/invert_tilt', True, type=bool)
        tilt_multiplier = -1.0 if invert_tilt else 1.0

        pan_delta = self.joystick_pan_velocity * sensitivity
        tilt_delta = self.joystick_tilt_velocity * sensitivity * tilt_multiplier
        
        if pan_delta == 0.0 and tilt_delta == 0.0:
            return

        for fixture_id in selected_ids:
            if fixture_id in self.live_fixture_states:
                current_pan = self.live_fixture_states[fixture_id].get('rotation_y', 0.0)
                current_tilt = self.live_fixture_states[fixture_id].get('rotation_x', 0.0)

                # New additive logic for unbounded pan
                new_pan = current_pan + pan_delta
                
                # Tilt remains clamped
                new_tilt = max(-90.0, min(90.0, current_tilt + tilt_delta))

                update_params = {}
                if pan_delta != 0.0:
                    update_params['rotation_y'] = new_pan
                if tilt_delta != 0.0:
                    update_params['rotation_x'] = new_tilt
                
                if update_params:
                    self.update_fixture_data_and_notify(fixture_id, update_params)


    def _on_executor_fader_updated(self, group_id: int, value: int):
        """Slot to handle value changes from an Executor Fader."""
        self.executor_fader_levels[group_id] = value
        
        try:
            # Get all fixtures in this group
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM fixtures WHERE id IN (SELECT fixture_id FROM fixture_group_mappings WHERE group_id = ?)", (group_id,))
            for (fix_id,) in cursor.fetchall():
                self.update_fixture_data_and_notify(fix_id, {})
        
        except Exception as e:
            print(f"Error updating fixtures for executor fader group {group_id}: {e}")

    def closeEvent(self, event):
        self.plugin_manager.shutdown_plugins() # Shutdown plugins before other managers
        
        # Stop threads cleanly
        if GAMEPAD_AVAILABLE and self.gamepad_manager.isRunning():
            self.gamepad_manager.stop()
            print("Gamepad manager stop signal sent.")
        
        if self.effect_timer and self.effect_timer.isActive():
            self.effect_timer.stop()
            print("Effect engine stopped on close.")
        
        if hasattr(self, 'video_sync_tab') and self.video_sync_tab:
            self.video_sync_tab.shutdown_player()
        
        if self.selection_refresh_timer.isActive():
            self.selection_refresh_timer.stop()
        
        if hasattr(self, 'http_manager') and self.http_manager.isRunning():
            self.http_manager.stop()
            # No .wait() call here, as it blocks the GUI and causes the non-responsive state.
            # The stop signal is enough to initiate a clean shutdown on the other thread.
            print("HTTP manager stop signal sent.")

        self.save_app_settings();
        if self.db_connection:
            try: self.db_connection.close(); print("Database connection closed.")
            except Exception as e: print(f"Error closing database: {e}")
        super().closeEvent(event)

    def request_roblox_positions(self):
        """Sends a command to the HTTP buffer to request positions from Roblox."""
        QMessageBox.information(self, "Requesting Positions",
                                "A request has been sent to your running ROBLOX game to provide fixture positions.\n\n"
                                "Please ensure the game is unpaused. Positions will be updated shortly.")
        self.http_manager.add_update(-1, {"command": "get_positions"})

    def _on_roblox_positions_reported(self, positions_data: dict):
        """Slot to handle the position data received from Roblox."""
        updated_count = 0
        newly_patched_fids = []
        not_found_count = 0
        auto_patch_enabled = self.settings.value('roblox/auto_patch_enabled', True, type=bool)
        
        default_profile_id = None
        if auto_patch_enabled:
            try:
                cursor = self.db_connection.cursor()
                cursor.execute("SELECT id FROM fixture_profiles WHERE name = 'PAR Can'")
                result = cursor.fetchone()
                if result:
                    default_profile_id = result[0]
                else: # Fallback to first available profile
                    cursor.execute("SELECT id FROM fixture_profiles LIMIT 1")
                    result = cursor.fetchone()
                    if result: default_profile_id = result[0]
            except Exception as e:
                print(f"Could not find a default profile for auto-patching: {e}")

        try:
            cursor = self.db_connection.cursor()
            for fid_str, pos_list in positions_data.items():
                try:
                    fixture_fid = int(fid_str)
                    if isinstance(pos_list, list) and len(pos_list) == 3:
                        x, y, z = float(pos_list[0]), float(pos_list[1]), float(pos_list[2])
                        
                        cursor.execute("SELECT id FROM fixtures WHERE fid = ?", (fixture_fid,))
                        existing_fixture = cursor.fetchone()

                        if existing_fixture:
                            cursor.execute("UPDATE fixtures SET x_pos=?, y_pos=?, z_pos=? WHERE fid=?", (x, y, z, fixture_fid))
                            updated_count += cursor.rowcount
                        elif auto_patch_enabled and default_profile_id:
                            cursor.execute("INSERT INTO fixtures (fid, sfi, profile_id, name, x_pos, y_pos, z_pos) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                           (fixture_fid, 1, default_profile_id, f"Roblox Fx {fixture_fid}", x, y, z))
                            newly_patched_fids.append(fixture_fid)
                        else:
                            not_found_count += 1
                except (ValueError, TypeError):
                    print(f"Warning: Could not parse fixture ID '{fid_str}' or its position data.")

            if updated_count > 0 or newly_patched_fids:
                self.db_connection.commit()
                
                # Build summary message
                summary_lines = []
                if updated_count > 0: summary_lines.append(f"Successfully updated positions for {updated_count} fixture instance(s).")
                if newly_patched_fids: summary_lines.append(f"Auto-patched {len(newly_patched_fids)} new fixture(s): {newly_patched_fids}")
                if not_found_count > 0: summary_lines.append(f"{not_found_count} fixture ID(s) reported by Roblox were not found in the patch.")
                QMessageBox.information(self, "Import Successful", "\n".join(summary_lines))
                
                # Refresh relevant UI
                self._initialize_live_fixture_states_from_db()
                self.fixtures_tab.refresh_fixtures()
                self.visualization_3d_tab.update_all_fixtures()
                self.populate_fixture_selector()
                self.main_tab.refresh_dynamic_content()
            else:
                 QMessageBox.warning(self, "Import Failed",
                                     "No matching fixtures were found to update. "
                                     "Ensure your patched fixture IDs (FID) match the names of the models in Roblox (e.g., FID 1 matches model 'Fix1').")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"An error occurred while updating fixture positions: {e}")
            self.db_connection.rollback()
            
    def export_show_data(self, file_path: str):
        show_data = {}
        try:
            cursor = self.db_connection.cursor()
            
            # Create a fixture ID-to-Name map for portability
            cursor.execute("SELECT id, name FROM fixtures")
            fixture_id_to_name_map = {row[0]: row[1] for row in cursor.fetchall()}
            if not fixture_id_to_name_map:
                print("No fixtures to build ID-to-name map for export.")

            cursor.execute("SELECT name, creator, attributes_json FROM fixture_profiles")
            show_data['fixture_profiles'] = [{'name': row[0], 'creator': row[1], 'attributes_json': json.loads(row[2])} for row in cursor.fetchall()]

            cursor.execute("SELECT f.*, fp.name as profile_name FROM fixtures f JOIN fixture_profiles fp ON f.profile_id = fp.id")
            fixture_cols = [desc[0] for desc in cursor.description]
            show_data['fixtures'] = [dict(zip(fixture_cols, row)) for row in cursor.fetchall()]

            # Export presets using fixture names instead of IDs
            cursor.execute("SELECT preset_number, name, data, type FROM presets")
            presets_export = []
            for p_num, p_name, p_data_json, p_type in cursor.fetchall():
                p_data_by_id = json.loads(p_data_json)
                p_data_by_name = {fixture_id_to_name_map.get(int(fix_id), f"UNKNOWN_FIXTURE_ID_{fix_id}"): params 
                                  for fix_id, params in p_data_by_id.items() if int(fix_id) in fixture_id_to_name_map}
                presets_export.append({'preset_number': p_num, 'name': p_name, 'data': p_data_by_name, 'type': p_type})
            show_data['presets'] = presets_export

            cursor.execute("SELECT id, cue_number, name, trigger_time_s, comment FROM cues")
            cue_cols = ['id', 'cue_number', 'name', 'trigger_time_s', 'comment']
            show_data['cues'] = [dict(zip(cue_cols, row)) for row in cursor.fetchall()]

            cursor.execute("SELECT name, start_time, duration, event_type, data, target_type, target_id, cue_id FROM timeline_events")
            event_cols = ['name', 'start_time', 'duration', 'event_type', 'data', 'target_type', 'target_id', 'cue_id']
            show_data['timeline_events'] = [dict(zip(event_cols, row)) for row in cursor.fetchall()]

            layout_json_str = self.settings.value("MainTab/Layout_v3.6_Panning", "{}")
            show_data['main_tab_layout'] = json.loads(layout_json_str) if layout_json_str else {}
            
            # Export groups using fixture names instead of IDs
            cursor.execute("SELECT id, name FROM fixture_groups")
            fixture_groups_export = []
            for group_id, group_name in cursor.fetchall():
                cursor.execute("SELECT fixture_id FROM fixture_group_mappings WHERE group_id = ?", (group_id,))
                fixture_names_in_group = [fixture_id_to_name_map.get(row[0], f"UNKNOWN_FIXTURE_ID_{row[0]}") 
                                          for row in cursor.fetchall() if row[0] in fixture_id_to_name_map]
                fixture_groups_export.append({'name': group_name, 'fixture_names': fixture_names_in_group})
            show_data['fixture_groups'] = fixture_groups_export

            cursor.execute("SELECT id, name, config_json FROM loop_palettes")
            show_data['loop_palettes'] = [{'name': row[1], 'config_json': json.loads(row[2])} for row in cursor.fetchall()]

            show_data['appearance_theme'] = theme_manager.get_saved_theme_name()
            show_data['appearance_theme_tab_position'] = int(theme_manager.get_saved_theme_tab_position().value)

            with open(file_path, 'w') as f:
                json.dump(show_data, f, indent=2)
            QMessageBox.information(self, "Export Successful", f"Show data exported to {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export show data: {e}")
            print(f"Export error: {e}")

    def import_show_data(self, file_path: str):
        try:
            with open(file_path, 'r') as f:
                show_data = json.load(f)

            # --- Stop any current state before clearing DB ---
            self.stop_effects_on_fixtures(list(self.live_fixture_states.keys()))
            self.active_effects.clear()
            self.clear_global_fixture_selection()

            cursor = self.db_connection.cursor()
            
            # --- Clear existing data ---
            tables_to_clear = ["timeline_events", "cues", "fixture_group_mappings", "fixture_groups", 
                               "presets", "loop_palettes", "fixtures", "fixture_profiles"]
            for table in tables_to_clear:
                cursor.execute(f"DELETE FROM {table}")
            self.db_connection.commit()

            # --- Import Fixture Profiles ---
            profile_name_to_id_map = {}
            if 'fixture_profiles' in show_data:
                for profile in show_data['fixture_profiles']:
                    creator_val = profile.get('creator') or profile.get('manufacturer')
                    cursor.execute("INSERT INTO fixture_profiles (name, creator, attributes_json) VALUES (?, ?, ?)",
                                   (profile['name'], creator_val, json.dumps(profile['attributes_json'])))
                    profile_name_to_id_map[profile['name']] = cursor.lastrowid
            
            # --- Import Fixtures ---
            fixture_name_to_id_map = {}
            if 'fixtures' in show_data:
                for fix_data in show_data['fixtures']:
                    profile_name = fix_data.pop('profile_name', 'Generic')
                    profile_id = profile_name_to_id_map.get(profile_name)
                    if profile_id is None:
                        generic_id_query = cursor.execute("SELECT id FROM fixture_profiles WHERE name = 'Generic'").fetchone()
                        profile_id = generic_id_query[0] if generic_id_query else 1
                    fix_data['profile_id'] = profile_id
                    cursor.execute("PRAGMA table_info(fixtures)")
                    db_cols = {info[1] for info in cursor.fetchall()}
                    cols_for_insert = [col for col in fix_data.keys() if col in db_cols]
                    values_for_insert = [fix_data[col] for col in cols_for_insert]
                    placeholders = ', '.join(['?'] * len(cols_for_insert))
                    insert_sql = f"INSERT INTO fixtures ({', '.join(cols_for_insert)}) VALUES ({placeholders})"
                    cursor.execute(insert_sql, tuple(values_for_insert))
                    fixture_name_to_id_map[fix_data['name']] = cursor.lastrowid
            
            # --- Import Groups (using name mapping) ---
            if 'fixture_groups' in show_data:
                for group_data in show_data['fixture_groups']:
                    cursor.execute("INSERT INTO fixture_groups (name) VALUES (?)", (group_data['name'],))
                    group_db_id = cursor.lastrowid
                    if 'fixture_names' in group_data:
                        for fix_name in group_data['fixture_names']:
                            fix_id = fixture_name_to_id_map.get(fix_name)
                            if fix_id:
                                cursor.execute("INSERT INTO fixture_group_mappings (group_id, fixture_id) VALUES (?, ?)", (group_db_id, fix_id))
            
            # --- Import Presets (using name mapping) ---
            if 'presets' in show_data:
                for preset in show_data['presets']:
                    p_data_by_name = preset.get('data', {})
                    p_data_by_id = {str(fixture_name_to_id_map.get(fix_name)): params 
                                    for fix_name, params in p_data_by_name.items() if fix_name in fixture_name_to_id_map}
                    cursor.execute("INSERT INTO presets (preset_number, name, data, type) VALUES (?, ?, ?, ?)",
                                   (preset['preset_number'], preset.get('name'), json.dumps(p_data_by_id), preset.get('type', 'All')))

            # --- Import Cues, Events, Loops ---
            if 'cues' in show_data:
                for cue_data in show_data['cues']: cursor.execute("INSERT INTO cues (cue_number, name, trigger_time_s, comment) VALUES (?, ?, ?, ?)", (cue_data['cue_number'], cue_data.get('name'), cue_data['trigger_time_s'], cue_data.get('comment')))
            if 'timeline_events' in show_data:
                for event in show_data['timeline_events']: cursor.execute("INSERT INTO timeline_events (name, start_time, duration, event_type, data, target_type, target_id, cue_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (event['name'], event['start_time'], event['duration'], event['event_type'], json.dumps(event.get('data', {})), event.get('target_type', 'master'), event.get('target_id'), event.get('cue_id')))
            if 'loop_palettes' in show_data:
                for lp_data in show_data['loop_palettes']: cursor.execute("INSERT INTO loop_palettes (name, config_json) VALUES (?, ?)",(lp_data['name'], json.dumps(lp_data.get('config_json', []))))

            self.db_connection.commit()
            
            # --- Refresh Application State ---
            self._initialize_live_fixture_states_from_db()
            if 'main_tab_layout' in show_data and self.main_tab: self.main_tab.load_layout_from_data_dict(show_data['main_tab_layout'])
            
            QMessageBox.information(self, "Import Successful", f"Show data imported from {file_path}. Application UI is now refreshing.")
            
            # --- Refresh all UI tabs ---
            self.fixtures_tab.refresh_fixtures()
            self.presets_tab.load_presets_from_db()
            self.loop_palettes_tab.loop_palettes_changed.emit()
            self.timeline_tab.refresh_event_list_and_timeline()
            self.fixture_groups_tab.refresh_all_data_and_ui()
            self.visualization_3d_tab.update_all_fixtures()
            self.main_tab.refresh_dynamic_content()
            self.populate_group_selector()
            self.populate_fixture_selector()
            self.clear_global_fixture_selection()

        except json.JSONDecodeError:
            QMessageBox.critical(self, "Import Error", "Failed to decode JSON from the show file. The file may be corrupted.")
            if self.db_connection: self.db_connection.rollback()
        except sqlite3.Error as e_sql:
            QMessageBox.critical(self, "DB Import Error", f"Error importing data into database: {e_sql}")
            if self.db_connection: self.db_connection.rollback()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import show data: {e}")
            print(f"Show import error: {e}")
            
    def _load_and_register_keybinds(self):
        """Reads keybinds from settings and creates QShortcut objects."""
        # First, disable and clear any previously registered shortcuts
        for shortcut in self.registered_shortcuts:
            shortcut.setEnabled(False)
            shortcut.setParent(None)
            shortcut.deleteLater()
        self.registered_shortcuts.clear()
        self.keybind_map.clear()

        settings = self.settings
        settings.beginGroup("keybinds")
        for action_id_raw in settings.childKeys():
            action_id = action_id_raw.replace("_", ".")
            key_sequence_str = settings.value(action_id_raw, "", type=str)
            self.keybind_map[action_id_raw] = key_sequence_str # Populate the registry
            if key_sequence_str:
                key_sequence = QKeySequence(key_sequence_str)
                shortcut = QShortcut(key_sequence, self)
                shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
                # Use a lambda to pass the action_id to the handler
                shortcut.activated.connect(lambda action=action_id: self._handle_shortcut_activated(action))
                self.registered_shortcuts.append(shortcut)
        settings.endGroup()
        
        self._update_header_tooltips_with_keybinds()
        print(f"Loaded and registered {len(self.registered_shortcuts)} keybinds.")
    
    def _handle_shortcut_activated(self, action_id: str):
        """Central handler for all registered keybinds."""
        print(f"Shortcut activated: {action_id}")
        parts = action_id.split('.')
        action_type = parts[0]
        
        try:
            if action_type == 'global':
                if parts[1] == 'clear_selection': self.clear_global_fixture_selection()
                elif parts[1] == 'toggle_blackout': self.blackout_button.toggle()
            elif action_type == 'timeline':
                if parts[1] == 'go_next_cue': self.timeline_tab._go_to_next_cue()
                elif parts[1] == 'go_prev_cue': self.timeline_tab._go_to_previous_cue()
                elif parts[1] == 'toggle_playback': self.timeline_tab.toggle_playback()
                elif parts[1] == 'stop_playback': self.timeline_tab.stop_playback()
            elif action_type == 'preset':
                if parts[1] == 'apply' and len(parts) > 2:
                    preset_num = ".".join(parts[2:])
                    self.on_preset_applied_from_tab(preset_num)
            elif action_type == 'loop':
                if parts[1] == 'toggle' and len(parts) > 2:
                    loop_id = int(parts[2])
                    self._toggle_loop_palette_from_keybind(loop_id)
            elif action_type == 'cue':
                if parts[1] == 'go' and len(parts) > 2:
                    cue_num = ".".join(parts[2:])
                    self.timeline_tab.go_to_cue_by_number(cue_num)
        except (IndexError, ValueError) as e:
            print(f"Error handling shortcut for action '{action_id}': {e}")

    def _toggle_loop_palette_from_keybind(self, loop_palette_db_id: int):
        """Helper to toggle a loop palette on the current selection."""
        selected_fixture_ids = self.main_tab.globally_selected_fixture_ids_for_controls
        if not selected_fixture_ids:
            QMessageBox.information(self, "Keybind Info", "Select fixtures to toggle a loop palette.")
            return

        is_active_on_any_selected = any(
            loop_palette_db_id == effect.loop_palette_db_id
            for fid in selected_fixture_ids
            if fid in self.active_effects
            for effect in self.active_effects[fid].values()
            if hasattr(effect, 'loop_palette_db_id')
        )
        
        if is_active_on_any_selected:
            self.stop_effects_on_fixtures(selected_fixture_ids, loop_palette_db_id_to_stop=loop_palette_db_id)
        else:
            self.apply_loop_effect_to_fixtures(selected_fixture_ids, loop_palette_db_id)

class CustomSplashScreen(QSplashScreen):
    def __init__(self, pixmap: QPixmap):
        super().__init__(pixmap)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setGeometry(
            10, pixmap.height() - 30,
            pixmap.width() - 20, 20
        )
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 5px;
                text-align: center;
                background-color: #333;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #0078D7;
                width: 10px;
                margin: 0.5px;
            }
        """)
        self.progress_bar.setMaximum(100)

    def show_message_and_progress(self, message: str, progress: int):
        super().showMessage(message, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, Qt.GlobalColor.white)
        self.progress_bar.setValue(progress)
        QApplication.processEvents()

def main():
    # Set AppUserModelID for Windows Taskbar icon
    if sys.platform == "win32":
        import ctypes
        myappid = u'lumenante.v1.1.0' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    
    splash_pixmap_path = BASE_PATH / "splash_logo.png"
    if not splash_pixmap_path.exists():
        temp_pixmap = QPixmap(480, 280)
        temp_pixmap.fill(QColor(30,30,35))
        painter = QPainter(temp_pixmap)
        font = QFont("Arial", 20, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("lightgray"))
        painter.drawText(temp_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Lumenante\nLoading...")
        painter.end()
        splash_pixmap = temp_pixmap
    else:
        splash_pixmap = QPixmap(str(splash_pixmap_path))

    splash = CustomSplashScreen(splash_pixmap)
    splash.show()
    QApplication.processEvents()

    splash.show_message_and_progress("Initializing Application...", 5)

    if OPENGL_AVAILABLE:
        try:
            glutInit([])
            print("Global glutInit([]) attempted at script start.")
            splash.show_message_and_progress("Initializing OpenGL...", 10)
        except ImportError:
            print("PyOpenGL GLUT bindings not found (main). GLUT drawing functions will likely not be available.")
        except Exception as e:
            print(f"Error during global initial glutInit in main: {e}. GLUT features might be unstable.")
    else:
        splash.show_message_and_progress("OpenGL Unavailable. Skipping GL Init...", 10)


    app.setApplicationName("Lumenante"); app.setOrganizationName("Lumenante"); app.setApplicationVersion("1.0.0")
    
    splash.show_message_and_progress("Loading Theme...", 20)
    _apply_success, _ = theme_manager.apply_theme_to_app(app, theme_manager.get_saved_theme_name())
    if not _apply_success:
        print("Initial theme styling application failed.")
        
    splash.show_message_and_progress("Initializing Main Window...", 30)
    window = Lumenante()
    
    splash.show_message_and_progress("Finalizing...", 95)

    window.show()
    splash.finish(window)
    sys.exit(app.exec())

if __name__ == '__main__': main()
