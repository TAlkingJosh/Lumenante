# tabs/presets_tab.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QPushButton, QHBoxLayout, QLineEdit, QMessageBox,
                             QDialog, QDialogButtonBox, QFormLayout, QTextEdit,
                             QSizePolicy, QComboBox)
from PyQt6.QtCore import pyqtSignal, Qt
import json
import sqlite3

class PresetDialog(QDialog):
    def __init__(self, current_number="", current_name="", current_type="All", parent=None, is_new=True):
        super().__init__(parent)
        self.setWindowTitle("Preset Properties")
        layout = QFormLayout(self)
        
        self.number_edit = QLineEdit(current_number)
        self.number_edit.setPlaceholderText("e.g., 1.1 or 5")
        layout.addRow("Preset Number:", self.number_edit)

        self.name_edit = QLineEdit(current_name)
        self.name_edit.setPlaceholderText("Optional descriptive name")
        layout.addRow("Name / Label:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All", "Dimmer", "Color", "Position", "Beam", "Gobo"])
        idx = self.type_combo.findText(current_type, Qt.MatchFlag.MatchFixedString | Qt.MatchFlag.CaseInsensitive)
        if idx != -1: self.type_combo.setCurrentIndex(idx)
        self.type_combo.setEnabled(is_new) # Only allow setting type on creation
        type_tooltip = "Select the type of parameters this preset will store.\n'All' stores everything. Cannot be changed after creation."
        self.type_combo.setToolTip(type_tooltip)

        layout.addRow("Preset Type:", self.type_combo)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
    def validate_and_accept(self):
        if not self.number_edit.text().strip():
            QMessageBox.warning(self, "Input Error", "Preset Number cannot be empty.")
            return
        self.accept()

    def get_preset_info(self):
        return self.number_edit.text().strip(), self.name_edit.text().strip(), self.type_combo.currentText()

class PresetViewDialog(QDialog):
    def __init__(self, preset_number, preset_name, preset_data_str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"View Preset {preset_number}: {preset_name}")
        self.setMinimumSize(500, 400)
        layout = QVBoxLayout(self)
        
        self.data_view = QTextEdit()
        self.data_view.setReadOnly(True)
        self.data_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        try:
            parsed_json = json.loads(preset_data_str)
            self.data_view.setText(json.dumps(parsed_json, indent=2, sort_keys=True))
        except json.JSONDecodeError:
            self.data_view.setText(f"Error decoding JSON data.\n\nRaw data:\n{preset_data_str}")

        layout.addWidget(self.data_view)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignRight)


