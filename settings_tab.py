# tabs/settings_tab.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QGroupBox,
                             QFormLayout, QPushButton, QFileDialog, QMessageBox,
                             QLineEdit, QScrollArea, QSpacerItem, QSizePolicy,
                             QComboBox, QApplication, QTabWidget, QDoubleSpinBox,
                             QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
                             QDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
import json
import theme_manager 

class KeybindCaptureDialog(QDialog):
    """A simple dialog to capture a key sequence from the user."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Keybind")
        self.setFixedSize(300, 100)
        layout = QVBoxLayout(self)
        self.info_label = QLabel("Press a key or key combination...\n(Press Escape to cancel)")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
        self.key_sequence = None

    def keyPressEvent(self, event):
        # Ignore modifier-only key presses
        if event.key() in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        # Use Escape to cancel the dialog
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
            
        # Combine modifiers with the key
        modifiers = event.modifiers()
        key = event.key()
        
        # This is how QKeySequence represents keys, so we must construct it this way
        seq = QKeySequence(modifiers.value + key)
        self.key_sequence = seq
        self.accept()
        
    def get_key_sequence(self) -> QKeySequence | None:
        return self.key_sequence

class SettingsTab(QWidget):
    # This signal will be emitted when the live mode checkbox is toggled
    live_mode_toggled = pyqtSignal(bool)
    # This signal will be emitted when keybinds are saved, to prompt main window to reload them
    keybinds_changed = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        
        main_layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        scroll_content_widget = QWidget()
        scroll_area.setWidget(scroll_content_widget)
        
        content_layout = QVBoxLayout(scroll_content_widget) 

        appearance_group = QGroupBox("Appearance")
        appearance_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        appearance_form_layout = QFormLayout()

        self.theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.populate_theme_combo()
        self.theme_combo.currentTextChanged.connect(self.on_theme_selected_by_user) 
        appearance_form_layout.addRow(self.theme_label, self.theme_combo)
        
        appearance_group.setLayout(appearance_form_layout)
        content_layout.addWidget(appearance_group)

        general_group = QGroupBox("Application Settings")
        general_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        general_form_layout = QFormLayout()

        self.always_on_top_checkbox = QCheckBox("Window Always on Top")
        self.always_on_top_checkbox.toggled.connect(self.toggle_always_on_top_setting) 
        general_form_layout.addRow(self.always_on_top_checkbox)
        
        general_group.setLayout(general_form_layout)
        content_layout.addWidget(general_group)

        gamepad_group = QGroupBox("Gamepad Settings")
        gamepad_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        gamepad_form_layout = QFormLayout()
        
        self.gamepad_enabled_checkbox = QCheckBox("Enable Gamepad Control")
        self.gamepad_enabled_checkbox.setToolTip("If unchecked, all joystick input will be ignored.")
        gamepad_form_layout.addRow(self.gamepad_enabled_checkbox)

        self.gamepad_mode_combo = QComboBox()
        self.gamepad_mode_combo.addItems(["Single Joystick (Right)", "Dual Joystick"])
        self.gamepad_mode_combo.setToolTip("Select how joysticks control Pan/Tilt.\nDual: Left Stick controls Tilt, Right Stick controls Pan.")
        gamepad_form_layout.addRow("Control Mode:", self.gamepad_mode_combo)

        self.gamepad_sensitivity_spinbox = QDoubleSpinBox()
        self.gamepad_sensitivity_spinbox.setRange(0.1, 10.0)
        self.gamepad_sensitivity_spinbox.setSingleStep(0.1)
        self.gamepad_sensitivity_spinbox.setDecimals(1)
        gamepad_form_layout.addRow("Pan/Tilt Sensitivity:", self.gamepad_sensitivity_spinbox)

        self.gamepad_invert_tilt_checkbox = QCheckBox("Invert Tilt (Y-Axis)")
        gamepad_form_layout.addRow(self.gamepad_invert_tilt_checkbox)

        gamepad_group.setLayout(gamepad_form_layout)
        content_layout.addWidget(gamepad_group)

        roblox_group = QGroupBox("ROBLOX Integration")
        roblox_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        roblox_form_layout = QFormLayout()
        
        self.roblox_live_mode_checkbox = QCheckBox("Enable Live Mode") 
        self.roblox_live_mode_checkbox.setToolTip("When enabled, fixture changes will be 'sent' to a ROBLOX endpoint via HTTP.")
        self.roblox_live_mode_checkbox.toggled.connect(self.live_mode_toggled.emit)
        roblox_form_layout.addRow(self.roblox_live_mode_checkbox)

        import_roblox_pos_button = QPushButton("Import Positions from ROBLOX")
        import_roblox_pos_button.setToolTip("Requests current fixture positions from the running ROBLOX game and updates the patch.")
        import_roblox_pos_button.clicked.connect(self.handle_import_from_roblox)
        roblox_form_layout.addRow(import_roblox_pos_button)


        roblox_group.setLayout(roblox_form_layout)
        content_layout.addWidget(roblox_group)

        # --- NEW: Keybinds Section ---
        keybinds_group = QGroupBox("Keybinds")
        keybinds_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        keybinds_layout = QVBoxLayout()

        self.keybinds_table = QTableWidget()
        self.keybinds_table.setColumnCount(2)
        self.keybinds_table.setHorizontalHeaderLabels(["Action", "Keybind"])
        self.keybinds_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.keybinds_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.keybinds_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.keybinds_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.keybinds_table.setMinimumHeight(250)
        self.populate_keybinds_table()

        keybinds_layout.addWidget(self.keybinds_table)
        
        keybind_buttons_layout = QHBoxLayout()
        change_keybind_button = QPushButton("Change Keybind...")
        change_keybind_button.clicked.connect(self.change_selected_keybind)
        keybind_buttons_layout.addWidget(change_keybind_button)

        clear_keybind_button = QPushButton("Clear Keybind")
        clear_keybind_button.clicked.connect(self.clear_selected_keybind)
        keybind_buttons_layout.addWidget(clear_keybind_button)
        keybind_buttons_layout.addStretch()

        apply_keybinds_button = QPushButton("Apply & Save Keybinds")
        apply_keybinds_button.setObjectName("PrimaryButton")
        apply_keybinds_button.clicked.connect(self.apply_and_save_keybinds)
        keybind_buttons_layout.addWidget(apply_keybinds_button)

        keybinds_layout.addLayout(keybind_buttons_layout)
        keybinds_group.setLayout(keybinds_layout)
        content_layout.addWidget(keybinds_group)
        # --- End Keybinds Section ---


        data_group = QGroupBox("Data Management")
        data_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        data_v_layout = QVBoxLayout() 

        export_show_button = QPushButton("Export Complete Show Data (to JSON)")
        export_show_button.clicked.connect(self.handle_export_show_data)
        data_v_layout.addWidget(export_show_button)
        
        import_show_button = QPushButton("Import Complete Show Data (from JSON)") 
        import_show_button.clicked.connect(self.handle_import_show_data)
        data_v_layout.addWidget(import_show_button)


        data_v_layout.addSpacing(10) 

        export_layout_button = QPushButton("Export Current Layout (to JSON)")
        export_layout_button.clicked.connect(self.handle_export_layout)
        data_v_layout.addWidget(export_layout_button)

        import_layout_button = QPushButton("Import Layout (from JSON)")
        import_layout_button.clicked.connect(self.handle_import_layout)
        data_v_layout.addWidget(import_layout_button)
        
        data_group.setLayout(data_v_layout)
        content_layout.addWidget(data_group)

        content_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        save_all_button = QPushButton("Save General Settings")
        save_all_button.setStyleSheet("padding: 8px;")
        save_all_button.clicked.connect(self.save_all_app_settings)
        content_layout.addWidget(save_all_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.load_app_settings() 

    def populate_theme_combo(self):
        self.theme_combo.blockSignals(True)
        current_data = self.theme_combo.currentData()
        self.theme_combo.clear()
        themes = theme_manager.list_available_themes()
        for theme_name in themes:
            self.theme_combo.addItem(theme_name.replace("_", " ").title(), userData=theme_name)
        
        if current_data: 
             idx = self.theme_combo.findData(current_data)
             if idx != -1: self.theme_combo.setCurrentIndex(idx)
        else: 
            saved_theme_actual_name = theme_manager.get_saved_theme_name()
            idx = self.theme_combo.findData(saved_theme_actual_name)
            if idx != -1: self.theme_combo.setCurrentIndex(idx)
            elif themes: self.theme_combo.setCurrentIndex(0)

        self.theme_combo.blockSignals(False)


    def on_theme_selected_by_user(self, display_text: str):
        if not display_text or self.theme_combo.signalsBlocked(): return 
        
        selected_theme_actual_name = self.theme_combo.currentData()
        if selected_theme_actual_name:
            current_tab_pos_before_change = theme_manager.get_saved_theme_tab_position()
            
            success, new_preferred_tab_pos = theme_manager.apply_theme_to_app(
                QApplication.instance(), selected_theme_actual_name
            )

            if success:
                print(f"Theme '{selected_theme_actual_name}' selected by user and applied via SettingsTab.")
                if new_preferred_tab_pos != current_tab_pos_before_change:
                    if hasattr(self.main_window, 'theme_change_requires_restart'):
                        self.main_window.theme_change_requires_restart.emit(selected_theme_actual_name)
            else:
                QMessageBox.warning(self, "Theme Error", f"Could not apply theme: {display_text}.")
                self.populate_theme_combo() 

    def load_app_settings(self):
        settings = self.main_window.settings
        self.populate_theme_combo() 

        always_on_top = settings.value('window/always_on_top', False, type=bool)
        self.always_on_top_checkbox.setChecked(always_on_top)
        
        self.roblox_live_mode_checkbox.setChecked(settings.value('roblox/live_mode_enabled', False, type=bool))

        # Load Gamepad settings
        self.gamepad_enabled_checkbox.setChecked(settings.value('gamepad/enabled', True, type=bool))
        self.gamepad_mode_combo.setCurrentIndex(settings.value('gamepad/mode', 0, type=int)) # 0: Single, 1: Dual
        self.gamepad_sensitivity_spinbox.setValue(settings.value('gamepad/sensitivity', 2.0, type=float))
        self.gamepad_invert_tilt_checkbox.setChecked(settings.value('gamepad/invert_tilt', True, type=bool))
        
        # This will now also load keybinds into the table
        self.populate_keybinds_table()

        print("Settings loaded into SettingsTab UI.")

    def save_all_app_settings(self):
        settings = self.main_window.settings
        
        selected_theme_actual_name = self.theme_combo.currentData()
        if selected_theme_actual_name:
            settings.setValue('Appearance/currentTheme', selected_theme_actual_name)
            preferred_pos = theme_manager.get_theme_preferred_tab_position(selected_theme_actual_name)
            # Correctly save the integer value of the enum
            settings.setValue('Appearance/currentThemeTabPosition', preferred_pos.value)


        settings.setValue('window/always_on_top', self.always_on_top_checkbox.isChecked())
        settings.setValue('roblox/live_mode_enabled', self.roblox_live_mode_checkbox.isChecked())

        # Save Gamepad settings
        settings.setValue('gamepad/enabled', self.gamepad_enabled_checkbox.isChecked())
        settings.setValue('gamepad/mode', self.gamepad_mode_combo.currentIndex())
        settings.setValue('gamepad/sensitivity', self.gamepad_sensitivity_spinbox.value())
        settings.setValue('gamepad/invert_tilt', self.gamepad_invert_tilt_checkbox.isChecked())
        
        QMessageBox.information(self, "Settings Saved", "General application settings have been saved.")
        print("SettingsTab general settings saved.")

    def toggle_always_on_top_setting(self, checked_bool): 
        is_checked = bool(checked_bool) 
        
        current_flags = self.main_window.windowFlags()
        if is_checked:
            self.main_window.setWindowFlags(current_flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.main_window.setWindowFlags(current_flags & ~Qt.WindowType.WindowStaysOnTopHint)
        
        self.main_window.show() 

    def handle_import_from_roblox(self):
        if not self.roblox_live_mode_checkbox.isChecked():
            QMessageBox.warning(self, "Live Mode Off", "Please enable Live Mode before trying to import positions from ROBLOX.")
            return

        if hasattr(self.main_window, 'request_roblox_positions'):
            self.main_window.request_roblox_positions()

    def populate_keybinds_table(self):
        self.keybinds_table.setRowCount(0)
        settings = self.main_window.settings
        
        actions = []
        # Static Actions
        actions.extend([
            {'id': 'global.clear_selection', 'name': 'Global: Clear Selection', 'group': 'Global'},
            {'id': 'global.toggle_blackout', 'name': 'Global: Toggle Blackout', 'group': 'Global'},
            {'id': 'timeline.go_next_cue', 'name': 'Timeline: Go to Next Cue', 'group': 'Timeline'},
            {'id': 'timeline.go_prev_cue', 'name': 'Timeline: Go to Previous Cue', 'group': 'Timeline'},
            {'id': 'timeline.toggle_playback', 'name': 'Timeline: Toggle Play/Pause', 'group': 'Timeline'},
            {'id': 'timeline.stop_playback', 'name': 'Timeline: Stop Playback', 'group': 'Timeline'},
        ])

        # Dynamic Actions from DB
        try:
            cursor = self.main_window.db_connection.cursor()
            # Presets
            cursor.execute("SELECT preset_number, name FROM presets ORDER BY preset_number")
            for p_num, p_name in cursor.fetchall():
                name = f"Apply Preset {p_num}" + (f" ({p_name})" if p_name else "")
                actions.append({'id': f'preset.apply.{p_num}', 'name': name, 'group': 'Presets'})
            # Loop Palettes
            cursor.execute("SELECT id, name FROM loop_palettes ORDER BY name")
            for l_id, l_name in cursor.fetchall():
                actions.append({'id': f'loop.toggle.{l_id}', 'name': f"Toggle Loop '{l_name}'", 'group': 'Loops'})
            # Cues
            cursor.execute("SELECT cue_number, name FROM cues ORDER BY cue_number")
            for c_num, c_name in cursor.fetchall():
                name = f"Go to Cue {c_num}" + (f" ({c_name})" if c_name else "")
                actions.append({'id': f'cue.go.{c_num}', 'name': name, 'group': 'Cues'})
        except Exception as e:
            print(f"Error populating dynamic keybind actions: {e}")

        # Populate table
        for action in actions:
            row_position = self.keybinds_table.rowCount()
            self.keybinds_table.insertRow(row_position)
            
            action_item = QTableWidgetItem(action['name'])
            action_item.setData(Qt.ItemDataRole.UserRole, action['id'])
            action_item.setToolTip(f"Internal ID: {action['id']}\nGroup: {action['group']}")
            self.keybinds_table.setItem(row_position, 0, action_item)
            
            key_sequence_str = settings.value(f"keybinds/{action['id']}", "", type=str)
            keybind_item = QTableWidgetItem(key_sequence_str)
            self.keybinds_table.setItem(row_position, 1, keybind_item)

        self.keybinds_table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.keybinds_table.resizeColumnsToContents()
        self.keybinds_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)


    def change_selected_keybind(self):
        selected_items = self.keybinds_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select an action in the table to change its keybind.")
            return

        selected_row = selected_items[0].row()
        dialog = KeybindCaptureDialog(self)
        if dialog.exec():
            key_sequence = dialog.get_key_sequence()
            if key_sequence:
                self.keybinds_table.item(selected_row, 1).setText(key_sequence.toString(QKeySequence.SequenceFormat.PortableText))

    def clear_selected_keybind(self):
        selected_items = self.keybinds_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select an action to clear its keybind.")
            return
        
        selected_row = selected_items[0].row()
        self.keybinds_table.item(selected_row, 1).setText("")

    def apply_and_save_keybinds(self):
        settings = self.main_window.settings
        
        # Clear all old keybinds first to remove stale ones
        settings.remove("keybinds")

        settings.beginGroup("keybinds")
        for row in range(self.keybinds_table.rowCount()):
            action_id = self.keybinds_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            key_sequence_str = self.keybinds_table.item(row, 1).text()
            
            if action_id and key_sequence_str:
                # Use a sanitized version of action_id for the key
                sanitized_action_id = action_id.replace("/", "_").replace("\\", "_")
                settings.setValue(sanitized_action_id, key_sequence_str)
        settings.endGroup()

        QMessageBox.information(self, "Keybinds Saved", "Keybinds have been saved. They will be active after a restart or can be activated now via a signal.")
        self.keybinds_changed.emit()

    def handle_export_show_data(self):
        file_path, _ = QFileDialog.getSaveFileName(self.main_window, "Export Complete Show Data", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            if hasattr(self.main_window, 'export_show_data'):
                 self.main_window.export_show_data(file_path)
            else:
                 QMessageBox.critical(self, "Error", "Export functionality not fully implemented in main window.")

    def handle_import_show_data(self): 
        file_path, _ = QFileDialog.getOpenFileName(self.main_window, "Import Complete Show Data", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            if hasattr(self.main_window, 'import_show_data'):
                self.main_window.import_show_data(file_path)
            else:
                QMessageBox.critical(self, "Error", "Import show functionality not implemented in main window.")


    def handle_export_layout(self):
        if not hasattr(self.main_window, 'main_tab') or not self.main_window.main_tab:
            QMessageBox.critical(self, "Error", "MainTab is not available for layout export.")
            return

        interactive_canvas = self.main_window.main_tab.interactive_canvas
        if not interactive_canvas:
            QMessageBox.critical(self, "Error", "InteractiveCanvas is not available for layout export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self.main_window, "Export Current Layout", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            try:
                layout_data = interactive_canvas.get_all_areas_data_for_saving()
                with open(file_path, 'w') as f:
                    json.dump(layout_data, f, indent=2)
                QMessageBox.information(self, "Export Successful", f"Layout data exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export layout data: {e}")
                print(f"Layout export error: {e}")

    def handle_import_layout(self):
        if not hasattr(self.main_window, 'main_tab') or not self.main_window.main_tab:
            QMessageBox.critical(self, "Error", "MainTab is not available for layout import.")
            return

        file_path, _ = QFileDialog.getOpenFileName(self.main_window, "Import Layout", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    layout_data = json.load(f)

                if not isinstance(layout_data, dict) or \
                   'areas' not in layout_data or \
                   'canvas_offset_x' not in layout_data or \
                   'canvas_offset_y' not in layout_data or \
                   not isinstance(layout_data['areas'], list):
                    QMessageBox.warning(self, "Import Error", "Invalid layout file format. Missing required keys ('areas', 'canvas_offset_x', 'canvas_offset_y') or 'areas' is not a list.")
                    return
                
                self.main_window.main_tab.load_layout_from_data_dict(layout_data)
                QMessageBox.information(self, "Import Successful", f"Layout data imported from {file_path} and applied. The imported layout has also been saved as the current default.")

            except json.JSONDecodeError:
                QMessageBox.critical(self, "Import Error", "Failed to decode JSON from the layout file. The file may be corrupted or not a valid layout export.")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import layout data: {e}")
                print(f"Layout import error: {e}")