# theme_manager.py
import os
import json # Added for manifest parsing
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QTabWidget
from PyQt6.QtCore import QSettings

THEMES_SUBDIR = "themes"
DEFAULT_THEME_NAME = "default_dark" 
DEFAULT_TAB_POSITION = QTabWidget.TabPosition.North

def get_themes_dir() -> Path:
    """Returns the absolute path to the themes directory."""
    script_dir = Path(__file__).resolve().parent
    return script_dir / THEMES_SUBDIR

def list_available_themes() -> list[str]:
    """
    Scans the themes directory and returns a list of available theme names
    (filenames without .qss extension).
    """
    themes_dir = get_themes_dir()
    available_themes = []
    if themes_dir.exists() and themes_dir.is_dir():
        for file_path in themes_dir.glob("*.qss"):
            available_themes.append(file_path.stem)
    
    if not available_themes and DEFAULT_THEME_NAME not in available_themes:
        print(f"Warning: No themes found in {themes_dir}. Defaulting to internal or none.")
    elif DEFAULT_THEME_NAME not in available_themes and available_themes:
        print(f"Warning: Default theme '{DEFAULT_THEME_NAME}.qss' not found in {themes_dir}.")
    
    if DEFAULT_THEME_NAME in available_themes:
        available_themes.remove(DEFAULT_THEME_NAME)
        available_themes.insert(0, DEFAULT_THEME_NAME)
    elif not available_themes: 
         available_themes.append(DEFAULT_THEME_NAME)

    return sorted(list(set(available_themes)))

def load_theme_qss_content(theme_name: str) -> str | None:
    """
    Loads the QSS content from a theme file.
    Returns the QSS string or None if the file is not found or cannot be read.
    """
    themes_dir = get_themes_dir()
    theme_file = themes_dir / f"{theme_name}.qss"
    if theme_file.exists() and theme_file.is_file():
        try:
            with open(theme_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error loading theme file '{theme_file}': {e}")
            return None
    else:
        print(f"Theme file not found: {theme_file}")
        return None

def get_theme_preferred_tab_position(theme_name: str) -> QTabWidget.TabPosition:
    """
    Reads the preferred tab position from a theme's manifest file (theme_name.manifest.json).
    Defaults to DEFAULT_TAB_POSITION if manifest is not found or key is missing.
    """
    themes_dir = get_themes_dir()
    manifest_file = themes_dir / f"{theme_name}.manifest.json"
    
    preferred_position = DEFAULT_TAB_POSITION

    if manifest_file.exists() and manifest_file.is_file():
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
                position_str = manifest_data.get("tabPosition", "").lower()
                if position_str == "west":
                    preferred_position = QTabWidget.TabPosition.West
                elif position_str == "east":
                    preferred_position = QTabWidget.TabPosition.East
                elif position_str == "south":
                    preferred_position = QTabWidget.TabPosition.South
                elif position_str == "north":
                    preferred_position = QTabWidget.TabPosition.North
                # Silently ignore invalid values, will use default
        except Exception as e:
            print(f"Error reading or parsing theme manifest '{manifest_file}': {e}")
            # Fallback to default if manifest is malformed
    
    # Ensure default theme also has a manifest or explicit default
    if theme_name == DEFAULT_THEME_NAME and not manifest_file.exists():
        return DEFAULT_TAB_POSITION # Explicitly return default for the default theme if no manifest
    
    # Special handling for ma_onpc_style if no manifest, assume West for backward compatibility
    # with previous hardcoding, but a manifest is preferred.
    if theme_name == "ma_onpc_style" and not manifest_file.exists():
        print(f"Warning: Theme 'ma_onpc_style' is missing a manifest. Defaulting tabPosition to West for this theme.")
        return QTabWidget.TabPosition.West
        
    return preferred_position


def apply_theme_to_app(app_instance: QApplication, theme_name: str) -> tuple[bool, QTabWidget.TabPosition]:
    """
    Applies the specified theme to the QApplication instance.
    Falls back to the default theme if the specified theme cannot be loaded.
    Saves the applied theme name and its preferred tab position to QSettings.
    Returns a tuple: (success_boolean, preferred_tab_position_for_this_theme).
    """
    qss_content = load_theme_qss_content(theme_name)
    applied_theme_name = theme_name
    
    if qss_content is None:
        if theme_name != DEFAULT_THEME_NAME:
            print(f"Theme '{theme_name}' QSS not found. Attempting default '{DEFAULT_THEME_NAME}'.")
            qss_content = load_theme_qss_content(DEFAULT_THEME_NAME)
            applied_theme_name = DEFAULT_THEME_NAME
        
        if qss_content is None: # If default also fails
            print(f"CRITICAL: Failed to load QSS for '{theme_name}' and default '{DEFAULT_THEME_NAME}'. No stylesheet applied.")
            app_instance.setStyleSheet("")
            # Return default tab position even if styling fails, so app structure is consistent
            return False, get_theme_preferred_tab_position(DEFAULT_THEME_NAME) 

    # At this point, qss_content is not None (it's either for the requested theme or default)
    app_instance.setStyleSheet(qss_content)
    print(f"Theme QSS for '{applied_theme_name}' applied.")
    
    # Get preferred tab position for the theme whose QSS was actually loaded
    preferred_tab_pos = get_theme_preferred_tab_position(applied_theme_name)

    # Save the successfully applied theme name and its tab position preference
    settings = QSettings('Lumenante', 'AppSettings_v1.0')
    settings.setValue("Appearance/currentTheme", applied_theme_name)
    settings.setValue("Appearance/currentThemeTabPosition", preferred_tab_pos.value)
    return True, preferred_tab_pos

def get_saved_theme_name() -> str:
    """
    Retrieves the saved theme name from QSettings.
    """
    settings = QSettings('Lumenante', 'AppSettings_v1.0')
    return settings.value("Appearance/currentTheme", DEFAULT_THEME_NAME, type=str)

def get_saved_theme_tab_position() -> QTabWidget.TabPosition:
    """
    Retrieves the saved tab position preference associated with the last applied theme.
    If not found, it derives it from the saved theme name.
    """
    settings = QSettings('Lumenante', 'AppSettings_v1.0')
    # Try to get the explicitly saved tab position first
    saved_pos_int = settings.value("Appearance/currentThemeTabPosition", -1, type=int)

    # Check if saved_pos_int is a valid enum value for QTabWidget.TabPosition
    # This creates a list of valid integer values for the enum.
    valid_enum_values = [tp.value for tp in QTabWidget.TabPosition]

    if saved_pos_int != -1 and saved_pos_int in valid_enum_values:
        return QTabWidget.TabPosition(saved_pos_int)
    
    # If not found, derive from the saved theme name (fallback/older saves)
    saved_theme = get_saved_theme_name()
    return get_theme_preferred_tab_position(saved_theme)