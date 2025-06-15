# plugins/plugin_api.py
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Any, Dict
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QIcon

if TYPE_CHECKING:
    from lumenante_main import Lumenante

class LumenantePlugin:
    """
    Base class for all plugins.
    Plugins must inherit from this class and be located in the 'plugins' directory.
    """
    # --- Plugin Metadata (must be overridden by subclasses) ---
    name: str = "Unnamed Plugin"
    author: str = "Unknown Author"
    version: str = "0.0.0"
    description: str = "No description provided."

    def __init__(self):
        self.api: PluginAPI | None = None

    def initialize(self, api: 'PluginAPI') -> bool:
        """
        Called once when the plugin is loaded and enabled.
        This is where the plugin should perform its initial setup, like
        registering tabs, widgets, and connecting to signals.

        :param api: The PluginAPI instance for interacting with the main application.
        :return: True if initialization was successful, False otherwise.
        """
        self.api = api
        self.api.log(f"Plugin '{self.name}' v{self.version} is initializing.")
        return True

    def shutdown(self):
        """
        Called once when the application is closing.
        Plugins should perform any necessary cleanup here, like disconnecting
        signals or saving state.
        """
        if self.api:
            self.api.log(f"Plugin '{self.name}' is shutting down.")


class PluginAPI:
    """
    A safe wrapper around the main window instance, providing a controlled
    and documented API for plugins to interact with the application.
    """
    def __init__(self, main_window: 'Lumenante'):
        self._main_window = main_window

    def log(self, message: str):
        """
        Prints a message to the console, prefixed with the plugin's name.
        """
        # In a real app, this could go to a dedicated log file or a log viewer widget.
        print(f"[Plugin] {message}")

    def add_tab(self, widget: QWidget, name: str, icon: QIcon = None) -> bool:
        """
        Adds a new top-level tab to the main application window.

        :param widget: The QWidget instance to be used as the tab's content.
        :param name: The display name for the new tab.
        :param icon: (Optional) A QIcon for the new tab.
        :return: True if the tab was added, False otherwise.
        """
        if not isinstance(widget, QWidget) or not name:
            self.log(f"Error: add_tab received invalid widget or name.")
            return False
        
        self._main_window.tab_widget.addTab(widget, name)
        if icon:
            self._main_window.tab_widget.setTabIcon(self._main_window.tab_widget.indexOf(widget), icon)
        
        self.log(f"Added new tab: '{name}'")
        return True

    def register_layout_widget(self, name: str, creation_callback: Callable[[QWidget, Dict], QWidget]) -> bool:
        """
        Registers a new custom widget type that can be added to the Main Tab's layout canvas.

        :param name: The name of the widget type as it will appear in the assignment panel's dropdown.
        :param creation_callback: A function that takes two arguments (the parent QWidget, and a data dict for state)
                                  and returns a new instance of your custom QWidget.
        :return: True if registration was successful, False otherwise.
        """
        if not hasattr(self._main_window, 'main_tab') or not self._main_window.main_tab:
            self.log("Error: Cannot register layout widget, MainTab is not available.")
            return False
            
        return self._main_window.main_tab.register_custom_layout_widget(name, creation_callback)

    def add_timeline_event(self, event_data: dict) -> bool:
        """
        Adds a new event to the timeline programmatically.

        :param event_data: A dictionary containing the event's properties.
                           See `TimelineTab.add_event_from_plugin` for required keys.
        :return: True if the event was added successfully, False otherwise.
        """
        if not hasattr(self._main_window, 'timeline_tab') or not self._main_window.timeline_tab:
            self.log("Error: Cannot add timeline event, TimelineTab is not available.")
            return False
            
        # In a real implementation, you would call a method on timeline_tab
        # e.g., return self._main_window.timeline_tab.add_event_from_plugin(event_data)
        self.log(f"Timeline event add requested (Not yet fully implemented): {event_data}")
        return True # Placeholder

    def get_main_window(self) -> 'Lumenante':
        """
        Returns a reference to the main application window.
        Use with caution. Prefer dedicated API methods where possible.
        """
        return self._main_window

    def get_tab_by_name(self, name: str) -> QWidget | None:
        """
        Retrieves a reference to a top-level tab by its display name.

        :param name: The case-sensitive name of the tab to find (e.g., "Presets", "Layouts").
        :return: The QWidget for the tab, or None if not found.
        """
        for i in range(self._main_window.tab_widget.count()):
            if self._main_window.tab_widget.tabText(i) == name:
                return self._main_window.tab_widget.widget(i)
        self.log(f"Warning: get_tab_by_name could not find a tab named '{name}'.")
        return None
