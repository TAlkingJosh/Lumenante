# tabs/plugins_tab.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QCheckBox, QHBoxLayout, QTextEdit, QFrame, QSplitter,
                             QPushButton, QMessageBox)
from PyQt6.QtCore import Qt, QSize
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lumenante_main import Lumenante, PluginManager

class PluginListItemWidget(QWidget):
    """A custom widget for displaying a single plugin in the list."""
    def __init__(self, plugin_info: dict, plugin_manager: 'PluginManager', parent=None):
        super().__init__(parent)
        self.plugin_id = plugin_info['id']
        self.plugin_manager = plugin_manager

        layout = QHBoxLayout(self)
        
        self.enable_checkbox = QCheckBox()
        self.enable_checkbox.setFixedWidth(20)
        is_enabled = self.plugin_manager.is_plugin_enabled(self.plugin_id)
        self.enable_checkbox.setChecked(is_enabled)
        self.enable_checkbox.toggled.connect(self.on_toggled)
        layout.addWidget(self.enable_checkbox)

        self.name_label = QLabel(f"{plugin_info['name']} <span style='color:#888;'>v{plugin_info['version']}</span>")
        self.name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.name_label, 1)

    def on_toggled(self, checked: bool):
        self.plugin_manager.set_plugin_enabled(self.plugin_id, checked)


class PluginsTab(QWidget):
    def __init__(self, main_window: 'Lumenante'):
        super().__init__()
        self.main_window = main_window
        self.plugin_manager = self.main_window.plugin_manager
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Top info and controls
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Enable or disable plugins. A restart is required for changes to take effect."))
        top_layout.addStretch()
        self.reload_button = QPushButton("Discover New Plugins")
        self.reload_button.clicked.connect(self.rediscover_plugins)
        top_layout.addWidget(self.reload_button)
        main_layout.addLayout(top_layout)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: List of plugins
        self.plugin_list_widget = QListWidget()
        self.plugin_list_widget.setSpacing(2)
        splitter.addWidget(self.plugin_list_widget)

        # Right side: Details of selected plugin
        details_frame = QFrame()
        details_frame.setFrameShape(QFrame.Shape.StyledPanel)
        details_layout = QVBoxLayout(details_frame)
        details_layout.addWidget(QLabel("Plugin Details:"))
        self.details_text_edit = QTextEdit()
        self.details_text_edit.setReadOnly(True)
        details_layout.addWidget(self.details_text_edit)
        splitter.addWidget(details_frame)

        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter)
        
        self.plugin_list_widget.currentItemChanged.connect(self.on_plugin_selected)

        self.populate_plugin_list()
        
    def rediscover_plugins(self):
        self.plugin_manager.discover_plugins()
        self.populate_plugin_list()
        QMessageBox.information(self, "Plugins Rediscovered", "Plugin list has been refreshed. Please restart the application to load new or enabled plugins.")
        
    def populate_plugin_list(self):
        self.plugin_list_widget.clear()
        for plugin_id, plugin_info in self.plugin_manager.discovered_plugins.items():
            list_item = QListWidgetItem(self.plugin_list_widget)
            item_widget = PluginListItemWidget(plugin_info, self.plugin_manager)
            
            list_item.setSizeHint(item_widget.sizeHint())
            # Store the plugin info in the item for easy access later
            list_item.setData(Qt.ItemDataRole.UserRole, plugin_info)
            
            self.plugin_list_widget.addItem(list_item)
            self.plugin_list_widget.setItemWidget(list_item, item_widget)
        
        if self.plugin_list_widget.count() > 0:
            self.plugin_list_widget.setCurrentRow(0)
        else:
            self.details_text_edit.setHtml("<i>No plugins found in the 'plugins' directory.</i>")

    def on_plugin_selected(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        if not current_item:
            self.details_text_edit.clear()
            return
            
        plugin_info = current_item.data(Qt.ItemDataRole.UserRole)
        if plugin_info:
            details_html = f"""
            <h3>{plugin_info['name']}</h3>
            <p>
                <b>Version:</b> {plugin_info['version']}<br>
                <b>Author:</b> {plugin_info['author']}
            </p>
            <hr>
            <p>{plugin_info['description'].replace('\n', '<br>')}</p>
            <hr>
            <p><i style='color:#888;'>Location: {plugin_info['path']}</i></p>
            """
            self.details_text_edit.setHtml(details_html)
