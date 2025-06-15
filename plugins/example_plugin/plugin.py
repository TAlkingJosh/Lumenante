# plugins/example_plugin/plugin.py
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
from plugins.plugin_api import LumenantePlugin, PluginAPI
from typing import Dict

# --- Example Custom Widget for the Layout Editor ---
class ExampleButtonWidget(QPushButton):
    def __init__(self, parent=None):
        super().__init__("Plugin Button", parent)
        self.clicked.connect(self.on_click)
        self.setStyleSheet("background-color: #8E44AD; color: white;")

    def on_click(self):
        QMessageBox.information(self, "Plugin Widget", "This button was created by the Example Plugin!")

# --- Example Custom Tab ---
class ExampleTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("This is a custom tab added by the Example Plugin.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

# --- The Main Plugin Class ---
class ExamplePlugin(LumenantePlugin):
    # Override metadata
    name = "Example Plugin"
    author = "Your Name"
    version = "1.0.1"
    description = "An example plugin demonstrating the plugin API capabilities."

    def initialize(self, api: PluginAPI) -> bool:
        # It's good practice to call the superclass's method
        super().initialize(api)

        # 1. Add a new top-level tab
        self.api.add_tab(ExampleTabWidget(), "Example Tab")

        # 2. Register a new custom widget for the layout editor
        # The API needs a function that it can call to create an instance of our widget.
        self.api.register_layout_widget("Example Button", self.create_example_button)

        # 3. Add an event to the timeline
        # This demonstrates how a plugin could programmatically add cues.
        event_details = {
            'name': 'Event from Plugin',
            'start_time': 5.0,
            'duration': 2.0,
            'type': 'blackout',
            'data': {'trigger_mode': 'absolute'},
            'target_type': 'master',
            'target_id': None,
            'cue_id': None
        }
        # self.api.add_timeline_event(event_details) # Uncomment to have it add an event on load
        
        # 4. Get a reference to an existing tab and connect to its signals
        presets_tab = self.api.get_tab_by_name("Presets")
        if presets_tab and hasattr(presets_tab, 'presets_changed'):
            presets_tab.presets_changed.connect(self.on_presets_changed)

        self.api.log("Initialization complete.")
        return True

    def shutdown(self):
        # Perform any cleanup here
        self.api.log("Shutting down and cleaning up resources.")
        super().shutdown()

    # This is the callback function passed to the API for creating our custom widget.
    # It must accept the parent widget and a data dictionary.
    def create_example_button(self, parent_widget: QWidget, data_dict: Dict) -> QWidget:
        # For this simple button, we don't use the data_dict, but the signature must match.
        return ExampleButtonWidget(parent_widget)

    def on_presets_changed(self):
        """A slot to react to a signal from another tab."""
        self.api.log("Detected that the presets have changed!")

# This function is required for the plugin manager to find the plugin class
def get_plugin_class():
    return ExamplePlugin
