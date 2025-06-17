# tabs/loop_palettes_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDoubleSpinBox, QDialogButtonBox, QSplitter, QGroupBox,
    QSizePolicy, QCheckBox, QSpacerItem, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
import json
import sqlite3

class LoopPaletteEffectConfigWidget(QWidget):
    """ A widget to configure a single effect within a loop palette. """
    effect_type_changed = pyqtSignal(str)

    # Centralized schema for all effect types. This makes adding new effects much easier.
    EFFECT_SCHEMAS = {
        "sine_wave": {
            "label": "Sine Wave",
            "targets": ["rotation_y", "rotation_x", "brightness", "zoom", "focus"],
            "params": [
                {'key': 'speed_hz', 'label': 'Speed', 'widget': QDoubleSpinBox, 'props': {'range': (0.01, 10.0), 'decimals': 2, 'suffix': ' Hz'}, 'default': 0.2},
                {'key': 'size', 'label': 'Size', 'widget': QDoubleSpinBox, 'props': {'range': (0.1, 360.0), 'decimals': 1, 'suffix': ' units'}, 'default': 45.0},
                {'key': 'center', 'label': 'Center', 'widget': QDoubleSpinBox, 'props': {'range': (-360.0, 360.0), 'decimals': 1, 'suffix': ' units'}, 'default': 0.0},
                {'key': 'phase_degrees', 'label': 'Phase Offset', 'widget': QDoubleSpinBox, 'props': {'range': (0, 359.9), 'decimals': 1, 'suffix': ' °'}, 'default': 0.0},
                {'key': 'direction', 'label': 'Direction', 'widget': QComboBox, 'props': {'items': ["Forward", "Backward"]}, 'default': "Forward"},
                {'key': 'group_mode', 'label': 'Group Mode', 'widget': QComboBox, 'props': {'items': {"All Same Phase": "all_same_phase", "Spread Phase Evenly": "spread_phase", "Block - Groups of 2": "block_2", "Block - Groups of 3": "block_3", "Block - Groups of 4": "block_4"}}, 'default': "all_same_phase"},
                {'key': 'wing_style', 'label': 'Wing Style', 'widget': QComboBox, 'props': {'items': {"None": "none", "Symmetrical 2 Wings": "symmetrical_2_wings", "Symmetrical 3 Wings": "symmetrical_3_wings", "Asymmetrical 2 Wings": "asymmetrical_2_wings"}}, 'default': "none"},
                {'key': 'wing_center_percent', 'label': 'Wing Center', 'widget': QDoubleSpinBox, 'props': {'range': (0.0, 100.0), 'decimals': 1, 'suffix': ' %'}, 'default': 50.0, 'condition': lambda cfg: cfg.get('wing_style') == 'asymmetrical_2_wings'},
            ]
        },
        "circle": {
            "label": "Circle (Pan/Tilt)",
            "implicit_target": "pan_tilt_shape",
            "params": [
                {'key': 'speed_hz', 'label': 'Speed', 'widget': QDoubleSpinBox, 'props': {'range': (0.01, 10.0), 'decimals': 2, 'suffix': ' Hz'}, 'default': 0.2},
                {'key': 'radius_pan', 'label': 'Pan Radius', 'widget': QDoubleSpinBox, 'props': {'range': (0.0, 180.0), 'decimals': 1, 'suffix': ' °'}, 'default': 45.0},
                {'key': 'radius_tilt', 'label': 'Tilt Radius', 'widget': QDoubleSpinBox, 'props': {'range': (0.0, 180.0), 'decimals': 1, 'suffix': ' °'}, 'default': 30.0},
                {'key': 'center_pan', 'label': 'Pan Center', 'widget': QDoubleSpinBox, 'props': {'range': (-180.0, 180.0), 'decimals': 1, 'suffix': ' °'}, 'default': 0.0},
                {'key': 'center_tilt', 'label': 'Tilt Center', 'widget': QDoubleSpinBox, 'props': {'range': (-180.0, 180.0), 'decimals': 1, 'suffix': ' °'}, 'default': 0.0},
                {'key': 'phase_degrees', 'label': 'Start Phase', 'widget': QDoubleSpinBox, 'props': {'range': (0, 359.9), 'decimals': 1, 'suffix': ' °'}, 'default': 0.0},
                {'key': 'group_mode', 'label': 'Group Mode', 'widget': QComboBox, 'props': {'items': {"All Same Phase": "all_same_phase", "Spread Phase Evenly": "spread_phase"}}, 'default': "all_same_phase"},
            ]
        },
        "u_shape": {"label": "U-Shape (Pan/Tilt)", "implicit_target": "pan_tilt_shape", "params": [
                {'key': 'speed_hz', 'label': 'Speed', 'widget': QDoubleSpinBox, 'props': {'range': (0.01, 10.0), 'decimals': 2, 'suffix': ' Hz'}, 'default': 0.5},
                {'key': 'width', 'label': 'Width (Pan)', 'widget': QDoubleSpinBox, 'props': {'range': (0.1, 360.0), 'decimals': 1, 'suffix': ' °'}, 'default': 90.0},
                {'key': 'height', 'label': 'Height (Tilt)', 'widget': QDoubleSpinBox, 'props': {'range': (0.1, 180.0), 'decimals': 1, 'suffix': ' °'}, 'default': 45.0},
                {'key': 'orientation', 'label': 'Orientation', 'widget': QComboBox, 'props': {'items': ["Up", "Down", "Left", "Right"]}, 'default': "Up"},
        ]},
        "figure_8": {"label": "Figure 8 (Pan/Tilt)", "implicit_target": "pan_tilt_shape", "params": [
                {'key': 'speed_hz', 'label': 'Speed', 'widget': QDoubleSpinBox, 'props': {'range': (0.01, 10.0), 'decimals': 2, 'suffix': ' Hz'}, 'default': 0.5},
                {'key': 'width', 'label': 'Width (Pan)', 'widget': QDoubleSpinBox, 'props': {'range': (0.1, 360.0), 'decimals': 1, 'suffix': ' °'}, 'default': 90.0},
                {'key': 'height', 'label': 'Height (Tilt)', 'widget': QDoubleSpinBox, 'props': {'range': (0.1, 180.0), 'decimals': 1, 'suffix': ' °'}, 'default': 45.0},
        ]},
        "bally": {"label": "Bally (Fan)", "implicit_target": "pan_tilt_shape", "params": [
                {'key': 'speed_hz', 'label': 'Speed', 'widget': QDoubleSpinBox, 'props': {'range': (0.1, 10.0), 'decimals': 2, 'suffix': ' Hz'}, 'default': 1.0},
                {'key': 'width', 'label': 'Width (Pan)', 'widget': QDoubleSpinBox, 'props': {'range': (0.1, 360.0), 'decimals': 1, 'suffix': ' °'}, 'default': 90.0},
        ]},
        "stagger": {"label": "Stagger (Dimmer Flicker)", "implicit_target": "dimmer_stagger", "params": [
                {'key': 'rate_hz', 'label': 'Rate', 'widget': QDoubleSpinBox, 'props': {'range': (0.1, 50.0), 'decimals': 1, 'suffix': ' Hz'}, 'default': 10.0},
        ]},
    }

    def __init__(self, parent_form: 'LoopPaletteEditFormWidget'):
        super().__init__(parent_form)
        self.parent_form = parent_form
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)

        # Static part of the form
        self.static_form_layout = QFormLayout()
        self.static_form_layout.setContentsMargins(5, 5, 5, 5)
        self.static_form_layout.setSpacing(8)

        self.effect_type_combo = QComboBox()
        for key, schema in self.EFFECT_SCHEMAS.items():
            self.effect_type_combo.addItem(schema['label'], key)
        self.effect_type_combo.currentIndexChanged.connect(self._rebuild_form_for_effect_type)
        self.static_form_layout.addRow("Effect Type:", self.effect_type_combo)

        self.main_layout.addLayout(self.static_form_layout)

        # Dynamic part will be in a groupbox
        self.dynamic_options_group = QGroupBox("Configuration")
        self.dynamic_options_group.setStyleSheet("QGroupBox { margin-top: 6px; }")
        self.dynamic_form_layout = QFormLayout(self.dynamic_options_group)
        self.dynamic_form_layout.setContentsMargins(6, 8, 6, 6)
        self.dynamic_form_layout.setSpacing(7)
        self.main_layout.addWidget(self.dynamic_options_group)

        self.dynamic_widgets = {} # To hold dynamically created widgets

        self._rebuild_form_for_effect_type()
    
    def get_current_effect_type(self) -> str:
        return self.effect_type_combo.currentData()

    def get_current_target_parameter(self) -> str | None:
        """Returns the target parameter, either implicit or from the combo."""
        effect_key = self.get_current_effect_type()
        schema = self.EFFECT_SCHEMAS.get(effect_key, {})
        
        if schema.get("implicit_target"):
            return schema["implicit_target"]
        
        target_combo = self.dynamic_widgets.get('target_parameter')
        if isinstance(target_combo, QComboBox):
            return target_combo.currentData()
        
        return None

    def _clear_dynamic_form(self):
        self.dynamic_widgets.clear()
        while self.dynamic_form_layout.count():
            item = self.dynamic_form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout(): # Clear sub-layouts if any
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def _rebuild_form_for_effect_type(self):
        self._clear_dynamic_form()
        
        effect_key = self.effect_type_combo.currentData()
        schema = self.EFFECT_SCHEMAS.get(effect_key, {})
        
        params = schema.get('params', [])
        
        # Add target parameter combo if applicable
        if "targets" in schema:
            target_combo = QComboBox()
            param_map = {"rotation_y": "Pan", "rotation_x": "Tilt", "brightness": "Dimmer", "zoom": "Zoom", "focus": "Focus"}
            for key in schema["targets"]:
                target_combo.addItem(param_map.get(key, key.capitalize()), key)
            self.dynamic_widgets['target_parameter'] = target_combo
            self.dynamic_form_layout.addRow("Target Parameter:", target_combo)
            target_combo.currentTextChanged.connect(self._update_sine_wave_spinbox_contexts)

        # Add other dynamic parameters
        for param_def in params:
            widget_class = param_def['widget']
            widget_instance = widget_class()
            props = param_def.get('props', {})
            
            # Apply properties
            if 'range' in props: widget_instance.setRange(*props['range'])
            if 'decimals' in props: widget_instance.setDecimals(props['decimals'])
            if 'suffix' in props: widget_instance.setSuffix(props['suffix'])
            if 'items' in props:
                if isinstance(props['items'], dict):
                    for text, data in props['items'].items():
                        widget_instance.addItem(text, data)
                else:
                    widget_instance.addItems(props['items'])
            
            # Special handling for conditional visibility
            if 'condition' in param_def:
                # Need to find the widget this one depends on
                dependent_on_key = 'wing_style' # Hardcoded for now, could be generalized
                master_widget = self.dynamic_widgets.get(dependent_on_key)
                if master_widget:
                    def update_visibility(index, cond=param_def['condition'], slave=widget_instance):
                        cfg = {dependent_on_key: master_widget.currentData()}
                        slave.setVisible(cond(cfg))
                        self.dynamic_form_layout.labelForField(slave).setVisible(cond(cfg))
                    master_widget.currentIndexChanged.connect(update_visibility)

            self.dynamic_widgets[param_def['key']] = widget_instance
            self.dynamic_form_layout.addRow(param_def['label'] + ":", widget_instance)
        
        self.effect_type_changed.emit(effect_key)
        self._update_sine_wave_spinbox_contexts() # Initial context update
        self._update_conditional_visbility()

    def _update_conditional_visbility(self):
        """Manually trigger visibility checks after form rebuild."""
        schema = self.EFFECT_SCHEMAS.get(self.get_current_effect_type(), {})
        params = schema.get('params', [])
        current_config = self.get_config_from_form()
        
        for param_def in params:
            if 'condition' in param_def:
                widget = self.dynamic_widgets.get(param_def['key'])
                if widget:
                    is_visible = param_def['condition'](current_config)
                    widget.setVisible(is_visible)
                    self.dynamic_form_layout.labelForField(widget).setVisible(is_visible)


    def _update_sine_wave_spinbox_contexts(self):
        """Adjusts ranges/suffixes for sine wave size/center based on target."""
        if self.get_current_effect_type() != 'sine_wave':
            return
            
        target_param_combo = self.dynamic_widgets.get('target_parameter')
        size_spin = self.dynamic_widgets.get('size')
        center_spin = self.dynamic_widgets.get('center')
        if not target_param_combo or not size_spin or not center_spin:
            return

        target_param = target_param_combo.currentData()
        
        # Define contexts
        contexts = {
            "brightness": {'range': (0, 100), 'suffix': ' %', 'decimals': 0},
            "zoom": {'range': (0.1, 85.0), 'suffix': ' °', 'decimals': 1},
            "focus": {'range': (0, 100), 'suffix': ' %', 'decimals': 1},
            "rotation_x": {'range': (0.1, 180.0), 'suffix': ' °', 'decimals': 1},
            "rotation_y": {'range': (0.1, 180.0), 'suffix': ' °', 'decimals': 1},
        }
        center_contexts = {
             "rotation_x": {'range': (-180.0, 180.0), 'suffix': ' °', 'decimals': 1},
             "rotation_y": {'range': (-180.0, 180.0), 'suffix': ' °', 'decimals': 1},
        }
        
        context = contexts.get(target_param, {'range': (0.1, 360.0), 'suffix': ' units', 'decimals': 1})
        center_context = center_contexts.get(target_param, context) # Default to size context for center

        # Apply to Size spinbox
        size_spin.blockSignals(True)
        size_spin.setRange(*context['range'])
        size_spin.setSuffix(context['suffix'])
        size_spin.setDecimals(context['decimals'])
        size_spin.setValue(max(size_spin.minimum(), min(size_spin.maximum(), size_spin.value())))
        size_spin.blockSignals(False)

        # Apply to Center spinbox
        center_spin.blockSignals(True)
        center_spin.setRange(*center_context['range'])
        center_spin.setSuffix(center_context['suffix'])
        center_spin.setDecimals(center_context['decimals'])
        center_spin.setValue(max(center_spin.minimum(), min(center_spin.maximum(), center_spin.value())))
        center_spin.blockSignals(False)

    def load_effect_config(self, effect_config: dict | None):
        if not effect_config:
            effect_config = {}

        effect_key = effect_config.get('effect_type', self.effect_type_combo.currentData())
        idx = self.effect_type_combo.findData(effect_key)
        self.effect_type_combo.setCurrentIndex(idx if idx != -1 else 0)
        
        # Ensure form is built for this effect type
        if self.get_current_effect_type() != effect_key:
             # This will trigger a rebuild if necessary
             self.effect_type_combo.setCurrentIndex(idx if idx != -1 else 0)
        
        schema = self.EFFECT_SCHEMAS.get(effect_key, {})
        config_data = effect_config.get('config', {})

        # Load target parameter
        target_param_combo = self.dynamic_widgets.get('target_parameter')
        if isinstance(target_param_combo, QComboBox):
            target_val = effect_config.get('target_parameter')
            if target_val:
                idx = target_param_combo.findData(target_val)
                if idx != -1: target_param_combo.setCurrentIndex(idx)

        # Load dynamic params
        for param_def in schema.get('params', []):
            key = param_def['key']
            widget = self.dynamic_widgets.get(key)
            if not widget: continue
            
            value = config_data.get(key, param_def.get('default'))
            if value is None: continue

            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value)
            elif isinstance(widget, QComboBox):
                idx = widget.findData(value)
                if idx == -1: idx = widget.findText(value) # Fallback to text match
                if idx != -1: widget.setCurrentIndex(idx)
        
        self._update_sine_wave_spinbox_contexts()
        self._update_conditional_visbility()

    def get_config_from_form(self) -> dict:
        """Helper to get current config values from the dynamic form."""
        config = {}
        for key, widget in self.dynamic_widgets.items():
            if not widget.isVisible(): continue
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                config[key] = widget.value()
            elif isinstance(widget, QComboBox):
                if widget.currentData() is not None:
                    config[key] = widget.currentData()
                else:
                    config[key] = widget.currentText()
        return config

    def get_effect_config_data(self) -> dict:
        effect_key = self.get_current_effect_type()
        
        return {
            "effect_type": effect_key,
            "target_parameter": self.get_current_target_parameter(),
            "config": self.get_config_from_form()
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
        self.primary_effect_config_widget = LoopPaletteEffectConfigWidget(self)
        self.primary_effect_config_widget.effect_type_changed.connect(self._update_secondary_effect_options)
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
        
        self.secondary_effect_config_widget = LoopPaletteEffectConfigWidget(self)
        secondary_effect_main_layout.addWidget(self.secondary_effect_config_widget)
        
        main_layout.addWidget(self.secondary_effect_main_group)
        
        main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        self._on_secondary_effect_toggled(False) # Initial state
        self._update_secondary_effect_options()

    def _update_secondary_effect_options(self):
        primary_target = self.primary_effect_config_widget.get_current_target_parameter()
        is_primary_pan_tilt_shape = "pan_tilt_shape" in str(primary_target)
        
        sec_combo = self.secondary_effect_config_widget.effect_type_combo
        sec_combo.blockSignals(True)
        for i in range(sec_combo.count()):
            effect_key = sec_combo.itemData(i)
            schema = LoopPaletteEffectConfigWidget.EFFECT_SCHEMAS.get(effect_key, {})
            is_secondary_pan_tilt_shape = "pan_tilt_shape" in str(schema.get("implicit_target"))
            
            # Disable secondary P/T shapes if primary is already a P/T shape
            is_disabled = is_primary_pan_tilt_shape and is_secondary_pan_tilt_shape
            
            item = sec_combo.model().item(i)
            if item:
                flags = item.flags()
                if is_disabled:
                    flags &= ~Qt.ItemFlag.ItemIsEnabled
                else:
                    flags |= Qt.ItemFlag.ItemIsEnabled
                item.setFlags(flags)

        # If current secondary selection is now disabled, reset it
        if not sec_combo.model().item(sec_combo.currentIndex()).isEnabled():
            sec_combo.setCurrentIndex(0)
            
        sec_combo.blockSignals(False)


    def _on_secondary_effect_toggled(self, checked: bool):
        self.secondary_effect_config_widget.setVisible(checked)

    def load_data(self, palette_data: dict | None):
        if palette_data:
            self.current_palette_id = palette_data.get('id')
            self.name_edit.setText(palette_data.get('name', 'New Loop'))
            
            config_json_str = palette_data.get('config_json', '[]') 
            try:
                effect_configs_list = json.loads(config_json_str)
            except json.JSONDecodeError:
                effect_configs_list = []

            # Load primary effect
            if len(effect_configs_list) > 0 and isinstance(effect_configs_list[0], dict):
                self.primary_effect_config_widget.load_effect_config(effect_configs_list[0])
            else:
                self.primary_effect_config_widget.load_effect_config(None)

            # Load secondary effect
            if len(effect_configs_list) > 1 and isinstance(effect_configs_list[1], dict):
                self.enable_secondary_effect_checkbox.setChecked(True)
                self.secondary_effect_config_widget.load_effect_config(effect_configs_list[1])
            else:
                self.enable_secondary_effect_checkbox.setChecked(False)
                self.secondary_effect_config_widget.load_effect_config(None)

            self.name_edit.setFocus()
            self.setEnabled(True)
        else: 
            self.current_palette_id = None
            self.name_edit.setText("New Loop")
            self.primary_effect_config_widget.load_effect_config(None)
            self.enable_secondary_effect_checkbox.setChecked(False)
            self.secondary_effect_config_widget.load_effect_config(None)
            self.name_edit.selectAll()
            self.name_edit.setFocus()
            self.setEnabled(False)
        
        self._on_secondary_effect_toggled(self.enable_secondary_effect_checkbox.isChecked())

    def get_data(self) -> dict | None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Loop Palette name cannot be empty.")
            return None
        
        effects_list_for_json = []
        
        primary_effect_data = self.primary_effect_config_widget.get_effect_config_data()
        effects_list_for_json.append(primary_effect_data)

        if self.enable_secondary_effect_checkbox.isChecked(): 
            secondary_effect_data = self.secondary_effect_config_widget.get_effect_config_data()
            
            primary_target = primary_effect_data.get("target_parameter")
            secondary_target = secondary_effect_data.get("target_parameter")

            if primary_target and secondary_target and primary_target == secondary_target:
                QMessageBox.warning(self, "Configuration Error", "Secondary effect cannot target the same parameter as the primary effect.")
                return None

            effects_list_for_json.append(secondary_effect_data)
        
        data = {"name": name, "config_json": json.dumps(effects_list_for_json)}
        if self.current_palette_id is not None:
            data['id'] = self.current_palette_id
        return data

class LoopPalettesTab(QWidget):
    loop_palettes_changed = pyqtSignal() 

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()
        self.load_palettes_into_list()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        controls_layout = QHBoxLayout()
        self.add_new_button = QPushButton("Add New")
        self.add_new_button.clicked.connect(self.prepare_new_palette_entry)
        controls_layout.addWidget(self.add_new_button)
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setObjectName("DestructiveButton")
        self.delete_button.clicked.connect(self.delete_selected_palette)
        controls_layout.addWidget(self.delete_button)
        self.save_button = QPushButton("Save Changes")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save_current_palette_changes)
        controls_layout.addWidget(self.save_button)
        controls_layout.addStretch()
        main_layout.addLayout(controls_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.addWidget(QLabel("Saved Loop Palettes:"))
        self.palettes_list_widget = QListWidget()
        self.palettes_list_widget.itemSelectionChanged.connect(self.on_palette_selected_in_list)
        self.palettes_list_widget.setSortingEnabled(True)
        list_layout.addWidget(self.palettes_list_widget)
        splitter.addWidget(list_container)

        self.edit_form_widget = LoopPaletteEditFormWidget(self.main_window.db_connection, self)
        splitter.addWidget(self.edit_form_widget)

        splitter.setSizes([280, 470])
        main_layout.addWidget(splitter)
        
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
                        effect_key = primary_eff_data.get("effect_type", "unknown")
                        schema = LoopPaletteEffectConfigWidget.EFFECT_SCHEMAS.get(effect_key, {})
                        eff_type_disp = schema.get("label", effect_key.replace('_',' ').title())

                        display_name = f"{name} ({eff_type_disp}"
                        if len(effect_configs_list) > 1: display_name += " + More"
                        display_name += ")"
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
            else:
                self.on_palette_selected_in_list()
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Error loading loop palettes into list: {e}")

    def on_palette_selected_in_list(self):
        current_item = self.palettes_list_widget.currentItem()
        if current_item:
            palette_data_for_form = current_item.data(Qt.ItemDataRole.UserRole + 1) 
            self.edit_form_widget.load_data(palette_data_for_form)
            self.save_button.setText("Save Changes")
        else:
            self.edit_form_widget.load_data(None) 
            self.save_button.setText("Save Changes")

    def prepare_new_palette_entry(self):
        self.palettes_list_widget.clearSelection()
        self.edit_form_widget.load_data(None)
        self.edit_form_widget.setEnabled(True)
        self.save_button.setText("Create New Palette")

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
        self.loop_palettes_changed.emit()

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
                self.loop_palettes_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Error deleting loop palette: {e}")
