# tabs/loop_palettes_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDoubleSpinBox, QDialogButtonBox, QSplitter, QGroupBox,
    QSizePolicy, QCheckBox, QSpacerItem
)
from PyQt6.QtCore import Qt, pyqtSignal
import json
import sqlite3

class LoopPaletteEffectConfigWidget(QWidget):
    """ A widget to configure a single effect within a loop palette. """
    def __init__(self, effect_number_display: int, parent_form: 'LoopPaletteEditFormWidget', is_secondary=False):
        super().__init__(parent_form)
        self.parent_form = parent_form
        self.is_secondary_effect_config = is_secondary

        layout = QFormLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        self.effect_type_combo = QComboBox()
        self.effect_type_combo.addItem("Sine Wave", "sine_wave")
        self.effect_type_combo.addItem("Circle (Pan/Tilt)", "circle")
        self.effect_type_combo.addItem("U-Shape (Pan/Tilt)", "u_shape")
        self.effect_type_combo.addItem("Figure 8 (Pan/Tilt)", "figure_8")
        self.effect_type_combo.addItem("Bally (Fan)", "bally")
        self.effect_type_combo.addItem("Stagger (Dimmer Flicker)", "stagger")
        self.effect_type_combo.currentTextChanged.connect(self.update_specific_config_fields_visibility)
        layout.addRow("Effect Type:", self.effect_type_combo)

        self.target_param_combo = QComboBox()
        self.target_param_combo.addItem("Pan (rotation_y)", "rotation_y")
        self.target_param_combo.addItem("Tilt (rotation_x)", "rotation_x")
        self.target_param_combo.addItem("Dimmer (brightness)", "brightness")
        self.target_param_combo.addItem("Zoom", "zoom")
        self.target_param_combo.addItem("Focus", "focus")
        self.target_param_combo.currentTextChanged.connect(self._update_sine_wave_spinbox_contexts_for_this_effect)
        layout.addRow("Target Parameter:", self.target_param_combo)

        self.sine_wave_group = QGroupBox("Sine Config")
        self.sine_wave_group.setStyleSheet("QGroupBox { margin-top: 6px; }")
        sine_layout = QFormLayout(self.sine_wave_group)
        sine_layout.setContentsMargins(6, 8, 6, 6)
        sine_layout.setSpacing(7)
        self.speed_spinbox_sine = QDoubleSpinBox(); self.speed_spinbox_sine.setRange(0.01, 10.0); self.speed_spinbox_sine.setDecimals(2); self.speed_spinbox_sine.setSuffix(" Hz")
        sine_layout.addRow("Speed:", self.speed_spinbox_sine)
        self.size_spinbox_sine = QDoubleSpinBox(); self.size_spinbox_sine.setRange(0.1, 360.0); self.size_spinbox_sine.setDecimals(1); self.size_spinbox_sine.setSuffix(" units")
        sine_layout.addRow("Size:", self.size_spinbox_sine)
        self.center_spinbox_sine = QDoubleSpinBox(); self.center_spinbox_sine.setRange(-360.0, 360.0); self.center_spinbox_sine.setDecimals(1); self.center_spinbox_sine.setSuffix(" units")
        sine_layout.addRow("Center:", self.center_spinbox_sine)
        self.phase_spinbox_sine = QDoubleSpinBox(); self.phase_spinbox_sine.setRange(0, 359.9); self.phase_spinbox_sine.setDecimals(1); self.phase_spinbox_sine.setSuffix(" °")
        sine_layout.addRow("Phase Offset:", self.phase_spinbox_sine)
        
        self.direction_combo_sine = QComboBox()
        self.direction_combo_sine.addItems(["Forward", "Backward"])
        sine_layout.addRow("Direction:", self.direction_combo_sine)

        self.group_mode_combo_sine = QComboBox()
        self.group_mode_combo_sine.addItem("All Same Phase", "all_same_phase")
        self.group_mode_combo_sine.addItem("Spread Phase Evenly", "spread_phase")
        self.group_mode_combo_sine.addItem("Block - Groups of 2", "block_2")
        self.group_mode_combo_sine.addItem("Block - Groups of 3", "block_3")
        self.group_mode_combo_sine.addItem("Block - Groups of 4", "block_4")
        sine_layout.addRow("Group Mode:", self.group_mode_combo_sine) 

        self.wing_style_combo_sine = QComboBox()
        self.wing_style_combo_sine.addItem("None", "none")
        self.wing_style_combo_sine.addItem("Symmetrical 2 Wings", "symmetrical_2_wings")
        self.wing_style_combo_sine.addItem("Symmetrical 3 Wings", "symmetrical_3_wings")
        self.wing_style_combo_sine.addItem("Asymmetrical 2 Wings", "asymmetrical_2_wings")
        self.wing_style_combo_sine.currentIndexChanged.connect(self._on_wing_style_changed)
        sine_layout.addRow("Wing Style:", self.wing_style_combo_sine)
        
        self.wing_center_percent_label = QLabel("Wing Center:")
        self.wing_center_percent_spinbox = QDoubleSpinBox(); self.wing_center_percent_spinbox.setRange(0.0, 100.0); self.wing_center_percent_spinbox.setDecimals(1); self.wing_center_percent_spinbox.setSuffix(" %")
        sine_layout.addRow(self.wing_center_percent_label, self.wing_center_percent_spinbox)
        layout.addWidget(self.sine_wave_group)

        self.circle_group = QGroupBox("Circle Config")
        self.circle_group.setStyleSheet("QGroupBox { margin-top: 6px; }")
        circle_layout = QFormLayout(self.circle_group)
        circle_layout.setContentsMargins(6, 8, 6, 6)
        circle_layout.setSpacing(7)
        self.speed_spinbox_circle = QDoubleSpinBox(); self.speed_spinbox_circle.setRange(0.01, 10.0); self.speed_spinbox_circle.setDecimals(2); self.speed_spinbox_circle.setSuffix(" Hz")
        circle_layout.addRow("Speed:", self.speed_spinbox_circle)
        self.radius_pan_spinbox = QDoubleSpinBox(); self.radius_pan_spinbox.setRange(0.0, 180.0); self.radius_pan_spinbox.setDecimals(1); self.radius_pan_spinbox.setSuffix(" °")
        circle_layout.addRow("Pan Radius:", self.radius_pan_spinbox)
        self.radius_tilt_spinbox = QDoubleSpinBox(); self.radius_tilt_spinbox.setRange(0.0, 180.0); self.radius_tilt_spinbox.setDecimals(1); self.radius_tilt_spinbox.setSuffix(" °")
        circle_layout.addRow("Tilt Radius:", self.radius_tilt_spinbox)
        self.center_pan_spinbox = QDoubleSpinBox(); self.center_pan_spinbox.setRange(-180.0, 180.0); self.center_pan_spinbox.setDecimals(1); self.center_pan_spinbox.setSuffix(" °")
        circle_layout.addRow("Pan Center:", self.center_pan_spinbox)
        self.center_tilt_spinbox = QDoubleSpinBox(); self.center_tilt_spinbox.setRange(-180.0, 180.0); self.center_tilt_spinbox.setDecimals(1); self.center_tilt_spinbox.setSuffix(" °")
        circle_layout.addRow("Tilt Center:", self.center_tilt_spinbox)
        self.phase_spinbox_circle = QDoubleSpinBox(); self.phase_spinbox_circle.setRange(0, 359.9); self.phase_spinbox_circle.setDecimals(1); self.phase_spinbox_circle.setSuffix(" °")
        circle_layout.addRow("Start Phase:", self.phase_spinbox_circle)
        self.group_mode_combo_circle = QComboBox(); self.group_mode_combo_circle.addItem("All Same Phase", "all_same_phase"); self.group_mode_combo_circle.addItem("Spread Phase Evenly", "spread_phase")
        circle_layout.addRow("Group Mode:", self.group_mode_combo_circle)
        layout.addWidget(self.circle_group)

        self.u_shape_group = QGroupBox("U-Shape Config")
        self.u_shape_group.setStyleSheet("QGroupBox { margin-top: 6px; }")
        u_shape_layout = QFormLayout(self.u_shape_group)
        u_shape_layout.setContentsMargins(6, 8, 6, 6)
        u_shape_layout.setSpacing(7)
        self.speed_spinbox_u_shape = QDoubleSpinBox(); self.speed_spinbox_u_shape.setRange(0.01, 10.0); self.speed_spinbox_u_shape.setDecimals(2); self.speed_spinbox_u_shape.setSuffix(" Hz")
        u_shape_layout.addRow("Speed:", self.speed_spinbox_u_shape)
        self.width_spinbox_u_shape = QDoubleSpinBox(); self.width_spinbox_u_shape.setRange(0.1, 360.0); self.width_spinbox_u_shape.setDecimals(1); self.width_spinbox_u_shape.setSuffix(" °")
        u_shape_layout.addRow("Width (Pan):", self.width_spinbox_u_shape)
        self.height_spinbox_u_shape = QDoubleSpinBox(); self.height_spinbox_u_shape.setRange(0.1, 180.0); self.height_spinbox_u_shape.setDecimals(1); self.height_spinbox_u_shape.setSuffix(" °")
        u_shape_layout.addRow("Height (Tilt):", self.height_spinbox_u_shape)
        self.orientation_combo_u_shape = QComboBox(); self.orientation_combo_u_shape.addItems(["Up", "Down", "Left", "Right"])
        u_shape_layout.addRow("Orientation:", self.orientation_combo_u_shape)
        layout.addWidget(self.u_shape_group)

        self.figure_8_group = QGroupBox("Figure 8 Config")
        self.figure_8_group.setStyleSheet("QGroupBox { margin-top: 6px; }")
        figure_8_layout = QFormLayout(self.figure_8_group)
        figure_8_layout.setContentsMargins(6, 8, 6, 6)
        figure_8_layout.setSpacing(7)
        self.speed_spinbox_figure_8 = QDoubleSpinBox(); self.speed_spinbox_figure_8.setRange(0.01, 10.0); self.speed_spinbox_figure_8.setDecimals(2); self.speed_spinbox_figure_8.setSuffix(" Hz")
        figure_8_layout.addRow("Speed:", self.speed_spinbox_figure_8)
        self.width_spinbox_figure_8 = QDoubleSpinBox(); self.width_spinbox_figure_8.setRange(0.1, 360.0); self.width_spinbox_figure_8.setDecimals(1); self.width_spinbox_figure_8.setSuffix(" °")
        figure_8_layout.addRow("Width (Pan):", self.width_spinbox_figure_8)
        self.height_spinbox_figure_8 = QDoubleSpinBox(); self.height_spinbox_figure_8.setRange(0.1, 180.0); self.height_spinbox_figure_8.setDecimals(1); self.height_spinbox_figure_8.setSuffix(" °")
        figure_8_layout.addRow("Height (Tilt):", self.height_spinbox_figure_8)
        layout.addWidget(self.figure_8_group)

        self.bally_group = QGroupBox("Bally (Fan) Config")
        self.bally_group.setStyleSheet("QGroupBox { margin-top: 6px; }")
        bally_layout = QFormLayout(self.bally_group)
        bally_layout.setContentsMargins(6, 8, 6, 6); bally_layout.setSpacing(7)
        self.speed_spinbox_bally = QDoubleSpinBox(); self.speed_spinbox_bally.setRange(0.1, 10.0); self.speed_spinbox_bally.setDecimals(2); self.speed_spinbox_bally.setSuffix(" Hz")
        bally_layout.addRow("Speed:", self.speed_spinbox_bally)
        self.width_spinbox_bally = QDoubleSpinBox(); self.width_spinbox_bally.setRange(0.1, 360.0); self.width_spinbox_bally.setDecimals(1); self.width_spinbox_bally.setSuffix(" °")
        bally_layout.addRow("Width (Pan):", self.width_spinbox_bally)
        layout.addWidget(self.bally_group)

        self.stagger_group = QGroupBox("Stagger (Dimmer) Config")
        self.stagger_group.setStyleSheet("QGroupBox { margin-top: 6px; }")
        stagger_layout = QFormLayout(self.stagger_group)
        stagger_layout.setContentsMargins(6, 8, 6, 6); stagger_layout.setSpacing(7)
        self.rate_spinbox_stagger = QDoubleSpinBox(); self.rate_spinbox_stagger.setRange(0.1, 50.0); self.rate_spinbox_stagger.setDecimals(1); self.rate_spinbox_stagger.setSuffix(" Hz")
        stagger_layout.addRow("Rate:", self.rate_spinbox_stagger)
        layout.addWidget(self.stagger_group)
        
        self.update_specific_config_fields_visibility()
        self._on_wing_style_changed()

    def _on_wing_style_changed(self):
        is_asym = (self.wing_style_combo_sine.currentData() == "asymmetrical_2_wings")
        self.wing_center_percent_label.setVisible(is_asym)
        self.wing_center_percent_spinbox.setVisible(is_asym)

    def _update_sine_wave_spinbox_contexts_for_this_effect(self):
        if self.effect_type_combo.currentData() != "sine_wave": return
        target_param = self.target_param_combo.currentData()
        size_spin, center_spin = self.size_spinbox_sine, self.center_spinbox_sine
        size_spin.blockSignals(True); center_spin.blockSignals(True)
        if target_param == "brightness": size_spin.setRange(0, 100); size_spin.setSuffix(" %"); size_spin.setDecimals(0); center_spin.setRange(0, 100); center_spin.setSuffix(" %"); center_spin.setDecimals(0)
        elif target_param == "zoom": size_spin.setRange(0.1, 85.0); size_spin.setSuffix(" °"); size_spin.setDecimals(1); center_spin.setRange(5.0, 90.0); center_spin.setSuffix(" °"); center_spin.setDecimals(1)
        elif target_param == "focus": size_spin.setRange(0, 100); size_spin.setSuffix(" %"); size_spin.setDecimals(1); center_spin.setRange(0, 100); center_spin.setSuffix(" %"); center_spin.setDecimals(1)
        elif target_param in ["rotation_x", "rotation_y"]: size_spin.setRange(0.1, 180.0); size_spin.setSuffix(" °"); size_spin.setDecimals(1); center_spin.setRange(-180.0, 180.0); center_spin.setSuffix(" °"); center_spin.setDecimals(1)
        else: size_spin.setRange(0.1, 360.0); size_spin.setSuffix(" units"); size_spin.setDecimals(1); center_spin.setRange(-360.0, 360.0); center_spin.setSuffix(" units"); center_spin.setDecimals(1)
        size_spin.setValue(max(size_spin.minimum(), min(size_spin.maximum(), size_spin.value())))
        center_spin.setValue(max(center_spin.minimum(), min(center_spin.maximum(), center_spin.value())))
        size_spin.blockSignals(False); center_spin.blockSignals(False)

    def update_specific_config_fields_visibility(self):
        effect_type = self.effect_type_combo.currentData()
        is_sine = effect_type == "sine_wave"
        is_pan_tilt_shape = effect_type in ["circle", "u_shape", "figure_8", "bally"]
        is_dimmer_shape = effect_type == "stagger"

        # Hide all groups first
        self.sine_wave_group.setVisible(False)
        self.circle_group.setVisible(False)
        self.u_shape_group.setVisible(False)
        self.figure_8_group.setVisible(False)
        self.bally_group.setVisible(False)
        self.stagger_group.setVisible(False)

        # Show the relevant group
        if is_sine: self.sine_wave_group.setVisible(True)
        elif effect_type == "circle": self.circle_group.setVisible(True)
        elif effect_type == "u_shape": self.u_shape_group.setVisible(True)
        elif effect_type == "figure_8": self.figure_8_group.setVisible(True)
        elif effect_type == "bally": self.bally_group.setVisible(True)
        elif is_dimmer_shape: self.stagger_group.setVisible(True)
        
        self.target_param_combo.setEnabled(is_sine)
        self.layout().labelForField(self.target_param_combo).setVisible(is_sine)
        
        if is_sine:
            self._update_sine_wave_spinbox_contexts_for_this_effect()
            self._on_wing_style_changed()

    def load_effect_config(self, effect_config_data: dict | None):
        if not effect_config_data: 
            self.effect_type_combo.setCurrentIndex(0) 
            self.target_param_combo.setCurrentIndex(0) 
            self.speed_spinbox_sine.setValue(0.2); self.size_spinbox_sine.setValue(45.0); self.center_spinbox_sine.setValue(0.0); self.phase_spinbox_sine.setValue(0.0); 
            self.direction_combo_sine.setCurrentText("Forward") 
            self.group_mode_combo_sine.setCurrentIndex(0)
            self.wing_style_combo_sine.setCurrentText("None") 
            self.wing_center_percent_spinbox.setValue(50.0)

            self.speed_spinbox_circle.setValue(0.2); self.radius_pan_spinbox.setValue(45.0); self.radius_tilt_spinbox.setValue(30.0); self.center_pan_spinbox.setValue(0.0); self.center_tilt_spinbox.setValue(0.0); self.phase_spinbox_circle.setValue(0.0); self.group_mode_combo_circle.setCurrentIndex(0)
            
            self.speed_spinbox_u_shape.setValue(0.5); self.width_spinbox_u_shape.setValue(90.0); self.height_spinbox_u_shape.setValue(45.0); self.orientation_combo_u_shape.setCurrentText("Up")
            self.speed_spinbox_figure_8.setValue(0.5); self.width_spinbox_figure_8.setValue(90.0); self.height_spinbox_figure_8.setValue(45.0)
            self.speed_spinbox_bally.setValue(1.0); self.width_spinbox_bally.setValue(90.0)
            self.rate_spinbox_stagger.setValue(10.0)

            self.update_specific_config_fields_visibility()
            if self.effect_type_combo.currentData() == "sine_wave": self._update_sine_wave_spinbox_contexts_for_this_effect()
            return

        effect_type_from_data = effect_config_data.get('effect_type', 'sine_wave')
        idx = self.effect_type_combo.findData(effect_type_from_data); self.effect_type_combo.setCurrentIndex(idx if idx != -1 else 0)
        
        if effect_type_from_data == "sine_wave": 
            idx_param = self.target_param_combo.findData(effect_config_data.get('target_parameter', 'rotation_y'))
            self.target_param_combo.setCurrentIndex(idx_param if idx_param != -1 else 0)
        
        self.update_specific_config_fields_visibility() 
        
        config_params = effect_config_data.get('config', {})
        self.speed_spinbox_sine.setValue(config_params.get('speed_hz', 0.2))
        self.size_spinbox_sine.setValue(config_params.get('size', 45.0))
        self.center_spinbox_sine.setValue(config_params.get('center', 0.0))
        self.phase_spinbox_sine.setValue(config_params.get('phase_degrees', 0.0))
        self.direction_combo_sine.setCurrentText(config_params.get('direction', "Forward")) 
        group_idx_s = self.group_mode_combo_sine.findData(config_params.get('group_mode', "all_same_phase")); self.group_mode_combo_sine.setCurrentIndex(group_idx_s if group_idx_s != -1 else 0)
        wing_style_data = config_params.get('wing_style', "none")
        wing_idx_s = self.wing_style_combo_sine.findData(wing_style_data)
        if wing_idx_s == -1: wing_idx_s = self.wing_style_combo_sine.findText(wing_style_data.replace("_", " ").title(), Qt.MatchFlag.MatchFixedString) # try display name
        self.wing_style_combo_sine.setCurrentIndex(wing_idx_s if wing_idx_s != -1 else 0)
        self.wing_center_percent_spinbox.setValue(config_params.get('wing_center_percent', 50.0))

        self.speed_spinbox_circle.setValue(config_params.get('speed_hz', 0.2)) 
        self.radius_pan_spinbox.setValue(config_params.get('radius_pan', 45.0))
        self.radius_tilt_spinbox.setValue(config_params.get('radius_tilt', 30.0))
        self.center_pan_spinbox.setValue(config_params.get('center_pan', 0.0))
        self.center_tilt_spinbox.setValue(config_params.get('center_tilt', 0.0))
        self.phase_spinbox_circle.setValue(config_params.get('phase_degrees', 0.0)) 
        group_idx_c = self.group_mode_combo_circle.findData(config_params.get('group_mode', "all_same_phase")); self.group_mode_combo_circle.setCurrentIndex(group_idx_c if group_idx_c != -1 else 0)

        self.speed_spinbox_u_shape.setValue(config_params.get('speed_hz', 0.5))
        self.width_spinbox_u_shape.setValue(config_params.get('width', 90.0))
        self.height_spinbox_u_shape.setValue(config_params.get('height', 45.0))
        self.orientation_combo_u_shape.setCurrentText(config_params.get('orientation', 'Up'))

        self.speed_spinbox_figure_8.setValue(config_params.get('speed_hz', 0.5))
        self.width_spinbox_figure_8.setValue(config_params.get('width', 90.0))
        self.height_spinbox_figure_8.setValue(config_params.get('height', 45.0))

        self.speed_spinbox_bally.setValue(config_params.get('speed_hz', 1.0))
        self.width_spinbox_bally.setValue(config_params.get('width', 90.0))

        self.rate_spinbox_stagger.setValue(config_params.get('rate_hz', 10.0))


        if effect_type_from_data == "sine_wave": self._update_sine_wave_spinbox_contexts_for_this_effect()

    def get_effect_config_data(self) -> dict:
        effect_conf = {}
        effect_type = self.effect_type_combo.currentData()
        target_param_val = ""
        
        if effect_type == "sine_wave":
            effect_conf = { 
                "speed_hz": self.speed_spinbox_sine.value(), 
                "size": self.size_spinbox_sine.value(), 
                "center": self.center_spinbox_sine.value(), 
                "phase_degrees": self.phase_spinbox_sine.value(), 
                "direction": self.direction_combo_sine.currentText(), 
                "group_mode": self.group_mode_combo_sine.currentData(),
                "wing_style": self.wing_style_combo_sine.currentData() 
            }
            if self.wing_style_combo_sine.currentData() == "asymmetrical_2_wings":
                effect_conf["wing_center_percent"] = self.wing_center_percent_spinbox.value()
            target_param_val = self.target_param_combo.currentData()
        elif effect_type == "circle":
            effect_conf = { 
                "speed_hz": self.speed_spinbox_circle.value(), 
                "radius_pan": self.radius_pan_spinbox.value(), 
                "radius_tilt": self.radius_tilt_spinbox.value(), 
                "center_pan": self.center_pan_spinbox.value(), 
                "center_tilt": self.center_tilt_spinbox.value(), 
                "phase_degrees": self.phase_spinbox_circle.value(), 
                "group_mode": self.group_mode_combo_circle.currentData()
            }
            target_param_val = "pan_tilt_circle"
        elif effect_type == "u_shape":
            effect_conf = {
                "speed_hz": self.speed_spinbox_u_shape.value(),
                "width": self.width_spinbox_u_shape.value(),
                "height": self.height_spinbox_u_shape.value(),
                "orientation": self.orientation_combo_u_shape.currentText()
            }
            target_param_val = "pan_tilt_u_shape"
        elif effect_type == "figure_8":
            effect_conf = {
                "speed_hz": self.speed_spinbox_figure_8.value(),
                "width": self.width_spinbox_figure_8.value(),
                "height": self.height_spinbox_figure_8.value()
            }
            target_param_val = "pan_tilt_figure_8"
        elif effect_type == "bally":
            effect_conf = {
                "speed_hz": self.speed_spinbox_bally.value(),
                "width": self.width_spinbox_bally.value()
            }
            target_param_val = "pan_tilt_bally"
        elif effect_type == "stagger":
            effect_conf = {
                "rate_hz": self.rate_spinbox_stagger.value()
            }
            target_param_val = "dimmer_stagger"
        
        return {
            "effect_type": effect_type,
            "target_parameter": target_param_val,
            "config": effect_conf
        }


