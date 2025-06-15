# tabs/timeline_tab.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea,
                             QHBoxLayout, QLineEdit, QFileDialog, QListWidget, QListWidgetItem,
                             QDialog, QFormLayout, QDoubleSpinBox, QComboBox, QDialogButtonBox,
                             QMessageBox, QSplitter, QSizePolicy, QMenu, QSpinBox, QAbstractItemView,
                             QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QApplication, QColorDialog)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QElapsedTimer, QRectF, QPointF, QMargins, QPoint, QSize, QUrl, QSizeF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QCursor, QMouseEvent, QWheelEvent, QAction, QFontMetrics, QFont, QPainterPath, QLinearGradient)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import json
import random
import math
import copy
import time
import sqlite3

class CueDialog(QDialog):
    # ... (CueDialog code remains unchanged) ...
    def __init__(self, main_window, cue_data=None, is_new_cue=True, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.is_new_cue = is_new_cue
        self.cue_data_original = cue_data if cue_data else {}
        self.setWindowTitle("Add Cue" if self.is_new_cue else "Edit Cue")

        self.layout = QFormLayout(self)

        self.cue_number_edit = QLineEdit(str(self.cue_data_original.get('cue_number', '')))
        self.name_edit = QLineEdit(str(self.cue_data_original.get('name', '')))
        
        self.trigger_time_edit = QDoubleSpinBox()
        self.trigger_time_edit.setRange(0, 36000); self.trigger_time_edit.setSuffix(" s"); self.trigger_time_edit.setDecimals(3)
        self.trigger_time_edit.setValue(float(self.cue_data_original.get('trigger_time_s', 0.0)))
        
        self.comment_edit = QLineEdit(str(self.cue_data_original.get('comment', '')))

        self.layout.addRow("Cue Number:", self.cue_number_edit)
        self.layout.addRow("Name (Optional):", self.name_edit)
        self.layout.addRow("Trigger Time:", self.trigger_time_edit)
        self.layout.addRow("Comment:", self.comment_edit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def validate_and_accept(self):
        cue_num_str = self.cue_number_edit.text().strip()
        if not cue_num_str:
            QMessageBox.warning(self, "Input Error", "Cue Number cannot be empty.")
            return
        self.accept()

    def get_data(self):
        data = {
            'cue_number': self.cue_number_edit.text().strip(),
            'name': self.name_edit.text().strip(),
            'trigger_time_s': self.trigger_time_edit.value(),
            'comment': self.comment_edit.text().strip()
        }
        if not self.is_new_cue and 'id' in self.cue_data_original:
            data['id'] = self.cue_data_original['id']
        return data


class TimelineEventDialog(QDialog):
    # ... (TimelineEventDialog code remains unchanged) ...
    def __init__(self, main_window, event_data=None, is_new_event=True, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.is_new_event = is_new_event
        self.event_data_original = event_data if event_data else {}
        self.currently_edited_event_id = self.event_data_original.get('id') if not is_new_event else None
        self.setWindowTitle("Add Timeline Event" if self.is_new_event else "Edit Timeline Event")
        
        self.layout = QFormLayout(self)
        
        self.name_edit = QLineEdit(self.event_data_original.get('name', "New Event"))
        
        self.trigger_type_combo = QComboBox()
        self.trigger_type_combo.addItem("Absolute Time", "absolute")
        self.trigger_type_combo.addItem("Relative to Cue Trigger", "relative_to_cue") 
        self.trigger_type_combo.addItem("Follow Event in Cue", "follow_event_in_cue")
        self.trigger_type_combo.currentIndexChanged.connect(self._on_trigger_type_changed)


        self.absolute_start_time_label = QLabel("Start Time:")
        self.absolute_start_time_edit = QDoubleSpinBox()
        self.absolute_start_time_edit.setRange(0, 36000); self.absolute_start_time_edit.setSuffix(" s"); self.absolute_start_time_edit.setDecimals(3)
        
        self.delay_label = QLabel("Delay:") 
        self.delay_edit = QDoubleSpinBox() 
        self.delay_edit.setRange(-3600, 36000); self.delay_edit.setSuffix(" s"); self.delay_edit.setDecimals(3)

        self.followed_event_label = QLabel("Follow Event:")
        self.followed_event_combo = QComboBox()
        self.followed_event_combo.addItem("None (Select Event)", None)
        self.followed_event_combo.currentIndexChanged.connect(self._update_timing_fields_visibility)

        self.duration_edit = QDoubleSpinBox() 
        self.duration_edit.setRange(0.000, 36000); self.duration_edit.setSuffix(" s"); self.duration_edit.setDecimals(3) 
        self.duration_edit.setValue(float(self.event_data_original.get('duration', 1.0)))

        self.cue_select_label = QLabel("Assign to Cue (Required for Relative/Follow):")
        self.cue_select_combo = QComboBox()
        self.cue_select_combo.addItem("None", None) 
        self.cue_select_combo.currentIndexChanged.connect(self._on_cue_selection_changed_for_dialog)


        self.target_type_combo = QComboBox()
        self.target_type_combo.addItem("Master", "master")
        self.target_type_combo.addItem("Group", "group")
        self.target_type_combo.addItem("Fixture", "fixture")
        self.target_type_combo.currentTextChanged.connect(self._update_target_id_options)

        self.target_id_label = QLabel("Target ID:") 
        self.target_id_combo = QComboBox()
        self.target_id_label.setVisible(False) 
        self.target_id_combo.setVisible(False) 
        
        self.event_type_combo = QComboBox()
        self.event_type_combo.addItems([
            "preset", "brightness", "color", "pan", "tilt", "zoom", "focus", "gobo", "strobe", "blackout"
        ]) 
        
        self.preset_select_label = QLabel("Preset:")
        self.preset_select_combo = QComboBox()
        
        self.brightness_value_label = QLabel("Value:") 
        self.brightness_value_spin = QSpinBox()
        self.brightness_value_spin.setRange(0,100); self.brightness_value_spin.setSuffix(" %")
        
        self.fade_in_label = QLabel("Fade In Time:")
        self.fade_in_spin = QDoubleSpinBox()
        self.fade_in_spin.setRange(0, 600); self.fade_in_spin.setSuffix(" s"); self.fade_in_spin.setDecimals(2)
        
        self.fade_out_label = QLabel("Fade Out Time:")
        self.fade_out_spin = QDoubleSpinBox()
        self.fade_out_spin.setRange(0, 600); self.fade_out_spin.setSuffix(" s"); self.fade_out_spin.setDecimals(2)
        
        self.blackout_label = QLabel("Action: Toggle Blackout State")

        # New widgets for specific parameter types
        self.color_label = QLabel("Color:")
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self._show_color_dialog)

        self.pan_label = QLabel("Pan:")
        self.pan_spin = QDoubleSpinBox(); self.pan_spin.setRange(-180, 180); self.pan_spin.setDecimals(2)

        self.tilt_label = QLabel("Tilt:")
        self.tilt_spin = QDoubleSpinBox(); self.tilt_spin.setRange(-180, 180); self.tilt_spin.setDecimals(2)

        self.zoom_label = QLabel("Zoom:")
        self.zoom_spin = QDoubleSpinBox(); self.zoom_spin.setRange(5, 90); self.zoom_spin.setDecimals(1)

        self.focus_label = QLabel("Focus:")
        self.focus_spin = QDoubleSpinBox(); self.focus_spin.setRange(0, 100); self.focus_spin.setDecimals(1)

        self.gobo_label = QLabel("Gobo Index:")
        self.gobo_spin = QSpinBox(); self.gobo_spin.setRange(0, 255)

        self.strobe_label = QLabel("Strobe Rate:")
        self.strobe_spin = QDoubleSpinBox(); self.strobe_spin.setRange(0, 30); self.strobe_spin.setDecimals(1); self.strobe_spin.setSuffix(" Hz")


        for widget in [self.preset_select_label, self.preset_select_combo, 
                       self.brightness_value_label, self.brightness_value_spin,
                       self.fade_in_label, self.fade_in_spin, self.fade_out_label, self.fade_out_spin,
                       self.blackout_label, self.color_label, self.color_button,
                       self.pan_label, self.pan_spin, self.tilt_label, self.tilt_spin,
                       self.zoom_label, self.zoom_spin, self.focus_label, self.focus_spin,
                       self.gobo_label, self.gobo_spin, self.strobe_label, self.strobe_spin]:
            widget.setVisible(False)

        self.layout.addRow("Event Name:", self.name_edit)
        self.layout.addRow(self.cue_select_label, self.cue_select_combo) 
        self.layout.addRow("Trigger Type:", self.trigger_type_combo)
        self.layout.addRow(self.absolute_start_time_label, self.absolute_start_time_edit)
        self.layout.addRow(self.delay_label, self.delay_edit)
        self.layout.addRow(self.followed_event_label, self.followed_event_combo)
        self.layout.addRow("Target Type:", self.target_type_combo)
        self.layout.addRow(self.target_id_label, self.target_id_combo)
        self.layout.addRow("Duration (Full Value):", self.duration_edit) 
        self.layout.addRow("Event Type:", self.event_type_combo)
        
        self.layout.addRow(self.preset_select_label, self.preset_select_combo)
        self.layout.addRow(self.brightness_value_label, self.brightness_value_spin) 
        self.layout.addRow(self.fade_in_label, self.fade_in_spin)
        self.layout.addRow(self.fade_out_label, self.fade_out_spin)
        self.layout.addRow(self.blackout_label)
        self.layout.addRow(self.color_label, self.color_button)
        self.layout.addRow(self.pan_label, self.pan_spin)
        self.layout.addRow(self.tilt_label, self.tilt_spin)
        self.layout.addRow(self.zoom_label, self.zoom_spin)
        self.layout.addRow(self.focus_label, self.focus_spin)
        self.layout.addRow(self.gobo_label, self.gobo_spin)
        self.layout.addRow(self.strobe_label, self.strobe_spin)

        self.event_type_combo.currentTextChanged.connect(self._update_event_specific_options)
        self.load_presets_for_combo() 
        self.load_cues_for_combo() 

        # --- Initial Population from Event Data ---
        data_payload = self.event_data_original.get('data', {})
        
        # Set initial color for the button
        initial_color_hex = data_payload.get('color_hex', '#ffffff')
        self._update_color_button(QColor(initial_color_hex))
        
        # Set initial values for other spinboxes, ensuring correct type casting
        self.brightness_value_spin.setValue(int(data_payload.get('value', 100))) 
        self.pan_spin.setValue(float(data_payload.get('value', 0.0)))
        self.tilt_spin.setValue(float(data_payload.get('value', 0.0)))
        self.zoom_spin.setValue(float(data_payload.get('value', 15.0)))
        self.focus_spin.setValue(float(data_payload.get('value', 50.0)))
        self.gobo_spin.setValue(int(data_payload.get('value', 0)))
        self.strobe_spin.setValue(float(data_payload.get('value', 0.0)))

        trigger_mode = data_payload.get('trigger_mode', 'absolute')
        if trigger_mode == 'relative_to_cue':
            self.trigger_type_combo.setCurrentText("Relative to Cue Trigger")
            self.delay_edit.setValue(float(self.event_data_original.get('start_time', 0.0))) 
            self.absolute_start_time_edit.setValue(0.0) 
        elif trigger_mode == 'follow_event_in_cue':
            self.trigger_type_combo.setCurrentText("Follow Event in Cue")
            self.delay_edit.setValue(float(self.event_data_original.get('start_time', 0.0)))
            self.absolute_start_time_edit.setValue(0.0)
        else: 
            self.trigger_type_combo.setCurrentText("Absolute Time")
            self.absolute_start_time_edit.setValue(float(self.event_data_original.get('start_time', 0.0)))
            self.delay_edit.setValue(0.0)

        initial_target_type = self.event_data_original.get('target_type', 'master')
        self.target_type_combo.setCurrentText(initial_target_type.capitalize())
        self._update_target_id_options(initial_target_type.capitalize()) 

        if not self.is_new_event:
            target_id_from_data = self.event_data_original.get('target_id')
            if target_id_from_data is not None:
                idx = self.target_id_combo.findData(target_id_from_data)
                if idx != -1: self.target_id_combo.setCurrentIndex(idx)
            
            event_type_from_data = self.event_data_original.get('type', 'preset')
            self.event_type_combo.setCurrentText(event_type_from_data)
            self._update_event_specific_options(event_type_from_data) 

            if event_type_from_data == 'preset':
                preset_number_to_select = data_payload.get('preset_number')
                if preset_number_to_select is not None:
                    idx = self.preset_select_combo.findData(str(preset_number_to_select))
                    if idx != -1: self.preset_select_combo.setCurrentIndex(idx)
            # ... (rest of elifs for old types) ...
            
            cue_id_from_data = self.event_data_original.get('cue_id')
            if cue_id_from_data is not None:
                idx_cue = self.cue_select_combo.findData(cue_id_from_data)
                if idx_cue != -1: self.cue_select_combo.setCurrentIndex(idx_cue) 
            
            if trigger_mode == 'follow_event_in_cue':
                if self.cue_select_combo.currentData() is not None:
                    self._populate_followed_event_combo() 
                followed_id_from_data = data_payload.get('followed_event_id')
                if followed_id_from_data is not None:
                    idx_followed = self.followed_event_combo.findData(followed_id_from_data)
                    if idx_followed != -1: self.followed_event_combo.setCurrentIndex(idx_followed)
                    else:
                        QMessageBox.warning(self, "Follow Event Invalid", "The previously followed event is no longer valid.")
                        self.trigger_type_combo.setCurrentText("Relative to Cue Trigger" if cue_id_from_data else "Absolute Time")
                        data_payload.pop('followed_event_id', None) 
                        self.event_data_original['data'] = data_payload 
                        trigger_mode = self.trigger_type_combo.currentData() 
        else: 
            self.absolute_start_time_edit.setValue(float(self.event_data_original.get('start_time', 0.0)))
            self.delay_edit.setValue(0.0) 
            self._update_target_id_options(self.target_type_combo.currentText()) 
            self._update_event_specific_options(self.event_type_combo.currentText())
        
        self._update_timing_fields_visibility() 

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept_data)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
    
    def _on_trigger_type_changed(self):
        self._update_timing_fields_visibility()
        if self.trigger_type_combo.currentData() == "follow_event_in_cue":
            self._populate_followed_event_combo()

    def _on_cue_selection_changed_for_dialog(self):
        self._update_timing_fields_visibility()
        if self.trigger_type_combo.currentData() == "follow_event_in_cue":
            self._populate_followed_event_combo()
        
    def _update_timing_fields_visibility(self):
        trigger_type = self.trigger_type_combo.currentData()
        is_absolute = trigger_type == "absolute"
        is_relative_to_cue = trigger_type == "relative_to_cue"
        is_follow_event = trigger_type == "follow_event_in_cue"
        is_cue_selected = self.cue_select_combo.currentData() is not None

        self.absolute_start_time_label.setVisible(is_absolute)
        self.absolute_start_time_edit.setVisible(is_absolute)
        self.absolute_start_time_edit.setEnabled(is_absolute)

        self.delay_label.setVisible(is_relative_to_cue or is_follow_event)
        self.delay_edit.setVisible(is_relative_to_cue or is_follow_event)
        
        if is_relative_to_cue:
            self.delay_label.setText("Delay from Cue Trigger:")
            self.delay_edit.setEnabled(is_cue_selected)
            if not is_cue_selected: self.delay_edit.setToolTip("Select a Cue to enable delay.")
            else: self.delay_edit.setToolTip("")
        elif is_follow_event:
            self.delay_label.setText("Delay from Followed Event End:")
            self.delay_edit.setEnabled(is_cue_selected and self.followed_event_combo.currentData() is not None)
            if not is_cue_selected: self.delay_edit.setToolTip("Select a Cue first.")
            elif self.followed_event_combo.currentData() is None: self.delay_edit.setToolTip("Select an Event to Follow.")
            else: self.delay_edit.setToolTip("")
        
        self.followed_event_label.setVisible(is_follow_event)
        self.followed_event_combo.setVisible(is_follow_event)
        self.followed_event_combo.setEnabled(is_follow_event and is_cue_selected)


    def _populate_followed_event_combo(self):
        current_followed_id = None
        if not self.is_new_event and 'data' in self.event_data_original and \
           self.event_data_original['data'].get('trigger_mode') == 'follow_event_in_cue':
            current_followed_id = self.event_data_original['data'].get('followed_event_id')
        
        if self.followed_event_combo.currentData() is not None: 
            current_followed_id = self.followed_event_combo.currentData()

        self.followed_event_combo.clear()
        self.followed_event_combo.addItem("None (Select Event)", None)

        selected_cue_id = self.cue_select_combo.currentData()
        if selected_cue_id is None:
            self.followed_event_combo.setEnabled(False)
            return

        try:
            cursor = self.main_window.db_connection.cursor()
            query = "SELECT id, name FROM timeline_events WHERE cue_id = ?"
            params = [selected_cue_id]
            if self.currently_edited_event_id is not None:
                query += " AND id != ?"
                params.append(self.currently_edited_event_id)
            query += " ORDER BY start_time, name" 
            
            cursor.execute(query, tuple(params))
            events_in_cue = cursor.fetchall()

            if not events_in_cue:
                self.followed_event_combo.addItem("No other events in this cue", None)
                self.followed_event_combo.setEnabled(False)
            else:
                self.followed_event_combo.setEnabled(True)
                found_current_followed_id_in_list = False
                for event_id, event_name in events_in_cue:
                    self.followed_event_combo.addItem(f"{event_name} (ID: {event_id})", event_id)
                    if event_id == current_followed_id:
                        found_current_followed_id_in_list = True
            
            if current_followed_id is not None and found_current_followed_id_in_list:
                idx = self.followed_event_combo.findData(current_followed_id)
                if idx != -1:
                    self.followed_event_combo.setCurrentIndex(idx)
            elif current_followed_id is not None and not found_current_followed_id_in_list:
                pass 


        except Exception as e:
            print(f"Error populating followed event combo: {e}")
            self.followed_event_combo.addItem("Error loading events", None)
            self.followed_event_combo.setEnabled(False)


    def load_cues_for_combo(self):
        current_data = self.cue_select_combo.currentData()
        self.cue_select_combo.clear()
        self.cue_select_combo.addItem("None", None)
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, cue_number, name FROM cues ORDER BY trigger_time_s, cue_number")
            cues = cursor.fetchall()
            for cue_id, cue_num, cue_name in cues:
                display_name = f"Cue {cue_num}"
                if cue_name:
                    display_name += f": {cue_name}"
                self.cue_select_combo.addItem(display_name, cue_id)
            
            if current_data is not None: 
                idx = self.cue_select_combo.findData(current_data)
                if idx != -1:
                    self.cue_select_combo.setCurrentIndex(idx)
        except Exception as e:
            print(f"Error loading cues for TimelineEventDialog: {e}")


    def _populate_target_fixtures_combo(self):
        self.target_id_combo.clear()
        self.target_id_label.setText("Target Fixture:")
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name FROM fixtures ORDER BY name")
            items = cursor.fetchall()
            if not items:
                self.target_id_combo.addItem("No Fixtures Available", -1)
                self.target_id_combo.setEnabled(False)
            else:
                self.target_id_combo.setEnabled(True)
                for fid, name in items:
                    self.target_id_combo.addItem(f"{name} (Fx {fid})", fid)
        except Exception as e:
            print(f"Error loading fixtures for TimelineEventDialog target: {e}")
            self.target_id_combo.addItem("Error Loading Fixtures", -1)
            self.target_id_combo.setEnabled(False)

    def _populate_target_groups_combo(self):
        self.target_id_combo.clear()
        self.target_id_label.setText("Target Group:")
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name FROM fixture_groups ORDER BY name")
            items = cursor.fetchall()
            if not items:
                self.target_id_combo.addItem("No Groups Available", -1)
                self.target_id_combo.setEnabled(False)
            else:
                self.target_id_combo.setEnabled(True)
                for gid, name in items:
                    self.target_id_combo.addItem(f"{name} (Grp {gid})", gid)
        except Exception as e:
            print(f"Error loading groups for TimelineEventDialog target: {e}")
            self.target_id_combo.addItem("Error Loading Groups", -1)
            self.target_id_combo.setEnabled(False)
            
    def _update_target_id_options(self, target_type_text: str):
        target_type = target_type_text.lower()
        if target_type == "fixture":
            self._populate_target_fixtures_combo()
            self.target_id_label.setVisible(True)
            self.target_id_combo.setVisible(True)
        elif target_type == "group":
            self._populate_target_groups_combo()
            self.target_id_label.setVisible(True)
            self.target_id_combo.setVisible(True)
        else: 
            self.target_id_label.setVisible(False)
            self.target_id_combo.setVisible(False)
            self.target_id_combo.clear()


    def _update_event_specific_options(self, event_type): 
        is_preset = (event_type == "preset")
        is_brightness = (event_type == "brightness")
        is_blackout = (event_type == "blackout")
        is_color = (event_type == "color")
        is_pan = (event_type == "pan")
        is_tilt = (event_type == "tilt")
        is_zoom = (event_type == "zoom")
        is_focus = (event_type == "focus")
        is_gobo = (event_type == "gobo")
        is_strobe = (event_type == "strobe")

        # Hide all specific controls first
        for widget in [self.preset_select_label, self.preset_select_combo, 
                       self.brightness_value_label, self.brightness_value_spin,
                       self.fade_in_label, self.fade_in_spin, self.fade_out_label, self.fade_out_spin,
                       self.blackout_label, self.color_label, self.color_button,
                       self.pan_label, self.pan_spin, self.tilt_label, self.tilt_spin,
                       self.zoom_label, self.zoom_spin, self.focus_label, self.focus_spin,
                       self.gobo_label, self.gobo_spin, self.strobe_label, self.strobe_spin]:
            widget.setVisible(False)

        # Show controls for the selected type
        if is_preset: self.preset_select_label.setVisible(True); self.preset_select_combo.setVisible(True)
        elif is_brightness:
            self.brightness_value_label.setVisible(True); self.brightness_value_spin.setVisible(True)
            self.fade_in_label.setVisible(True); self.fade_in_spin.setVisible(True)
            self.fade_out_label.setVisible(True); self.fade_out_spin.setVisible(True)
        elif is_blackout: self.blackout_label.setVisible(True)
        elif is_color: self.color_label.setVisible(True); self.color_button.setVisible(True)
        elif is_pan: self.pan_label.setVisible(True); self.pan_spin.setVisible(True)
        elif is_tilt: self.tilt_label.setVisible(True); self.tilt_spin.setVisible(True)
        elif is_zoom: self.zoom_label.setVisible(True); self.zoom_spin.setVisible(True)
        elif is_focus: self.focus_label.setVisible(True); self.focus_spin.setVisible(True)
        elif is_gobo: self.gobo_label.setVisible(True); self.gobo_spin.setVisible(True)
        elif is_strobe: self.strobe_label.setVisible(True); self.strobe_spin.setVisible(True)

    
    def _show_color_dialog(self):
        current_color = self.color_button.palette().color(self.color_button.backgroundRole())
        new_color = QColorDialog.getColor(current_color, self, "Select Event Color")
        if new_color.isValid():
            self._update_color_button(new_color)

    def _update_color_button(self, color):
        self.color_button.setProperty("color_hex", color.name())
        self.color_button.setStyleSheet(f"background-color: {color.name()};")

    def load_presets_for_combo(self):
        current_data = self.preset_select_combo.currentData()
        self.preset_select_combo.clear()
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT preset_number, name, type FROM presets ORDER BY type, preset_number")
            presets = cursor.fetchall()
            if not presets:
                self.preset_select_combo.addItem("No Presets Available")
                self.preset_select_combo.setEnabled(False)
            else:
                self.preset_select_combo.setEnabled(True)
                for number, name, preset_type in presets:
                    type_str = f"[{preset_type.capitalize()}] " if preset_type.lower() != 'all' else ""
                    display_text = f"{type_str}P {number}"
                    if name: display_text += f": {name}"
                    self.preset_select_combo.addItem(display_text, str(number))
                if current_data is not None: 
                    idx = self.preset_select_combo.findData(current_data)
                    if idx != -1: self.preset_select_combo.setCurrentIndex(idx)
                    elif self.preset_select_combo.count() > 0 : self.preset_select_combo.setCurrentIndex(0)
                elif self.preset_select_combo.count() > 0 : self.preset_select_combo.setCurrentIndex(0)
        except Exception as e:
            print(f"Error loading presets for TimelineEventDialog: {e}")
            self.preset_select_combo.addItem("Error Loading Presets")
            self.preset_select_combo.setEnabled(False)

    def accept_data(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Input Error", "Event name cannot be empty.")
            return
        target_type_value = self.target_type_combo.currentData()
        if target_type_value in ["fixture", "group"] and (self.target_id_combo.currentData() is None or self.target_id_combo.currentData() == -1):
            QMessageBox.warning(self, "Input Error", f"A valid {target_type_value} must be selected for a '{target_type_value.capitalize()}' target type.")
            return
        
        trigger_type_value = self.trigger_type_combo.currentData()
        cue_id_value = self.cue_select_combo.currentData()

        if trigger_type_value == "relative_to_cue" and cue_id_value is None:
            QMessageBox.warning(self, "Input Error", "A Cue must be selected for 'Relative to Cue Trigger' type.")
            return
        if trigger_type_value == "follow_event_in_cue":
            if cue_id_value is None:
                QMessageBox.warning(self, "Input Error", "A Cue must be selected to follow an event within it.")
                return
            
            followed_event_id_value = self.followed_event_combo.currentData()
            if followed_event_id_value is None:
                QMessageBox.warning(self, "Input Error", "An Event must be selected to follow.")
                return
            
            valid_followed_event_ids_in_cue = []
            try:
                cursor = self.main_window.db_connection.cursor()
                query = "SELECT id FROM timeline_events WHERE cue_id = ?"
                params = [cue_id_value]
                if self.currently_edited_event_id is not None:
                    query += " AND id != ?"
                    params.append(self.currently_edited_event_id)
                cursor.execute(query, tuple(params))
                valid_followed_event_ids_in_cue = [row[0] for row in cursor.fetchall()]
            except Exception as e:
                print(f"DB error re-validating followed event: {e}") 

            if followed_event_id_value not in valid_followed_event_ids_in_cue:
                QMessageBox.warning(self, "Follow Event Invalid",
                                    f"The selected event to follow (ID: {followed_event_id_value}) is no longer valid for the chosen cue. "
                                    "It might have been deleted or moved. Please re-select or change trigger type.")
                self._populate_followed_event_combo() 
                return
        
        event_type_str = self.event_type_combo.currentText()
        if event_type_str == "preset":
            if self.preset_select_combo.currentData() is None:
                QMessageBox.warning(self, "Input Error", "A valid preset must be selected for a 'preset' event.")
                return

        self.accept()

    def get_data(self):
        data_obj = {} 
        event_type = self.event_type_combo.currentText()

        if event_type == "preset":
            data_obj['preset_number'] = self.preset_select_combo.currentData()
        elif event_type == "brightness":
            data_obj['value'] = self.brightness_value_spin.value()
            data_obj['fade_in'] = self.fade_in_spin.value()
            data_obj['fade_out'] = self.fade_out_spin.value()
        elif event_type == "color":
            data_obj['color_hex'] = self.color_button.property("color_hex")
        elif event_type == "pan":
            data_obj['value'] = self.pan_spin.value()
        elif event_type == "tilt":
            data_obj['value'] = self.tilt_spin.value()
        elif event_type == "zoom":
            data_obj['value'] = self.zoom_spin.value()
        elif event_type == "focus":
            data_obj['value'] = self.focus_spin.value()
        elif event_type == "gobo":
            data_obj['value'] = self.gobo_spin.value()
        elif event_type == "strobe":
            data_obj['value'] = self.strobe_spin.value()
        elif event_type == "blackout": 
            data_obj['action'] = 'toggle' 

        target_type = self.target_type_combo.currentData()
        target_id_val = None
        if target_type in ["fixture", "group"]:
            target_id_val = self.target_id_combo.currentData()
        
        cue_id_val = self.cue_select_combo.currentData()
        trigger_type_val = self.trigger_type_combo.currentData()
        data_obj['trigger_mode'] = trigger_type_val 
        
        if trigger_type_val == "follow_event_in_cue":
            data_obj['followed_event_id'] = self.followed_event_combo.currentData()
        else: 
            if 'followed_event_id' in data_obj: 
                del data_obj['followed_event_id']


        start_time_to_store = 0.0
        if trigger_type_val == "relative_to_cue" or trigger_type_val == "follow_event_in_cue":
            start_time_to_store = self.delay_edit.value() 
        else: 
            start_time_to_store = self.absolute_start_time_edit.value()


        result = {
            'name': self.name_edit.text().strip(),
            'start_time': start_time_to_store, 
            'duration': self.duration_edit.value(),
            'type': event_type,
            'data': data_obj, 
            'target_type': target_type,
            'target_id': target_id_val,
            'cue_id': cue_id_val 
        }
        if not self.is_new_event and 'id' in self.event_data_original:
            result['id'] = self.event_data_original['id']
        return result

class AssignEventToCueDialog(QDialog):
    def __init__(self, main_window, event_name: str, current_cue_id: int | None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.event_name_str = event_name
        self.current_cue_id = current_cue_id
        self.setWindowTitle(f"Set Cue for Event: {self.event_name_str}")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Assign event '{self.event_name_str}' to which Cue?"))

        self.cue_list_widget = QListWidget()
        self._populate_cues()
        layout.addWidget(self.cue_list_widget)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _populate_cues(self):
        self.cue_list_widget.clear()
        
        remove_item = QListWidgetItem("[Remove from Cue / Set to Absolute Time]")
        remove_item.setData(Qt.ItemDataRole.UserRole, None) 
        self.cue_list_widget.addItem(remove_item)

        selected_item_to_restore = None
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, cue_number, name, trigger_time_s FROM cues ORDER BY trigger_time_s, cue_number")
            cues = cursor.fetchall()
            for cue_id, cue_num, name, time_s in cues:
                display_name = f"Cue {cue_num}"
                if name: display_name += f": {name}"
                display_name += f" (@ {time_s:.2f}s)"
                item = QListWidgetItem(display_name)
                item.setData(Qt.ItemDataRole.UserRole, cue_id)
                self.cue_list_widget.addItem(item)
                if cue_id == self.current_cue_id:
                    selected_item_to_restore = item
        except Exception as e:
            print(f"Error populating cues in AssignEventToCueDialog: {e}")
            self.cue_list_widget.addItem("Error loading cues.")
        
        if selected_item_to_restore:
            self.cue_list_widget.setCurrentItem(selected_item_to_restore)
        elif self.current_cue_id is None and self.cue_list_widget.count() > 0 : 
             self.cue_list_widget.setCurrentItem(self.cue_list_widget.item(0))


    def get_selected_cue_id(self) -> int | None:
        current_item = self.cue_list_widget.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole) 
        return None


class TimelineWidget(QWidget): 
    playhead_moved_by_user = pyqtSignal(float) 
    event_modified_on_timeline = pyqtSignal(int, dict) 
    multiple_events_modified_on_timeline = pyqtSignal(list)
    event_delete_requested_on_timeline = pyqtSignal(int) 
    event_selected_on_timeline = pyqtSignal(list) 
    delete_multiple_events_requested = pyqtSignal(list) 

    cue_marker_clicked = pyqtSignal(int) 
    add_cue_requested_at_time = pyqtSignal(float)
    cue_modified_on_timeline = pyqtSignal(int, float) 
    assign_event_to_cue_requested = pyqtSignal(int) 

    MIN_PIXELS_PER_SECOND = 5
    MAX_PIXELS_PER_SECOND = 300
    EDGE_DRAG_SENSITIVITY_PIXELS = 8 
    MIN_EVENT_DURATION_S = 0.05 
    SNAP_THRESHOLD_PIXELS = 8 
    
    TIMELINE_LEFT_OFFSET = 0 
    RULER_HEIGHT = 30
    CUE_MARKER_AREA_HEIGHT = 20 
    AUDIO_TRACK_HEIGHT = 40
    EVENT_BASE_HEIGHT = 22
    TRACK_SPACING = 4
    TRACK_INTERNAL_PADDING = 2 

    def __init__(self, main_window, parent_tab_ref, parent=None): 
        super().__init__(parent)
        self.main_window = main_window
        self.parent_tab = parent_tab_ref 
        self.events = [] 
        self.cues = [] 
        self.audio_duration = 0.0 
        self.pixels_per_second = 30
        self.current_playhead_position = 0.0 
        self.is_playing = False 
        self.simulated_waveform_data = [] 
        
        self.is_dragging_playhead = False
        self.playhead_drag_offset = 0.0 
        
        self.is_panning_timeline = False
        self.pan_start_mouse_x = 0.0
        self.pan_start_scroll_value = 0
        
        self.is_marquee_selecting = False
        self.marquee_start_pos = QPointF()
        self.marquee_current_rect = QRectF()
        self.right_click_is_active = False # New flag for right-click start

        self.selected_event_ids: list[int] = [] 
        self.selected_cue_id: int | None = None 
        self.dragging_event_id: int | None = None 
        self.drag_start_multi_event_originals: dict[int, dict] = {}
        self.dragging_cue_id: int | None = None
        self.drag_mode: str | None = None 
        self.drag_start_event_original_start_s_or_delay: float = 0.0 
        self.drag_start_event_original_duration_s: float = 0.0 
        self.drag_start_cue_original_time_s: float = 0.0
        self.drag_start_mouse_x_pixels: float = 0.0
        self.drag_start_event_original_target_type: str | None = None
        self.drag_start_event_original_target_id: int | None = None
        
        self._painted_event_rects_map: dict[int, QRectF] = {} 
        self._painted_cue_marker_rects_map: dict[int, QRectF] = {} 
        self.tracks: list[dict] = [] 

        self.setMouseTracking(True) 
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_timeline_context_menu)


        self.setMinimumHeight(200) 
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._build_track_list() 
        self.load_events_from_db()
        self.load_cues_from_db() 

    def _build_track_list(self):
        self.tracks = [{'type': 'master', 'id': None, 'name': 'Master'}]
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name FROM fixture_groups ORDER BY name") 
            groups = cursor.fetchall()
            for gid, name in groups:
                self.tracks.append({'type': 'group', 'id': gid, 'name': f"{name} (Grp {gid})"})

            cursor.execute("SELECT id, name FROM fixtures ORDER BY id") 
            fixtures = cursor.fetchall()
            for fid, name in fixtures:
                self.tracks.append({'type': 'fixture', 'id': fid, 'name': f"{name} (Fx {fid})"})
        except Exception as e:
            print(f"Error building track list: {e}")
        self.update()


    def _generate_simulated_waveform(self): 
        self.simulated_waveform_data = []
        if self.audio_duration <= 0: 
            self.update()
            return
        points_per_second_of_audio = 50 
        num_points = int(self.audio_duration * points_per_second_of_audio)
        num_points = max(50, min(num_points, 20000)) 
        if num_points == 0:
            self.update()
            return
        last_amp = 0.5
        for i in range(num_points):
            rand_factor = (random.random() - 0.5) * 0.4 
            target_amp = last_amp + rand_factor
            if random.random() < 0.1 or target_amp < 0.05 or target_amp > 0.95:
                target_amp = 0.5 + (random.random() - 0.5) * 0.3
            target_amp = max(0.05, min(0.95, target_amp)) 
            current_amp = last_amp * 0.6 + target_amp * 0.4
            self.simulated_waveform_data.append(current_amp)
            last_amp = current_amp
        self.update()

    def _update_minimum_widget_width(self):
        max_time_for_width = self.audio_duration
        if self.events:
             event_end_time = max((self._get_effective_event_start_time(ev) + self._get_event_visual_duration_s(ev) for ev in self.events), default=0) 
             max_time_for_width = max(max_time_for_width, event_end_time)
        if self.cues: 
            cue_max_time = max((c['trigger_time_s'] for c in self.cues), default=0)
            max_time_for_width = max(max_time_for_width, cue_max_time)

        self.setMinimumWidth(int(max_time_for_width * self.pixels_per_second) + 100)


    def load_events_from_db(self, regenerate_waveform=True): 
        self._build_track_list() 
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name, start_time, duration, event_type, data, target_type, target_id, cue_id FROM timeline_events") 
            db_events = cursor.fetchall()
            self.events = []
            for ev_tuple in db_events:
                start_time_or_delay = float(ev_tuple[2]) 
                
                event_data_json = json.loads(ev_tuple[5]) if isinstance(ev_tuple[5], str) else ev_tuple[5]
                if not isinstance(event_data_json, dict): event_data_json = {} 
                trigger_mode = event_data_json.get('trigger_mode', 'absolute')

                if trigger_mode == 'absolute':
                    if start_time_or_delay < 0 : start_time_or_delay = 0.0
                else: 
                     if start_time_or_delay < -3600 : start_time_or_delay = -3600.0


                event_item = {
                    'id': ev_tuple[0], 'name': ev_tuple[1], 'start_time': start_time_or_delay,
                    'duration': float(ev_tuple[3]), 'type': ev_tuple[4],
                    'data': event_data_json,
                    'target_type': ev_tuple[6] if ev_tuple[6] else 'master', 
                    'target_id': ev_tuple[7],
                    'cue_id': ev_tuple[8] 
                }
                self.events.append(event_item)
            
            self.events.sort(key=lambda ev: self._get_effective_event_start_time(ev))


            self._update_minimum_widget_width()
            if regenerate_waveform and self.audio_duration > 0 : 
                self._generate_simulated_waveform() 
            self.update() 
        except Exception as e:
            print(f"Error loading timeline events from DB: {e}")

    def _get_effective_event_start_time(self, event_data: dict, recursion_depth=0, visited_ids=None) -> float:
        MAX_RECURSION_DEPTH = 10 
        if visited_ids is None: visited_ids = set()
        
        event_id = event_data.get('id')
        if event_id is not None and event_id in visited_ids:
            print(f"Warning: Circular dependency detected for event ID {event_id} at depth {recursion_depth}. Defaulting to fallback timing.")
            if event_data.get('cue_id') is not None:
                cue = next((c for c in self.cues if c['id'] == event_data['cue_id']), None)
                if cue: return cue['trigger_time_s'] + event_data.get('start_time', 0.0) 
            return event_data.get('start_time', 0.0) 
        
        if recursion_depth > MAX_RECURSION_DEPTH:
            print(f"Warning: Max recursion depth ({MAX_RECURSION_DEPTH}) reached for event ID {event_id}. Defaulting to fallback timing.")
            if event_data.get('cue_id') is not None:
                cue = next((c for c in self.cues if c['id'] == event_data['cue_id']), None)
                if cue: return cue['trigger_time_s'] + event_data.get('start_time', 0.0)
            return event_data.get('start_time', 0.0)

        current_visited_ids = visited_ids.copy()
        if event_id is not None: current_visited_ids.add(event_id)

        trigger_mode = event_data.get('data', {}).get('trigger_mode', 'absolute')
        delay_or_absolute_start = event_data.get('start_time', 0.0)
        
        if trigger_mode == 'relative_to_cue' and event_data.get('cue_id') is not None:
            cue = next((c for c in self.cues if c['id'] == event_data['cue_id']), None)
            if cue:
                return cue['trigger_time_s'] + delay_or_absolute_start
        
        elif trigger_mode == 'follow_event_in_cue' and event_data.get('cue_id') is not None:
            followed_event_id = event_data.get('data', {}).get('followed_event_id')
            current_event_cue_id = event_data.get('cue_id')

            if followed_event_id is not None:
                followed_event = next((ev for ev in self.events if ev['id'] == followed_event_id), None)
                if followed_event:
                    if followed_event.get('cue_id') == current_event_cue_id:
                        followed_event_effective_start = self._get_effective_event_start_time(followed_event, recursion_depth + 1, current_visited_ids)
                        
                        followed_event_visual_duration = self._get_event_visual_duration_s(followed_event)
                        
                        followed_event_end_time = followed_event_effective_start + followed_event_visual_duration
                        return followed_event_end_time + delay_or_absolute_start
                    else:
                        print(f"Warning: Event ID {event_id} follows event ID {followed_event_id} which is not in the same cue ({current_event_cue_id}). Fallback to relative to cue.")
                        cue = next((c for c in self.cues if c['id'] == current_event_cue_id), None)
                        if cue: return cue['trigger_time_s'] + delay_or_absolute_start
            
            cue = next((c for c in self.cues if c['id'] == current_event_cue_id), None)
            if cue: return cue['trigger_time_s'] + delay_or_absolute_start 
            
        return delay_or_absolute_start 

    def load_cues_from_db(self):
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, cue_number, name, trigger_time_s, comment FROM cues ORDER BY trigger_time_s")
            fetched_cues = cursor.fetchall()
            self.cues = []
            for cue_tuple in fetched_cues:
                self.cues.append({
                    'id': cue_tuple[0], 'cue_number': cue_tuple[1], 'name': cue_tuple[2],
                    'trigger_time_s': float(cue_tuple[3]), 'comment': cue_tuple[4]
                })
            self._update_minimum_widget_width() 
            self.update()
        except Exception as e:
            print(f"Error loading cues from DB: {e}")


    def set_audio_duration(self, duration_seconds):
        self.audio_duration = duration_seconds
        self._update_minimum_widget_width()
        if self.audio_duration > 0 : self._generate_simulated_waveform()
        else: self.simulated_waveform_data.clear()
        self.update()

    def set_playhead_position(self, position_seconds, from_user_seek=False):
        old_pos = self.current_playhead_position
        self.current_playhead_position = position_seconds
        if abs(old_pos - position_seconds) > 0.001 : 
            self.update() 
        if from_user_seek: 
            self.playhead_moved_by_user.emit(self.current_playhead_position)

    def get_current_playhead_time(self) -> float:
        return self.current_playhead_position

    def _get_track_y_start_and_height(self, track_index: int) -> tuple[float, float]:
        y_offset_within_tracks_area = 0 
        track_full_height = self.EVENT_BASE_HEIGHT + self.TRACK_SPACING + (2 * self.TRACK_INTERNAL_PADDING) 
        track_y = y_offset_within_tracks_area + track_index * track_full_height
        return track_y, self.EVENT_BASE_HEIGHT 

    def _get_event_visual_duration_s(self, event_data: dict) -> float:
        """Helper to get the full visual duration of an event, including fades."""
        visual_duration_s = event_data.get('duration', 0.0) 
        if event_data.get('type') == 'brightness':
            data_payload = event_data.get('data', {})
            visual_duration_s += data_payload.get('fade_in', 0.0) 
            visual_duration_s += data_payload.get('fade_out', 0.0)
            if event_data.get('duration', 0.0) == 0 and visual_duration_s == 0 : 
                visual_duration_s = self.MIN_EVENT_DURATION_S 
        elif visual_duration_s == 0: 
             visual_duration_s = self.MIN_EVENT_DURATION_S
        return visual_duration_s

    def _get_event_rect_on_track(self, event_data, track_y_pos, event_base_height) -> QRectF:
        effective_start_time_s = self._get_effective_event_start_time(event_data)
        start_x = effective_start_time_s * self.pixels_per_second
        
        visual_duration_s = self._get_event_visual_duration_s(event_data)
        event_visual_duration_pixels = max(3, visual_duration_s * self.pixels_per_second)
        
        display_start_x = start_x 

        return QRectF(display_start_x, track_y_pos + self.TRACK_INTERNAL_PADDING, event_visual_duration_pixels, event_base_height)


    def _get_event_at_pixel_pos(self, pos: QPointF) -> tuple[int | None, str | None]: 
        y_event_tracks_start_abs = self.RULER_HEIGHT + self.TRACK_SPACING

        for event_data in self.events: 
            event_id = event_data['id']
            event_rect_on_content_area = self._painted_event_rects_map.get(event_id) 
            
            if event_rect_on_content_area:
                if event_rect_on_content_area.contains(pos):
                    if len(self.selected_event_ids) <= 1 or (len(self.selected_event_ids) == 1 and self.selected_event_ids[0] == event_id) :
                        if abs(pos.x() - event_rect_on_content_area.left()) < self.EDGE_DRAG_SENSITIVITY_PIXELS:
                            return event_id, "resize_left"
                        elif abs(pos.x() - event_rect_on_content_area.right()) < self.EDGE_DRAG_SENSITIVITY_PIXELS:
                            return event_id, "resize_right"
                    return event_id, "move" 
        return None, None
    
    def _get_cue_at_pixel_pos(self, pos: QPointF) -> int | None:
        total_event_tracks_height = 0
        if self.tracks:
            total_event_tracks_height = len(self.tracks) * (self.EVENT_BASE_HEIGHT + self.TRACK_SPACING + 2 * self.TRACK_INTERNAL_PADDING)
        
        cue_area_y_start = self.RULER_HEIGHT + self.TRACK_SPACING + total_event_tracks_height 

        cue_area_full_rect = QRectF(0, cue_area_y_start, self.width(), self.CUE_MARKER_AREA_HEIGHT)
        if not cue_area_full_rect.contains(pos):
            return None
        
        for cue_id, cue_rect_in_map in self._painted_cue_marker_rects_map.items():
            clickable_cue_rect = cue_rect_in_map.adjusted(-3, -3, 3, 3) 
            if clickable_cue_rect.contains(pos):
                return cue_id
        return None


    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            scroll_widget = self.parentWidget()
            scroll_area = None
            if scroll_widget and isinstance(scroll_widget, QScrollArea): 
                 scroll_area = scroll_widget
            elif scroll_widget and scroll_widget.parentWidget() and isinstance(scroll_widget.parentWidget(), QScrollArea):
                 scroll_area = scroll_widget.parentWidget()
            
            if not scroll_area:
                super().wheelEvent(event); return

            delta = event.angleDelta().y()
            zoom_factor = 1.15 if delta > 0 else 1 / 1.15
            
            old_pixels_per_second = self.pixels_per_second
            self.pixels_per_second = max(self.MIN_PIXELS_PER_SECOND, min(self.MAX_PIXELS_PER_SECOND, old_pixels_per_second * zoom_factor))

            if abs(old_pixels_per_second - self.pixels_per_second) > 0.1: 
                mouse_x_on_timeline_area = event.position().x() 
                time_at_mouse_before_zoom = mouse_x_on_timeline_area / old_pixels_per_second if old_pixels_per_second > 0 else 0
                
                self._update_minimum_widget_width() 
                self.update() 

                new_mouse_x_on_timeline_area_if_no_scroll_change = time_at_mouse_before_zoom * self.pixels_per_second
                new_scrollbar_value = scroll_area.horizontalScrollBar().value() + (new_mouse_x_on_timeline_area_if_no_scroll_change - mouse_x_on_timeline_area)
                scroll_area.horizontalScrollBar().setValue(int(new_scrollbar_value))
                self.update() 
            event.accept()
        else:
            super().wheelEvent(event) 


    def mousePressEvent(self, event_mouse: QMouseEvent): 
        click_pos = event_mouse.position() 
        timeline_content_x = click_pos.x() 
        
        event_id_under_cursor, _ = self._get_event_at_pixel_pos(click_pos)
        cue_id_at_click = self._get_cue_at_pixel_pos(click_pos)
        
        is_ctrl_pressed = bool(event_mouse.modifiers() & Qt.KeyboardModifier.ControlModifier)

        if event_mouse.button() == Qt.MouseButton.LeftButton:
            playhead_x_on_timeline_content = self.current_playhead_position * self.pixels_per_second
            playhead_clickable_rect_on_widget = QRectF(playhead_x_on_timeline_content - 5, 0, 10, self.height())

            if cue_id_at_click is not None:
                self.dragging_cue_id = cue_id_at_click
                cue_obj = next((c for c in self.cues if c['id'] == cue_id_at_click), None)
                if cue_obj:
                    self.drag_start_cue_original_time_s = cue_obj['trigger_time_s']
                    self.drag_start_mouse_x_pixels = timeline_content_x
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                    if self.selected_cue_id != cue_id_at_click:
                        self.selected_event_ids.clear(); self.event_selected_on_timeline.emit([])
                        self.selected_cue_id = cue_id_at_click
                        self.cue_marker_clicked.emit(cue_id_at_click)
                    self.update()
                event_mouse.accept(); return

            if playhead_clickable_rect_on_widget.contains(click_pos):
                self.is_dragging_playhead = True
                self.playhead_drag_offset = playhead_x_on_timeline_content - timeline_content_x
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.selected_event_ids.clear(); self.event_selected_on_timeline.emit([])
                if self.selected_cue_id is not None: self.selected_cue_id = None; self.cue_marker_clicked.emit(-1)
                self.update(); event_mouse.accept(); return

            event_id, drag_mode_detected = self._get_event_at_pixel_pos(click_pos)
            if event_id is not None:
                event_obj = next((ev for ev in self.events if ev['id'] == event_id), None)
                if event_obj:
                    if self.selected_cue_id is not None: self.selected_cue_id = None; self.cue_marker_clicked.emit(-1)
                    if is_ctrl_pressed:
                        if event_id in self.selected_event_ids: self.selected_event_ids.remove(event_id)
                        else: self.selected_event_ids.append(event_id)
                    else:
                        if event_id not in self.selected_event_ids: self.selected_event_ids = [event_id]
                    
                    self.event_selected_on_timeline.emit(list(self.selected_event_ids))
                    
                    self.drag_start_multi_event_originals.clear()
                    for selected_id in self.selected_event_ids:
                        sel_event_obj = next((e for e in self.events if e['id'] == selected_id), None)
                        if sel_event_obj:
                            self.drag_start_multi_event_originals[selected_id] = {'start_time': sel_event_obj['start_time']}

                    # NEW: Add logic for capturing single event state for resizing
                    if drag_mode_detected in ["resize_left", "resize_right"]:
                        self.drag_start_event_original_start_s_or_delay = event_obj.get('start_time', 0.0)
                        self.drag_start_event_original_duration_s = event_obj.get('duration', 0.0)

                    self.dragging_event_id = event_id # This is the "anchor" event
                    self.drag_mode = "move_multi" if len(self.selected_event_ids) > 1 else drag_mode_detected
                    self.drag_start_mouse_x_pixels = timeline_content_x

                    if self.drag_mode == "move": self.setCursor(Qt.CursorShape.OpenHandCursor)
                    else: self.setCursor(Qt.CursorShape.SizeHorCursor)

                    self.update(); event_mouse.accept(); return
            
            deselected_something = False
            if self.selected_event_ids: self.selected_event_ids.clear(); self.event_selected_on_timeline.emit([]); deselected_something = True
            if self.selected_cue_id is not None: self.selected_cue_id = None; self.cue_marker_clicked.emit(-1); deselected_something = True
            if deselected_something: self.update()
            
            if self.pixels_per_second > 0 and cue_id_at_click is None:
                new_pos_seconds = timeline_content_x / self.pixels_per_second
                self.set_playhead_position(max(0, new_pos_seconds), from_user_seek=True)
                event_mouse.accept(); return

        elif event_mouse.button() == Qt.MouseButton.MiddleButton:
            parent_vp = self.parentWidget()
            scroll_area = parent_vp.parentWidget() if parent_vp and isinstance(parent_vp.parentWidget(), QScrollArea) else parent_vp if isinstance(parent_vp, QScrollArea) else None
            if scroll_area:
                self.is_panning_timeline = True; self.pan_start_mouse_x = event_mouse.position().x()
                self.pan_start_scroll_value = scroll_area.horizontalScrollBar().value()
                self.setCursor(Qt.CursorShape.ClosedHandCursor); event_mouse.accept(); return

        elif event_mouse.button() == Qt.MouseButton.RightButton:
            self.right_click_is_active = True
            self.marquee_start_pos = click_pos
            event_mouse.accept()

    def _get_snap_targets(self, event_to_modify: dict | None) -> list[float]:
        """Generates a list of time points (in seconds) for potential snapping."""
        snap_targets_s = [self.current_playhead_position]
        
        currently_dragged_ids = {self.dragging_event_id}
        if self.drag_mode == "move_multi":
            currently_dragged_ids.update(self.selected_event_ids)

        for other_ev in self.events:
            if other_ev['id'] in currently_dragged_ids:
                continue

            if self.drag_mode != "move_multi":
                if event_to_modify and self._get_track_index_for_event(other_ev) != self._get_track_index_for_event(event_to_modify):
                    continue
            
            other_ev_start_s = self._get_effective_event_start_time(other_ev)
            other_ev_visual_dur_s = self._get_event_visual_duration_s(other_ev)
            snap_targets_s.append(other_ev_start_s)
            snap_targets_s.append(other_ev_start_s + other_ev_visual_dur_s)
        
        for cue in self.cues:
            snap_targets_s.append(cue['trigger_time_s'])
            
        return sorted(list(set(snap_targets_s)))


    def mouseMoveEvent(self, event_mouse: QMouseEvent): 
        click_pos = event_mouse.position() 
        timeline_content_x = click_pos.x() 

        if self.is_dragging_playhead and event_mouse.buttons() & Qt.MouseButton.LeftButton:
            if self.pixels_per_second > 0:
                new_x_on_timeline_content = timeline_content_x + self.playhead_drag_offset
                new_pos_seconds = new_x_on_timeline_content / self.pixels_per_second
                effective_duration = self._get_effective_total_duration()
                clamped_pos_seconds = max(0, min(new_pos_seconds, effective_duration if effective_duration > 0 else float('inf')))
                self.set_playhead_position(clamped_pos_seconds, from_user_seek=True)
                event_mouse.accept(); return

        elif self.dragging_cue_id is not None and event_mouse.buttons() & Qt.MouseButton.LeftButton:
            cue_to_modify = next((c for c in self.cues if c['id'] == self.dragging_cue_id), None)
            if not cue_to_modify: return
            if self.pixels_per_second > 0:
                mouse_dx_pixels = timeline_content_x - self.drag_start_mouse_x_pixels
                time_delta_s = mouse_dx_pixels / self.pixels_per_second
                new_cue_time_candidate = self.drag_start_cue_original_time_s + time_delta_s
                
                snap_targets_s = [self.current_playhead_position] 
                for ev in self.events:
                    ev_start = self._get_effective_event_start_time(ev)
                    ev_dur = self._get_event_visual_duration_s(ev)
                    snap_targets_s.append(ev_start)
                    snap_targets_s.append(ev_start + ev_dur)

                final_new_cue_time = new_cue_time_candidate
                for target_s in sorted(list(set(snap_targets_s))):
                    if abs((new_cue_time_candidate * self.pixels_per_second) - (target_s * self.pixels_per_second)) < self.SNAP_THRESHOLD_PIXELS:
                        final_new_cue_time = target_s
                        break
                
                cue_to_modify['trigger_time_s'] = max(0.0, final_new_cue_time)
                self.cues.sort(key=lambda c: (c['trigger_time_s'], c['cue_number'])) 
                self.update() 
                event_mouse.accept(); return

        elif self.dragging_event_id is not None and event_mouse.buttons() & Qt.MouseButton.LeftButton:
            anchor_event = next((ev for ev in self.events if ev['id'] == self.dragging_event_id), None)
            if not anchor_event: return

            if self.drag_mode == "move_multi":
                mouse_dx_pixels = timeline_content_x - self.drag_start_mouse_x_pixels
                time_delta_s = mouse_dx_pixels / self.pixels_per_second
                
                leading_event = min([ev for ev in self.events if ev['id'] in self.selected_event_ids], 
                                    key=lambda x: self._get_effective_event_start_time(x))
                
                original_leading_info = self.drag_start_multi_event_originals.get(leading_event['id'])
                if not original_leading_info: return

                proposed_raw_start_for_leading = original_leading_info['start_time'] + time_delta_s

                snap_targets_s = self._get_snap_targets(leading_event)
                temp_leading_for_snap = copy.deepcopy(leading_event)
                temp_leading_for_snap['start_time'] = proposed_raw_start_for_leading
                proposed_abs_start_for_leading = self._get_effective_event_start_time(temp_leading_for_snap)

                final_abs_start_for_leading = proposed_abs_start_for_leading
                for target_s in snap_targets_s:
                    if abs((proposed_abs_start_for_leading * self.pixels_per_second) - (target_s * self.pixels_per_second)) < self.SNAP_THRESHOLD_PIXELS:
                        final_abs_start_for_leading = target_s
                        break
                
                original_leading_state_for_calc = copy.deepcopy(leading_event)
                original_leading_state_for_calc['start_time'] = original_leading_info['start_time']
                original_effective_start_of_leading = self._get_effective_event_start_time(original_leading_state_for_calc)
                
                snapped_time_delta = final_abs_start_for_leading - original_effective_start_of_leading
                
                for event_id_in_group in self.selected_event_ids:
                    event_in_group = next((ev for ev in self.events if ev['id'] == event_id_in_group), None)
                    original_info_for_event = self.drag_start_multi_event_originals.get(event_id_in_group)
                    if event_in_group and original_info_for_event:
                        new_start_time = original_info_for_event['start_time'] + snapped_time_delta
                        trigger_mode_event = event_in_group.get('data', {}).get('trigger_mode', 'absolute')
                        event_in_group['start_time'] = max(0.0, new_start_time) if trigger_mode_event == 'absolute' else new_start_time

            else: # Single event drag logic
                mouse_dx_pixels_on_timeline = timeline_content_x - self.drag_start_mouse_x_pixels
                time_delta_s = mouse_dx_pixels_on_timeline / self.pixels_per_second
                
                trigger_mode = anchor_event.get('data', {}).get('trigger_mode', 'absolute')
                snap_targets_s = self._get_snap_targets(anchor_event) 
                
                if self.drag_mode == "move":
                    original_info = self.drag_start_multi_event_originals.get(self.dragging_event_id)
                    if not original_info: return
                    proposed_raw_delay_or_start = original_info['start_time'] + time_delta_s
                    temp_event_for_snap_check = anchor_event.copy()
                    temp_event_for_snap_check['start_time'] = proposed_raw_delay_or_start
                    if 'data' not in temp_event_for_snap_check: temp_event_for_snap_check['data'] = {}
                    temp_event_for_snap_check['data']['trigger_mode'] = trigger_mode 
                    proposed_abs_start_s_for_snap = self._get_effective_event_start_time(temp_event_for_snap_check)
                    final_abs_start_s = proposed_abs_start_s_for_snap
                    for target_s in snap_targets_s:
                        if abs((proposed_abs_start_s_for_snap * self.pixels_per_second) - (target_s * self.pixels_per_second)) < self.SNAP_THRESHOLD_PIXELS:
                            final_abs_start_s = target_s
                            break
                    new_start_time_to_store = 0.0
                    if trigger_mode == "relative_to_cue" and anchor_event.get('cue_id') is not None:
                        cue = next((c for c in self.cues if c['id'] == anchor_event['cue_id']), None)
                        if cue: new_start_time_to_store = final_abs_start_s - cue['trigger_time_s']
                        else: new_start_time_to_store = final_abs_start_s 
                    elif trigger_mode == "follow_event_in_cue" and anchor_event.get('cue_id') is not None:
                        followed_event_id = anchor_event.get('data',{}).get('followed_event_id')
                        followed_event = next((ev_f for ev_f in self.events if ev_f['id'] == followed_event_id and ev_f.get('cue_id') == anchor_event['cue_id']), None)
                        if followed_event:
                            followed_end = self._get_effective_event_start_time(followed_event) + self._get_event_visual_duration_s(followed_event)
                            new_start_time_to_store = final_abs_start_s - followed_end
                        else: 
                            cue = next((c for c in self.cues if c['id'] == anchor_event['cue_id']), None)
                            if cue: new_start_time_to_store = final_abs_start_s - cue['trigger_time_s']
                            else: new_start_time_to_store = final_abs_start_s
                    else: 
                        new_start_time_to_store = max(0.0, final_abs_start_s)
                    anchor_event['start_time'] = new_start_time_to_store
                    y_event_tracks_start_abs = self.RULER_HEIGHT + self.TRACK_SPACING
                    mouse_y_relative_to_tracks_start = click_pos.y() - y_event_tracks_start_abs
                    target_track_index_under_mouse = -1
                    cumulative_height_check = 0
                    for idx, track_data_iter in enumerate(self.tracks):
                        track_full_height_iter = self.EVENT_BASE_HEIGHT + self.TRACK_SPACING + (2 * self.TRACK_INTERNAL_PADDING)
                        if cumulative_height_check <= mouse_y_relative_to_tracks_start < cumulative_height_check + track_full_height_iter:
                            target_track_index_under_mouse = idx; break
                        cumulative_height_check += track_full_height_iter
                    if 0 <= target_track_index_under_mouse < len(self.tracks):
                        new_track_info = self.tracks[target_track_index_under_mouse]
                        anchor_event['target_type'] = new_track_info['type']; anchor_event['target_id'] = new_track_info['id']
                    else: 
                        anchor_event['target_type'] = self.drag_start_event_original_target_type
                        anchor_event['target_id'] = self.drag_start_event_original_target_id
                
                elif self.drag_mode == "resize_right":
                    new_duration_candidate = self.drag_start_event_original_duration_s + time_delta_s
                    temp_event_for_calc = anchor_event.copy()
                    temp_event_for_calc['start_time'] = self.drag_start_event_original_start_s_or_delay
                    original_effective_start_s = self._get_effective_event_start_time(temp_event_for_calc)
                    proposed_end_time_s = original_effective_start_s + new_duration_candidate
                    snapped_end_time_s = proposed_end_time_s
                    for target_s in snap_targets_s:
                        if abs((proposed_end_time_s * self.pixels_per_second) - (target_s * self.pixels_per_second)) < self.SNAP_THRESHOLD_PIXELS:
                            snapped_end_time_s = target_s
                            break
                    new_duration = snapped_end_time_s - original_effective_start_s
                    anchor_event['duration'] = max(self.MIN_EVENT_DURATION_S, new_duration)

                elif self.drag_mode == "resize_left":
                    temp_event_for_calc = anchor_event.copy()
                    temp_event_for_calc['start_time'] = self.drag_start_event_original_start_s_or_delay
                    original_effective_start_s = self._get_effective_event_start_time(temp_event_for_calc)
                    proposed_new_abs_start = original_effective_start_s + time_delta_s
                    snapped_new_abs_start = proposed_new_abs_start
                    for target_s in snap_targets_s:
                        if abs((proposed_new_abs_start * self.pixels_per_second) - (target_s * self.pixels_per_second)) < self.SNAP_THRESHOLD_PIXELS:
                            snapped_new_abs_start = target_s
                            break
                    final_abs_delta_s = snapped_new_abs_start - original_effective_start_s
                    new_start_val = self.drag_start_event_original_start_s_or_delay + final_abs_delta_s
                    new_duration_val = self.drag_start_event_original_duration_s - final_abs_delta_s
                    if new_duration_val >= self.MIN_EVENT_DURATION_S:
                        anchor_event['start_time'] = new_start_val
                        anchor_event['duration'] = new_duration_val

            self.events.sort(key=lambda ev: (self._get_track_index_for_event(ev), self._get_effective_event_start_time(ev))) 
            self._update_minimum_widget_width(); self.update()
            event_mouse.accept(); return
        
        elif self.is_panning_timeline and event_mouse.buttons() & Qt.MouseButton.MiddleButton:
            parent_vp = self.parentWidget()
            scroll_area = parent_vp.parentWidget() if parent_vp and isinstance(parent_vp.parentWidget(), QScrollArea) else parent_vp if isinstance(parent_vp, QScrollArea) else None
            if scroll_area:
                dx = event_mouse.position().x() - self.pan_start_mouse_x
                scroll_area.horizontalScrollBar().setValue(self.pan_start_scroll_value - int(dx))
                event_mouse.accept(); return
        
        elif self.right_click_is_active and event_mouse.buttons() & Qt.MouseButton.RightButton:
            if not self.is_marquee_selecting and (self.marquee_start_pos - click_pos).manhattanLength() > QApplication.startDragDistance():
                self.is_marquee_selecting = True
                
            if self.is_marquee_selecting:
                self.marquee_current_rect = QRectF(self.marquee_start_pos, click_pos).normalized()
                
                newly_selected_ids = set()
                for event_id, event_rect in self._painted_event_rects_map.items():
                    if self.marquee_current_rect.intersects(event_rect):
                        newly_selected_ids.add(event_id)
                
                if set(self.selected_event_ids) != newly_selected_ids:
                    self.selected_event_ids = list(newly_selected_ids)
                    self.event_selected_on_timeline.emit(list(self.selected_event_ids))
                self.update(); event_mouse.accept(); return

        else: 
            playhead_x_on_widget = self.current_playhead_position * self.pixels_per_second
            draggable_playhead_rect_on_widget = QRectF(playhead_x_on_widget - 5, 0, 10, self.height())
            new_cursor = Qt.CursorShape.ArrowCursor 
            if draggable_playhead_rect_on_widget.contains(click_pos): new_cursor = Qt.CursorShape.SizeHorCursor
            else:
                _, hover_drag_mode = self._get_event_at_pixel_pos(click_pos)
                if hover_drag_mode == "move": new_cursor = Qt.CursorShape.OpenHandCursor 
                elif hover_drag_mode in ["resize_left", "resize_right"]:
                    if len(self.selected_event_ids) <= 1: new_cursor = Qt.CursorShape.SizeHorCursor
                elif self._get_cue_at_pixel_pos(click_pos) is not None: new_cursor = Qt.CursorShape.SizeHorCursor 
            if self.cursor().shape() != new_cursor: self.setCursor(new_cursor)
        super().mouseMoveEvent(event_mouse)

    def _get_track_index_for_event(self, event_data: dict) -> int:
        target_type = event_data.get('target_type', 'master')
        target_id = event_data.get('target_id')
        try: 
            return next(i for i, t in enumerate(self.tracks) 
                        if t['type'] == target_type and t['id'] == target_id)
        except StopIteration: 
            return 0 
            

    def mouseReleaseEvent(self, event_mouse: QMouseEvent): 
        if self.is_dragging_playhead and event_mouse.button() == Qt.MouseButton.LeftButton:
            self.is_dragging_playhead = False; self.unsetCursor(); event_mouse.accept(); return
        
        if self.is_panning_timeline and event_mouse.button() == Qt.MouseButton.MiddleButton:
            self.is_panning_timeline = False; self.unsetCursor(); event_mouse.accept(); return
        
        if self.right_click_is_active and event_mouse.button() == Qt.MouseButton.RightButton:
            if not self.is_marquee_selecting:
                self._show_timeline_context_menu(event_mouse.pos())
            self.is_marquee_selecting = False
            self.right_click_is_active = False
            self.marquee_current_rect = QRectF()
            self.update()
            event_mouse.accept(); return


        if self.dragging_event_id is not None and event_mouse.button() == Qt.MouseButton.LeftButton:
            if self.drag_mode == "move_multi":
                modified_events_data = []
                for event_id in self.selected_event_ids:
                    event_obj = next((ev for ev in self.events if ev['id'] == event_id), None)
                    if event_obj:
                         modified_events_data.append({'id': event_id, 'start_time': event_obj['start_time'], 
                                                      'target_type': event_obj['target_type'], 'target_id': event_obj['target_id']})
                if modified_events_data:
                    self.multiple_events_modified_on_timeline.emit(modified_events_data)
            else:
                event_obj = next((ev for ev in self.events if ev['id'] == self.dragging_event_id), None)
                if event_obj: 
                    modified_data = {'start_time': event_obj['start_time'], 'duration': event_obj['duration'], 
                                     'target_type': event_obj['target_type'], 'target_id': event_obj['target_id'],
                                     'data': event_obj['data'], 'cue_id': event_obj.get('cue_id')}
                    self.event_modified_on_timeline.emit(self.dragging_event_id, modified_data)
            
            self.dragging_event_id = None
            self.drag_mode = None
            self.drag_start_multi_event_originals.clear()
            self.unsetCursor()
            event_mouse.accept(); return

        super().mouseReleaseEvent(event_mouse)

    def _show_timeline_context_menu(self, pos_in_widget_coords: QPoint):
        if self.is_marquee_selecting: return

        global_pos = self.mapToGlobal(pos_in_widget_coords)
        menu = QMenu(self)

        cue_id_at_click = self._get_cue_at_pixel_pos(QPointF(pos_in_widget_coords))
        
        event_id_for_single_actions = None
        event_obj_for_single_actions = None

        if self.selected_event_ids:
            if len(self.selected_event_ids) == 1: 
                event_id_for_single_actions = self.selected_event_ids[0]
                event_obj_for_single_actions = next((ev for ev in self.events if ev['id'] == event_id_for_single_actions), None)
        else: 
            event_id_under_cursor, _ = self._get_event_at_pixel_pos(QPointF(pos_in_widget_coords))
            if event_id_under_cursor:
                event_id_for_single_actions = event_id_under_cursor
                event_obj_for_single_actions = next((ev for ev in self.events if ev['id'] == event_id_for_single_actions), None)
                if event_id_for_single_actions not in self.selected_event_ids: 
                     self.selected_event_ids = [event_id_for_single_actions]
                     self.event_selected_on_timeline.emit(list(self.selected_event_ids))
                     self.update()


        if cue_id_at_click is not None:
            cue_obj_at_click = next((c for c in self.cues if c['id'] == cue_id_at_click), None)
            if not cue_obj_at_click: return

            if self.selected_cue_id != cue_id_at_click:
                self.selected_cue_id = cue_id_at_click
                self.cue_marker_clicked.emit(cue_id_at_click) 
                self.selected_event_ids.clear() 
                self.event_selected_on_timeline.emit([])
                self.update()
            
            cue_name = cue_obj_at_click.get('cue_number', str(cue_id_at_click))
            if cue_obj_at_click.get('name'): cue_name += f": {cue_obj_at_click['name']}"
            
            edit_cue_action = QAction(f"Edit Cue '{cue_name}'...", self)
            edit_cue_action.triggered.connect(lambda: self.parent_tab.show_edit_cue_dialog(cue_id_to_edit=cue_id_at_click))
            menu.addAction(edit_cue_action)

            delete_cue_action = QAction(f"Delete Cue '{cue_name}'", self)
            delete_cue_action.triggered.connect(lambda: self.parent_tab.delete_selected_cue(cue_id_to_delete=cue_id_at_click))
            menu.addAction(delete_cue_action)


        elif self.selected_event_ids: 
            if len(self.selected_event_ids) >= 1:
                copy_action = QAction(f"Copy {len(self.selected_event_ids)} Event(s)", self)
                copy_action.triggered.connect(self.parent_tab._handle_copy_request)
                menu.addAction(copy_action)

            if len(self.selected_event_ids) == 1 and event_obj_for_single_actions:
                event_name = event_obj_for_single_actions['name']
                edit_event_action = QAction(f"Edit Event '{event_name}'...", self)
                menu.addAction(edit_event_action)
                edit_event_action.triggered.connect(self.parent_tab.show_edit_event_dialog)

                action_text = "Set Cue for Event..." if event_obj_for_single_actions.get('cue_id') is None else "Change Cue for Event..."
                set_cue_action = QAction(action_text, self)
                set_cue_action.triggered.connect(lambda checked=False, ev_id=event_obj_for_single_actions['id']: self.assign_event_to_cue_requested.emit(ev_id))
                menu.addAction(set_cue_action)

                delete_event_action = QAction(f"Delete Event '{event_name}'", self)
                delete_event_action.triggered.connect(lambda: self.event_delete_requested_on_timeline.emit(event_obj_for_single_actions['id']))
                menu.addAction(delete_event_action)
            
            elif len(self.selected_event_ids) > 1:
                delete_multi_action = QAction(f"Delete {len(self.selected_event_ids)} Selected Events", self)
                delete_multi_action.triggered.connect(lambda: self.delete_multiple_events_requested.emit(list(self.selected_event_ids)))
                menu.addAction(delete_multi_action)
        
        else: 
            if self.parent_tab.event_clipboard:
                paste_action = QAction(f"Paste {len(self.parent_tab.event_clipboard)} Event(s) here", self)
                paste_action.triggered.connect(lambda: self.parent_tab._handle_paste_request(pos_in_widget_coords))
                menu.addAction(paste_action)

            total_event_tracks_height = 0
            if self.tracks:
                total_event_tracks_height = len(self.tracks) * (self.EVENT_BASE_HEIGHT + self.TRACK_SPACING + 2 * self.TRACK_INTERNAL_PADDING)
            cue_area_y_start = self.RULER_HEIGHT + self.TRACK_SPACING + total_event_tracks_height

            cue_area_rect = QRectF(0, cue_area_y_start, self.width(), self.CUE_MARKER_AREA_HEIGHT)

            if cue_area_rect.contains(QPointF(pos_in_widget_coords)):
                clicked_time_s = pos_in_widget_coords.x() / self.pixels_per_second if self.pixels_per_second > 0 else 0
                add_cue_here_action = QAction(f"Add New Cue at {clicked_time_s:.2f}s...", self)
                add_cue_here_action.triggered.connect(lambda: self.add_cue_requested_at_time.emit(clicked_time_s))
                menu.addAction(add_cue_here_action)
            else: 
                # This ensures paste is available even when clicking on an empty track area
                if not menu.actions() and not self.parent_tab.event_clipboard:
                     return # Only return if there's truly nothing to do
        
        if menu.actions():
            menu.exec(global_pos)
        else: 
            if self.selected_event_ids or self.selected_cue_id is not None:
                self.selected_event_ids.clear(); self.event_selected_on_timeline.emit([])
                self.selected_cue_id = None; self.cue_marker_clicked.emit(-1)
                self.update()


    def paintEvent(self, event_paint):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._painted_event_rects_map.clear() 
        self._painted_cue_marker_rects_map.clear() 
        
        font_before_ruler = painter.font()
        ruler_font = QFont(font_before_ruler); ruler_font.setPointSize(10) 
        painter.setFont(ruler_font)
        painter.setPen(QColor(Qt.GlobalColor.lightGray))
        painter.drawLine(0, self.RULER_HEIGHT, self.width(), self.RULER_HEIGHT) 
        
        if self.pixels_per_second <= 0: 
            painter.setFont(font_before_ruler); painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Timeline scale error."); return

        max_seconds_on_ruler = int(self.width() / self.pixels_per_second)
        for i in range(max_seconds_on_ruler + 2): 
            x = i * self.pixels_per_second
            is_major = (i % 5 == 0); tick_len = 10 if is_major else 5
            painter.drawLine(int(x), self.RULER_HEIGHT - tick_len, int(x), self.RULER_HEIGHT)
            if is_major: painter.drawText(int(x) + 2, self.RULER_HEIGHT - tick_len - 2, f"{i}s")
        
        y_pos_for_first_event_track = self.RULER_HEIGHT + self.TRACK_SPACING
        
        current_font = painter.font() 
        font_for_events = QFont(current_font); font_for_events.setPointSize(8)
        painter.setFont(font_for_events) 
        
        current_y_offset_for_tracks = y_pos_for_first_event_track 
        for track_idx, track_info in enumerate(self.tracks):
            track_y_within_event_area, event_render_height_on_track = self._get_track_y_start_and_height(track_idx)
            absolute_track_y_for_this_event_set = y_pos_for_first_event_track + track_y_within_event_area

            events_on_this_track_data = [ev for ev in self.events if self._get_track_index_for_event(ev) == track_idx]
            for ev_data in events_on_this_track_data:
                event_rect_in_timeline_content = self._get_event_rect_on_track(ev_data, absolute_track_y_for_this_event_set, event_render_height_on_track)
                self._painted_event_rects_map[ev_data['id']] = event_rect_in_timeline_content 
                
                base_event_color = QColor("#2196f3"); text_color = Qt.GlobalColor.white
                target_type = ev_data.get('target_type', 'master'); is_orphaned = False
                if target_type == 'master': base_event_color = QColor("#707075") 
                elif target_type == 'group': base_event_color = QColor(230, 126, 34) 
                elif target_type == 'fixture': base_event_color = QColor(52, 152, 219) 
                event_type = ev_data['type']
                if event_type == 'preset': base_event_color = base_event_color.lighter(115)
                elif event_type == 'blackout': base_event_color = QColor("#f44336") 
                elif event_type == 'brightness': base_event_color = QColor("#ffc107"); text_color = Qt.GlobalColor.black
                elif event_type == 'color': base_event_color = QColor(ev_data.get('data',{}).get('color_hex', '#800080'))
                elif event_type in ['pan', 'tilt', 'zoom', 'focus', 'gobo', 'strobe']: base_event_color = QColor("#4dd0e1")

                if target_type != 'master' and ev_data.get('target_id') is not None:
                    target_found_in_current_tracks = any(t['type'] == target_type and t['id'] == ev_data['target_id'] for t in self.tracks)
                    if not target_found_in_current_tracks: is_orphaned = True; base_event_color = QColor("#B00020"); text_color = QColor(Qt.GlobalColor.white)
                
                active_event_state = self.parent_tab.active_event_states.get(ev_data['id'])
                is_selected = (ev_data['id'] in self.selected_event_ids) 
                is_currently_fading = active_event_state and active_event_state.get('status') in ['fade_in', 'fade_out']
                
                final_brush_color = QColor(base_event_color); current_pen = QPen(base_event_color.darker(110), 0.5) 
                if is_selected: current_pen = QPen(QColor("yellow"), 2); final_brush_color = final_brush_color.lighter(130)
                elif is_currently_fading: current_pen = QPen(QColor(0, 255, 0, 180), 1.5, Qt.PenStyle.DashLine) 
                elif active_event_state: final_brush_color = final_brush_color.lighter(115); current_pen = QPen(base_event_color.darker(120), 1)
                
                is_linked_to_selected_cue = (
                    ev_data.get('data',{}).get('trigger_mode') == 'relative_to_cue' and
                    ev_data.get('cue_id') is not None and
                    ev_data['cue_id'] == self.selected_cue_id
                )
                is_following_event_in_selected_cue = (
                    ev_data.get('data',{}).get('trigger_mode') == 'follow_event_in_cue' and
                    ev_data.get('cue_id') is not None and
                    ev_data['cue_id'] == self.selected_cue_id and
                    ev_data.get('data',{}).get('followed_event_id') is not None
                )

                if is_linked_to_selected_cue and not is_selected: 
                    current_pen = QPen(QColor(128, 0, 128, 200), 1.8, Qt.PenStyle.DotLine) 
                elif is_following_event_in_selected_cue and not is_selected:
                    current_pen = QPen(QColor(255, 105, 180, 200), 1.8, Qt.PenStyle.DashDotLine)

                painter.setBrush(QBrush(final_brush_color)); painter.setPen(current_pen)
                painter.drawRoundedRect(event_rect_in_timeline_content, 3, 3)

                if is_selected and len(self.selected_event_ids) == 1 and ev_data.get('data', {}).get('trigger_mode') == 'follow_event_in_cue': 
                    followed_event_id = ev_data['data'].get('followed_event_id')
                    if followed_event_id:
                        followed_event_rect = self._painted_event_rects_map.get(followed_event_id)
                        if followed_event_rect:
                            line_pen = QPen(QColor(100, 180, 255, 180), 1.5, Qt.PenStyle.DashLine)
                            painter.setPen(line_pen)
                            start_point = QPointF(followed_event_rect.right(), followed_event_rect.center().y())
                            end_point = QPointF(event_rect_in_timeline_content.left(), event_rect_in_timeline_content.center().y())
                            painter.drawLine(start_point, end_point)
                            arrow_size = 4
                            angle = math.atan2(end_point.y() - start_point.y(), end_point.x() - start_point.x())
                            painter.drawLine(QPointF(end_point.x() - arrow_size * math.cos(angle - math.pi / 6), 
                                                     end_point.y() - arrow_size * math.sin(angle - math.pi / 6)), end_point)
                            painter.drawLine(QPointF(end_point.x() - arrow_size * math.cos(angle + math.pi / 6),
                                                     end_point.y() - arrow_size * math.sin(angle + math.pi / 6)), end_point)

                if event_type == 'brightness': 
                    fade_in_s = ev_data['data'].get('fade_in', 0.0); fade_out_s = ev_data['data'].get('fade_out', 0.0)
                    if fade_in_s > 0: 
                        fade_in_px = fade_in_s * self.pixels_per_second
                        actual_fade_in_rect_width = min(fade_in_px, event_rect_in_timeline_content.width())
                        path = QPainterPath(); path.moveTo(event_rect_in_timeline_content.topLeft())
                        path.lineTo(event_rect_in_timeline_content.left() + actual_fade_in_rect_width, event_rect_in_timeline_content.top())
                        path.lineTo(event_rect_in_timeline_content.left() + actual_fade_in_rect_width, event_rect_in_timeline_content.bottom())
                        path.lineTo(event_rect_in_timeline_content.bottomLeft()); path.closeSubpath()
                        fade_in_gradient = QLinearGradient(event_rect_in_timeline_content.topLeft(), QPointF(event_rect_in_timeline_content.left() + actual_fade_in_rect_width, event_rect_in_timeline_content.top()))
                        fade_in_gradient.setColorAt(0, base_event_color.darker(150)); fade_in_gradient.setColorAt(1, base_event_color)
                        painter.fillPath(path, QBrush(fade_in_gradient))
                    if fade_out_s > 0: 
                        main_duration_s = ev_data['duration']
                        fade_out_px = fade_out_s * self.pixels_per_second
                        fade_out_start_x_offset_px = (fade_in_s + main_duration_s) * self.pixels_per_second
                        actual_fade_out_rect_width = min(fade_out_px, event_rect_in_timeline_content.width() - fade_out_start_x_offset_px)
                        actual_fade_out_rect_width = max(0, actual_fade_out_rect_width) 
                        path = QPainterPath()
                        path.moveTo(event_rect_in_timeline_content.left() + fade_out_start_x_offset_px, event_rect_in_timeline_content.top())
                        path.lineTo(event_rect_in_timeline_content.left() + fade_out_start_x_offset_px + actual_fade_out_rect_width, event_rect_in_timeline_content.top())
                        path.lineTo(event_rect_in_timeline_content.left() + fade_out_start_x_offset_px + actual_fade_out_rect_width, event_rect_in_timeline_content.bottom())
                        path.lineTo(event_rect_in_timeline_content.left() + fade_out_start_x_offset_px, event_rect_in_timeline_content.bottom()); path.closeSubpath()
                        fade_out_gradient = QLinearGradient(QPointF(event_rect_in_timeline_content.left() + fade_out_start_x_offset_px, event_rect_in_timeline_content.top()), 
                                                          QPointF(event_rect_in_timeline_content.left() + fade_out_start_x_offset_px + actual_fade_out_rect_width, event_rect_in_timeline_content.top()))
                        fade_out_gradient.setColorAt(0, base_event_color); fade_out_gradient.setColorAt(1, base_event_color.darker(150))
                        painter.fillPath(path, QBrush(fade_out_gradient))
                
                painter.setPen(QColor(text_color))
                text_clip_rect = QRectF(event_rect_in_timeline_content.left() + 4, event_rect_in_timeline_content.top(), event_rect_in_timeline_content.width() - 8, event_rect_in_timeline_content.height())
                display_text_parts = [f"{ev_data['name']}"]
                if is_orphaned: display_text_parts.append("(Orphaned)")
                elif target_type == 'fixture' and ev_data.get('target_id') is not None: display_text_parts.append(f"[Fx{ev_data['target_id']}]")
                elif target_type == 'group' and ev_data.get('target_id') is not None: display_text_parts.append(f"[Grp{ev_data['target_id']}]")
                final_display_text = " ".join(display_text_parts)
                painter.drawText(text_clip_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, final_display_text)
        
        total_event_tracks_height = len(self.tracks) * (self.EVENT_BASE_HEIGHT + self.TRACK_SPACING + (2 * self.TRACK_INTERNAL_PADDING)) if self.tracks else 0
        y_after_event_tracks = y_pos_for_first_event_track + total_event_tracks_height

        cue_area_y_start = y_after_event_tracks 
        painter.setPen(QColor(60, 60, 60)) 
        painter.drawLine(0, cue_area_y_start + self.CUE_MARKER_AREA_HEIGHT, self.width(), cue_area_y_start + self.CUE_MARKER_AREA_HEIGHT) 
        
        cue_font = QFont(font_before_ruler); cue_font.setPointSize(7) 
        painter.setFont(cue_font)

        for cue_data in self.cues:
            cue_x = cue_data['trigger_time_s'] * self.pixels_per_second
            marker_top_y = cue_area_y_start + 2
            marker_bottom_y = cue_area_y_start + self.CUE_MARKER_AREA_HEIGHT - 2
            is_selected_cue = (self.selected_cue_id == cue_data['id'])
            cue_color = QColor(255, 223, 0) if is_selected_cue else QColor(255, 165, 0) 
            cue_pen_width = 2.0 if is_selected_cue else 1.5
            painter.setPen(QPen(cue_color, cue_pen_width)) 
            painter.drawLine(int(cue_x), int(marker_top_y), int(cue_x), int(marker_bottom_y))
            path = QPainterPath(); path.moveTo(QPointF(cue_x, marker_top_y - 4)); path.lineTo(QPointF(cue_x - 4, marker_top_y)); path.lineTo(QPointF(cue_x, marker_top_y + 4)); path.lineTo(QPointF(cue_x + 4, marker_top_y)); path.closeSubpath()
            painter.fillPath(path, QBrush(cue_color))
            text_to_draw = f"Q {cue_data['cue_number']}"
            if cue_data.get('name'): text_to_draw += f": {cue_data['name'][:15]}" 
            fm = QFontMetrics(cue_font); text_width = fm.horizontalAdvance(text_to_draw)
            text_rect = QRectF(cue_x + 6, marker_top_y, text_width + 4, self.CUE_MARKER_AREA_HEIGHT - 4)
            painter.setPen(QColor(220,220,220)); painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text_to_draw)
            self._painted_cue_marker_rects_map[cue_data['id']] = QRectF(cue_x - 5, marker_top_y - 5, 10 + text_width + 10, self.CUE_MARKER_AREA_HEIGHT + 10)
        
        y_after_cue_area = cue_area_y_start + self.CUE_MARKER_AREA_HEIGHT + self.TRACK_SPACING

        y_after_audio_area = y_after_cue_area 
        if self.audio_duration > 0:
            audio_area_y_start = y_after_cue_area
            audio_rect_width = int(self.audio_duration * self.pixels_per_second)
            audio_track_content_rect = QRectF(0, audio_area_y_start, audio_rect_width, self.AUDIO_TRACK_HEIGHT)
            if self.simulated_waveform_data: 
                waveform_pen_color = QColor(70, 90, 120); painter.setPen(QPen(waveform_pen_color, 1))
                y_center = audio_track_content_rect.top() + audio_track_content_rect.height() / 2; max_amplitude_pixels = audio_track_content_rect.height() / 2 * 0.9
                points_per_second_in_data = len(self.simulated_waveform_data) / self.audio_duration if self.audio_duration > 0 else 0
                if points_per_second_in_data > 0:
                    for px_on_timeline in range(int(audio_track_content_rect.width())):
                        time_at_px = px_on_timeline / self.pixels_per_second; data_idx = int(time_at_px * points_per_second_in_data)
                        if 0 <= data_idx < len(self.simulated_waveform_data):
                            amplitude = self.simulated_waveform_data[data_idx]; line_height = amplitude * max_amplitude_pixels
                            painter.drawLine(px_on_timeline, int(y_center - line_height), px_on_timeline, int(y_center + line_height))
            else: 
                painter.setBrush(QColor("#404040")); painter.setPen(Qt.PenStyle.NoPen); painter.drawRect(audio_track_content_rect)
            y_after_audio_area = audio_area_y_start + self.AUDIO_TRACK_HEIGHT + self.TRACK_SPACING
        
        painter.setFont(font_before_ruler) 
        
        final_painted_height = y_after_audio_area 
        if not self.events and self.audio_duration <=0 and not self.cues : 
            painter.setPen(QColor(Qt.GlobalColor.gray)); painter.drawText(QRectF(0, self.RULER_HEIGHT + 20, self.width(), 50), Qt.AlignmentFlag.AlignCenter, "Load audio or add events/cues.")
            final_painted_height = max(final_painted_height, self.RULER_HEIGHT + 70) 

        current_min_height = self.minimumHeight()
        if current_min_height < final_painted_height:
            self.setMinimumHeight(int(final_painted_height))
        elif current_min_height > final_painted_height + 20 and final_painted_height > (self.RULER_HEIGHT + self.TRACK_SPACING + total_event_tracks_height + self.CUE_MARKER_AREA_HEIGHT + self.TRACK_SPACING + (self.AUDIO_TRACK_HEIGHT if self.audio_duration > 0 else 0) + 20) : 
            self.setMinimumHeight(int(final_painted_height))
            
        if self.is_marquee_selecting and self.marquee_current_rect.isValid():
            painter.setPen(QPen(QColor(150, 200, 255, 200), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(135, 180, 255, 40)))
            painter.drawRect(self.marquee_current_rect)


        playhead_x_on_timeline = self.current_playhead_position * self.pixels_per_second
        painter.setPen(QPen(QColor(Qt.GlobalColor.red), 2))
        painter.drawLine(int(playhead_x_on_timeline), 0, int(playhead_x_on_timeline), self.height()) 
            
    def _get_effective_total_duration(self) -> float: 
        if not self: return 0.0
        
        effective_duration = self.audio_duration 
        if self.events:
            max_event_time = 0
            for ev in self.events: 
                event_visual_start = self._get_effective_event_start_time(ev)
                event_total_visual_duration = self._get_event_visual_duration_s(ev)
                max_event_time = max(max_event_time, event_visual_start + event_total_visual_duration)
            effective_duration = max(effective_duration, max_event_time)
        
        if self.cues:
            max_cue_time = max((c['trigger_time_s'] for c in self.cues), default=0)
            effective_duration = max(effective_duration, max_cue_time)

        if effective_duration == 0:
            return 60.0 
        return effective_duration