class PresetsTab(QWidget):
    preset_applied = pyqtSignal(str) # preset_number
    presets_changed = pyqtSignal()   # To notify other tabs (like MainTab) to update their preset lists

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()
        self.load_presets_from_db()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        controls_panel = QWidget()
        controls_layout = QHBoxLayout(controls_panel)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        self.create_preset_button = QPushButton("Create New (from Selection)")
        self.create_preset_button.setToolTip("Create a new preset containing the state of the currently selected fixtures.")
        self.create_preset_button.clicked.connect(self.create_new_preset)
        controls_layout.addWidget(self.create_preset_button)

        self.update_preset_button = QPushButton("Update (from Selection)")
        self.update_preset_button.setToolTip("Update the selected preset with the values of the currently selected fixtures.")
        self.update_preset_button.clicked.connect(self.update_selected_preset)
        controls_layout.addWidget(self.update_preset_button)

        self.apply_preset_button = QPushButton("Apply Selected")
        self.apply_preset_button.clicked.connect(self.apply_selected_preset)
        controls_layout.addWidget(self.apply_preset_button)
        
        self.rename_preset_button = QPushButton("Edit Label")
        self.rename_preset_button.setToolTip("Edit the name/label of the selected preset.")
        self.rename_preset_button.clicked.connect(self.rename_selected_preset)
        controls_layout.addWidget(self.rename_preset_button)

        self.view_preset_button = QPushButton("View Data")
        self.view_preset_button.clicked.connect(self.view_selected_preset_data)
        controls_layout.addWidget(self.view_preset_button)

        self.delete_preset_button = QPushButton("Delete Selected")
        self.delete_preset_button.setStyleSheet("background-color: #c62828;")
        self.delete_preset_button.clicked.connect(self.delete_selected_preset)
        controls_layout.addWidget(self.delete_preset_button)
        controls_layout.addStretch()

        layout.addWidget(controls_panel)

        self.presets_list_widget = QListWidget()
        self.presets_list_widget.itemDoubleClicked.connect(self.apply_selected_preset_from_item)
        self.presets_list_widget.setSortingEnabled(True)
        layout.addWidget(self.presets_list_widget)
        
        self.setLayout(layout)

    def load_presets_from_db(self):
        current_selection_info = None
        if self.presets_list_widget.currentItem():
            current_selection_info = self.presets_list_widget.currentItem().data(Qt.ItemDataRole.UserRole)

        self.presets_list_widget.clear()
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT preset_number, name, type FROM presets ORDER BY type, preset_number")
            presets = cursor.fetchall()
            new_selection_item = None
            for preset_number, name, preset_type in presets:
                type_str = f"[{preset_type.capitalize()}] " if preset_type.lower() != 'all' else ""
                display_text = f"{type_str}P {preset_number}"
                if name:
                    display_text += f": {name}"
                item = QListWidgetItem(display_text)
                # Store tuple of (number, type)
                item.setData(Qt.ItemDataRole.UserRole, (preset_number, preset_type))

                # Set tooltip with keybind
                action_id = f"preset.apply.{preset_number}".replace('.', '_')
                keybind_str = self.main_window.keybind_map.get(action_id, '')
                tooltip = f"Apply Preset {preset_number}"
                if keybind_str:
                    tooltip += f" ({keybind_str})"
                item.setToolTip(tooltip)
                
                self.presets_list_widget.addItem(item)
                if current_selection_info and current_selection_info[0] == preset_number:
                    new_selection_item = item
            
            if new_selection_item:
                self.presets_list_widget.setCurrentItem(new_selection_item)

            self.presets_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not load presets: {e}")

    def create_new_preset(self):
        selected_fixture_ids = self.main_window.main_tab.globally_selected_fixture_ids_for_controls
        if not selected_fixture_ids:
            QMessageBox.warning(self, "No Selection", "Please select one or more fixtures before creating a preset.")
            return

        dialog = PresetDialog(parent=self, is_new=True)
        if dialog.exec():
            preset_number, preset_name, preset_type = dialog.get_preset_info()
            if not preset_number: return
            
            # Delegate to the main window's central store_preset method
            self.main_window.store_preset(preset_number, preset_name, selected_fixture_ids, preset_type)
            
    def update_selected_preset(self):
        current_item = self.presets_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a preset to update.")
            return
            
        selected_fixture_ids = self.main_window.main_tab.globally_selected_fixture_ids_for_controls
        if not selected_fixture_ids:
            QMessageBox.warning(self, "No Selection", "Please select one or more fixtures to get values from.")
            return

        preset_info = current_item.data(Qt.ItemDataRole.UserRole)
        preset_number, _ = preset_info

        reply = QMessageBox.question(self, "Confirm Update", 
                                     f"Are you sure you want to update Preset {preset_number} with the current fixture selection?\nThis will overwrite its values.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.main_window.update_preset(preset_number, selected_fixture_ids)

    def apply_selected_preset_from_item(self, item_or_none):
        current_item = item_or_none if isinstance(item_or_none, QListWidgetItem) else self.presets_list_widget.currentItem()
        if current_item:
            preset_info = current_item.data(Qt.ItemDataRole.UserRole)
            if preset_info and isinstance(preset_info, tuple):
                preset_number, _ = preset_info
                self.preset_applied.emit(preset_number)
            else:
                QMessageBox.warning(self, "Error", "Invalid preset data in list item.")
        else:
            QMessageBox.warning(self, "No Selection", "Please select a preset to apply.")
    
    def apply_selected_preset(self):
        self.apply_selected_preset_from_item(None)

    def rename_selected_preset(self):
        current_item = self.presets_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a preset to edit its label.")
            return
        
        preset_info = current_item.data(Qt.ItemDataRole.UserRole)
        if not (preset_info and isinstance(preset_info, tuple)): return
        preset_number, preset_type = preset_info
        
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT name FROM presets WHERE preset_number = ?", (preset_number,))
            result = cursor.fetchone()
            current_name = result[0] if result else ""

            dialog = PresetDialog(current_number=preset_number, current_name=current_name, current_type=preset_type, parent=self, is_new=False)
            dialog.number_edit.setReadOnly(True)
            dialog.setWindowTitle("Edit Preset Label")

            if dialog.exec():
                new_number, new_name, _ = dialog.get_preset_info()
                if new_name != current_name:
                    cursor.execute("UPDATE presets SET name = ? WHERE preset_number = ?", (new_name, new_number))
                    self.main_window.db_connection.commit()
                    self.load_presets_from_db()
                    QMessageBox.information(self, "Preset Labeled", f"Preset {new_number} label updated.")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not edit preset label: {e}")

    def view_selected_preset_data(self):
        current_item = self.presets_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a preset to view its data.")
            return

        preset_info = current_item.data(Qt.ItemDataRole.UserRole)
        if not (preset_info and isinstance(preset_info, tuple)): return
        preset_number, _ = preset_info
        
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT name, data FROM presets WHERE preset_number = ?", (preset_number,))
            result = cursor.fetchone()
            if result:
                name, data_str = result
                dialog = PresetViewDialog(preset_number, name, data_str, self)
                dialog.exec()
            else:
                QMessageBox.critical(self, "Error", f"Preset data for '{preset_number}' not found.")
        except Exception as e:
             QMessageBox.critical(self, "Database Error", f"Could not load preset data for viewing: {e}")

    def delete_selected_preset(self):
        current_item = self.presets_list_widget.currentItem()
        if current_item:
            preset_info = current_item.data(Qt.ItemDataRole.UserRole)
            if not (preset_info and isinstance(preset_info, tuple)): return
            preset_number, _ = preset_info

            reply = QMessageBox.question(self, "Confirm Delete", 
                                         f"Are you sure you want to delete preset {preset_number}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    cursor = self.main_window.db_connection.cursor()
                    cursor.execute("DELETE FROM presets WHERE preset_number = ?", (preset_number,))
                    self.main_window.db_connection.commit()
                    self.load_presets_from_db()
                    QMessageBox.information(self, "Preset Deleted", f"Preset {preset_number} deleted.")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not delete preset: {e}")
        else:
            QMessageBox.warning(self, "No Selection", "Please select a preset to delete.")