class LoopPaletteEditFormWidget(QWidget): 
    def __init__(self, db_connection, parent=None):
        super().__init__(parent)
        self.db_connection = db_connection
        self.current_palette_id = None 

        main_layout = QVBoxLayout(self) 
        main_layout.setContentsMargins(5,5,5,5) 
        main_layout.setSpacing(10) 

        name_form_layout = QFormLayout()
        name_form_layout.setSpacing(8) 
        self.name_edit = QLineEdit()
        name_form_layout.addRow("Palette Name:", self.name_edit)
        main_layout.addLayout(name_form_layout)

        self.primary_effect_group = QGroupBox("Primary Effect")
        self.primary_effect_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 5px; }")
        primary_effect_layout = QVBoxLayout(self.primary_effect_group)
        primary_effect_layout.setContentsMargins(8,10,8,8) 
        primary_effect_layout.setSpacing(6)
        self.primary_effect_config_widget = LoopPaletteEffectConfigWidget(1, self)
        primary_effect_layout.addWidget(self.primary_effect_config_widget)
        main_layout.addWidget(self.primary_effect_group)

        self.secondary_effect_main_group = QGroupBox("Secondary Effect")
        self.secondary_effect_main_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 5px; }")
        secondary_effect_main_layout = QVBoxLayout(self.secondary_effect_main_group)
        secondary_effect_main_layout.setContentsMargins(8, 6, 8, 8) 
        secondary_effect_main_layout.setSpacing(6)

        self.enable_secondary_effect_checkbox = QCheckBox("Enable Secondary Effect")
        self.enable_secondary_effect_checkbox.setChecked(False)
        self.enable_secondary_effect_checkbox.toggled.connect(self._on_secondary_effect_toggled)
        secondary_effect_main_layout.addWidget(self.enable_secondary_effect_checkbox)
        
        self.secondary_effect_config_widget = LoopPaletteEffectConfigWidget(2, self, is_secondary=True)
        secondary_effect_main_layout.addWidget(self.secondary_effect_config_widget)
        
        main_layout.addWidget(self.secondary_effect_main_group)
        self.secondary_effect_config_widget.setVisible(self.enable_secondary_effect_checkbox.isChecked())
        
        main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))


    def _on_secondary_effect_toggled(self, checked: bool):
        self.secondary_effect_config_widget.setVisible(checked)


    def load_data(self, palette_data: dict | None):
        self.primary_effect_config_widget.load_effect_config(None) 
        self.enable_secondary_effect_checkbox.setChecked(False) 
        self.secondary_effect_config_widget.load_effect_config(None) 

        if palette_data:
            self.current_palette_id = palette_data.get('id')
            self.name_edit.setText(palette_data.get('name', 'New Loop'))
            
            config_json_str = palette_data.get('config_json', '[]') 
            try:
                effect_configs_list = json.loads(config_json_str)
                if not isinstance(effect_configs_list, list): 
                    if isinstance(effect_configs_list, dict): 
                        old_effect_type = palette_data.get('effect_type', 'sine_wave') 
                        old_target_param = palette_data.get('target_parameter', 'rotation_y')
                        effect_configs_list = [{
                            "effect_type": old_effect_type,
                            "target_parameter": old_target_param,
                            "config": effect_configs_list 
                        }]
                    else:
                        effect_configs_list = []
            except json.JSONDecodeError:
                effect_configs_list = [] 
            
            if len(effect_configs_list) > 0:
                self.primary_effect_config_widget.load_effect_config(effect_configs_list[0])
            
            if len(effect_configs_list) > 1:
                self.enable_secondary_effect_checkbox.setChecked(True) 
                self.secondary_effect_config_widget.load_effect_config(effect_configs_list[1])
            else:
                self.enable_secondary_effect_checkbox.setChecked(False)

            self.name_edit.setFocus()
        else: 
            self.current_palette_id = None
            self.name_edit.setText("New Loop")
            self.name_edit.selectAll()
            self.name_edit.setFocus()
        
        self.secondary_effect_config_widget.setVisible(self.enable_secondary_effect_checkbox.isChecked())


    def get_data(self) -> dict | None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Loop Palette name cannot be empty.")
            return None
        
        effects_list_for_json = []
        
        primary_effect_data = self.primary_effect_config_widget.get_effect_config_data()
        if primary_effect_data: 
            effects_list_for_json.append(primary_effect_data)

        if self.enable_secondary_effect_checkbox.isChecked(): 
            secondary_effect_data = self.secondary_effect_config_widget.get_effect_config_data()
            if secondary_effect_data:
                primary_target = primary_effect_data.get("target_parameter", "")
                secondary_target = secondary_effect_data.get("target_parameter", "")

                is_primary_pan_tilt = "pan_tilt" in primary_target
                is_secondary_pan_tilt = "pan_tilt" in secondary_target
                
                # Cannot have two pan/tilt shape effects
                if is_primary_pan_tilt and is_secondary_pan_tilt:
                    QMessageBox.warning(self, "Configuration Error", "Cannot have two Pan/Tilt shape effects in one palette.")
                    return None
                
                # Cannot have Sine on Pan or Tilt if a shape effect is already active
                if is_primary_pan_tilt and secondary_target in ["rotation_x", "rotation_y"]:
                     QMessageBox.warning(self, "Configuration Error", f"Cannot have a Sine wave on '{secondary_target}' when the primary effect is a Pan/Tilt shape.")
                     return None
                
                # Vice-versa
                if is_secondary_pan_tilt and primary_target in ["rotation_x", "rotation_y"]:
                     QMessageBox.warning(self, "Configuration Error", f"Cannot have a Sine wave on '{primary_target}' when the secondary effect is a Pan/Tilt shape.")
                     return None

                # Cannot have two sine waves on the same parameter
                if not is_primary_pan_tilt and not is_secondary_pan_tilt and primary_target == secondary_target:
                    QMessageBox.warning(self, "Configuration Error", "Secondary effect cannot target the same parameter as the primary effect.")
                    return None

                effects_list_for_json.append(secondary_effect_data)
        
        data = {
            "name": name,
            "config_json": json.dumps(effects_list_for_json)
        }
        if self.current_palette_id is not None:
            data['id'] = self.current_palette_id
        return data