class TimelineTab(QWidget):
    event_triggered = pyqtSignal(dict)
    cues_changed = pyqtSignal()
    playback_state_changed_for_embedded = pyqtSignal(bool) # is_playing
    content_or_playhead_changed_for_embedded = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.event_clipboard = []
        
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput() 
        self.media_player.setAudioOutput(self.audio_output) 
        
        self.media_player.positionChanged.connect(self._media_position_changed)
        self.media_player.durationChanged.connect(self._media_duration_changed)
        self.media_player.playbackStateChanged.connect(self._media_playback_state_changed)
        self.media_player.errorOccurred.connect(self._media_error_occurred)
        
        self.current_audio_file = None
        self.active_event_states = {} 
        self.pre_playback_states = {}
        
        self.timeline_widget: TimelineWidget | None = None 
        self.event_list_widget: QListWidget | None = None 
        
        self.track_info_table_widget: QTableWidget | None = None 
        self.track_info_container_widget: QWidget | None = None 

        self.scroll_area_instance: QScrollArea | None = None
        self._is_scrolling_programmatically = False

        self.pending_video_sync_timestamps_list: list[float] = [] 
        self._is_processing_synced_cue_dialog = False 
        
        # Recording state
        self.is_recording = False
        self.recording_debounce_timers = {} # {f"{fixture_id}-{param_name}": QTimer}
        self.last_recorded_fixture_states = {} # {fixture_id: {param: value}}

        self.init_ui() 
        if self.timeline_widget: 
             self.timeline_widget.playhead_moved_by_user.connect(self.handle_playhead_seek_by_user)
             self.timeline_widget.event_modified_on_timeline.connect(self._handle_timeline_widget_modified)
             self.timeline_widget.multiple_events_modified_on_timeline.connect(self._handle_timeline_widget_multi_modified)
             self.timeline_widget.event_delete_requested_on_timeline.connect(self.delete_event_by_id)
             self.timeline_widget.event_selected_on_timeline.connect(self._on_timeline_widget_event_selected)
             self.timeline_widget.cue_marker_clicked.connect(self._on_timeline_cue_marker_clicked)
             self.timeline_widget.add_cue_requested_at_time.connect(self.show_add_cue_dialog) 
             self.timeline_widget.cue_modified_on_timeline.connect(self._handle_timeline_widget_cue_modified)
             self.timeline_widget.assign_event_to_cue_requested.connect(self.show_assign_event_to_cue_dialog) 
             self.timeline_widget.delete_multiple_events_requested.connect(self._handle_delete_multiple_events) 

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        controls_layout = QHBoxLayout()
        self.load_audio_button = QPushButton("Load MP3 Audio")
        self.load_audio_button.clicked.connect(self.load_audio_file)
        controls_layout.addWidget(self.load_audio_button)
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.play_button)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.stop_button)
        self.reset_timeline_button = QPushButton("Reset Timeline") 
        self.reset_timeline_button.clicked.connect(self.reset_timeline_data_action)
        controls_layout.addWidget(self.reset_timeline_button)
        self.prev_cue_button = QPushButton("<< Prev Cue")
        self.prev_cue_button.clicked.connect(self._go_to_previous_cue) 
        controls_layout.addWidget(self.prev_cue_button)
        self.next_cue_button = QPushButton("Next Cue >>")
        self.next_cue_button.clicked.connect(self._go_to_next_cue) 
        controls_layout.addWidget(self.next_cue_button)
        self.current_time_label = QLabel() 
        self.current_time_label.setObjectName("TimelineTimeLabel") 
        self.current_time_label.setTextFormat(Qt.TextFormat.RichText) 
        base_font_time = QFont(); base_font_time.setPointSize(18); base_font_time.setBold(True)
        self.current_time_label.setFont(base_font_time)
        self.current_time_label.setStyleSheet("QLabel#TimelineTimeLabel { background-color: #20232A; color: #E6E6E6; padding: 6px 10px; border-radius: 4px; margin-right: 10px; }")
        self.update_time_label(0,0)
        controls_layout.addWidget(self.current_time_label)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        management_buttons_layout = QHBoxLayout()
        self.record_button = QPushButton("Record")
        self.record_button.setCheckable(True)
        self.record_button.toggled.connect(self._handle_record_toggled)
        self.record_button.setObjectName("RecordButton") # For styling
        management_buttons_layout.addWidget(self.record_button)
        
        add_cue_button = QPushButton("Add Cue (at Playhead)") 
        add_cue_button.clicked.connect(lambda: self.show_add_cue_dialog(prefill_time=self.timeline_widget.current_playhead_position if self.timeline_widget else 0.0))
        management_buttons_layout.addWidget(add_cue_button)
        management_buttons_layout.addSpacing(20) 
        self.add_event_button = QPushButton("Add Event")
        self.add_event_button.clicked.connect(lambda: self.show_add_event_dialog())
        management_buttons_layout.addWidget(self.add_event_button)
        self.edit_event_button = QPushButton("Edit Event")
        self.edit_event_button.clicked.connect(self.show_edit_event_dialog)
        management_buttons_layout.addWidget(self.edit_event_button)
        self.delete_event_button = QPushButton("Delete Event(s)") 
        self.delete_event_button.setStyleSheet("background-color: #c62828;")
        self.delete_event_button.clicked.connect(self.delete_selected_event_from_list_widget) 
        management_buttons_layout.addWidget(self.delete_event_button)
        management_buttons_layout.addStretch()
        layout.addLayout(management_buttons_layout)
        
        main_v_splitter = QSplitter(Qt.Orientation.Vertical)
        timeline_area_splitter = QSplitter(Qt.Orientation.Horizontal) 

        self.track_info_container_widget = QWidget()
        track_info_container_layout = QVBoxLayout(self.track_info_container_widget)
        track_info_container_layout.setContentsMargins(0,0,0,0)
        track_info_container_layout.setSpacing(0)
        
        self.track_info_table_widget = QTableWidget()
        self.track_info_table_widget.setColumnCount(4) 
        self.track_info_table_widget.setHorizontalHeaderLabels(["#", "Name", "Type", "ID"])
        self.track_info_table_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.track_info_table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.track_info_table_widget.verticalHeader().setVisible(False)
        self.track_info_table_widget.horizontalHeader().setFixedHeight(TimelineWidget.RULER_HEIGHT) 
        self.track_info_table_widget.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


        self.track_info_table_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.track_info_table_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded) 
        self.track_info_table_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) 
        self.track_info_table_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.track_info_table_widget.setStyleSheet("""
            QTableWidget { background-color: #2A2A2E; border: none; color: #E0E0E0; } 
            QHeaderView::section { background-color: #3A3A3C; color: lightgray; border: 1px solid #202020; padding: 4px; } 
            QTableWidget::item { padding: 3px 5px; border-bottom: 1px solid #404045; }
        """)
        self.track_info_table_widget.setColumnWidth(0, 30) 
        self.track_info_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) 
        self.track_info_table_widget.setColumnWidth(2, 70) 
        self.track_info_table_widget.setColumnWidth(3, 50)
        track_info_container_layout.addWidget(self.track_info_table_widget)
        
        self.track_info_container_widget.setMinimumWidth(150)
        self.track_info_container_widget.setMaximumWidth(450)
        timeline_area_splitter.addWidget(self.track_info_container_widget)
        
        self.scroll_area_instance = QScrollArea()
        self.scroll_area_instance.setWidgetResizable(True) 
        self.scroll_area_instance.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area_instance.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded) 
        self.timeline_widget = TimelineWidget(self.main_window, self) 
        self.scroll_area_instance.setWidget(self.timeline_widget) 
        timeline_area_splitter.addWidget(self.scroll_area_instance)
        timeline_area_splitter.setSizes([220, 530]) 
        main_v_splitter.addWidget(timeline_area_splitter) 
        
        event_list_container = QWidget()
        event_list_layout = QVBoxLayout(event_list_container)
        event_list_layout.setContentsMargins(0,0,0,0) 
        event_list_layout.addWidget(QLabel("Events (Scroll to see all):"))
        self.event_list_widget = QListWidget()
        self.event_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.event_list_widget.itemDoubleClicked.connect(lambda item: self.show_edit_event_dialog()) 
        self.event_list_widget.itemSelectionChanged.connect(self._on_event_list_selection_changed)
        event_list_layout.addWidget(self.event_list_widget)
        main_v_splitter.addWidget(event_list_container) 

        main_v_splitter.setSizes([500, 100]) 
        layout.addWidget(main_v_splitter)
        
        self.refresh_event_list_and_timeline() 
        self.setLayout(layout)
        
        if self.track_info_table_widget and self.scroll_area_instance:
            self.scroll_area_instance.verticalScrollBar().valueChanged.connect(self._sync_timeline_scroll_to_track_info)
            self.track_info_table_widget.verticalScrollBar().valueChanged.connect(self._sync_track_info_scroll_to_timeline)

    def _handle_record_toggled(self, checked):
        self.is_recording = checked
        if checked:
            self.record_button.setText("RECORDING")
            self.record_button.setStyleSheet("background-color: #e53935; color: white; font-weight: bold;")
            
            # Reset states from previous recording sessions
            self.last_recorded_fixture_states.clear()
            for timer in self.recording_debounce_timers.values():
                timer.stop()
            self.recording_debounce_timers.clear()
            
            self.main_window.fixture_data_globally_changed.connect(self._record_fixture_change)
            QMessageBox.information(self, "Recording Started", "Live recording to timeline is now active.\nAny manual fixture changes will be captured as new events.")
        else:
            self.record_button.setText("Record")
            self.record_button.setStyleSheet("") # Revert to default stylesheet
            try:
                self.main_window.fixture_data_globally_changed.disconnect(self._record_fixture_change)
            except TypeError:
                pass
            print("Recording stopped.")
            
    def _record_fixture_change(self, fixture_id: int, data: dict):
        if not self.is_recording or not self.timeline_widget:
            return

        recordable_params = ['red', 'green', 'blue', 'brightness', 'gobo_index', 'zoom', 'focus', 'shutter_strobe_rate', 'rotation_x', 'rotation_y', 'rotation_z']
        changed_params = {key: val for key, val in data.items() if key in recordable_params}
        
        if not changed_params:
            return

        # Handle color as a single change event
        if 'red' in changed_params or 'green' in changed_params or 'blue' in changed_params:
            # Group RGB changes into one 'color' event
            color_params = {k: v for k, v in changed_params.items() if k in ['red', 'green', 'blue']}
            for k in color_params: del changed_params[k] # Remove from individual processing
            self._debounce_and_create_recorded_event(fixture_id, "color", color_params)

        # Handle other parameters individually
        for param, value in changed_params.items():
            param_to_event_type_map = {
                'brightness': 'brightness', 'rotation_y': 'pan', 'rotation_x': 'tilt',
                'zoom': 'zoom', 'focus': 'focus', 'gobo_index': 'gobo', 'shutter_strobe_rate': 'strobe',
                'rotation_z': None # Not directly mapped to a simple event type currently
            }
            event_type = param_to_event_type_map.get(param)
            if event_type:
                self._debounce_and_create_recorded_event(fixture_id, event_type, value)

    def _debounce_and_create_recorded_event(self, fixture_id, event_type, value_or_dict):
        debounce_key = f"{fixture_id}-{event_type}"
        if debounce_key in self.recording_debounce_timers:
            self.recording_debounce_timers[debounce_key].stop()

        debounce_ms = 350
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda fid=fixture_id, et=event_type, val=value_or_dict: self._create_recorded_event(fid, et, val))
        timer.start(debounce_ms)
        self.recording_debounce_timers[debounce_key] = timer

    def _create_recorded_event(self, fixture_id, event_type, value_or_dict):
        debounce_key = f"{fixture_id}-{event_type}"
        if debounce_key in self.recording_debounce_timers:
            del self.recording_debounce_timers[debounce_key]
        
        if not self.is_recording or self.timeline_widget is None:
            return

        # Determine the full current value that would be recorded
        current_value_to_record = None
        if event_type == 'color':
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("SELECT red, green, blue FROM fixtures WHERE id = ?", (fixture_id,))
                color_tuple = cursor.fetchone()
                if color_tuple:
                    current_value_to_record = {'red': color_tuple[0], 'green': color_tuple[1], 'blue': color_tuple[2]}
                else:
                    return # Can't get current state, so can't record
            except Exception as e:
                print(f"DB Error getting current color for recording check: {e}")
                return
        else:
            current_value_to_record = value_or_dict

        # Get the last recorded state for this specific parameter
        last_recorded_state = self.last_recorded_fixture_states.get(fixture_id, {}).get(event_type)

        # Compare current value with last recorded value to prevent redundant events
        if last_recorded_state is not None:
            if event_type == 'color':
                if last_recorded_state == current_value_to_record:
                    return # No change in color
            else: # Handle numeric values
                if isinstance(last_recorded_state, float) and isinstance(current_value_to_record, (float, int)):
                    if math.isclose(last_recorded_state, float(current_value_to_record), rel_tol=1e-4):
                        return # Value is close enough, no change
                elif last_recorded_state == current_value_to_record:
                    return # Exact same value, no change
        
        try:
            current_time_s = self.timeline_widget.current_playhead_position
            event_name = f"Rec {event_type.capitalize()} Fx{fixture_id}"
            
            data_payload = {'trigger_mode': 'absolute'}
            if event_type == 'color':
                color = QColor(current_value_to_record['red'], current_value_to_record['green'], current_value_to_record['blue'])
                data_payload['color_hex'] = color.name()
            else:
                data_payload['value'] = current_value_to_record

            cursor = self.main_window.db_connection.cursor()
            cursor.execute(
                """INSERT INTO timeline_events (name, start_time, duration, event_type, data, target_type, target_id, cue_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_name, current_time_s, 0.1, event_type, json.dumps(data_payload), 'fixture', fixture_id, None)
            )
            self.main_window.db_connection.commit()
            
            # Update the last recorded state only after successful DB insert
            if fixture_id not in self.last_recorded_fixture_states:
                self.last_recorded_fixture_states[fixture_id] = {}
            self.last_recorded_fixture_states[fixture_id][event_type] = current_value_to_record

            self.refresh_event_list_and_timeline(regenerate_waveform=False)
            
        except sqlite3.Error as e:
            print(f"Database error during live recording for fixture {fixture_id}, event {event_type}: {e}")
        except Exception as e:
            print(f"Generic error during live recording for fixture {fixture_id}, event {event_type}: {e}")
            
    def _get_timeline_content_header_height(self) -> int:
        if not self.timeline_widget: return 0
        return int(TimelineWidget.RULER_HEIGHT + TimelineWidget.TRACK_SPACING)


    def _sync_timeline_scroll_to_track_info(self, timeline_scroll_value: int):
        if not self._is_scrolling_programmatically and self.track_info_table_widget and self.timeline_widget:
            self._is_scrolling_programmatically = True
            
            timeline_widget_internal_header_height = self._get_timeline_content_header_height()
            event_tracks_scroll_offset = max(0, timeline_scroll_value - timeline_widget_internal_header_height)
            
            current_table_scroll = self.track_info_table_widget.verticalScrollBar().value()
            if current_table_scroll != event_tracks_scroll_offset:
                 self.track_info_table_widget.verticalScrollBar().setValue(event_tracks_scroll_offset)
            
            self._is_scrolling_programmatically = False

    def _sync_track_info_scroll_to_timeline(self, track_info_scroll_value: int):
        if not self._is_scrolling_programmatically and self.scroll_area_instance and self.timeline_widget:
            self._is_scrolling_programmatically = True

            timeline_widget_internal_header_height = self._get_timeline_content_header_height()
            timeline_target_scroll = track_info_scroll_value + timeline_widget_internal_header_height
            
            current_timeline_scroll = self.scroll_area_instance.verticalScrollBar().value()
            if current_timeline_scroll != timeline_target_scroll:
                self.scroll_area_instance.verticalScrollBar().setValue(timeline_target_scroll)

            self._is_scrolling_programmatically = False
            
    def _media_position_changed(self, position_ms: int):
        if not self.timeline_widget: return
        position_s = position_ms / 1000.0
        
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and \
           not self.timeline_widget.is_dragging_playhead:
            self.timeline_widget.set_playhead_position(position_s) 
            self._check_and_trigger_events(position_s) 
        
        effective_total_duration_s = self._get_effective_timeline_duration()
        self.update_time_label(position_s, effective_total_duration_s)

    def _media_duration_changed(self, duration_ms: int):
        if not self.timeline_widget: return
        duration_s = duration_ms / 1000.0
        self.timeline_widget.set_audio_duration(duration_s)
        effective_total_duration_s = self._get_effective_timeline_duration()
        self.update_time_label(self.timeline_widget.current_playhead_position, effective_total_duration_s)

    def _media_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        if not self.timeline_widget: return
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.timeline_widget.is_playing = is_playing
        self.play_button.setText("Pause" if is_playing else "Play")
        self.record_button.setEnabled(not is_playing)
        self.playback_state_changed_for_embedded.emit(is_playing)

        if not is_playing and self.is_recording:
            self.record_button.setChecked(False) # Stop recording if playback stops

        if state == QMediaPlayer.PlaybackState.StoppedState:
            if self.media_player.duration() > 0 and \
               abs(self.media_player.position() - self.media_player.duration()) < 100: 
                self.timeline_widget.set_playhead_position(0) 
                self.active_event_states.clear()
                self.update_time_label(0, self.timeline_widget.audio_duration)


    def _media_error_occurred(self, error: QMediaPlayer.Error, error_string: str = ""): 
        error_code = self.media_player.error()
        actual_error_string = self.media_player.errorString() 
        media_status = self.media_player.mediaStatus()
        print(f"QMediaPlayer Error Debug: Code {error_code} String: '{actual_error_string}' Status: {media_status}")
        user_message = f"An issue occurred with the audio player: {actual_error_string}\n\n"
        if "Could not find codec parameters for stream" in actual_error_string and "Video" in actual_error_string:
            user_message += ("This often means the loaded file is not a pure audio file...")
        elif "Could not update timestamps for skipped samples" in actual_error_string:
             user_message += ("The audio file might have encoding issues or inconsistencies...")
        elif error_code == QMediaPlayer.Error.ResourceError:
            user_message += "The audio resource could not be resolved or is invalid..."
        else:
            user_message += ("If this persists, the audio file might be corrupted...")
        QMessageBox.warning(self, "Media Player Issue", user_message)
        self.play_button.setText("Play")
        if self.timeline_widget: self.timeline_widget.is_playing = False
    
    def handle_video_sync_cue_request(self, timestamp_s: float):
        self.pending_video_sync_timestamps_list.append(timestamp_s)
        if not self._is_processing_synced_cue_dialog:
            self._show_next_add_event_dialog_for_synced_cue()

    def _show_next_add_event_dialog_for_synced_cue(self):
        if not self.pending_video_sync_timestamps_list:
            self._is_processing_synced_cue_dialog = False
            return
        self._is_processing_synced_cue_dialog = True
        timestamp_to_use = self.pending_video_sync_timestamps_list.pop(0)
        self.show_add_event_dialog(prefill_timestamp=timestamp_to_use, is_from_sync_queue=True)

    def reset_timeline_data_action(self):
        reply = QMessageBox.question(self, "Confirm Reset",
                                     "Are you sure you want to delete ALL timeline events, cues, and clear loaded audio?\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("DELETE FROM timeline_events")
                cursor.execute("DELETE FROM cues") 
                self.main_window.db_connection.commit()
                self.stop_playback() 
                self.current_audio_file = None
                self.media_player.setSource(QUrl()) 
                if self.timeline_widget:
                    self.timeline_widget.set_audio_duration(0.0) 
                    self.timeline_widget.selected_event_ids.clear() 
                    self.timeline_widget.selected_cue_id = None 
                self.active_event_states.clear() 
                self.refresh_event_list_and_timeline() 
                QMessageBox.information(self, "Timeline Reset", "All timeline events, cues, and audio have been cleared.")
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Could not reset timeline: {e}")

    def _on_event_list_selection_changed(self):
        if not self.timeline_widget or not self.event_list_widget: return
        
        newly_selected_ids_in_list = [item.data(Qt.ItemDataRole.UserRole) for item in self.event_list_widget.selectedItems()]
        
        if set(self.timeline_widget.selected_event_ids) != set(newly_selected_ids_in_list):
            self.timeline_widget.selected_event_ids = newly_selected_ids_in_list
            if newly_selected_ids_in_list: 
                self.timeline_widget.selected_cue_id = None 
            self.timeline_widget.update()


    def _on_timeline_widget_event_selected(self, selected_ids: list[int]): 
        if not self.event_list_widget: return
        self.event_list_widget.blockSignals(True) 
        
        current_list_selection_items = self.event_list_widget.selectedItems()
        current_list_selected_ids = {item.data(Qt.ItemDataRole.UserRole) for item in current_list_selection_items}

        if set(selected_ids) != current_list_selected_ids:
            self.event_list_widget.clearSelection()
            first_item_to_scroll_to = None
            for i in range(self.event_list_widget.count()):
                item = self.event_list_widget.item(i)
                item_event_id = item.data(Qt.ItemDataRole.UserRole)
                if item_event_id in selected_ids:
                    item.setSelected(True) 
                    if first_item_to_scroll_to is None and item_event_id == (selected_ids[0] if selected_ids else None):
                        first_item_to_scroll_to = item 
            
            if first_item_to_scroll_to:
                 self.event_list_widget.setCurrentItem(first_item_to_scroll_to)
                 self.event_list_widget.scrollToItem(first_item_to_scroll_to, QAbstractItemView.ScrollHint.PositionAtCenter)
            elif not selected_ids : 
                 self.event_list_widget.setCurrentItem(None) 


        if selected_ids and self.timeline_widget: 
            self.timeline_widget.selected_cue_id = None 
        
        self.event_list_widget.blockSignals(False)


    def _on_timeline_cue_marker_clicked(self, cue_id: int):
        if not self.timeline_widget: return
        
        if cue_id == -1: 
            if self.timeline_widget.selected_cue_id is not None:
                self.timeline_widget.selected_cue_id = None
            self.timeline_widget.update()
            return

        self.timeline_widget.selected_cue_id = cue_id
        if self.timeline_widget.selected_event_ids: 
            self.timeline_widget.selected_event_ids.clear()
            if self.event_list_widget: self.event_list_widget.clearSelection() 

        self.timeline_widget.update() 

        selected_cue_data = next((c for c in self.timeline_widget.cues if c['id'] == cue_id), None)
        if selected_cue_data:
             time_diff = abs(self.timeline_widget.current_playhead_position - selected_cue_data['trigger_time_s'])
             if time_diff > 0.050: 
                self.timeline_widget.set_playhead_position(selected_cue_data['trigger_time_s'], from_user_seek=True)

    def _handle_timeline_widget_modified(self, event_id: int, modified_data: dict):
        try:
            cursor = self.main_window.db_connection.cursor()
            data_to_store_json = json.dumps(modified_data.get('data', {})) 
            cursor.execute(
                """UPDATE timeline_events SET 
                   start_time = ?, duration = ?, target_type = ?, target_id = ?, data = ?, cue_id = ?
                   WHERE id = ?""",
                (modified_data['start_time'], modified_data['duration'], 
                 modified_data['target_type'], modified_data['target_id'],
                 data_to_store_json, modified_data.get('cue_id'), 
                 event_id)
            )
            self.main_window.db_connection.commit()
            self.refresh_event_list_and_timeline(regenerate_waveform=False) 
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not update modified event (ID: {event_id}): {e}")

    def _handle_timeline_widget_multi_modified(self, modified_events_data: list[dict]):
        try:
            cursor = self.main_window.db_connection.cursor()
            for event_update in modified_events_data:
                cursor.execute(
                    "UPDATE timeline_events SET start_time = ?, target_type = ?, target_id = ? WHERE id = ?",
                    (event_update['start_time'], event_update['target_type'], event_update['target_id'], event_update['id'])
                )
            self.main_window.db_connection.commit()
            self.refresh_event_list_and_timeline(regenerate_waveform=False)
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not update multiple modified events: {e}")

    def _handle_timeline_widget_cue_modified(self, cue_id: int, new_trigger_time_s: float):
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("UPDATE cues SET trigger_time_s = ? WHERE id = ?", (new_trigger_time_s, cue_id))
            self.main_window.db_connection.commit()
            self.refresh_event_list_and_timeline(regenerate_waveform=False)
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not update modified cue (ID: {cue_id}): {e}")


    def load_audio_file(self, file_path_arg=None):
        file_path = file_path_arg
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self.main_window, "Load Audio", "", 
                "Audio Files (*.mp3 *.wav *.aac *.flac);;All Files (*)"
            )
        if file_path:
            self.current_audio_file = file_path
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            self.stop_playback() 
            if not file_path_arg:
                 QMessageBox.information(self, "Audio Loaded", f"Audio file '{file_path}' loaded.")
            self.refresh_event_list_and_timeline(regenerate_waveform=True)


    def toggle_playback(self):
        if not self.timeline_widget: return
        if self.is_recording:
            QMessageBox.warning(self, "Recording Active", "Stop recording before controlling playback.")
            return

        if self.media_player.source().isEmpty() and not self.timeline_widget.events and not self.timeline_widget.cues: 
             QMessageBox.warning(self, "No Content", "Please load audio or add events/cues to the timeline.")
             return
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            if not self.pre_playback_states: # Only store state if we're starting fresh, not resuming
                self.pre_playback_states = copy.deepcopy(self.main_window.live_fixture_states)

            if self.media_player.position() >= self.media_player.duration() and self.media_player.duration() > 0:
                self.media_player.setPosition(0)
                if self.timeline_widget: self.timeline_widget.set_playhead_position(0)
                self.active_event_states.clear()
            self.media_player.play()


    def stop_playback(self):
        if not self.timeline_widget: return 
        if self.is_recording:
            self.record_button.setChecked(False) # This will trigger the _handle_record_toggled slot
        
        self.media_player.stop()
        self.active_event_states.clear() 
        
        # Restore pre-playback state if it exists
        if self.pre_playback_states:
            for fixture_id, params in self.pre_playback_states.items():
                self.main_window.update_fixture_data_and_notify(fixture_id, params)
            self.pre_playback_states.clear()

        if self.timeline_widget.current_playhead_position != 0:
            self.timeline_widget.set_playhead_position(0, from_user_seek=False) # Important: Don't re-seek
            self.update_time_label(0, self.timeline_widget.audio_duration)


    def handle_playhead_seek_by_user(self, new_time_s: float):
        if not self.timeline_widget:
            return

        # Ensure we have a pre-playback state to revert to if user stops after seeking
        if not self.pre_playback_states:
            self.pre_playback_states = copy.deepcopy(self.main_window.live_fixture_states)
        
        # Get the default state for all fixtures
        base_states = self._get_base_fixture_states()
        if not base_states:
            print("Warning: Could not get base fixture states for seek.")
            return

        # Calculate the final "stomped" state at the target time
        state_to_apply = self._calculate_tracked_state_at_time(new_time_s, base_states)

        # Go through events again to handle active interpolations (like fades)
        sorted_events = sorted(self.timeline_widget.events, key=self.timeline_widget._get_effective_event_start_time)

        for event in sorted_events:
            event_type = event['type']
            if event_type != 'brightness':
                continue

            event_start_time = self.timeline_widget._get_effective_event_start_time(event)
            fade_in = event['data'].get('fade_in', 0.0)
            duration = event['duration']
            fade_out = event['data'].get('fade_out', 0.0)
            event_end_time = event_start_time + fade_in + duration + fade_out
            
            # Check if the event is currently active at the seek time
            if event_start_time <= new_time_s < event_end_time:
                state_before_event = self._calculate_tracked_state_at_time(event_start_time - 0.001, base_states)
                target_fixtures = self._get_fixture_ids_for_target(event['target_type'], event['target_id'])

                for fid in target_fixtures:
                    if fid not in state_to_apply:
                        continue
                    
                    initial_value = state_before_event[fid]['brightness']
                    final_target_value = event['data']['value']
                    time_into_event = new_time_s - event_start_time
                    
                    interpolated_value = initial_value
                    if time_into_event < fade_in and fade_in > 0:
                        progress = time_into_event / fade_in
                        interpolated_value = initial_value + (final_target_value - initial_value) * progress
                    elif time_into_event < fade_in + duration:
                        interpolated_value = final_target_value
                    elif time_into_event < fade_in + duration + fade_out and fade_out > 0:
                        fade_out_target_value = self._determine_fade_out_target_value(event, sorted_events)
                        time_into_fade_out = time_into_event - (fade_in + duration)
                        progress = time_into_fade_out / fade_out
                        interpolated_value = final_target_value + (fade_out_target_value - final_target_value) * progress

                    state_to_apply[fid]['brightness'] = interpolated_value

        # Apply the final calculated state to live fixtures
        for fixture_id, params in state_to_apply.items():
            current_live_params = self.main_window.live_fixture_states.get(fixture_id, {})
            params_to_update = {}
            for p_name, p_val in params.items():
                if p_name == 'brightness':
                    if self.main_window.blackout_button.isChecked():
                        p_val = 0
                    else:
                        p_val = int(p_val * (self.main_window.master_fader.value() / 100.0))

                if not p_name in current_live_params or self._is_value_different(current_live_params[p_name], p_val):
                    params_to_update[p_name] = p_val
            
            if params_to_update:
                self.main_window.update_fixture_data_and_notify(fixture_id, params_to_update)

        # Update media player and UI
        if abs(self.media_player.position() / 1000.0 - new_time_s) > 0.1:
            self.media_player.setPosition(int(new_time_s * 1000))
        
        self.timeline_widget.set_playhead_position(new_time_s)
        self.active_event_states.clear()
        self._check_and_trigger_events(new_time_s, is_seek=True)

    def _is_value_different(self, val1, val2, tolerance=1e-3):
        """Helper to compare values, especially floats."""
        if isinstance(val1, (float, int)) and isinstance(val2, (float, int)):
            return abs(val1 - val2) > tolerance
        return val1 != val2

    def _get_base_fixture_states(self) -> dict:
        """Queries the database for the default state of all fixtures."""
        base_states = {}
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT * FROM fixtures")
            db_cols = [desc[0] for desc in cursor.description]
            for row in cursor.fetchall():
                fixture_dict = dict(zip(db_cols, row))
                base_states[fixture_dict['id']] = fixture_dict
        except Exception as e:
            print(f"Error fetching base fixture states: {e}")
        return base_states

    def _get_fixture_ids_for_target(self, target_type: str, target_id: int | None) -> list[int]:
        """Resolves a target type and ID to a list of fixture IDs."""
        if target_type == "fixture" and target_id is not None:
            return [target_id]
        if target_type == "group" and target_id is not None:
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("SELECT fixture_id FROM fixture_group_mappings WHERE group_id = ?", (target_id,))
                return [row[0] for row in cursor.fetchall()]
            except Exception as e:
                print(f"Error getting fixtures for group {target_id}: {e}")
                return []
        if target_type == "master":
            # Return all fixture IDs
            return list(self.main_window.live_fixture_states.keys())
        return []

    def _get_preset_info(self, preset_number: str) -> tuple[dict | None, str | None]:
        """Fetches and returns the data dictionary and type for a given preset number."""
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT data, type FROM presets WHERE preset_number = ?", (preset_number,))
            result = cursor.fetchone()
            if result and result[0]:
                return json.loads(result[0]), result[1]
        except Exception as e:
            print(f"Error fetching data for preset {preset_number}: {e}")
        return None, None

    def _get_params_for_preset_type(self, preset_type: str) -> list[str]:
        """Resolves a preset type string to a list of fixture parameter keys."""
        preset_type = preset_type.lower()
        params = {
            "dimmer": ["brightness"],
            "color": ["red", "green", "blue"],
            "position": ["rotation_x", "rotation_y", "rotation_z"],
            "gobo": ["gobo_index"],
            "beam": ["zoom", "focus", "shutter_strobe_rate"],
        }
        if preset_type in params:
            return params[preset_type]
        # 'All' or unknown type returns all valid params
        return [
            "rotation_x", "rotation_y", "rotation_z", "red", "green", "blue", 
            "brightness", "gobo_index", "zoom", "focus", "shutter_strobe_rate"
        ]

    def _calculate_tracked_state_at_time(self, target_time_s: float, base_states: dict) -> dict:
        """Calculates the 'stomped' state of all fixtures at a specific time."""
        tracked_state = copy.deepcopy(base_states)
        if not self.timeline_widget:
            return tracked_state

        sorted_events = sorted(self.timeline_widget.events, key=self.timeline_widget._get_effective_event_start_time)
        
        for event in sorted_events:
            event_start_time = self.timeline_widget._get_effective_event_start_time(event)
            if event_start_time > target_time_s:
                break
            
            event_type = event.get('type')
            target_type = event.get('target_type')
            target_id = event.get('target_id')
            data = event.get('data', {})
            fixture_ids_for_event = self._get_fixture_ids_for_target(target_type, target_id)

            if not fixture_ids_for_event:
                continue

            if event_type == 'preset':
                preset_data_map, preset_type = self._get_preset_info(data.get('preset_number'))
                if not preset_data_map or not preset_type:
                    continue
                
                params_to_track = self._get_params_for_preset_type(preset_type)

                for fid in fixture_ids_for_event:
                    if str(fid) in preset_data_map and fid in tracked_state:
                        source_params = preset_data_map[str(fid)]
                        for param_key in params_to_track:
                            if param_key in source_params:
                                tracked_state[fid][param_key] = source_params[param_key]

            elif event_type in ['brightness', 'pan', 'tilt', 'zoom', 'focus', 'gobo', 'strobe']:
                param_map = {'brightness': 'brightness', 'pan': 'rotation_y', 'tilt': 'rotation_x', 'zoom': 'zoom',
                             'focus': 'focus', 'gobo': 'gobo_index', 'strobe': 'shutter_strobe_rate'}
                param_key = param_map.get(event_type)
                if param_key and 'value' in data:
                    for fid in fixture_ids_for_event:
                        if fid in tracked_state:
                            tracked_state[fid][param_key] = data['value']
            
            elif event_type == 'color' and 'color_hex' in data:
                color = QColor(data['color_hex'])
                for fid in fixture_ids_for_event:
                    if fid in tracked_state:
                        tracked_state[fid]['red'] = color.red()
                        tracked_state[fid]['green'] = color.green()
                        tracked_state[fid]['blue'] = color.blue()
        
        return tracked_state


    def _process_single_active_brightness_event(self, event_id: int, current_time_s: float, is_seek: bool = False):
        if not self.timeline_widget: return
        if event_id not in self.active_event_states:
            return 
        
        state = self.active_event_states[event_id]
        event_data = next((ev for ev in self.timeline_widget.events if ev['id'] == event_id), None)

        if not event_data or event_data['type'] != 'brightness':
            if event_id in self.active_event_states: del self.active_event_states[event_id]
            return

        actual_event_start_s = self.timeline_widget._get_effective_event_start_time(event_data)

        main_duration_s = event_data['duration']
        fade_in_s = event_data['data'].get('fade_in', 0.0)
        fade_out_s = event_data['data'].get('fade_out', 0.0)
        event_target_value = float(event_data['data'].get('value', 0))

        fade_in_start_s = actual_event_start_s
        fade_in_end_s = actual_event_start_s + fade_in_s
        full_value_start_s = fade_in_end_s
        full_value_end_s = full_value_start_s + main_duration_s
        fade_out_start_s = full_value_end_s
        fade_out_end_s = fade_out_start_s + fade_out_s

        if 'status' not in state or is_seek:
            # For a seek or first-time process, we need the "from" value, which is the tracked state right before this event
            state_before_event = self._calculate_tracked_state_at_time(actual_event_start_s - 0.001, self._get_base_fixture_states())
            
            # Since a brightness event can target multiple fixtures, we take the value from the first one as representative.
            # This is a simplification; a more complex system might store a "from" value per fixture.
            target_fixtures_ids = self._get_fixture_ids_for_target(event_data['target_type'], event_data['target_id'])
            initial_brightness_for_fade_in = 100 # Default
            if target_fixtures_ids and target_fixtures_ids[0] in state_before_event:
                initial_brightness_for_fade_in = state_before_event[target_fixtures_ids[0]]['brightness']

            state['initial_value_at_fade_in_start'] = initial_brightness_for_fade_in
            state['event_target_value'] = event_target_value
            state['calculated_fade_out_target_value'] = self._determine_fade_out_target_value(event_data, self.timeline_widget.events) 
            
            if current_time_s < fade_in_start_s: state['status'] = 'pending' 
            elif current_time_s < fade_in_end_s: state['status'] = 'fade_in'
            elif current_time_s < full_value_end_s: state['status'] = 'full'
            elif current_time_s < fade_out_end_s: state['status'] = 'fade_out'
            else: state['status'] = 'ended'

        current_val_to_apply = None

        if state['status'] == 'pending' and current_time_s >= fade_in_start_s:
            state['status'] = 'fade_in' 

        if state['status'] == 'fade_in':
            if current_time_s < fade_in_end_s:
                progress = (current_time_s - fade_in_start_s) / fade_in_s if fade_in_s > 1e-6 else 1.0
                current_val_to_apply = state['initial_value_at_fade_in_start'] + \
                                     (state['event_target_value'] - state['initial_value_at_fade_in_start']) * progress
            else: 
                current_val_to_apply = state['event_target_value']
                if current_time_s < full_value_end_s: state['status'] = 'full'
                elif current_time_s < fade_out_end_s: 
                    state['status'] = 'fade_out'
                    state['initial_value_at_fade_out_start'] = state['event_target_value'] 
                else: state['status'] = 'ended'
        
        elif state['status'] == 'full':
            if current_time_s < full_value_end_s:
                current_val_to_apply = state['event_target_value']
            else: 
                if current_time_s < fade_out_end_s : 
                    state['status'] = 'fade_out'
                    state['initial_value_at_fade_out_start'] = state['event_target_value']
                else: state['status'] = 'ended'
        
        if state['status'] == 'fade_out': 
            if current_time_s < fade_out_end_s:
                if 'initial_value_at_fade_out_start' not in state: 
                    state['initial_value_at_fade_out_start'] = state['event_target_value']
                
                progress = (current_time_s - fade_out_start_s) / fade_out_s if fade_out_s > 1e-6 else 1.0
                current_val_to_apply = state['initial_value_at_fade_out_start'] + \
                                     (state['calculated_fade_out_target_value'] - state['initial_value_at_fade_out_start']) * progress
            else: 
                current_val_to_apply = state['calculated_fade_out_target_value']
                state['status'] = 'ended'

        if state['status'] == 'ended':
            if current_val_to_apply is None: current_val_to_apply = state['calculated_fade_out_target_value']
            self._apply_brightness_to_target(event_data['target_type'], event_data['target_id'], current_val_to_apply)
            if event_id in self.active_event_states: del self.active_event_states[event_id]
            return

        if current_val_to_apply is not None:
            self._apply_brightness_to_target(event_data['target_type'], event_data['target_id'], current_val_to_apply)
            state['last_applied_val'] = current_val_to_apply 

    def _determine_fade_out_target_value(self, current_event: dict, all_timeline_events: list[dict]) -> float:
        if not self.timeline_widget: return 0.0
        target_type = current_event['target_type']
        target_id = current_event['target_id']
        
        effective_current_event_start_s = self.timeline_widget._get_effective_event_start_time(current_event)

        current_event_fade_in_time = current_event['data'].get('fade_in', 0.0)
        current_event_main_duration = current_event['duration']
        
        current_event_full_value_end_time = effective_current_event_start_s + current_event_fade_in_time + current_event_main_duration
        current_event_fade_out_finish_time = current_event_full_value_end_time + current_event['data'].get('fade_out', 0.0)


        next_event_on_target = None
        min_next_start_time = float('inf')

        for e_next in all_timeline_events:
            if e_next['id'] == current_event['id']: continue
            if e_next['target_type'] == target_type and e_next['target_id'] == target_id:
                effective_next_event_start_s = self.timeline_widget._get_effective_event_start_time(e_next)
                if effective_next_event_start_s >= current_event_full_value_end_time:
                    if effective_next_event_start_s < min_next_start_time:
                        min_next_start_time = effective_next_event_start_s
                        next_event_on_target = e_next
        
        if next_event_on_target and next_event_on_target['type'] == 'brightness':
            if min_next_start_time <= current_event_fade_out_finish_time:
                return float(next_event_on_target['data'].get('value', 0))
        
        return 0.0 
    
    def _apply_brightness_to_target(self, target_type: str, target_id: int | None, value: float):
        clamped_value = max(0, min(100, int(round(value)))) 
        if target_type == "master":
            if abs(self.main_window.master_fader.value() - clamped_value) > 0:
                 self.main_window.master_fader.setValue(clamped_value)
        elif target_type == "fixture" and target_id is not None:
            self.main_window.update_fixture_data_and_notify(target_id, {'brightness': clamped_value})
        elif target_type == "group" and target_id is not None:
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("SELECT fixture_id FROM fixture_group_mappings WHERE group_id = ?", (target_id,))
                for (fix_id,) in cursor.fetchall():
                    self.main_window.update_fixture_data_and_notify(fix_id, {'brightness': clamped_value})
            except Exception as e:
                print(f"Error applying group brightness from timeline fade: {e}")


    def _check_and_trigger_events(self, current_time_s, is_seek=False):
        if not self.timeline_widget or not self.event_list_widget: return 

        if is_seek:
            # On a seek, the handle_playhead_seek_by_user function takes care of setting the correct state.
            # We just need to manage the active_event_states dictionary here.
            self.active_event_states.clear()
            for event_data in self.timeline_widget.events:
                event_start = self.timeline_widget._get_effective_event_start_time(event_data)
                event_end = event_start + self.timeline_widget._get_event_visual_duration_s(event_data)
                if event_start <= current_time_s < event_end:
                    self.active_event_states[event_data['id']] = {} # Mark as active
                    if event_data['type'] == 'brightness':
                        self._process_single_active_brightness_event(event_data['id'], current_time_s, is_seek=True)
            self._update_list_widget_styles(current_time_s)
            return

        # ---- Normal Playback Logic ----
        active_brightness_event_ids = [eid for eid, estate in self.active_event_states.items() if 'status' in estate and estate['status'] not in ['triggered_once', 'ended']]
        for event_id in active_brightness_event_ids:
            self._process_single_active_brightness_event(event_id, current_time_s, is_seek=False)


        for event_data in self.timeline_widget.events:
            event_id = event_data['id']
            actual_event_start_s = self.timeline_widget._get_effective_event_start_time(event_data)
            visual_event_end_s = actual_event_start_s + self.timeline_widget._get_event_visual_duration_s(event_data)


            if event_id in self.active_event_states and self.active_event_states[event_id].get('status') == 'ended':
                continue 

            if current_time_s >= actual_event_start_s and current_time_s < visual_event_end_s:
                if event_id not in self.active_event_states:
                    if event_data['type'] == 'brightness':
                        self.active_event_states[event_id] = {} 
                        self._process_single_active_brightness_event(event_id, current_time_s, is_seek=False) 
                    else: 
                        self.event_triggered.emit(event_data)
                        self.active_event_states[event_id] = {'status': 'triggered_once'}
            
            elif current_time_s >= visual_event_end_s: 
                if event_id in self.active_event_states:
                    if self.active_event_states[event_id].get('status') != 'ended':
                        if event_data['type'] == 'brightness':
                            self.active_event_states[event_id]['status'] = 'fade_out' 
                            self._process_single_active_brightness_event(event_id, current_time_s, is_seek=False) 
                    if event_id in self.active_event_states and self.active_event_states[event_id].get('status') == 'ended':
                        del self.active_event_states[event_id] 
                    elif event_data['type'] != 'brightness' and event_id in self.active_event_states: 
                        del self.active_event_states[event_id]
        
        self._update_list_widget_styles(current_time_s)


    def _update_list_widget_styles(self, current_time_s):
        """Helper to update list widget styles based on playhead position."""
        if not self.timeline_widget or not self.event_list_widget: return

        next_upcoming_event_id_for_style: int | None = None
        min_abs_diff_for_selection = float('inf')
        current_active_event_ids_for_styling = []

        for ev_data_list_scan in self.timeline_widget.events:
            visual_event_start_time = self.timeline_widget._get_effective_event_start_time(ev_data_list_scan)
            visual_event_end_time = visual_event_start_time + self.timeline_widget._get_event_visual_duration_s(ev_data_list_scan)
            
            is_active_for_style = visual_event_start_time <= current_time_s < visual_event_end_time
            current_event_id_scan = ev_data_list_scan['id']

            if is_active_for_style:
                current_active_event_ids_for_styling.append(current_event_id_scan)
            
            if visual_event_start_time > current_time_s:
                time_diff = visual_event_start_time - current_time_s
                if next_upcoming_event_id_for_style is None or time_diff < min_abs_diff_for_selection:
                    min_abs_diff_for_selection = time_diff
                    next_upcoming_event_id_for_style = current_event_id_scan

        default_bg = self.event_list_widget.palette().base().color()
        active_color = QColor(self.main_window.settings.value("theme/activeListItemColor", "#4a5d23")) 
        next_color = QColor(self.main_window.settings.value("theme/nextListItemColor", "#604520"))   
        default_text_color = self.event_list_widget.palette().text().color()

        for i in range(self.event_list_widget.count()):
            item = self.event_list_widget.item(i)
            event_id_in_list = item.data(Qt.ItemDataRole.UserRole)
            font = item.font(); font.setBold(False)
            item.setForeground(default_text_color)

            is_timeline_selected = event_id_in_list in self.timeline_widget.selected_event_ids
            is_playhead_active = event_id_in_list in current_active_event_ids_for_styling
            is_playhead_next = event_id_in_list == next_upcoming_event_id_for_style and not current_active_event_ids_for_styling

            if is_timeline_selected:
                item.setBackground(active_color); font.setBold(True)
            elif is_playhead_active:
                item.setBackground(active_color); font.setBold(True)
            elif is_playhead_next:
                item.setBackground(next_color)
            else:
                item.setBackground(default_bg)
            item.setFont(font)

    def _format_time_parts_for_rich_text(self, time_s: float, is_total_time: bool = False) -> str:
        time_ms = int(time_s * 1000)
        seconds_total_abs = (time_ms // 1000)
        
        sign = "-" if time_s < 0 else "" 
        seconds_total_abs = abs(seconds_total_abs) 

        s = seconds_total_abs % 60
        m = (seconds_total_abs // 60) % 60
        h = (seconds_total_abs // 3600) 
        
        ms = abs(time_ms % 1000)

        main_size = "18pt" 
        ms_size = "12pt" 
        total_size = "12pt"
        total_ms_size = "10pt"
        
        current_weight = "bold"
        total_weight = "normal"


        main_part_str = ""
        if h > 0: main_part_str = f"{sign}{h:01d}:{m:02d}:{s:02d}"
        else: main_part_str = f"{sign}{m:02d}:{s:02d}"
            
        if is_total_time:
             return f"<span style='font-size:{total_size}; font-weight:{total_weight};'>{main_part_str}</span><span style='font-size:{total_ms_size}; font-weight:{total_weight};'>.{ms:03d}</span>"
        else:
            return f"<span style='font-size:{main_size}; font-weight:{current_weight};'>{main_part_str}</span><span style='font-size:{ms_size}; font-weight:normal;'>.{ms:03d}</span>"


    def update_time_label(self, current_s, total_s):
        formatted_current_time = self._format_time_parts_for_rich_text(current_s, is_total_time=False)
        formatted_total_time = self._format_time_parts_for_rich_text(total_s, is_total_time=True)
        
        self.current_time_label.setText(
            f"{formatted_current_time} <span style='font-size:12pt; font-weight:normal;'>/ {formatted_total_time}s</span>"
        )
        self.content_or_playhead_changed_for_embedded.emit()


    def show_add_event_dialog(self, prefill_timestamp: float | None = None, is_from_sync_queue: bool = False):
        try:
            default_start_time = prefill_timestamp if prefill_timestamp is not None \
                else (self.timeline_widget.current_playhead_position if self.timeline_widget else 0.0)
            dialog = TimelineEventDialog(self.main_window, event_data={'start_time': default_start_time}, is_new_event=True, parent=self)
            dialog_result = dialog.exec()
            if dialog_result == QDialog.DialogCode.Accepted:
                event_details = dialog.get_data()
                if event_details: 
                    cursor = self.main_window.db_connection.cursor()
                    cursor.execute(
                        "INSERT INTO timeline_events (name, start_time, duration, event_type, data, target_type, target_id, cue_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                        (event_details['name'], event_details['start_time'], event_details['duration'], 
                         event_details['type'], json.dumps(event_details['data']),
                         event_details['target_type'], event_details['target_id'],
                         event_details['cue_id']) 
                    )
                    self.main_window.db_connection.commit()
                    self.refresh_event_list_and_timeline()
                    QMessageBox.information(self, "Event Added", f"Event '{event_details['name']}' added.")
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not add event: {e}")
            print(f"Error adding event: {e}")
        finally:
            if is_from_sync_queue:
                QTimer.singleShot(0, self._show_next_add_event_dialog_for_synced_cue)
            else: 
                self._is_processing_synced_cue_dialog = False


    def show_edit_event_dialog(self):
        event_id_to_edit = None
        if self.timeline_widget and self.timeline_widget.selected_event_ids:
            event_id_to_edit = self.timeline_widget.selected_event_ids[0] 
        elif self.event_list_widget and self.event_list_widget.currentItem():
            event_id_to_edit = self.event_list_widget.currentItem().data(Qt.ItemDataRole.UserRole)

        if event_id_to_edit is None: QMessageBox.warning(self, "Selection Error", "Please select an event to edit."); return
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name, start_time, duration, event_type, data, target_type, target_id, cue_id FROM timeline_events WHERE id = ?", (event_id_to_edit,)) 
            ev_tuple = cursor.fetchone()
            if not ev_tuple: QMessageBox.critical(self, "Error", "Event not found in database."); self.refresh_event_list_and_timeline(); return
            event_data_for_dialog = {
                'id': ev_tuple[0], 'name': ev_tuple[1], 'start_time': float(ev_tuple[2]),
                'duration': float(ev_tuple[3]), 'type': ev_tuple[4],
                'data': json.loads(ev_tuple[5]) if isinstance(ev_tuple[5], str) else ev_tuple[5],
                'target_type': ev_tuple[6] if ev_tuple[6] else 'master',
                'target_id': ev_tuple[7],
                'cue_id': ev_tuple[8] 
            }
        except Exception as e: QMessageBox.critical(self, "DB Error", f"Could not fetch event for editing: {e}"); return
        dialog = TimelineEventDialog(self.main_window, event_data=event_data_for_dialog, is_new_event=False, parent=self)
        if dialog.exec():
            try:
                updated_details = dialog.get_data()
                if not updated_details: return
                cursor = self.main_window.db_connection.cursor()
                cursor.execute(
                    """UPDATE timeline_events SET 
                       name = ?, start_time = ?, duration = ?, event_type = ?, data = ?,
                       target_type = ?, target_id = ?, cue_id = ? 
                       WHERE id = ?""", 
                    (updated_details['name'], updated_details['start_time'], updated_details['duration'],
                     updated_details['type'], json.dumps(updated_details['data']),
                     updated_details['target_type'], updated_details['target_id'],
                     updated_details['cue_id'], 
                     event_id_to_edit)
                )
                self.main_window.db_connection.commit()
                self.refresh_event_list_and_timeline()
                QMessageBox.information(self, "Event Updated", f"Event '{updated_details['name']}' updated.")
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Could not update event: {e}")

    def _handle_delete_multiple_events(self, event_ids: list[int]):
        if not event_ids: return
        reply = QMessageBox.question(self, "Confirm Delete", 
                                     f"Are you sure you want to delete {len(event_ids)} selected events?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for event_id in event_ids:
                try:
                    self._handle_dependent_events_on_delete(event_id) 
                    cursor = self.main_window.db_connection.cursor()
                    cursor.execute("DELETE FROM timeline_events WHERE id = ?", (event_id,))
                    self.main_window.db_connection.commit() 
                    if event_id in self.active_event_states: 
                        del self.active_event_states[event_id]
                    deleted_count += 1
                except Exception as e:
                    QMessageBox.critical(self, "DB Error", f"Could not delete event ID {event_id}: {e}")
            
            if deleted_count > 0:
                if self.timeline_widget: self.timeline_widget.selected_event_ids.clear()
                self.refresh_event_list_and_timeline()
                QMessageBox.information(self, "Events Deleted", f"{deleted_count} event(s) deleted successfully.")


    def delete_selected_event_from_list_widget(self): 
        if not self.timeline_widget: return
        
        ids_to_delete = list(self.timeline_widget.selected_event_ids) 
        if not ids_to_delete : 
            selected_list_items = self.event_list_widget.selectedItems()
            if selected_list_items:
                 ids_to_delete = [item.data(Qt.ItemDataRole.UserRole) for item in selected_list_items]
            elif self.event_list_widget.currentItem(): 
                 ids_to_delete = [self.event_list_widget.currentItem().data(Qt.ItemDataRole.UserRole)]

            
        if not ids_to_delete:
            QMessageBox.warning(self, "Selection Error", "Please select event(s) to delete from the timeline or list.")
            return
        
        self._handle_delete_multiple_events(ids_to_delete)


    def delete_event_by_id(self, event_id: int): 
        self._handle_delete_multiple_events([event_id])


    def _handle_dependent_events_on_delete(self, deleted_event_id: int):
        events_modified_count = 0
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, data, cue_id FROM timeline_events WHERE data LIKE ?", (f'%\"followed_event_id\": {deleted_event_id}%',))
            dependent_events = cursor.fetchall()

            for dep_event_id, dep_data_json, dep_cue_id in dependent_events:
                try:
                    dep_data = json.loads(dep_data_json)
                    if dep_data.get("trigger_mode") == "follow_event_in_cue" and dep_data.get("followed_event_id") == deleted_event_id:
                        dep_data["trigger_mode"] = "relative_to_cue" 
                        del dep_data["followed_event_id"] 
                        
                        cursor.execute("UPDATE timeline_events SET data = ? WHERE id = ?",
                                       (json.dumps(dep_data), dep_event_id))
                        events_modified_count += 1
                        print(f"Event ID {dep_event_id} was following deleted event {deleted_event_id}. Switched to relative_to_cue.")
                except json.JSONDecodeError:
                    print(f"Error decoding JSON for event ID {dep_event_id} while handling dependent event deletion.")
                except Exception as e_inner:
                    print(f"Error updating dependent event {dep_event_id}: {e_inner}")

            if events_modified_count > 0:
                self.main_window.db_connection.commit()
                QMessageBox.information(self, "Dependent Events Updated", 
                                        f"{events_modified_count} event(s) that were following the deleted event "
                                        "have been updated to be relative to their respective cues.")
        except Exception as e:
            print(f"Error handling dependent events on delete: {e}")
            QMessageBox.critical(self, "DB Error", f"Error updating dependent events: {e}")



    def refresh_event_list_and_timeline(self, regenerate_waveform=True):
        if self.timeline_widget:
            self.cues_changed.emit()
            
        old_selected_event_ids = []
        if self.timeline_widget and self.timeline_widget.selected_event_ids:
            old_selected_event_ids = list(self.timeline_widget.selected_event_ids)
        
        old_selected_cue_id = None
        if self.timeline_widget and self.timeline_widget.selected_cue_id is not None:
            old_selected_cue_id = self.timeline_widget.selected_cue_id

        if self.timeline_widget:
            self.timeline_widget.load_events_from_db(regenerate_waveform=regenerate_waveform) 
            self.timeline_widget.load_cues_from_db() 
            
            self.timeline_widget.selected_event_ids = [
                ev_id for ev_id in old_selected_event_ids 
                if any(ev['id'] == ev_id for ev in self.timeline_widget.events)
            ]
            
            if old_selected_cue_id and any(c['id'] == old_selected_cue_id for c in self.timeline_widget.cues):
                self.timeline_widget.selected_cue_id = old_selected_cue_id
            else:
                self.timeline_widget.selected_cue_id = None
        
        self.event_list_widget.blockSignals(True)
        self.event_list_widget.clear()
        
        # Add Cues to the List Widget
        if self.timeline_widget and self.timeline_widget.cues:
            cue_header = QListWidgetItem("--- Cues ---")
            font = cue_header.font(); font.setBold(True); cue_header.setFont(font)
            cue_header.setFlags(cue_header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.event_list_widget.addItem(cue_header)
            
            for cue_data in self.timeline_widget.cues:
                item_text = f"Cue {cue_data['cue_number']}"
                if cue_data.get('name'): item_text += f": {cue_data['name']}"
                item_text += f" @ {cue_data['trigger_time_s']:.3f}s"
                list_item = QListWidgetItem(item_text)
                
                action_id = f"cue.go.{cue_data['cue_number']}".replace('.','_')
                keybind_str = self.main_window.keybind_map.get(action_id, '')
                tooltip = f"Go to Cue {cue_data['cue_number']}"
                if keybind_str:
                    tooltip += f" ({keybind_str})"
                list_item.setToolTip(tooltip)
                
                list_item.setData(Qt.ItemDataRole.UserRole, f"cue_{cue_data['id']}")
                self.event_list_widget.addItem(list_item)


        if self.timeline_widget and self.timeline_widget.events:
            event_header = QListWidgetItem("--- Events ---")
            font = event_header.font(); font.setBold(True); event_header.setFont(font)
            event_header.setFlags(event_header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.event_list_widget.addItem(event_header)

            grouped_events = {}
            for track_idx, track_info in enumerate(self.timeline_widget.tracks):
                key = (track_idx, track_info['name']) 
                grouped_events[key] = []
            for event_data in self.timeline_widget.events:
                track_idx = self.timeline_widget._get_track_index_for_event(event_data)
                if 0 <= track_idx < len(self.timeline_widget.tracks):
                    track_info_for_event = self.timeline_widget.tracks[track_idx]
                    key = (track_idx, track_info_for_event['name'])
                    grouped_events.setdefault(key, []).append(event_data)
                else: 
                    key_master = (0, self.timeline_widget.tracks[0]['name']) 
                    grouped_events.setdefault(key_master, []).append(event_data)
            
            for (track_idx, track_name_display), events_on_track in sorted(grouped_events.items()):
                events_on_track.sort(key=lambda x: self.timeline_widget._get_effective_event_start_time(x))
                for event_data in events_on_track:
                    event_specific_data_str = ""
                    if event_data['type'] == 'preset':
                        preset_num = event_data['data'].get('preset_number')
                        event_specific_data_str = f" (P {preset_num or 'N/A'})"
                    elif event_data['type'] == 'brightness':
                        event_specific_data_str = f" ({event_data['data'].get('value', 'N/A')}%)"
                        if event_data['data'].get('fade_in', 0) > 0:
                            event_specific_data_str += f" In:{event_data['data']['fade_in']:.1f}s"
                        if event_data['data'].get('fade_out', 0) > 0:
                            event_specific_data_str += f" Out:{event_data['data']['fade_out']:.1f}s"
                    
                    cue_info_str = ""
                    effective_display_time_s = self.timeline_widget._get_effective_event_start_time(event_data)

                    if event_data.get('cue_id') and self.timeline_widget.cues:
                        cue = next((c for c in self.timeline_widget.cues if c['id'] == event_data['cue_id']), None)
                        if cue: cue_info_str = f" (Cue {cue['cue_number']})"

                    item_text = (f"[{track_name_display}] {event_data['name']}{cue_info_str} @ {effective_display_time_s:.3f}s "
                                 f"({event_data['type']}{event_specific_data_str})")
                    list_item = QListWidgetItem(item_text)
                    list_item.setData(Qt.ItemDataRole.UserRole, event_data['id']) 
                    self.event_list_widget.addItem(list_item)
            
            first_item_to_scroll_to = None
            self.event_list_widget.clearSelection() 
            for i in range(self.event_list_widget.count()):
                item = self.event_list_widget.item(i)
                item_data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(item_data, int) and item_data in self.timeline_widget.selected_event_ids:
                    item.setSelected(True)
                    if first_item_to_scroll_to is None and item_data == (self.timeline_widget.selected_event_ids[0] if self.timeline_widget.selected_event_ids else None):
                        first_item_to_scroll_to = item 
            if first_item_to_scroll_to:
                 self.event_list_widget.setCurrentItem(first_item_to_scroll_to)
                 self.event_list_widget.scrollToItem(first_item_to_scroll_to, QAbstractItemView.ScrollHint.PositionAtCenter)
            elif not self.timeline_widget.selected_event_ids : 
                 self.event_list_widget.setCurrentItem(None) 


        self.event_list_widget.blockSignals(False)
        
        if self.track_info_table_widget and self.timeline_widget: 
            self.track_info_table_widget.setRowCount(0) 
            current_row_idx_for_table = 0
            
            for track_display_order, track_info in enumerate(self.timeline_widget.tracks):
                self.track_info_table_widget.insertRow(current_row_idx_for_table)
                
                num_item = QTableWidgetItem(str(track_display_order + 1)) 
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.track_info_table_widget.setItem(current_row_idx_for_table, 0, num_item)

                self.track_info_table_widget.setItem(current_row_idx_for_table, 1, QTableWidgetItem(track_info['name']))
                self.track_info_table_widget.setItem(current_row_idx_for_table, 2, QTableWidgetItem(track_info['type'].capitalize()))
                id_text = str(track_info['id']) if track_info['id'] is not None else "N/A"
                id_item = QTableWidgetItem(id_text)
                id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.track_info_table_widget.setItem(current_row_idx_for_table, 3, id_item)

                track_item_row_total_height = TimelineWidget.EVENT_BASE_HEIGHT + \
                                              (2 * TimelineWidget.TRACK_INTERNAL_PADDING) + \
                                              TimelineWidget.TRACK_SPACING
                self.track_info_table_widget.setRowHeight(current_row_idx_for_table, track_item_row_total_height)
                current_row_idx_for_table += 1
            
            self.track_info_table_widget.resizeColumnsToContents() 
            self.track_info_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) 
            self.track_info_table_widget.setColumnWidth(0, 30) 
            self.track_info_table_widget.setColumnWidth(2, 70) 
            self.track_info_table_widget.setColumnWidth(3, 50) 


        effective_duration = self._get_effective_timeline_duration()
        current_pos = self.timeline_widget.current_playhead_position if self.timeline_widget else 0.0
        self.update_time_label(current_pos, effective_duration)
        if self.timeline_widget:
            self.timeline_widget.update()
            self.content_or_playhead_changed_for_embedded.emit()

    def get_current_playhead_time(self):
        return self.timeline_widget.get_current_playhead_time() if self.timeline_widget else 0.0
    
    def _get_effective_timeline_duration(self) -> float: 
        if not self.timeline_widget: return 0.0
        
        effective_duration = self.timeline_widget.audio_duration 
        if self.timeline_widget.events:
            max_event_time = 0
            for ev in self.timeline_widget.events: 
                event_visual_start = self.timeline_widget._get_effective_event_start_time(ev)
                event_total_visual_duration = self.timeline_widget._get_event_visual_duration_s(ev)
                max_event_time = max(max_event_time, event_visual_start + event_total_visual_duration)
            effective_duration = max(effective_duration, max_event_time)
        
        if self.timeline_widget.cues:
            max_cue_time = max((c['trigger_time_s'] for c in self.timeline_widget.cues), default=0)
            effective_duration = max(effective_duration, max_cue_time)

        if effective_duration == 0:
            return 60.0 
        return effective_duration

    def on_timeline_event_triggered(self, event_data: dict):
        event_type = event_data.get('type')
        payload = event_data.get('data', {})
        target_type = event_data.get('target_type', 'master') 
        target_id = event_data.get('target_id') 
        cue_id = event_data.get('cue_id') 

        if event_type == 'preset':
            preset_number = payload.get('preset_number')
            if preset_number:
                self.main_window.on_preset_applied_from_tab(str(preset_number), target_type=target_type, target_id=target_id)
        elif event_type == 'blackout':
            current_blackout_state = self.main_window.blackout_button.isChecked()
            action = payload.get('action', 'toggle') 
            if action == 'on':
                if not current_blackout_state: self.main_window.blackout_button.setChecked(True)
            elif action == 'off':
                if current_blackout_state: self.main_window.blackout_button.setChecked(False)
            elif action == 'toggle': self.main_window.blackout_button.setChecked(not current_blackout_state)
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
            # ... add other direct parameter events here ...
            
            if params_to_update:
                target_fixture_ids = self._get_fixture_ids_for_target(target_type, target_id)
                for fid in target_fixture_ids:
                    self.main_window.update_fixture_data_and_notify(fid, params_to_update)

    def show_add_cue_dialog(self, prefill_time: float | None = None): 
        try:
            default_time = prefill_time if prefill_time is not None else \
                           (self.timeline_widget.current_playhead_position if self.timeline_widget else 0.0)
            
            next_cue_num_suggestion = "1"
            if self.timeline_widget and self.timeline_widget.cues:
                max_int_cue_num = 0
                cue_numbers_str = [c['cue_number'] for c in self.timeline_widget.cues]
                
                for num_str in cue_numbers_str:
                    try:
                        num_int = int(num_str)
                        if num_int > max_int_cue_num:
                            max_int_cue_num = num_int
                    except ValueError:
                        try:
                            base_num = int(num_str.split('.')[0]) 
                            if base_num > max_int_cue_num:
                                max_int_cue_num = base_num
                        except ValueError:
                            pass 
                if max_int_cue_num > 0:
                    next_cue_num_suggestion = str(max_int_cue_num + 1)
                elif cue_numbers_str: 
                    def robust_cue_sort_key(cue_num_str_val):
                        parts = cue_num_str_val.split('.')
                        try:
                            return tuple(float(p) if p.replace('.', '', 1).isdigit() else float('inf') for p in parts) + (cue_num_str_val,)
                        except: 
                            return (float('inf'),) + (cue_num_str_val,)
                    
                    sorted_cue_numbers = sorted(cue_numbers_str, key=robust_cue_sort_key)
                    last_cue_num_str = sorted_cue_numbers[-1] if sorted_cue_numbers else ""
                    
                    if '.' in last_cue_num_str:
                        base, *sub_parts = last_cue_num_str.split('.')
                        sub_str = sub_parts[-1] if sub_parts else "0"
                        try:
                            next_cue_num_suggestion = f"{base}.{int(sub_str) + 1}"
                        except ValueError: 
                             next_cue_num_suggestion = last_cue_num_str + "A"
                    elif last_cue_num_str.isdigit():
                         next_cue_num_suggestion = str(int(last_cue_num_str) + 1)
                    else: 
                        next_cue_num_suggestion = last_cue_num_str + "A" if last_cue_num_str else "1"


            dialog = CueDialog(self.main_window, cue_data={'trigger_time_s': default_time, 'cue_number': next_cue_num_suggestion}, is_new_cue=True, parent=self)
            if dialog.exec():
                cue_details = dialog.get_data()
                if cue_details:
                    cursor = self.main_window.db_connection.cursor()
                    cursor.execute("SELECT id FROM cues WHERE cue_number = ?", (cue_details['cue_number'],))
                    if cursor.fetchone():
                        QMessageBox.warning(self, "Duplicate Cue Number", f"A cue with number '{cue_details['cue_number']}' already exists.")
                        return
                    cursor.execute(
                        "INSERT INTO cues (cue_number, name, trigger_time_s, comment) VALUES (?, ?, ?, ?)",
                        (cue_details['cue_number'], cue_details['name'], cue_details['trigger_time_s'], cue_details['comment'])
                    )
                    self.main_window.db_connection.commit()
                    self.refresh_event_list_and_timeline() 
                    QMessageBox.information(self, "Cue Added", f"Cue '{cue_details['cue_number']}' added.")
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not add cue: {e}")

    def show_edit_cue_dialog(self, cue_id_to_edit: int | None = None): 
        if cue_id_to_edit is None:
            if not self.timeline_widget or self.timeline_widget.selected_cue_id is None:
                 QMessageBox.warning(self, "Selection Error", "Please select a cue on the timeline to edit, or right-click a cue.")
                 return
            cue_id_to_edit = self.timeline_widget.selected_cue_id

        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, cue_number, name, trigger_time_s, comment FROM cues WHERE id = ?", (cue_id_to_edit,))
            cue_tuple = cursor.fetchone()
            if not cue_tuple:
                QMessageBox.critical(self, "Error", "Cue not found in database.")
                self.refresh_event_list_and_timeline()
                return
            cue_data_for_dialog = {
                'id': cue_tuple[0], 'cue_number': cue_tuple[1], 'name': cue_tuple[2],
                'trigger_time_s': float(cue_tuple[3]), 'comment': cue_tuple[4]
            }
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not fetch cue for editing: {e}")
            return
        
        dialog = CueDialog(self.main_window, cue_data=cue_data_for_dialog, is_new_cue=False, parent=self)
        if dialog.exec():
            try:
                updated_details = dialog.get_data()
                if not updated_details: return

                cursor = self.main_window.db_connection.cursor()
                cursor.execute("SELECT id FROM cues WHERE cue_number = ? AND id != ?", (updated_details['cue_number'], cue_id_to_edit))
                if cursor.fetchone():
                    QMessageBox.warning(self, "Duplicate Cue Number", f"Another cue with number '{updated_details['cue_number']}' already exists.")
                    return
                
                cursor.execute(
                    "UPDATE cues SET cue_number = ?, name = ?, trigger_time_s = ?, comment = ? WHERE id = ?",
                    (updated_details['cue_number'], updated_details['name'], updated_details['trigger_time_s'], updated_details['comment'], cue_id_to_edit)
                )
                self.main_window.db_connection.commit()
                self.refresh_event_list_and_timeline()
                QMessageBox.information(self, "Cue Updated", f"Cue '{updated_details['cue_number']}' updated.")
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Could not update cue: {e}")

    def delete_selected_cue(self, cue_id_to_delete: int | None = None):
        if cue_id_to_delete is None: 
            if not self.timeline_widget or self.timeline_widget.selected_cue_id is None:
                QMessageBox.warning(self, "Selection Error", "Please select a cue on the timeline to delete, or right-click a cue.")
                return
            cue_id_to_delete = self.timeline_widget.selected_cue_id
        
        cue_name_for_msg = f"ID: {cue_id_to_delete}"
        if self.timeline_widget:
            cue_data = next((c for c in self.timeline_widget.cues if c['id'] == cue_id_to_delete), None)
            if cue_data: cue_name_for_msg = f"Cue {cue_data.get('cue_number', '')}: {cue_data.get('name', '')}"

        reply = QMessageBox.question(self, "Confirm Delete", 
                                     f"Delete cue '{cue_name_for_msg}'?\nEvents associated with this cue will have their cue link removed (but events themselves won't be deleted).",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("DELETE FROM cues WHERE id = ?", (cue_id_to_delete,))
                self.main_window.db_connection.commit()

                if self.timeline_widget and self.timeline_widget.selected_cue_id == cue_id_to_delete:
                    self.timeline_widget.selected_cue_id = None 
                
                self.refresh_event_list_and_timeline()
                QMessageBox.information(self, "Cue Deleted", f"Cue '{cue_name_for_msg}' deleted.")
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Could not delete cue: {e}")
    
    def _go_to_previous_cue(self):
        if not self.timeline_widget or not self.timeline_widget.cues:
            QMessageBox.information(self, "No Cues", "There are no cues in the timeline.")
            return

        current_time = self.timeline_widget.current_playhead_position
        epsilon = 0.001 
        sorted_cues = sorted(self.timeline_widget.cues, key=lambda c: (c['trigger_time_s'], c['cue_number']))
        
        prev_cue_data = None
        for cue in reversed(sorted_cues): 
            if cue['trigger_time_s'] < (current_time - epsilon):
                prev_cue_data = cue
                break
        
        if prev_cue_data:
            self.go_to_cue_by_number(prev_cue_data['cue_number'])
        else:
            QMessageBox.information(self, "Start of Cues", "No previous cues in the timeline from this position.")

    def _go_to_next_cue(self):
        if not self.timeline_widget or not self.timeline_widget.cues:
            QMessageBox.information(self, "No Cues", "There are no cues in the timeline.")
            return

        current_time = self.timeline_widget.current_playhead_position
        sorted_cues = sorted(self.timeline_widget.cues, key=lambda c: (c['trigger_time_s'], c['cue_number']))
        
        next_cue_data = None
        for cue in sorted_cues:
            if cue['trigger_time_s'] > current_time:
                next_cue_data = cue
                break
        
        if next_cue_data:
            self.go_to_cue_by_number(next_cue_data['cue_number'])
        else:
            QMessageBox.information(self, "End of Cues", "No further cues in the timeline.")

    def go_to_cue_by_number(self, cue_number: str):
        if not self.timeline_widget:
            return
        
        target_cue = next((c for c in self.timeline_widget.cues if c['cue_number'] == cue_number), None)

        if target_cue:
            # The new tracking logic is called by handle_playhead_seek_by_user
            self.handle_playhead_seek_by_user(target_cue['trigger_time_s'])

            # The rest of this updates the UI selection state
            self.timeline_widget.selected_cue_id = target_cue['id']
            if self.timeline_widget.selected_event_ids:
                self.timeline_widget.selected_event_ids.clear()
                if self.event_list_widget: self.event_list_widget.clearSelection()
            self.timeline_widget.update()
            self._on_timeline_cue_marker_clicked(target_cue['id'])
            print(f"CMD: Go Cue {cue_number} successful.")
        else:
            QMessageBox.warning(self, "Cue Not Found", f"Cue number '{cue_number}' does not exist in the timeline.")
            print(f"CMD Error: Cue '{cue_number}' not found.")

    def show_assign_event_to_cue_dialog(self, event_id: int):
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name, start_time, duration, event_type, data, target_type, target_id, cue_id FROM timeline_events WHERE id = ?", (event_id,))
            event_tuple = cursor.fetchone()
            if not event_tuple:
                QMessageBox.warning(self, "Error", f"Event ID {event_id} not found.")
                return
            
            current_event_full_data = {
                'id': event_tuple[0], 'name': event_tuple[1], 
                'start_time': float(event_tuple[2]), 'duration': float(event_tuple[3]), 
                'type': event_tuple[4],
                'data': json.loads(event_tuple[5]) if isinstance(event_tuple[5], str) else event_tuple[5],
                'target_type': event_tuple[6], 'target_id': event_tuple[7],
                'cue_id': event_tuple[8]
            }
            if not isinstance(current_event_full_data['data'], dict): current_event_full_data['data'] = {}

            event_name_str = current_event_full_data['name']
            current_cue_id_for_event = current_event_full_data['cue_id']
            
            dialog = AssignEventToCueDialog(self.main_window, event_name_str, current_cue_id_for_event, self)
            if dialog.exec():
                selected_new_cue_id = dialog.get_selected_cue_id() 

                effective_absolute_start_time_before_change = self.timeline_widget._get_effective_event_start_time(current_event_full_data)
                
                new_event_start_time_val = current_event_full_data['start_time']
                new_event_data_payload = current_event_full_data['data'].copy() 


                if selected_new_cue_id is None: 
                    new_event_start_time_val = effective_absolute_start_time_before_change
                    new_event_data_payload['trigger_mode'] = 'absolute'
                    if 'followed_event_id' in new_event_data_payload:
                        del new_event_data_payload['followed_event_id']
                else: 
                    new_event_data_payload['trigger_mode'] = 'relative_to_cue' 
                    
                    new_cue_obj = next((c for c in self.timeline_widget.cues if c['id'] == selected_new_cue_id), None)
                    if new_cue_obj:
                        new_event_start_time_val = max(0, effective_absolute_start_time_before_change - new_cue_obj['trigger_time_s'])
                    else: 
                        new_event_start_time_val = 0.0 
                    
                    if 'followed_event_id' in new_event_data_payload: 
                        del new_event_data_payload['followed_event_id']
                
                cursor.execute("UPDATE timeline_events SET cue_id = ?, start_time = ?, data = ? WHERE id = ?",
                               (selected_new_cue_id, new_event_start_time_val, json.dumps(new_event_data_payload), event_id))
                self.main_window.db_connection.commit()
                self.refresh_event_list_and_timeline()
                QMessageBox.information(self, "Cue Assignment Updated", f"Event '{event_name_str}' cue assignment has been updated.")

        except Exception as e:
            QMessageBox.critical(self, "Error Assigning Cue", f"Could not assign event to cue: {e}")
            print(f"Error in show_assign_event_to_cue_dialog: {e}")


    def closeEvent(self, event): 
        if self.media_player:
            self.media_player.stop()
        super().closeEvent(event)

    def setVisible(self, visible: bool): 
        super().setVisible(visible)
        if not visible and self.media_player:
            if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.media_player.pause()

    def _handle_copy_request(self):
        if not self.timeline_widget or not self.timeline_widget.selected_event_ids:
            return
        
        self.event_clipboard.clear()
        for event_id in self.timeline_widget.selected_event_ids:
            event_data = next((e for e in self.timeline_widget.events if e['id'] == event_id), None)
            if event_data:
                self.event_clipboard.append(copy.deepcopy(event_data))

        QMessageBox.information(self, "Copy", f"{len(self.event_clipboard)} event(s) copied to clipboard.")

    def _handle_paste_request(self, click_pos: QPoint):
        if not self.timeline_widget: return
        paste_time_s = click_pos.x() / self.timeline_widget.pixels_per_second if self.timeline_widget.pixels_per_second > 0 else 0
        self.paste_events_from_clipboard(paste_time_s)

    def paste_events_from_clipboard(self, paste_time_s: float):
        if not self.event_clipboard or not self.timeline_widget:
            return

        try:
            base_time = min(self.timeline_widget._get_effective_event_start_time(ev) for ev in self.event_clipboard)
            newly_pasted_ids = []
            
            cursor = self.main_window.db_connection.cursor()
            
            for event_to_copy in self.event_clipboard:
                offset = self.timeline_widget._get_effective_event_start_time(event_to_copy) - base_time
                new_start_time = paste_time_s + offset
                
                new_data_payload = event_to_copy.get('data', {}).copy()
                new_data_payload['trigger_mode'] = 'absolute'
                if 'followed_event_id' in new_data_payload:
                    del new_data_payload['followed_event_id']

                new_event_name = f"Copy of {event_to_copy['name']}"
                
                cursor.execute(
                    """INSERT INTO timeline_events (name, start_time, duration, event_type, data, target_type, target_id, cue_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (new_event_name, new_start_time, event_to_copy['duration'], event_to_copy['type'],
                     json.dumps(new_data_payload), event_to_copy['target_type'], event_to_copy['target_id'],
                     None) # Set cue_id to None for pasted events
                )
                newly_pasted_ids.append(cursor.lastrowid)

            self.main_window.db_connection.commit()
            
            self.refresh_event_list_and_timeline(regenerate_waveform=False)
            
            # Select the newly created events
            if newly_pasted_ids:
                self.timeline_widget.selected_event_ids = newly_pasted_ids
                self.timeline_widget.event_selected_on_timeline.emit(newly_pasted_ids)
                self.timeline_widget.update()

        except Exception as e:
            QMessageBox.critical(self, "Paste Error", f"Failed to paste events: {e}")
            if self.main_window.db_connection:
                self.main_window.db_connection.rollback()