class LoopPaletteManagementDialog(QDialog):
    palettes_changed = pyqtSignal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Manage Loop Palettes")
        self.setMinimumSize(750, 600) 

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10) 
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setSpacing(6)
        list_layout.addWidget(QLabel("Saved Loop Palettes:"))
        self.palettes_list_widget = QListWidget()
        self.palettes_list_widget.itemSelectionChanged.connect(self.on_palette_selected_in_list)
        self.palettes_list_widget.setSortingEnabled(True)
        list_layout.addWidget(self.palettes_list_widget)
        
        list_buttons_layout = QHBoxLayout()
        self.add_new_button = QPushButton("Add New")
        self.add_new_button.clicked.connect(self.prepare_new_palette_entry)
        list_buttons_layout.addWidget(self.add_new_button)
        
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setObjectName("DestructiveButton")
        self.delete_button.clicked.connect(self.delete_selected_palette)
        list_buttons_layout.addWidget(self.delete_button)
        list_layout.addLayout(list_buttons_layout)
        
        splitter.addWidget(list_container)

        self.edit_form_widget = LoopPaletteEditFormWidget(self.main_window.db_connection, self)
        splitter.addWidget(self.edit_form_widget)
        
        splitter.setSizes([280, 470]) 
        main_layout.addWidget(splitter)

        self.dialog_buttons = QDialogButtonBox()
        self.save_changes_button = self.dialog_buttons.addButton("Save Changes", QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_changes_button.clicked.connect(self.save_current_palette_changes)
        self.dialog_buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self.dialog_buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.dialog_buttons)
        
        self.load_palettes_into_list()
        if self.palettes_list_widget.count() > 0:
            self.palettes_list_widget.setCurrentRow(0)
        else:
            self.prepare_new_palette_entry() 

    def load_palettes_into_list(self):
        current_id_to_reselect = None
        if self.palettes_list_widget.currentItem():
             current_id_to_reselect = self.palettes_list_widget.currentItem().data(Qt.ItemDataRole.UserRole)
        elif self.edit_form_widget.current_palette_id is not None:
             current_id_to_reselect = self.edit_form_widget.current_palette_id

        self.palettes_list_widget.clear()
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name, config_json FROM loop_palettes ORDER BY name")
            palettes = cursor.fetchall()
            selected_item_to_restore = None
            for p_id, name, cfg_json_str in palettes:
                display_name = name
                try:
                    effect_configs_list = json.loads(cfg_json_str) 
                    if isinstance(effect_configs_list, list) and effect_configs_list:
                        primary_eff_data = effect_configs_list[0]
                        eff_type_disp = primary_eff_data.get('effect_type',"").replace('_',' ').title()
                        tgt_param_disp = primary_eff_data.get('target_parameter',"").replace('_',' ').title()
                        if "pan_tilt" in tgt_param_disp.lower(): tgt_param_disp = "Pan/Tilt"
                        
                        display_name = f"{name} ({eff_type_disp} on {tgt_param_disp}"
                        if len(effect_configs_list) > 1: display_name += " + More"
                        display_name += ")"
                    elif isinstance(effect_configs_list, dict): 
                        display_name = f"{name} [Old Single Effect Format]"
                except Exception as e_disp: 
                    print(f"Error generating display name for palette '{name}': {e_disp}")

                item = QListWidgetItem(display_name)
                item.setData(Qt.ItemDataRole.UserRole, p_id)
                item_data_payload = {"id":p_id, "name":name, "config_json":cfg_json_str}
                
                item.setData(Qt.ItemDataRole.UserRole+1, item_data_payload)
                self.palettes_list_widget.addItem(item)

                if p_id == current_id_to_reselect:
                    selected_item_to_restore = item
            
            if selected_item_to_restore:
                self.palettes_list_widget.setCurrentItem(selected_item_to_restore)
            elif self.palettes_list_widget.count() > 0:
                self.palettes_list_widget.setCurrentRow(0)
            
            self.on_palette_selected_in_list() 

        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Error loading loop palettes into list: {e}")

    def on_palette_selected_in_list(self):
        current_item = self.palettes_list_widget.currentItem()
        if current_item:
            palette_data_for_form = current_item.data(Qt.ItemDataRole.UserRole + 1) 
            self.edit_form_widget.load_data(palette_data_for_form) 

            self.save_changes_button.setText("Save Changes")
            self.save_changes_button.setEnabled(True)
            self.delete_button.setEnabled(True)
        else:
            self.edit_form_widget.load_data(None) 
            self.save_changes_button.setText("Create New")
            self.save_changes_button.setEnabled(True) 
            self.delete_button.setEnabled(False)

    def prepare_new_palette_entry(self):
        self.palettes_list_widget.setCurrentItem(None) 
        self.edit_form_widget.load_data(None) 
        self.save_changes_button.setText("Create")

    def save_current_palette_changes(self):
        data_to_save = self.edit_form_widget.get_data()
        if not data_to_save:
            return

        is_new_entry = self.edit_form_widget.current_palette_id is None

        if is_new_entry: 
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("SELECT id FROM loop_palettes WHERE name = ?", (data_to_save['name'],))
                if cursor.fetchone():
                    QMessageBox.warning(self, "Name Exists", f"A loop palette named '{data_to_save['name']}' already exists.")
                    return
                
                cursor.execute(
                    "INSERT INTO loop_palettes (name, config_json) VALUES (?, ?)",
                    (data_to_save['name'], data_to_save['config_json'])
                )
                new_id = cursor.lastrowid
                self.main_window.db_connection.commit()
                self.edit_form_widget.current_palette_id = new_id 
                QMessageBox.information(self, "Success", "Loop Palette created.")
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Could not create loop palette: {e}")
                return
        else: 
            original_id = self.edit_form_widget.current_palette_id
            original_name_from_list_item_data = "" 
            current_list_item = self.palettes_list_widget.currentItem()
            if current_list_item: 
                 original_name_from_list_item_data = current_list_item.data(Qt.ItemDataRole.UserRole + 1)['name']
            
            if data_to_save['name'] != original_name_from_list_item_data: 
                try:
                    cursor = self.main_window.db_connection.cursor()
                    cursor.execute("SELECT id FROM loop_palettes WHERE name = ? AND id != ?", (data_to_save['name'], original_id))
                    if cursor.fetchone():
                        QMessageBox.warning(self, "Name Exists", f"Another loop palette named '{data_to_save['name']}' already exists.")
                        return
                except Exception as e:
                    QMessageBox.critical(self, "DB Error", f"Error checking name uniqueness on update: {e}")
                    return
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute(
                    """UPDATE loop_palettes SET name = ?, config_json = ?
                       WHERE id = ?""",
                    (data_to_save['name'], data_to_save['config_json'], original_id)
                )
                self.main_window.db_connection.commit()
                QMessageBox.information(self, "Success", "Loop Palette updated.")
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Could not update loop palette: {e}")
                return
        
        self.load_palettes_into_list() 
        self.palettes_changed.emit()

    def delete_selected_palette(self):
        current_item = self.palettes_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Selection Error", "Please select a loop palette to delete.")
            return

        palette_id = current_item.data(Qt.ItemDataRole.UserRole)
        palette_name = current_item.data(Qt.ItemDataRole.UserRole + 1)['name']
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                     f"Are you sure you want to delete loop palette '{palette_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("DELETE FROM loop_palettes WHERE id = ?", (palette_id,))
                self.main_window.db_connection.commit()
                self.load_palettes_into_list()
                if self.palettes_list_widget.count() == 0:
                    self.prepare_new_palette_entry()
                QMessageBox.information(self, "Deleted", f"Loop Palette '{palette_name}' deleted.")
                self.palettes_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Error deleting loop palette: {e}")

class LoopPalettesTab(QWidget):
    loop_palettes_changed = pyqtSignal() 

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10,10,10,10)
        
        manage_button = QPushButton("Manage Loop Palettes...")
        manage_button.clicked.connect(self.show_manage_dialog)
        manage_button.setFixedHeight(40)
        manage_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(manage_button)
        
        main_layout.addStretch() 
        self.setLayout(main_layout)

    def show_manage_dialog(self):
        dialog = LoopPaletteManagementDialog(self.main_window, self)
        dialog.palettes_changed.connect(self.loop_palettes_changed.emit)
        dialog.exec()