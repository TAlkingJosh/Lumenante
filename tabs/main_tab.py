# tabs/main_tab.py
import json
import uuid
import math
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QFrame,
                             QHBoxLayout, QComboBox, QMessageBox, QDialog,
                             QDialogButtonBox, QSlider, QColorDialog, QListWidget,
                             QListWidgetItem, QApplication, QSpinBox, QDoubleSpinBox,
                             QLineEdit, QGridLayout, QSizePolicy, QGroupBox,
                             QFormLayout, QCheckBox, QAbstractItemView, QMenu,
                             QSpacerItem, QSplitter, QStyleOptionGroupBox, QStyle)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QPointF, QRect, QRectF, QSize, QItemSelectionModel, QItemSelection, QTimer, QTime
from PyQt6.QtGui import (QColor, QPainter, QPainterPath, QPalette, QPen,
                         QBrush, QMouseEvent, QPaintEvent, QFontMetrics, QIcon, QFont, QAction, QWheelEvent)

# IMPORT FROM THE WIDGETS PACKAGE
from widgets import (FixtureControlWidget, CustomColorWheelWidget, GradientEditorWidget,
                     LayoutOverviewWidget, EmbeddedStageViewWidget, EmbeddedTimelineWidget,
                     ProgrammerViewWidget, CueListWidget)


import sqlite3

# Import for type hinting
from typing import TYPE_CHECKING, List, Dict, Tuple, Any, Optional, Callable

if TYPE_CHECKING:
    from ..lumenante_main import Lumenante

class SelectFixtureDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window=main_window
        self.setWindowTitle("Select Fixture")
        self.setMinimumSize(300,400)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel("Select a fixture:"))
        self.fixture_list_widget=QListWidget()
        self.populate_fixtures()
        layout.addWidget(self.fixture_list_widget)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.selected_fixture_id=None
        self.selected_fixture_name=None

    def populate_fixtures(self):
        self.fixture_list_widget.clear()
        try:
            if not self.main_window or not self.main_window.db_connection:
                self.fixture_list_widget.addItem("DB not connected.")
                self.fixture_list_widget.setEnabled(False)
                return
            cursor=self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name, fid, sfi FROM fixtures ORDER BY fid, sfi")
            fixtures=cursor.fetchall()
            if not fixtures:
                self.fixture_list_widget.addItem("No fixtures.")
                self.fixture_list_widget.setEnabled(False)
            else:
                for pk_id, name, fid, sfi in fixtures:
                    item=QListWidgetItem(f"{name} ({fid}.{sfi})")
                    item.setData(Qt.ItemDataRole.UserRole, pk_id)
                    item.setData(Qt.ItemDataRole.DisplayRole+1, name)
                    self.fixture_list_widget.addItem(item)
                self.fixture_list_widget.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self,"DB Error",f"Load fixtures fail: {e}")

    def accept_selection(self):
        item=self.fixture_list_widget.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole) is not None:
            self.selected_fixture_id=item.data(Qt.ItemDataRole.UserRole)
            self.selected_fixture_name=item.data(Qt.ItemDataRole.DisplayRole+1)
            self.accept()
        else:
            QMessageBox.warning(self,"No Selection","Please select a fixture.")

    def get_selected_fixture(self):
        return self.selected_fixture_id, self.selected_fixture_name

class SelectLoopsDialog(QDialog):
    def __init__(self, main_window, pre_selected_configs, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Select Loop Palettes for Area")
        self.setMinimumSize(400, 500)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Select one or more Loop Palettes to display in this area:"))
        self.loop_list_widget = QListWidget()
        self.loop_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.populate_loops(pre_selected_configs)
        layout.addWidget(self.loop_list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_loops(self, pre_selected_configs: List[Dict]):
        self.loop_list_widget.clear()
        pre_selected_ids = {conf.get('id') for conf in pre_selected_configs if conf.get('id') is not None}
        
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name, config_json FROM loop_palettes ORDER BY name")
            all_loops = cursor.fetchall()

            if not all_loops:
                self.loop_list_widget.addItem("No loop palettes created yet.")
                self.loop_list_widget.setEnabled(False)
            else:
                for db_id, name, config_json in all_loops:
                    item = QListWidgetItem(f"{name} (ID: {db_id})")
                    item.setData(Qt.ItemDataRole.UserRole, (db_id, name, config_json))
                    self.loop_list_widget.addItem(item)
                    if db_id in pre_selected_ids:
                        item.setSelected(True)
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Failed to load loop palettes: {e}")

    def get_selected_loop_configs(self) -> List[Dict]:
        selected_configs = []
        for item in self.loop_list_widget.selectedItems():
            db_id, name, config_json_str = item.data(Qt.ItemDataRole.UserRole)
            selected_configs.append({
                "id": db_id,
                "name": name,
                "display_text": name[:10], # Default display text
                "config_json": config_json_str
            })
        return selected_configs

class GridFunctionSliderDialog(QDialog):
    value_changed = pyqtSignal(int)
    def __init__(self, title, initial_value=50, min_val=0, max_val=100, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)
        layout=QVBoxLayout(self)
        self.slider_label=QLabel(f"Value: {initial_value}")
        layout.addWidget(self.slider_label)
        self.slider=QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(min_val,max_val)
        self.slider.setValue(initial_value)
        self.slider.valueChanged.connect(lambda v:self.slider_label.setText(f"Value: {v}"))
        self.slider.valueChanged.connect(self.value_changed)
        layout.addWidget(self.slider)
        self.button_box=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)
        layout.addWidget(self.button_box)

    def get_value(self):
        return self.slider.value()

class NamePromptDialog(QDialog):
    def __init__(self, title="Enter Name", current_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.layout = QVBoxLayout(self)
        self.label = QLabel(f"Enter a name for this item:")
        self.name_edit = QLineEdit(current_name)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.name_edit)
        self.layout.addWidget(self.buttons)
        
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def get_name(self):
        return self.name_edit.text().strip()

class ColorPalettePreview(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Sunken)    
        self.setMinimumSize(40, 40)
        self.setAutoFillBackground(True)
        self._color = QColor("transparent")
        self._text_label = QLabel("", self)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setStyleSheet("background-color: transparent; color: #888; font-size: 7pt;")
        
        preview_layout = QVBoxLayout(self)
        preview_layout.setContentsMargins(0,0,0,0)
        preview_layout.addWidget(self._text_label)
        self.setLayout(preview_layout)

        self.update_preview_content(QColor("transparent"), "Color")

    def update_preview_content(self, color_or_none: QColor | None, palette_kind: str):
        palette_style = self.palette()
        if palette_kind == "Color":
            self._text_label.setText("")
            self._text_label.setVisible(False)
            current_color = color_or_none if color_or_none else QColor("transparent")
            if self._color != current_color:
                self._color = QColor(current_color)
            palette_style.setColor(QPalette.ColorRole.Window, self._color)
        elif palette_kind == "Position":
            self._text_label.setText("POS")
            self._text_label.setVisible(True)
            palette_style.setColor(QPalette.ColorRole.Window, QColor("transparent"))
        else:
            self._text_label.setText("N/A")
            self._text_label.setVisible(True)
            palette_style.setColor(QPalette.ColorRole.Window, QColor("transparent"))
        
        self.setPalette(palette_style)
        self.update()

    def getColor(self) -> QColor:
        return self._color

class ClockWidget(QWidget):
    """
    A widget that displays the current time, styled to match other layout widgets.
    This version manually paints its border and title to ensure consistency.
    """
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ClockWidgetArea")
        self.setMinimumSize(120, 60)
        self.setAutoFillBackground(True) # Important for the QSS to work
        self.setStyleSheet("background-color: transparent;")
        
        self._show_24_hour = True
        self._show_milliseconds = False
        self._format_string = "HH:mm:ss"
        self._title = "Clock"

        # The actual time label is a child of this widget
        self.time_label = QLabel("00:00:00", self)
        self.time_label.setObjectName("ClockWidgetLabel")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("background-color: #202020; border-radius: 4px; font-weight: bold;")
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_time)
        self._update_timer_interval()

    def setConfig(self, show_24_hour: bool, show_milliseconds: bool):
        """Sets the display configuration for the clock."""
        self._show_24_hour = show_24_hour
        self._show_milliseconds = show_milliseconds
        self._build_format_string()
        self._update_timer_interval()
        self._update_time() # Update immediately
        self.update() # Trigger repaint for potential text length change

    def _build_format_string(self):
        """Constructs the time format string based on current settings."""
        parts = []
        if self._show_24_hour:
            parts.append("HH:mm:ss")
        else:
            parts.append("h:mm:ss")
        
        if self._show_milliseconds:
            parts.append(".zzz")
        
        if not self._show_24_hour:
            parts.append(" AP")
            
        self._format_string = "".join(parts)

    def _update_timer_interval(self):
        """Adjusts the timer's update interval based on millisecond display."""
        if self.timer.isActive():
            self.timer.stop()
        interval = 50 if self._show_milliseconds else 1000
        self.timer.start(interval)

    def _update_time(self):
        """Updates the time label with the current time and format."""
        current_time = QTime.currentTime()
        self.time_label.setText(current_time.toString(self._format_string))
        self._adjust_font_size() # Adjust font size every time text is set
        
    def paintEvent(self, event: QPaintEvent):
        """Manually paint the widget to look like a QGroupBox."""
        super().paintEvent(event)
        painter = QPainter(self)
        
        # Use QStyle to draw a group box frame and label consistent with the current theme
        opt = QStyleOptionGroupBox()
        opt.initFrom(self)
        opt.text = self._title
        opt.subControls = (QStyle.SubControl.SC_GroupBoxFrame | QStyle.SubControl.SC_GroupBoxLabel)
        opt.textAlignment = Qt.AlignmentFlag.AlignHCenter
        
        # Draw the frame and label
        self.style().drawComplexControl(QStyle.ComplexControl.CC_GroupBox, opt, painter, self)

    def resizeEvent(self, event):
        """Position the label and adjust font size."""
        super().resizeEvent(event)
        
        # Get the rect for the content area inside the painted groupbox frame
        opt = QStyleOptionGroupBox()
        opt.initFrom(self)
        content_rect = self.style().subControlRect(QStyle.ComplexControl.CC_GroupBox, opt, QStyle.SubControl.SC_GroupBoxContents, self)
        
        self.time_label.setGeometry(content_rect)
        
        self._adjust_font_size()

    def _adjust_font_size(self):
        font = self.time_label.font()
        
        available_height = self.time_label.height() - 6
        available_width = self.time_label.width() - 8
        if available_height <= 0 or available_width <= 0:
            return

        sample_string = self.time_label.text()
        if not sample_string:
            sample_string = "00:00:00.000"

        font_size = 100 # Start very large
        while font_size > 5:
            font.setPointSize(font_size)
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(sample_string)
            text_height = fm.height()
            
            if text_width < available_width and text_height < available_height:
                break
            font_size -= 1
            
        self.time_label.setFont(font)
        
class DefinedArea:
    def __init__(self, rect: QRect, area_id: str = None, grid_cells: set[tuple[int,int]] = None):
        self.id=area_id if area_id else str(uuid.uuid4())
        self.rect=rect
        self.grid_cells=grid_cells if grid_cells else set()
        self.function_type:str="None"
        self.data:dict={}
        self.display_text:str=""
        self.embedded_widget:QWidget|None=None
        self.label_widget:QLabel|None=None
        self.input_widget:QSpinBox|QDoubleSpinBox|None=None
        self.embedded_widget_2:QWidget|None=None
        self.input_widget_2:QSpinBox|QDoubleSpinBox|None=None
        self.set_function(self.function_type, self.data)

    def __repr__(self):
        return f"<Area {self.id[:4]} f='{self.function_type}' d='{self.data.get('palette_kind', self.data.get('gradient_stops', self.data.get('selected_loop_palette_configs', '')))}'>"


    def set_function(self, func_type:str,data:dict,display_text_override:str=None):
        self.function_type=func_type
        self.data=data
        if display_text_override:self.display_text=display_text_override;return

        if func_type=="Slider Control":
            st1=data.get('slider1_type','Generic').capitalize()
            if data.get('enable_dual_sliders')and data.get('slider2_type'):
                st2=data.get('slider2_type','Generic').capitalize()
                self.display_text=f"Sel Fx {st1} / {st2}"
            else:
                self.display_text=f"Sel Fx {st1}"
        elif func_type=="Fixture Control":self.display_text=f"FX: {data.get('fixture_name','N/A')[:12]}"
        elif func_type=="Fixture Selector List": self.display_text="Fixture List"
        elif func_type=="Multi-Group Selector List": self.display_text="Group List"
        elif func_type=="Master Cue List": self.display_text="Cue List"
        elif func_type=="Color Palette":
            palette_kind = data.get('palette_kind', 'Color')
            if palette_kind == "Position":
                self.display_text="Position Palette"
            else:
                self.display_text="Color Palette"
        elif func_type=="Loop Palette":
            self.display_text="Loop Effects"
        elif func_type=="Gradient Editor":
            self.display_text="Gradient Editor"
        elif func_type=="Executor Fader":
            self.display_text=f"Exec: {data.get('group_name', 'N/A')[:10]}"
        elif func_type=="Preset Trigger":self.display_text=f"Preset:\n{data.get('preset_name','N/A')[:12]}"
        elif func_type=="Executor Button": self.display_text="Timeline GO"
        elif func_type=="Master Intensity":self.display_text="Master"
        elif func_type=="Toggle Fixture Power":self.display_text=f"Toggle\n{data.get('fixture_name','Fx N/A')[:10]}"
        elif func_type=="Flash Fixture":self.display_text=f"Flash\n{data.get('fixture_name','Fx N/A')[:10]}"
        elif func_type=="Color Picker":self.display_text="Sel Fx Color"
        elif func_type=="Sequence Go":self.display_text="SEQ GO"
        elif func_type=="Group Selector": self.display_text=f"Group: {data.get('group_name', 'N/A')[:10]}"
        elif func_type=="Embedded Stage View": self.display_text="Stage View"
        elif func_type=="Embedded Timeline": self.display_text="Timeline Controls"
        elif func_type == "Clock Display": self.display_text = "Clock"
        elif func_type == "Programmer View": self.display_text = "Programmer"
        elif func_type=="None":self.display_text=f"Area {self.id[:4]}"
        else:self.display_text=func_type

    def clear_embedded_widget(self, main_window: 'Lumenante'):
        if self.embedded_widget:
            if self.function_type == "Color Palette" and isinstance(self.embedded_widget, QFrame):
                if hasattr(self.embedded_widget, "_palette_button_container"):
                    button_container_frame = getattr(self.embedded_widget, "_palette_button_container", None)
                    if button_container_frame and isinstance(button_container_frame, QFrame):
                        layout_to_clear = button_container_frame.layout()
                        if layout_to_clear:
                            while layout_to_clear.count():
                                child_item = layout_to_clear.takeAt(0)
                                if child_item.widget():
                                    child_item.widget().deleteLater()
                if hasattr(self.embedded_widget, "_palette_buttons"):
                    setattr(self.embedded_widget, "_palette_buttons", [])
                if hasattr(self.embedded_widget, '_active_button_widget'):
                    setattr(self.embedded_widget, '_active_button_widget', None)
            elif self.function_type == "Loop Palette" and isinstance(self.embedded_widget, QFrame):
                if hasattr(self.embedded_widget, "_loop_button_container"):
                    button_container_frame = getattr(self.embedded_widget, "_loop_button_container", None)
                    if button_container_frame and isinstance(button_container_frame, QFrame):
                        layout_to_clear = button_container_frame.layout()
                        if layout_to_clear:
                            while layout_to_clear.count():
                                child_item = layout_to_clear.takeAt(0)
                                if child_item.widget():
                                    try: child_item.widget().toggled.disconnect()
                                    except: pass
                                    child_item.widget().deleteLater()
                if hasattr(self.embedded_widget, "_loop_buttons_map"):
                    setattr(self.embedded_widget, "_loop_buttons_map", {})

            elif isinstance(self.embedded_widget, GradientEditorWidget):
                try: self.embedded_widget.gradientChanged.disconnect()
                except TypeError: pass
                try: self.embedded_widget.applyGradientClicked.disconnect()
                except TypeError: pass
            elif isinstance(self.embedded_widget, QListWidget):
                 try: self.embedded_widget.itemSelectionChanged.disconnect()
                 except TypeError: pass
            elif isinstance(self.embedded_widget, QPushButton) and self.function_type in ["Group Selector", "Executor Button", "Preset Trigger", "Sequence Go"]:
                 try: self.embedded_widget.clicked.disconnect()
                 except TypeError: pass
            elif isinstance(self.embedded_widget, QPushButton) and self.function_type == "Toggle Fixture Power":
                 try: self.embedded_widget.toggled.disconnect()
                 except TypeError: pass
            elif isinstance(self.embedded_widget, QPushButton) and self.function_type == "Flash Fixture":
                 try: self.embedded_widget.pressed.disconnect()
                 except TypeError: pass
                 try: self.embedded_widget.released.disconnect()
                 except TypeError: pass
            elif isinstance(self.embedded_widget, EmbeddedStageViewWidget):
                if hasattr(self.embedded_widget, 'opengl_scene') and self.embedded_widget.opengl_scene:
                    if hasattr(self.embedded_widget.opengl_scene, 'strobe_timer_embedded'):
                        self.embedded_widget.opengl_scene.strobe_timer_embedded.stop()
                    # Persist camera state before deleting
                    self.data['camera_x_angle'] = self.embedded_widget.opengl_scene.camera_x_angle
                    self.data['camera_y_angle'] = self.embedded_widget.opengl_scene.camera_y_angle
                    self.data['camera_zoom'] = self.embedded_widget.opengl_scene.camera_zoom_distance
                    self.data['camera_target'] = self.embedded_widget.opengl_scene.camera_target.tolist()
            elif isinstance(self.embedded_widget, EmbeddedTimelineWidget):
                if hasattr(self.embedded_widget, 'view'): # The new view widget
                    try: self.embedded_widget.view.playhead_scrubbed.disconnect()
                    except TypeError: pass
                try: self.embedded_widget.go_pressed.disconnect()
                except TypeError: pass
                try: self.embedded_widget.stop_pressed.disconnect()
                except TypeError: pass
                try: self.embedded_widget.prev_pressed.disconnect()
                except TypeError: pass
                try: self.embedded_widget.next_pressed.disconnect()
                except TypeError: pass
            elif isinstance(self.embedded_widget, ClockWidget):
                if hasattr(self.embedded_widget, 'timer') and self.embedded_widget.timer.isActive():
                    self.embedded_widget.timer.stop()
            elif isinstance(self.embedded_widget, ProgrammerViewWidget):
                if hasattr(self.embedded_widget, 'parent_tab') and self.embedded_widget.parent_tab:
                     try: self.embedded_widget.parent_tab.global_fixture_selection_changed.disconnect(self.embedded_widget.update_view)
                     except (TypeError, RuntimeError): pass
                     try: main_window.fixture_data_globally_changed.disconnect(self.embedded_widget.handle_single_fixture_update)
                     except (TypeError, RuntimeError): pass
            elif isinstance(self.embedded_widget, CueListWidget):
                 if hasattr(self.embedded_widget, 'timeline_tab') and self.embedded_widget.timeline_tab:
                    try: self.embedded_widget.timeline_tab.cues_changed.disconnect(self.embedded_widget.refresh_cues)
                    except (TypeError, RuntimeError): pass
            
            self.embedded_widget.deleteLater()
            self.embedded_widget=None
        
        if self.label_widget:self.label_widget.deleteLater();self.label_widget=None
        if self.input_widget:self.input_widget.deleteLater();self.input_widget=None
        if self.embedded_widget_2:self.embedded_widget_2.deleteLater();self.embedded_widget_2=None
        if self.input_widget_2:self.input_widget_2.deleteLater();self.input_widget_2=None

# <<<< MainTab class is now defined FIRST >>>>
class MainTab(QWidget):
    global_fixture_selection_changed = pyqtSignal(list)
    preset_triggered = pyqtSignal(str)
    master_intensity_changed = pyqtSignal(int)
    toggle_fixture_power_signal = pyqtSignal(str, int, bool)
    flash_fixture_signal = pyqtSignal(str, int, bool)
    sequence_go_signal = pyqtSignal(str)
    fixture_parameter_changed_from_area = pyqtSignal(int, dict)
    generic_slider_activated = pyqtSignal(str, object, str)
    generic_color_activated = pyqtSignal(str, QColor, str)
    loop_palette_triggered = pyqtSignal(str, int, bool)
    executor_fader_changed = pyqtSignal(int, int) # NEW: group_id, value

    def __init__(self, main_window: 'Lumenante'):
        super().__init__()
        self.main_window = main_window
        self.settings = self.main_window.settings
        
        self.globally_selected_fixture_ids_for_controls: list[int] = []
        self.globally_selected_group_name_for_display: str | None = None

        # Dictionary to hold registered plugin widgets
        # Format: {"Display Name": creation_callback_function}
        self.custom_layout_widgets: Dict[str, Callable[[QWidget, Dict], QWidget]] = {}

        self.init_ui()
        
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        self.interactive_canvas = InteractiveGridCanvas(self)
        
        self.assignment_panel = QFrame()
        self.assignment_panel.setObjectName("AssignmentPanel")
        self.assignment_panel.setFixedWidth(280)
        self.assignment_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.assignment_panel_layout = QVBoxLayout(self.assignment_panel)
        
        self.create_assignment_panel_content(self.assignment_panel_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.interactive_canvas)
        splitter.addWidget(self.assignment_panel)
        splitter.setSizes([self.width() - 280, 280])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # Overview Widget
        self.overview_widget = LayoutOverviewWidget(self.interactive_canvas, self.interactive_canvas)
        self.interactive_canvas.viewOrContentChanged.connect(self.overview_widget.force_repaint)
        self.overview_widget.viewportChangedByOverview.connect(self.interactive_canvas._handle_viewport_change_from_overview)

        self.interactive_canvas.area_selected_for_assignment.connect(self.handle_area_selected_for_panel)
        self.interactive_canvas.embedded_list_fixture_selected.connect(self._handle_embedded_list_selection)
        self.interactive_canvas.embedded_multi_group_list_selected.connect(self._handle_embedded_group_list_selection)
        self.global_fixture_selection_changed.connect(self._on_main_tab_global_fixture_selection_changed)
        self.global_fixture_selection_changed.connect(self.interactive_canvas.update_all_fixture_list_selections)


    def register_custom_layout_widget(self, name: str, creation_callback: Callable[[QWidget, Dict], QWidget]) -> bool:
        """Allows plugins to register a new type of widget for the layout canvas."""
        if name in self.custom_layout_widgets:
            print(f"Warning: Plugin widget with name '{name}' is already registered. Overwriting.")
        
        self.custom_layout_widgets[name] = creation_callback
        self.populate_function_type_combo() # Repopulate to include the new widget type
        return True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overview_widget') and self.overview_widget.parent() == self.interactive_canvas:
            overview_pos = self.interactive_canvas.rect().bottomRight() - self.overview_widget.rect().bottomRight() - QPoint(10, 10)
            self.overview_widget.move(overview_pos)
            self.overview_widget.raise_()

    def create_assignment_panel_content(self, layout: QVBoxLayout):
        self.area_id_label = QLabel("No Area Selected")
        self.area_id_label.setObjectName("PanelHeaderLabel")
        layout.addWidget(self.area_id_label)

        self.function_type_combo = QComboBox()
        self.populate_function_type_combo()
        self.function_type_combo.currentTextChanged.connect(self._update_assignment_panel_for_type)
        layout.addWidget(self.function_type_combo)

        self.function_specific_options_container = QGroupBox("Options")
        self.function_specific_options_container.setObjectName("AssignmentOptionsGroup")
        self.function_specific_layout = QVBoxLayout(self.function_specific_options_container)
        layout.addWidget(self.function_specific_options_container)

        self.save_area_button = QPushButton("Apply Assignment")
        self.save_area_button.setObjectName("PrimaryButton")
        self.save_area_button.clicked.connect(self.save_area_assignment)
        layout.addWidget(self.save_area_button)

        layout.addStretch(1)
        self.handle_area_selected_for_panel(None)

    def populate_function_type_combo(self):
        self.function_type_combo.blockSignals(True)
        current_text = self.function_type_combo.currentText()
        self.function_type_combo.clear()
        
        # Add built-in types
        standard_types = [ 
            "None", "Programmer View", "Master Cue List", "Preset Trigger", "Executor Fader", "Executor Button",
            "Fixture Selector List", "Multi-Group Selector List", "Group Selector",
            "Slider Control", "Color Picker", "Color Palette", "Loop Palette", "Gradient Editor",
            "Fixture Control", "Master Intensity", "Toggle Fixture Power", "Flash Fixture",
            "Embedded Stage View", "Embedded Timeline", "Clock Display"
        ]
        self.function_type_combo.addItems(standard_types)
        
        # Add plugin-registered types
        if self.custom_layout_widgets:
            self.function_type_combo.insertSeparator(self.function_type_combo.count())
            plugin_widget_names = sorted(self.custom_layout_widgets.keys())
            self.function_type_combo.addItems(plugin_widget_names)

        # Restore previous selection if possible
        idx = self.function_type_combo.findText(current_text)
        if idx != -1:
            self.function_type_combo.setCurrentIndex(idx)

        self.function_type_combo.blockSignals(False)


    def _clear_assignment_panel_options(self):
        # This properly deletes all widgets inside the layout
        layout = self.function_specific_layout
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                # Also handle nested layouts
                layout_item = item.layout()
                if layout_item is not None:
                    # Recursively delete widgets from nested layouts
                    while layout_item.count():
                        sub_item = layout_item.takeAt(0)
                        sub_widget = sub_item.widget()
                        if sub_widget is not None:
                            sub_widget.deleteLater()
                    layout_item.deleteLater()


    def _create_and_populate_fixture_combo(self, area: 'DefinedArea', object_name: str) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(object_name)
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name, fid, sfi FROM fixtures ORDER BY fid, sfi")
            fixtures = cursor.fetchall()
            combo.addItem("Select a fixture...", -1)
            for pk_id, name, fid, sfi in fixtures:
                combo.addItem(f"{name} ({fid}.{sfi})", pk_id)
            
            current_fixture_id = area.data.get('fixture_id')
            if current_fixture_id is not None:
                idx = combo.findData(current_fixture_id)
                if idx != -1: combo.setCurrentIndex(idx)
        except Exception as e:
            print(f"Error loading fixtures for assignment panel: {e}")
            combo.addItem("Error loading", -1)
        return combo

    def _create_and_populate_preset_combo(self, area: 'DefinedArea') -> QComboBox:
        combo = QComboBox()
        combo.setObjectName("AssignmentPresetCombo")
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT preset_number, name FROM presets ORDER BY preset_number")
            presets = cursor.fetchall()
            combo.addItem("Select a preset...", None)
            for num, name in presets:
                display_name = f"P {num}"
                if name: display_name += f": {name}"
                combo.addItem(display_name, num)
            
            current_preset_num = area.data.get('preset_number')
            if current_preset_num is not None:
                idx = combo.findData(current_preset_num)
                if idx != -1: combo.setCurrentIndex(idx)
        except Exception as e:
            print(f"Error loading presets for assignment panel: {e}")
            combo.addItem("Error loading", None)
        return combo

    def _update_assignment_panel_for_type(self, func_type: str):
        self._clear_assignment_panel_options()
        area = self.interactive_canvas.currently_selected_area_for_panel
        if not area: return

        # Use a new layout instance to ensure it's clean
        form_layout = QFormLayout()
        form_layout.setContentsMargins(2, 8, 2, 8) # Add some padding

        if func_type in ["Fixture Control", "Toggle Fixture Power", "Flash Fixture"]:
            fixture_combo = self._create_and_populate_fixture_combo(area, "AssignmentFixtureCombo")
            form_layout.addRow("Target Fixture:", fixture_combo)

        elif func_type == "Preset Trigger":
            preset_combo = self._create_and_populate_preset_combo(area)
            form_layout.addRow("Preset:", preset_combo)
        
        elif func_type == "Embedded Stage View":
            show_beams_check = QCheckBox()
            show_beams_check.setObjectName("AssignmentShowBeamsCheck")
            show_beams_check.setChecked(area.data.get('show_beams', True))
            form_layout.addRow("Show Beams:", show_beams_check)
            
        elif func_type == "Color Palette":
            kind_combo = QComboBox()
            kind_combo.setObjectName("AssignmentPaletteKindCombo")
            kind_combo.addItems(["Color", "Position"])
            kind_combo.setCurrentText(area.data.get('palette_kind', "Color"))
            form_layout.addRow("Palette Type:", kind_combo)

            num_buttons_spin = QSpinBox()
            num_buttons_spin.setObjectName("AssignmentPaletteNumButtonsSpin")
            num_buttons_spin.setRange(2, 64)
            num_buttons_spin.setValue(area.data.get('num_buttons', 8))
            form_layout.addRow("Number of Buttons:", num_buttons_spin)
            
            num_cols_spin = QSpinBox()
            num_cols_spin.setObjectName("AssignmentPaletteColsSpin")
            num_cols_spin.setRange(1, 10)
            num_cols_spin.setValue(area.data.get('num_cols', 4))
            form_layout.addRow("Number of Columns:", num_cols_spin)

        elif func_type == "Loop Palette":
            select_loops_button = QPushButton("Select Loops to Display...")
            select_loops_button.setObjectName("AssignmentSelectLoopsButton")
            select_loops_button.clicked.connect(self._open_loop_selection_dialog)
            form_layout.addRow(select_loops_button)
            
            num_cols_spin = QSpinBox()
            num_cols_spin.setObjectName("AssignmentLoopColsSpin")
            num_cols_spin.setRange(1, 10)
            num_cols_spin.setValue(area.data.get('num_cols', 2))
            form_layout.addRow("Number of Columns:", num_cols_spin)
        
        elif func_type == "Group Selector" or func_type == "Executor Fader":
            group_combo = QComboBox()
            group_combo.setObjectName("AssignmentGroupCombo")
            form_layout.addRow("Target Group:", group_combo)
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("SELECT id, name FROM fixture_groups ORDER BY name")
                groups = cursor.fetchall()
                group_combo.addItem("Select a group...", -1)
                for gid, name in groups:
                    group_combo.addItem(name, gid)
                current_group_id = area.data.get('group_id')
                if current_group_id is not None:
                    idx = group_combo.findData(current_group_id)
                    if idx != -1: group_combo.setCurrentIndex(idx)
            except Exception as e:
                print(f"Error loading groups for assignment panel: {e}")
                group_combo.addItem("Error loading", -1)

        elif func_type == "Slider Control":
            slider1_type_combo = QComboBox()
            slider1_type_combo.addItems(["Intensity", "Pan", "Tilt", "Focus", "Strobe", "Gobo Spin", "Speed"])
            slider1_type_combo.setObjectName("Slider1TypeCombo")
            form_layout.addRow("Slider 1 Type:", slider1_type_combo)

            dual_slider_checkbox = QCheckBox("Enable Dual Sliders")
            dual_slider_checkbox.setObjectName("DualSliderCheckbox")
            form_layout.addRow(dual_slider_checkbox)
            
            slider2_label = QLabel("Slider 2 Type:")
            slider2_type_combo = QComboBox()
            slider2_type_combo.addItems(["Intensity", "Pan", "Tilt", "Focus", "Strobe", "Gobo Spin", "Speed"])
            slider2_type_combo.setObjectName("Slider2TypeCombo")
            form_layout.addRow(slider2_label, slider2_type_combo)
            
            def toggle_slider2(checked):
                slider2_label.setVisible(checked)
                slider2_type_combo.setVisible(checked)
            
            dual_slider_checkbox.toggled.connect(toggle_slider2)
            
            slider1_type_combo.setCurrentText(area.data.get("slider1_type", "Intensity"))
            slider2_type_combo.setCurrentText(area.data.get("slider2_type", "Pan"))
            is_dual = area.data.get("enable_dual_sliders", False)
            dual_slider_checkbox.setChecked(is_dual)
            toggle_slider2(is_dual)
        
        elif func_type == "Clock Display": 
            check_24h = QCheckBox("24-Hour Format")
            check_24h.setObjectName("AssignmentClock24hCheck")
            check_24h.setChecked(area.data.get('show_24_hour', True))
            form_layout.addRow(check_24h)

            check_ms = QCheckBox("Show Milliseconds")
            check_ms.setObjectName("AssignmentClockMsCheck")
            check_ms.setChecked(area.data.get('show_milliseconds', False))
            form_layout.addRow(check_ms)

        # Only add the form layout if it contains widgets
        if form_layout.rowCount() > 0:
            self.function_specific_layout.addLayout(form_layout)
        
        self.function_specific_layout.addStretch(1)

    def _open_loop_selection_dialog(self):
        area = self.interactive_canvas.currently_selected_area_for_panel
        if not area: return

        current_configs = area.data.get('selected_loop_palette_configs', [])
        dialog = SelectLoopsDialog(self.main_window, current_configs, self)
        
        if dialog.exec():
            selected_configs = dialog.get_selected_loop_configs()
            # We don't save here directly. The selection is temporary until "Apply Assignment" is clicked.
            # We store it on a temporary property of the button to be retrieved by the save method.
            button = self.function_specific_options_container.findChild(QPushButton, "AssignmentSelectLoopsButton")
            if button:
                button.setProperty("selected_configs", selected_configs)
                button.setText(f"{len(selected_configs)} Loop(s) Selected")

    def save_area_assignment(self):
        area = self.interactive_canvas.currently_selected_area_for_panel
        if not area: return
        
        new_func_type = self.function_type_combo.currentText()
        new_data = {}
        cont = self.function_specific_options_container

        if new_func_type in ["Fixture Control", "Toggle Fixture Power", "Flash Fixture"]:
            combo = cont.findChild(QComboBox, "AssignmentFixtureCombo")
            if combo and combo.currentData() != -1:
                new_data['fixture_id'] = combo.currentData()
                new_data['fixture_name'] = combo.currentText().split(" (")[0]
            else:
                QMessageBox.warning(self, "Input Error", "Please select a valid fixture.")
                return

        elif new_func_type == "Preset Trigger":
            combo = cont.findChild(QComboBox, "AssignmentPresetCombo")
            if combo and combo.currentData() is not None:
                new_data['preset_number'] = combo.currentData()
                new_data['preset_name'] = combo.currentText() # Store display name for widget
            else:
                QMessageBox.warning(self, "Input Error", "Please select a valid preset.")
                return

        elif new_func_type == "Embedded Stage View":
            check = cont.findChild(QCheckBox, "AssignmentShowBeamsCheck")
            if check:
                new_data['show_beams'] = check.isChecked()

        elif new_func_type == "Color Palette":
            kind_combo = cont.findChild(QComboBox, "AssignmentPaletteKindCombo")
            num_buttons_spin = cont.findChild(QSpinBox, "AssignmentPaletteNumButtonsSpin")
            num_cols_spin = cont.findChild(QSpinBox, "AssignmentPaletteColsSpin")
            if kind_combo and num_buttons_spin and num_cols_spin:
                new_data['palette_kind'] = kind_combo.currentText()
                new_data['num_buttons'] = num_buttons_spin.value()
                new_data['num_cols'] = num_cols_spin.value()
                # If kind/num changes, preserve button data if possible, or reset
                if area.data.get('palette_kind') != new_data['palette_kind']:
                    new_data['buttons_data'] = [{'name':f'Item {i+1}'} for i in range(new_data['num_buttons'])]
                else:
                    new_data['buttons_data'] = area.data.get('buttons_data', [])
                    # Resize button data list if num_buttons changed
                    while len(new_data['buttons_data']) < new_data['num_buttons']:
                        new_data['buttons_data'].append({'name': f'Item {len(new_data["buttons_data"])+1}'})
                    new_data['buttons_data'] = new_data['buttons_data'][:new_data['num_buttons']]

        elif new_func_type == "Loop Palette":
            button = cont.findChild(QPushButton, "AssignmentSelectLoopsButton")
            spin = cont.findChild(QSpinBox, "AssignmentLoopColsSpin")
            if spin:
                new_data['num_cols'] = spin.value()
            if button and button.property("selected_configs") is not None:
                new_data['selected_loop_palette_configs'] = button.property("selected_configs")
            else: # Use existing config if user didn't open the dialog
                new_data['selected_loop_palette_configs'] = area.data.get('selected_loop_palette_configs', [])
        
        elif new_func_type == "Group Selector" or new_func_type == "Executor Fader":
            combo = cont.findChild(QComboBox, "AssignmentGroupCombo")
            if combo and combo.currentData() != -1:
                new_data['group_id'] = combo.currentData()
                new_data['group_name'] = combo.currentText()
            else:
                QMessageBox.warning(self, "Input Error", "Please select a valid group.")
                return

        elif new_func_type == "Slider Control":
            combo1 = cont.findChild(QComboBox, "Slider1TypeCombo")
            combo2 = cont.findChild(QComboBox, "Slider2TypeCombo")
            checkbox = cont.findChild(QCheckBox, "DualSliderCheckbox")
            if combo1 and combo2 and checkbox:
                new_data['slider1_type'] = combo1.currentText()
                new_data['enable_dual_sliders'] = checkbox.isChecked()
                if checkbox.isChecked():
                    new_data['slider2_type'] = combo2.currentText()
        
        elif new_func_type == "Clock Display":
            check_24h = cont.findChild(QCheckBox, "AssignmentClock24hCheck")
            check_ms = cont.findChild(QCheckBox, "AssignmentClockMsCheck")
            if check_24h and check_ms:
                new_data['show_24_hour'] = check_24h.isChecked()
                new_data['show_milliseconds'] = check_ms.isChecked()


        self.interactive_canvas.update_area_properties_and_widget(area.id, new_func_type, new_data)
        self.save_defined_areas_to_settings()
        QMessageBox.information(self, "Assignment Saved", f"Area assignment updated to '{new_func_type}'.")

    def handle_area_selected_for_panel(self, area: Optional[DefinedArea]):
        is_area_selected = area is not None
        
        self.assignment_panel.setEnabled(is_area_selected)
        
        if is_area_selected:
            self.area_id_label.setText(f"Area: {area.id[:8]}...")
            idx = self.function_type_combo.findText(area.function_type)
            self.function_type_combo.setCurrentIndex(idx if idx != -1 else 0)
            self._update_assignment_panel_for_type(area.function_type)
        else:
            self.area_id_label.setText("No Area Selected")
            self.function_type_combo.setCurrentIndex(0)
            self._clear_assignment_panel_options()

    def _handle_embedded_list_selection(self, selected_ids: List[int]):
        self.clear_all_global_selections()
        self.globally_selected_fixture_ids_for_controls = selected_ids
        self.global_fixture_selection_changed.emit(selected_ids)
        
    def _handle_embedded_group_list_selection(self, selected_group_ids: List[int]):
        fixture_ids = []
        if selected_group_ids:
            try:
                cursor = self.main_window.db_connection.cursor()
                placeholders = ','.join('?' for _ in selected_group_ids)
                cursor.execute(f"SELECT fixture_id FROM fixture_group_mappings WHERE group_id IN ({placeholders})", tuple(selected_group_ids))
                fixture_ids = [row[0] for row in cursor.fetchall()]
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Error fetching fixtures for groups: {e}")
        
        self.clear_all_global_selections()
        self.globally_selected_fixture_ids_for_controls = list(set(fixture_ids))
        self.globally_selected_group_name_for_display = f"{len(selected_group_ids)} Grp(s)"
        self.global_fixture_selection_changed.emit(self.globally_selected_fixture_ids_for_controls)

    def _sync_global_controls_to_selected_fixture(self, selected_ids: List[int]):
        if not selected_ids:
            return

        selected_states = [self.main_window.live_fixture_states.get(fid) for fid in selected_ids if self.main_window.live_fixture_states.get(fid)]
        if not selected_states: return

        first_fixture_state = selected_states[0]

        for area in self.interactive_canvas.defined_areas:
            # --- Sync Slider Controls ---
            if area.function_type == "Slider Control" and area.embedded_widget:
                # Helper function to sync a single slider/spinbox pair
                def sync_slider(slider, spinbox, type_key):
                    if not slider or not spinbox: return

                    param_key = self._map_slider_type_to_param_key(area.data.get(type_key, 'generic').lower())
                    if not param_key: return

                    first_val = first_fixture_state.get(param_key)
                    if first_val is None: return

                    slider.blockSignals(True)
                    spinbox.blockSignals(True)
                    
                    display_val = float(first_val)
                    # Check if this is the pan slider and wrap its value for display
                    if area.data.get(type_key, '').lower() == 'pan':
                        display_val = (display_val + 180) % 360 - 180

                    is_double = slider.property("is_double")
                    scale_factor = slider.property("scale_factor")

                    if is_double:
                        spinbox.setValue(display_val)
                    else:
                        spinbox.setValue(int(display_val))
                    
                    if scale_factor is not None:
                        slider.setValue(int(display_val * scale_factor))

                    slider.blockSignals(False)
                    spinbox.blockSignals(False)

                sync_slider(area.embedded_widget, area.input_widget, 'slider1_type')
                if area.data.get('enable_dual_sliders'):
                    sync_slider(area.embedded_widget_2, area.input_widget_2, 'slider2_type')

            # --- Sync Color Picker ---
            elif area.function_type == "Color Picker" and isinstance(area.embedded_widget, CustomColorWheelWidget):
                first_color = QColor(first_fixture_state.get('red',0), first_fixture_state.get('green',0), first_fixture_state.get('blue',0))
                area.embedded_widget.setColor(first_color)
                
    def refresh_dynamic_content(self):
        self.interactive_canvas.refresh_all_fixture_list_areas()
        self.interactive_canvas.refresh_all_multi_group_list_areas()
        
        # After any content refresh that might affect keybinds, re-apply them to tooltips
        for area in self.interactive_canvas.defined_areas:
            self.interactive_canvas.update_area_widget(area)

    def on_global_fixture_data_changed(self, fixture_id: int, new_data: Dict[str, Any]):
        # Sync controls (sliders, color pickers, etc.) if the changed fixture is part of the current selection
        if fixture_id in self.globally_selected_fixture_ids_for_controls:
            self._sync_global_controls_to_selected_fixture(self.globally_selected_fixture_ids_for_controls)
        
        # Also, broadcast the update to any embedded stage views, regardless of selection.
        for area in self.interactive_canvas.defined_areas:
            if isinstance(area.embedded_widget, EmbeddedStageViewWidget):
                area.embedded_widget.update_fixture(fixture_id, new_data)
        
    def save_defined_areas_to_settings(self):
        all_areas_data = self.interactive_canvas.get_all_areas_data_for_saving()
        self.settings.setValue("MainTab/Layout_v3.6_Panning", json.dumps(all_areas_data))
    
    def load_layout_from_data_dict(self, layout_data: Dict):
        areas = layout_data.get('areas', [])
        offset_x = layout_data.get('canvas_offset_x', 0.0)
        offset_y = layout_data.get('canvas_offset_y', 0.0)
        self.interactive_canvas.canvas_offset_x = offset_x
        self.interactive_canvas.canvas_offset_y = offset_y
        self.interactive_canvas.load_areas_from_data(areas)
        self.save_defined_areas_to_settings()
        
    def _handle_group_selector_button_clicked(self, group_id: int):
        if group_id is None: return
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT name FROM fixture_groups WHERE id = ?", (group_id,))
            group_name_tuple = cursor.fetchone()
            group_name = group_name_tuple[0] if group_name_tuple else "Unknown Group"
            
            cursor.execute("SELECT fixture_id FROM fixture_group_mappings WHERE group_id = ?", (group_id,))
            fixture_ids = [row[0] for row in cursor.fetchall()]
            
            self.clear_all_global_selections()
            self.globally_selected_fixture_ids_for_controls = fixture_ids
            self.globally_selected_group_name_for_display = group_name
            self.global_fixture_selection_changed.emit(fixture_ids)
            
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Failed to select group {group_id}: {e}")

    def update_loop_palette_area_button_states(self):
        if not hasattr(self, 'interactive_canvas'): return

        selected_fixture_ids = self.globally_selected_fixture_ids_for_controls
        active_effects = self.main_window.active_effects
        
        for area in self.interactive_canvas.defined_areas:
            if area.function_type == "Loop Palette" and isinstance(area.embedded_widget, QFrame):
                container_frame = area.embedded_widget
                if hasattr(container_frame, "_loop_buttons_map"):
                    for lp_db_id, button in container_frame._loop_buttons_map.items():
                        is_active_on_any_selected = False
                        if selected_fixture_ids:
                             is_active_on_any_selected = any(
                                 lp_db_id == effect.loop_palette_db_id
                                 for fid in selected_fixture_ids
                                 if fid in active_effects
                                 for effect in active_effects[fid].values()
                                 if hasattr(effect, 'loop_palette_db_id')
                             )
                        
                        button.blockSignals(True)
                        button.setChecked(is_active_on_any_selected)
                        button.blockSignals(False)

        
    def clear_all_global_selections(self):
        if self.globally_selected_fixture_ids_for_controls:
            self.globally_selected_fixture_ids_for_controls = []
        if self.globally_selected_group_name_for_display:
            self.globally_selected_group_name_for_display = None
        self.global_fixture_selection_changed.emit([])

    def update_active_group_selection_display(self, group_name: Optional[str]):
        self.globally_selected_group_name_for_display = group_name

    def _map_slider_type_to_param_key(self, slider_type: str) -> Optional[str]:
        mapping = {
            "intensity": "brightness", "pan": "rotation_y", "tilt": "rotation_x",
            "zoom": "zoom", "focus": "focus", "gobo spin": "gobo_spin", 
            "strobe": "shutter_strobe_rate", "speed": "speed"
        }
        return mapping.get(slider_type.lower())

    def toggle_area_creation_mode(self, enabled: bool):
        self.interactive_canvas.area_creation_enabled = enabled

    def _on_main_tab_global_fixture_selection_changed(self, fixture_ids: list[int]):
        """
        This slot is connected to the global_fixture_selection_changed signal.
        It is responsible ONLY for updating widgets within the MainTab itself.
        """
        self.main_window.update_header_selected_info()
        # Sync any listening widgets within this tab, like sliders and color pickers.
        self._sync_global_controls_to_selected_fixture(fixture_ids)

class InteractiveGridCanvas(QWidget):
    area_selected_for_assignment = pyqtSignal(object)
    embedded_list_fixture_selected = pyqtSignal(list)
    embedded_multi_group_list_selected = pyqtSignal(list)
    viewOrContentChanged = pyqtSignal()

    GRID_CELL_WIDTH=80
    GRID_CELL_HEIGHT=70
    MIN_CELLS_WIDTH=1; MIN_CELLS_HEIGHT=1
    MIN_CELLS_WIDTH_COLORWHEEL=4; MIN_CELLS_HEIGHT_COLORWHEEL=3
    MIN_CELLS_HEIGHT_SLIDER=1; MIN_CELLS_WIDTH_SLIDER=1
    MIN_CELLS_FOR_DUAL_SLIDER_HORIZONTAL_LAYOUT=2; MIN_CELLS_FOR_DUAL_SLIDER_VERTICAL_LAYOUT=2
    MIN_CELLS_HEIGHT_FIXTURE_WIDGET = 2
    MIN_CELLS_HEIGHT_FIXTURE_LIST = 2
    MIN_CELLS_HEIGHT_GROUP_LIST = 2
    MIN_CELLS_HEIGHT_FOR_PALETTE = 2
    MIN_CELLS_HEIGHT_LOOP_PALETTE = 1
    MIN_CELLS_WIDTH_GRADIENT = 2
    MIN_CELLS_HEIGHT_GRADIENT = 1
    MIN_CELLS_WIDTH_STAGE_VIEW = 3
    MIN_CELLS_HEIGHT_STAGE_VIEW = 2
    MIN_CELLS_WIDTH_TIMELINE = 3
    MIN_CELLS_HEIGHT_TIMELINE = 1
    MIN_CELLS_WIDTH_PROGRAMMER = 4 
    MIN_CELLS_HEIGHT_PROGRAMMER = 2 


    def __init__(self, parent_tab: 'MainTab', parent=None):
        super().__init__(parent)
        self.parent_tab=parent_tab
        self.main_window=parent_tab.main_window
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.setMouseTracking(True)
        self.area_creation_enabled = True
        self.is_dragging=False
        self.drag_start_cell=None
        self.current_drag_end_cell=None
        self.defined_areas:list[DefinedArea]=[]
        self.currently_selected_area_for_panel:DefinedArea|None=None
        self.multi_selected_areas: list[DefinedArea] = []

        self.selection_rect_pen=QPen(QColor(0,122,255,220),2,Qt.PenStyle.SolidLine)
        self.defined_area_pen=QPen(QColor(70,70,70,200),1.5)
        self.defined_area_selected_pen=QPen(QColor(0,122,255,255),2.5)
        self.defined_area_multi_selected_pen = QPen(QColor(255, 149, 0, 220), 2.0, Qt.PenStyle.DashLine)
        
        self.grid_line_pen=QPen(QColor(50,50,50,180),0.8,Qt.PenStyle.SolidLine)
        self.defined_area_text_color=QColor(220,220,220)

        self.canvas_offset_x = 0.0
        self.canvas_offset_y = 0.0
        self.is_panning = False
        self.pan_start_mouse_pos = QPointF()
        self.pan_start_canvas_offset = QPointF()
        self.right_click_drag_threshold = QApplication.startDragDistance() * 2

    def resizeEvent(self, event: QPaintEvent):
        super().resizeEvent(event)
        self.update_all_embedded_widget_geometries()
        self.parent_tab.overview_widget.raise_()
        self.viewOrContentChanged.emit()

    def _handle_viewport_change_from_overview(self, new_offset_x: float, new_offset_y: float):
        self.canvas_offset_x = new_offset_x
        self.canvas_offset_y = new_offset_y
        self.update_all_embedded_widget_geometries()
        self.update()
        self.viewOrContentChanged.emit()

    def update_all_embedded_widget_geometries(self):
        padding = 4
        for area_item in self.defined_areas:
            if not area_item.embedded_widget and not area_item.label_widget:
                continue

            rect_on_canvas = area_item.rect.translated(
                int(-self.canvas_offset_x),
                int(-self.canvas_offset_y)
            )
            
            widget_area_rect_on_canvas = QRect(rect_on_canvas).adjusted(padding, padding, -padding, -padding)
            
            if area_item.label_widget:
                fm = QFontMetrics(area_item.label_widget.font())
                label_height = fm.height() + 2
                label_geom_rect = QRect(
                    rect_on_canvas.x() + padding, rect_on_canvas.y() + padding,
                    rect_on_canvas.width() - 2 * padding, label_height
                )
                area_item.label_widget.setGeometry(label_geom_rect)
                widget_area_rect_on_canvas.setTop(label_geom_rect.bottom() + 2)
            
            if area_item.embedded_widget:
                if area_item.function_type == "Slider Control":
                    has_dual = area_item.data.get('enable_dual_sliders', False)
                    s1_container_rect = QRect(widget_area_rect_on_canvas)
                    s2_container_rect = QRect()

                    if has_dual:
                        num_cells_w = area_item.rect.width() // self.GRID_CELL_WIDTH
                        if widget_area_rect_on_canvas.width() >= widget_area_rect_on_canvas.height() * 1.5 and num_cells_w >= self.MIN_CELLS_FOR_DUAL_SLIDER_HORIZONTAL_LAYOUT:
                            w1 = widget_area_rect_on_canvas.width() // 2 - 1
                            s1_container_rect = QRect(widget_area_rect_on_canvas.left(), widget_area_rect_on_canvas.top(), w1, widget_area_rect_on_canvas.height())
                            s2_container_rect = QRect(s1_container_rect.right() + 2, widget_area_rect_on_canvas.top(), widget_area_rect_on_canvas.width() - w1 - 2, widget_area_rect_on_canvas.height())
                        else:
                            h1 = widget_area_rect_on_canvas.height() // 2 - 1
                            s1_container_rect = QRect(widget_area_rect_on_canvas.left(), widget_area_rect_on_canvas.top(), widget_area_rect_on_canvas.width(), h1)
                            s2_container_rect = QRect(widget_area_rect_on_canvas.left(), s1_container_rect.bottom() + 2, widget_area_rect_on_canvas.width(), widget_area_rect_on_canvas.height() - h1 - 2)
                        
                        if area_item.embedded_widget and area_item.input_widget:
                            self._position_slider_and_input_within_container(s1_container_rect, area_item.embedded_widget, area_item.input_widget)
                        if area_item.embedded_widget_2 and area_item.input_widget_2:
                           self._position_slider_and_input_within_container(s2_container_rect, area_item.embedded_widget_2, area_item.input_widget_2)
                    else:
                        if area_item.embedded_widget and area_item.input_widget:
                            self._position_slider_and_input_within_container(widget_area_rect_on_canvas, area_item.embedded_widget, area_item.input_widget)
                elif area_item.function_type == "Loop Palette" or area_item.function_type == "Color Palette":
                    area_item.embedded_widget.setGeometry(widget_area_rect_on_canvas)

                else:
                    area_item.embedded_widget.setGeometry(widget_area_rect_on_canvas)
                    if area_item.input_widget and isinstance(area_item.embedded_widget, QSlider):
                         self._position_slider_and_input_within_container(widget_area_rect_on_canvas, area_item.embedded_widget, area_item.input_widget)
    
    def update_all_fixture_list_selections(self, selected_ids: list[int]):
        """A new slot to update all Fixture Selector List widgets on the canvas."""
        for area in self.defined_areas:
            if area.function_type == "Fixture Selector List" and isinstance(area.embedded_widget, QListWidget):
                list_widget = area.embedded_widget
                list_widget.blockSignals(True)
                selection_model = list_widget.selectionModel()
                if selection_model:
                    new_selection = QItemSelection()
                    for i in range(list_widget.count()):
                        item_fid = list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                        if item_fid in selected_ids:
                            model_index = list_widget.model().index(i, 0)
                            new_selection.select(model_index, model_index)
                    selection_model.select(new_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.NoUpdate)
                list_widget.blockSignals(False)

    def update_all_embedded_view_selections(self, selected_ids: list[int]):
        for area in self.defined_areas:
            if isinstance(area.embedded_widget, EmbeddedStageViewWidget):
                area.embedded_widget.set_selection(selected_ids)

    def _position_slider_and_input_within_container(self, container_rect: QRect, slider_widget: QSlider, input_widget: QSpinBox | QDoubleSpinBox):
        slider_height_for_input = 28
        slider_width_for_input = 55
        
        slider_final_rect = QRect(container_rect)
        input_final_rect = QRect(container_rect)

        if slider_widget.orientation() == Qt.Orientation.Horizontal:
            if container_rect.height() > slider_height_for_input + 5:
                slider_final_rect.setHeight(max(15, container_rect.height() - slider_height_for_input - 4))
                input_final_rect.setTop(slider_final_rect.bottom() + 4)
                input_final_rect.setHeight(slider_height_for_input)
            else:
                slider_final_rect.setHeight(max(15, container_rect.height() // 2))
                input_final_rect.setTop(slider_final_rect.bottom() + 2)
                input_final_rect.setHeight(max(slider_height_for_input // 2, container_rect.height() - slider_final_rect.height() - 2))
        else:
            if container_rect.width() > slider_width_for_input + 5:
                slider_final_rect.setWidth(max(15, container_rect.width() - slider_width_for_input - 4))
                input_final_rect.setLeft(slider_final_rect.right() + 4)
                input_final_rect.setWidth(slider_width_for_input)
                input_final_rect.setTop(slider_final_rect.top() + (slider_final_rect.height() - slider_height_for_input) // 2)
                input_final_rect.setHeight(slider_height_for_input)
            else:
                slider_final_rect.setWidth(max(15, container_rect.width() // 2))
                input_final_rect.setLeft(slider_final_rect.right() + 2)
                input_final_rect.setWidth(max(slider_width_for_input // 2, container_rect.width() - slider_final_rect.width() - 2))
                input_final_rect.setTop(slider_final_rect.top() + (slider_final_rect.height() - slider_height_for_input) // 2)
                input_final_rect.setHeight(slider_height_for_input)
        
        slider_widget.setGeometry(slider_final_rect)
        input_widget.setGeometry(input_final_rect)


    def _get_grid_cell_from_point(self,point:QPointF)->tuple[int,int]:
        actual_x = point.x() + self.canvas_offset_x
        actual_y = point.y() + self.canvas_offset_y
        cell_r = int(actual_y // self.GRID_CELL_HEIGHT)
        cell_c = int(actual_x // self.GRID_CELL_WIDTH)
        return cell_r, cell_c


    def _get_rect_from_grid_cells(self,r1,c1,r2,c2)->QRect:
        r_s,c_s=min(r1,r2),min(c1,c2)
        r_e,c_e=max(r1,r2),max(c1,c2)
        return QRect(c_s*self.GRID_CELL_WIDTH,r_s*self.GRID_CELL_HEIGHT,(c_e-c_s+1)*self.GRID_CELL_WIDTH,(r_e-r_s+1)*self.GRID_CELL_HEIGHT)

    def _get_occupied_cells_for_rect(self,rect:QRect)->set[tuple[int,int]]:
        cells=set()
        start_row = rect.top() // self.GRID_CELL_HEIGHT
        start_col = rect.left() // self.GRID_CELL_WIDTH
        end_row = (rect.bottom() - 1) // self.GRID_CELL_HEIGHT if rect.height() > 0 else start_row
        end_col = (rect.right() - 1) // self.GRID_CELL_WIDTH if rect.width() > 0 else start_col
        
        for r_idx in range(start_row, end_row + 1):
            for c_idx in range(start_col, end_col + 1):
                cells.add((r_idx, c_idx))
        return cells

    def _is_area_overlapping(self,new_cells:set[tuple[int,int]],exclude_id:str=None)->bool:
        return any(not new_cells.isdisjoint(a.grid_cells) for a in self.defined_areas if not(exclude_id and a.id==exclude_id))

    def paintEvent(self,event:QPaintEvent):
        super().paintEvent(event)
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.translate(-self.canvas_offset_x, -self.canvas_offset_y)
        
        visible_rect = QRectF(self.canvas_offset_x, self.canvas_offset_y, self.width(), self.height())
        
        grid_draw_margin = 2 * max(self.GRID_CELL_WIDTH, self.GRID_CELL_HEIGHT)
        min_x_to_draw = math.floor((visible_rect.left() - grid_draw_margin) / self.GRID_CELL_WIDTH) * self.GRID_CELL_WIDTH
        max_x_to_draw = math.ceil((visible_rect.right() + grid_draw_margin) / self.GRID_CELL_WIDTH) * self.GRID_CELL_WIDTH
        min_y_to_draw = math.floor((visible_rect.top() - grid_draw_margin) / self.GRID_CELL_HEIGHT) * self.GRID_CELL_HEIGHT
        max_y_to_draw = math.ceil((visible_rect.bottom() + grid_draw_margin) / self.GRID_CELL_HEIGHT) * self.GRID_CELL_HEIGHT


        painter.setPen(self.grid_line_pen)
        for x_coord in range(int(min_x_to_draw), int(max_x_to_draw) + self.GRID_CELL_WIDTH, self.GRID_CELL_WIDTH):
            painter.drawLine(x_coord, int(min_y_to_draw), x_coord, int(max_y_to_draw))
        for y_coord in range(int(min_y_to_draw), int(max_y_to_draw) + self.GRID_CELL_HEIGHT, self.GRID_CELL_HEIGHT):
            painter.drawLine(int(min_x_to_draw), y_coord, int(max_x_to_draw), y_coord)
        
        for area_item in self.defined_areas:
            if not isinstance(area_item,DefinedArea):continue
            
            is_selected_for_panel = (area_item == self.currently_selected_area_for_panel)
            is_multi_selected = (area_item in self.multi_selected_areas)

            painter.setBrush(self._get_area_base_brush(area_item, is_selected_for_panel or is_multi_selected))
            
            if is_multi_selected:
                painter.setPen(self.defined_area_multi_selected_pen)
            elif is_selected_for_panel:
                painter.setPen(self.defined_area_selected_pen)
            else:
                painter.setPen(self.defined_area_pen)
            
            painter.drawRoundedRect(area_item.rect,3,3)
            
            types_that_manage_their_own_text_or_have_no_text = [
                 "Preset Trigger", "Toggle Fixture Power", "Flash Fixture", "Sequence Go", "Group Selector", "Executor Button",
                 "Fixture Control", "Loop Palette", "Embedded Timeline", "Executor Fader", "Clock Display", "Programmer View"
            ]
            if not area_item.label_widget and not area_item.embedded_widget and \
               area_item.function_type not in types_that_manage_their_own_text_or_have_no_text:
                painter.setPen(self.defined_area_text_color)
                text_rect=area_item.rect.adjusted(5,5,-5,-5)
                font=painter.font()
                font.setPointSize(9)
                painter.setFont(font)
                painter.drawText(text_rect,Qt.AlignmentFlag.AlignCenter,area_item.display_text)
        
        if self.is_dragging and self.drag_start_cell and self.current_drag_end_cell and self.area_creation_enabled:
            drag_r_virtual=self._get_rect_from_grid_cells(self.drag_start_cell[0],self.drag_start_cell[1],self.current_drag_end_cell[0],self.current_drag_end_cell[1])
            painter.setPen(self.selection_rect_pen)
            painter.setBrush(QColor(0,122,255,30))
            painter.drawRoundedRect(drag_r_virtual,3,3)
        
    def _get_area_base_brush(self,area:DefinedArea,is_selected:bool):
        base_alpha=100 if is_selected else 60
        color_map={
            "Preset Trigger":QColor(52,199,89,base_alpha),
            "Executor Button":QColor(52,199,89,base_alpha -10),
            "Executor Fader":QColor(255,149,0,base_alpha),
            "Slider Control":QColor(255,149,0,base_alpha),
            "Color Picker":QColor(0,122,255,base_alpha),
            "Fixture Control":QColor(175,82,222,base_alpha),
            "Fixture Selector List":QColor(90,200,250,base_alpha),
            "Multi-Group Selector List":QColor(90,200,250,base_alpha-10),
            "Master Cue List":QColor(90,200,250,base_alpha-10),
            "Color Palette":QColor(255,193,7,base_alpha),
            "Loop Palette":QColor(0, 190, 200, base_alpha),
            "Gradient Editor":QColor(120,81,169, base_alpha),
            "Master Intensity":QColor(255,59,48,base_alpha),
            "Toggle Fixture Power":QColor(88,86,214,base_alpha),
            "Flash Fixture":QColor(255,45,85,base_alpha),
            "Sequence Go":QColor(48,209,88,base_alpha),
            "Group Selector": QColor(10, 132, 255, base_alpha),
            "Embedded Stage View": QColor(30, 30, 33, 180 if is_selected else 130),
            "Embedded Timeline": QColor(60, 60, 65, 180 if is_selected else 130),
            "Clock Display": QColor(100, 100, 100, base_alpha + 20),
            "Programmer View": QColor(40, 42, 54, 180 if is_selected else 130),
            "None":QColor(60,60,60,base_alpha-20)
        }
        col=color_map.get(area.function_type,QColor(70,70,70,base_alpha))
        return QBrush(col.lighter(110) if is_selected else col)
    
    def mousePressEvent(self,event:QMouseEvent):
        mouse_pos_local_f = event.position()
        
        child_at_pos = self.childAt(mouse_pos_local_f.toPoint())

        # Path A: Check for special interactive views that need event propagation.
        is_interactive_view_click = False
        widget_to_check = child_at_pos
        while widget_to_check:
            if isinstance(widget_to_check, (EmbeddedStageViewWidget, EmbeddedTimelineWidget)):
                is_interactive_view_click = True
                break
            widget_to_check = widget_to_check.parentWidget()
            if widget_to_check == self:
                break
        
        if is_interactive_view_click:
            if child_at_pos and hasattr(child_at_pos, 'mousePressEvent'):
                 remapped_event = QMouseEvent(event.type(), QPointF(child_at_pos.mapFromParent(event.position().toPoint())), event.globalPosition(), event.button(), event.buttons(), event.modifiers())
                 QApplication.sendEvent(child_at_pos, remapped_event)
                 if remapped_event.isAccepted():
                     return

            super().mousePressEvent(event)
            return

        # Path B/C: Differentiate standard widgets from non-interactive area widgets.
        is_standard_child_widget = False
        is_non_interactive_view_click = False # True for widgets like ClockWidget
        if child_at_pos and child_at_pos != self:
            is_standard_child_widget = True
            widget_to_check = child_at_pos
            while widget_to_check:
                if isinstance(widget_to_check, (ClockWidget, ProgrammerViewWidget, CueListWidget)):
                    is_non_interactive_view_click = True
                    break
                widget_to_check = widget_to_check.parentWidget()
                if widget_to_check == self:
                    break

        # Path B: Handle standard widgets (sliders, buttons), but NOT the non-interactive ones.
        if is_standard_child_widget and not is_non_interactive_view_click:
            if event.button() == Qt.MouseButton.RightButton:
                # Handle context menus for special buttons like palettes
                potential_button = child_at_pos
                while potential_button and potential_button != self:
                    if hasattr(potential_button, "_is_palette_button") and potential_button._is_palette_button:
                        self._show_palette_button_context_menu(potential_button.mapToGlobal(QPoint(0,0)), potential_button)
                        return
                    elif hasattr(potential_button, "_is_loop_palette_button") and potential_button._is_loop_palette_button:
                        self._show_loop_palette_button_context_menu(potential_button.mapToGlobal(QPoint(0,0)), potential_button)
                        return
                    parent_widget = potential_button.parentWidget()
                    if parent_widget == self: break
                    potential_button = parent_widget
            
            super().mousePressEvent(event)
            return
        
        # Path C: The click was on the canvas background or a non-interactive view.
        # Proceed with area selection and creation logic.
        virtual_grid_cell = self._get_grid_cell_from_point(mouse_pos_local_f)
        actual_click_point = mouse_pos_local_f + QPointF(self.canvas_offset_x, self.canvas_offset_y)
        area_under_cursor = None
        for area_item in reversed(self.defined_areas):
            if area_item.rect.contains(actual_click_point.toPoint()):
                area_under_cursor = area_item
                break

        if event.button()==Qt.MouseButton.LeftButton:
            self.is_panning = False
            is_ctrl_pressed = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

            if is_ctrl_pressed and area_under_cursor:
                self.is_dragging = False
                if area_under_cursor in self.multi_selected_areas:
                    self.multi_selected_areas.remove(area_under_cursor)
                else:
                    self.multi_selected_areas.append(area_under_cursor)
                self.select_area_for_panel(None)
            
            elif area_under_cursor:
                self.multi_selected_areas.clear()
                panel_selectable_types = ["None", "Color Palette", "Loop Palette", "Gradient Editor", "Group Selector",
                                          "Fixture Selector List", "Multi-Group Selector List", "Embedded Stage View",
                                          "Embedded Timeline", "Slider Control", "Fixture Control", "Preset Trigger",
                                          "Toggle Fixture Power", "Flash Fixture", "Executor Fader", "Clock Display", "Programmer View",
                                          "Master Cue List"] 
                
                # Also include plugin widgets in selectable types
                panel_selectable_types.extend(self.parent_tab.custom_layout_widgets.keys())

                if not area_under_cursor.embedded_widget or area_under_cursor.function_type in panel_selectable_types:
                    self.select_area_for_panel(area_under_cursor)
                elif area_under_cursor.embedded_widget:
                     self.select_area_for_panel(area_under_cursor)
                self.is_dragging=False
                self.drag_start_cell=None
            
            else:
                self.multi_selected_areas.clear()
                self.select_area_for_panel(None)
                if not self.area_creation_enabled: return
                self.is_dragging=True
                self.drag_start_cell = virtual_grid_cell
                self.current_drag_end_cell = virtual_grid_cell
            
            self.update()


        elif event.button()==Qt.MouseButton.RightButton:
            self.is_dragging = False
            self.is_panning = True
            self.pan_start_mouse_pos = mouse_pos_local_f
            self.pan_start_canvas_offset = QPointF(self.canvas_offset_x, self.canvas_offset_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)


    def mouseMoveEvent(self,event:QMouseEvent):
        mouse_pos_local_f = event.position()
        child_at_pos = self.childAt(mouse_pos_local_f.toPoint())

        if self.is_panning and event.buttons() & Qt.MouseButton.RightButton:
            delta = mouse_pos_local_f - self.pan_start_mouse_pos
            self.canvas_offset_x = self.pan_start_canvas_offset.x() - delta.x()
            self.canvas_offset_y = self.pan_start_canvas_offset.y() - delta.y()
            
            self.update_all_embedded_widget_geometries()
            self.update()
            self.viewOrContentChanged.emit()


        elif self.is_dragging and self.drag_start_cell and self.area_creation_enabled and event.buttons() & Qt.MouseButton.LeftButton:
            self.current_drag_end_cell = self._get_grid_cell_from_point(mouse_pos_local_f)
            self.update()
        else:
            is_embedded_view_internals = False
            current_widget = child_at_pos
            while current_widget:
                if isinstance(current_widget, (EmbeddedStageViewWidget, EmbeddedTimelineWidget)):
                    is_embedded_view_internals = True
                    break
                current_widget = current_widget.parentWidget()
                if current_widget == self: break

            if is_embedded_view_internals:
                if child_at_pos and hasattr(child_at_pos, 'mouseMoveEvent'):
                    remapped_event = QMouseEvent(event.type(), QPointF(child_at_pos.mapFromParent(event.position().toPoint())) , event.globalPosition(), event.button(), event.buttons(), event.modifiers())
                    QApplication.sendEvent(child_at_pos, remapped_event)
                    if remapped_event.isAccepted():
                        return
            super().mouseMoveEvent(event)


    def mouseReleaseEvent(self,event:QMouseEvent):
        mouse_pos_local_f = event.position()
        child_at_pos = self.childAt(mouse_pos_local_f.toPoint())

        if event.button()==Qt.MouseButton.RightButton:
            if self.is_panning:
                self.is_panning = False
                self.unsetCursor()
                pan_distance = (mouse_pos_local_f - self.pan_start_mouse_pos).manhattanLength()
                if pan_distance < self.right_click_drag_threshold:
                    virtual_click_point = mouse_pos_local_f + QPointF(self.canvas_offset_x, self.canvas_offset_y)
                    area_for_menu = None
                    for area_item in reversed(self.defined_areas):
                        if area_item.rect.contains(virtual_click_point.toPoint()):
                            area_for_menu = area_item
                            break
                    if area_for_menu:
                        # Check if right click was on a loop palette button itself
                        clicked_widget = self.childAt(mouse_pos_local_f.toPoint())
                        if hasattr(clicked_widget, "_is_loop_palette_button") and clicked_widget._is_loop_palette_button:
                            self._show_loop_palette_button_context_menu(event.globalPosition().toPoint(), clicked_widget)
                        elif hasattr(clicked_widget, "_is_palette_button") and clicked_widget._is_palette_button:
                             self._show_palette_button_context_menu(event.globalPosition().toPoint(), clicked_widget)
                        else: # General area context menu
                            self._show_area_context_menu(event.globalPosition().toPoint(), area_for_menu)
                    else:
                        if not self.multi_selected_areas:
                            self.select_area_for_panel(None)
                self.update()
                self.viewOrContentChanged.emit()


        elif event.button()==Qt.MouseButton.LeftButton and self.is_dragging and self.drag_start_cell and self.current_drag_end_cell and self.area_creation_enabled:
            self.is_dragging=False
            rect_virtual = self._get_rect_from_grid_cells(
                self.drag_start_cell[0], self.drag_start_cell[1],
                self.current_drag_end_cell[0], self.current_drag_end_cell[1]
            )
            num_cells_w=abs(self.current_drag_end_cell[1]-self.drag_start_cell[1])+1
            num_cells_h=abs(self.current_drag_end_cell[0]-self.drag_start_cell[0])+1
            
            min_w_cells, min_h_cells = self.MIN_CELLS_WIDTH, self.MIN_CELLS_HEIGHT
            
            potential_func_type = self.parent_tab.function_type_combo.currentText()
            if potential_func_type == "Color Picker":
                 min_w_cells, min_h_cells = self.MIN_CELLS_WIDTH_COLORWHEEL, self.MIN_CELLS_HEIGHT_COLORWHEEL
            elif potential_func_type == "Programmer View":
                 min_w_cells, min_h_cells = self.MIN_CELLS_WIDTH_PROGRAMMER, self.MIN_CELLS_HEIGHT_PROGRAMMER
            elif potential_func_type == "Slider Control":
                 min_w_cells, min_h_cells = self.MIN_CELLS_WIDTH_SLIDER, self.MIN_CELLS_HEIGHT_SLIDER
            elif potential_func_type == "Loop Palette":
                 min_w_cells, min_h_cells = self.MIN_CELLS_WIDTH, self.MIN_CELLS_HEIGHT_LOOP_PALETTE
            elif potential_func_type == "Embedded Timeline":
                min_w_cells, min_h_cells = self.MIN_CELLS_WIDTH_TIMELINE, self.MIN_CELLS_HEIGHT_TIMELINE


            if num_cells_w < min_w_cells or num_cells_h < min_h_cells:
                 QMessageBox.information(self, "Area Too Small",
                                         f"Minimum size for the function type '{potential_func_type}' (or default) is {min_w_cells}W x {min_h_cells}H cells.\n"
                                         f"You drew {num_cells_w}W x {num_cells_h}H.")
                 self.drag_start_cell=None; self.current_drag_end_cell=None; self.update(); return

            cells_val = self._get_occupied_cells_for_rect(rect_virtual)
            if self._is_area_overlapping(cells_val):
                QMessageBox.warning(self,"Overlap","Area overlaps with an existing area.")
            else:
                new_area_obj=DefinedArea(rect_virtual,grid_cells=cells_val)
                self.defined_areas.append(new_area_obj)
                self.multi_selected_areas.clear()
                self.select_area_for_panel(new_area_obj)
                self.update_area_widget(new_area_obj)
            
            self.drag_start_cell=None
            self.current_drag_end_cell=None
            self.update()
            self.viewOrContentChanged.emit()
        elif self.is_dragging:
            self.is_dragging = False
            self.drag_start_cell=None
            self.current_drag_end_cell=None
            self.update()
        else:
            is_embedded_view_internals = False
            current_widget = child_at_pos
            while current_widget:
                if isinstance(current_widget, (EmbeddedStageViewWidget, EmbeddedTimelineWidget)):
                    is_embedded_view_internals = True
                    break
                current_widget = current_widget.parentWidget()
                if current_widget == self: break
            
            if is_embedded_view_internals:
                if child_at_pos and hasattr(child_at_pos, 'mouseReleaseEvent'):
                    remapped_event = QMouseEvent(event.type(), QPointF(child_at_pos.mapFromParent(event.position().toPoint())), event.globalPosition(), event.button(), event.buttons(), event.modifiers())
                    QApplication.sendEvent(child_at_pos, remapped_event)
                    if remapped_event.isAccepted():
                        return
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        child_at_pos = self.childAt(event.position().toPoint())
        
        is_embedded_view_internals = False
        current_widget = child_at_pos
        while current_widget:
            if isinstance(current_widget, (EmbeddedStageViewWidget, EmbeddedTimelineWidget)):
                is_embedded_view_internals = True
                break
            current_widget = current_widget.parentWidget()
            if current_widget == self: break

        if is_embedded_view_internals:
            if child_at_pos and hasattr(child_at_pos, 'wheelEvent'):
                local_pos_f = QPointF(child_at_pos.mapFromParent(event.position().toPoint()))
                remapped_event = QWheelEvent(
                    local_pos_f,                  
                    event.globalPosition(),       
                    event.pixelDelta(),           
                    event.angleDelta(),           
                    event.buttons(),              
                    event.modifiers(),            
                    event.phase(),                
                    event.inverted(),             
                    event.source() if hasattr(event, 'source') else Qt.ScrollSource.ScrollSourceMouse
                )
                QApplication.sendEvent(child_at_pos, remapped_event)
                if remapped_event.isAccepted():
                    event.accept() 
                    return
        super().wheelEvent(event)
        
    def _show_area_context_menu(self, global_pos: QPoint, area_under_cursor: DefinedArea):
        menu = QMenu(self)
        
        edit_action = QAction(f"Edit Assignment ({area_under_cursor.display_text[:15]}...)", self)
        edit_action.triggered.connect(lambda: self.select_area_for_panel(area_under_cursor))
        menu.addAction(edit_action)

        delete_action = QAction(f"Delete Area ({area_under_cursor.display_text[:15]}...)", self)
        delete_action.triggered.connect(lambda checked=False, a=area_under_cursor: self.remove_area_and_widget(a))
        menu.addAction(delete_action)

        if self.multi_selected_areas and area_under_cursor in self.multi_selected_areas:
            menu.addSeparator()
            delete_multi_action = QAction(f"Delete {len(self.multi_selected_areas)} Selected Areas", self)
            delete_multi_action.triggered.connect(self.prompt_and_remove_multiple_areas)
            menu.addAction(delete_multi_action)
            
        menu.exec(global_pos)

    def _show_loop_palette_button_context_menu(self, global_pos: QPoint, button_widget: QPushButton):
        area_id = button_widget.property("area_id")
        loop_palette_db_id = button_widget.property("loop_palette_db_id")

        target_area = next((area for area in self.defined_areas if area.id == area_id), None)
        if not target_area or target_area.function_type != "Loop Palette" or loop_palette_db_id is None:
            return

        menu = QMenu(self)
        
        remove_from_area_action = QAction("Remove from this Area", self)
        remove_from_area_action.triggered.connect(lambda: self._remove_loop_from_area(target_area, loop_palette_db_id))
        menu.addAction(remove_from_area_action)
        
        menu.exec(global_pos)

    def _remove_loop_from_area(self, target_area: DefinedArea, loop_palette_db_id_to_remove: int):
        if target_area.function_type == "Loop Palette":
            selected_configs = target_area.data.get('selected_loop_palette_configs', [])
            new_configs = [conf for conf in selected_configs if conf.get('id') != loop_palette_db_id_to_remove]
            
            if len(new_configs) < len(selected_configs):
                target_area.data['selected_loop_palette_configs'] = new_configs
                target_area.data.get('active_loops', {}).pop(str(loop_palette_db_id_to_remove), None)
                
                self.update_area_widget(target_area)
                self.parent_tab.save_defined_areas_to_settings()
                self.viewOrContentChanged.emit()
                QMessageBox.information(self, "Loop Removed", "Loop palette removed from this area.")

    def select_area_for_panel(self,area_to_select:DefinedArea|None):
        if area_to_select is not None:
            self.multi_selected_areas.clear()

        self.currently_selected_area_for_panel=area_to_select
        self.area_selected_for_assignment.emit(area_to_select)
        self.update()
        self.viewOrContentChanged.emit()


    def _get_slider_params_from_type(self, slider_type_str: str) -> tuple[float, float, bool]:
        slider_type_str = slider_type_str.lower()
        if slider_type_str == "intensity": return 0.0, 100.0, False
        elif slider_type_str == "pan": return -180.0, 180.0, True
        elif slider_type_str == "tilt": return -90.0, 90.0, True
        elif slider_type_str == "speed": return 0.0, 100.0, True
        elif slider_type_str == "gobo spin": return 0.0, 255.0, False
        elif slider_type_str == "focus": return 0.0, 1.0, True # CHANGED
        elif slider_type_str == "strobe": return 0.0, 30.0, True
        else: return 0.0, 100.0, False

    def _create_slider_with_input(self, parent_area: DefinedArea, rect_on_canvas: QRect,
                                  orientation: Qt.Orientation,
                                  data_key_value: str, data_key_type_str: str,
                                  signal_to_emit,
                                  min_val=0.0, max_val=100.0, is_double=False
                                 ) -> tuple[QSlider, QSpinBox | QDoubleSpinBox]:
        
        container_for_slider_and_input = QRect(rect_on_canvas)

        slider = QSlider(orientation, self)
        slider.setObjectName(f"slider_{parent_area.id}_{data_key_type_str if data_key_type_str else 'generic'}")
        
        initial_area_value = parent_area.data.get(data_key_value)
        if initial_area_value is None:
            initial_slider_value_to_set_float = (min_val + max_val) / 2.0 if min_val < 0 and max_val > 0 and min_val <=0 <=max_val else min_val
        else:
            initial_slider_value_to_set_float = float(initial_area_value)
        
        scale_factor = 1.0
        if is_double:
            if (max_val - min_val) != 0 and abs(max_val - min_val) <= 20: scale_factor = 10.0
            elif (max_val - min_val) != 0 and abs(max_val - min_val) <= 2: scale_factor = 100.0
        
        # Store properties for later retrieval in sync function
        slider.setProperty("scale_factor", scale_factor)
        slider.setProperty("is_double", is_double)

        qslider_min = int(min_val * scale_factor)
        qslider_max = int(max_val * scale_factor)
        qslider_initial_val = int(initial_slider_value_to_set_float * scale_factor)
        
        slider.setRange(qslider_min, qslider_max)
        slider.setValue(qslider_initial_val)
        
        spinbox_font = QFont(); spinbox_font.setPointSize(8)

        if is_double:
            spinbox = QDoubleSpinBox(self)
            spinbox.setDecimals(1)
            if abs(max_val - min_val) <= 20 and abs(max_val-min_val) > 2 : spinbox.setDecimals(1)
            elif abs(max_val - min_val) <= 2: spinbox.setDecimals(2)
            
            spinbox.setSingleStep(0.1 if abs(max_val - min_val) > 2 else 0.01)
            if data_key_type_str.lower() == "strobe": spinbox.setSingleStep(0.5)
            
            spinbox.setRange(min_val, max_val)
            spinbox.setValue(initial_slider_value_to_set_float)
        else:
            spinbox = QSpinBox(self)
            spinbox.setSingleStep(1)
            spinbox.setRange(int(round(min_val)), int(round(max_val)))
            spinbox.setValue(int(round(initial_slider_value_to_set_float)))


        spinbox.setFont(spinbox_font)
        spinbox.setObjectName(f"spinbox_{parent_area.id}_{data_key_type_str if data_key_type_str else 'generic'}")
        spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        spinbox.setAlignment(Qt.AlignmentFlag.AlignRight)
        spinbox.setSpecialValueText("--")
        
        self._position_slider_and_input_within_container(container_for_slider_and_input, slider, spinbox)
        
        effective_slider_display_range = qslider_max - qslider_min
        tick_interval = effective_slider_display_range // 10
        if tick_interval == 0 and effective_slider_display_range != 0: tick_interval = 1
        elif effective_slider_display_range == 0 : tick_interval = 0
        if tick_interval > 0: slider.setTickPosition(QSlider.TickPosition.TicksBothSides); slider.setTickInterval(tick_interval)

        if is_double:
            spinbox.valueChanged.connect(lambda val_float, sldr=slider, sf=scale_factor: sldr.setValue(int(val_float * sf)))
            slider.valueChanged.connect(lambda val_int, sbox=spinbox, sf=scale_factor: sbox.setValue(float(val_int) / sf if sf != 0 else 0.0))
        else:
            slider.valueChanged.connect(spinbox.setValue)
            spinbox.valueChanged.connect(slider.setValue)
        
        def on_value_changed_from_control(value_from_signal, area=parent_area, key_val=data_key_value, sig_emitter=signal_to_emit, sbox_instance=spinbox, d_key_type=data_key_type_str):
            actual_value_to_store = sbox_instance.value()
            
            self._update_area_data_from_widget(area, key_val, actual_value_to_store)
            if sig_emitter: sig_emitter.emit(area.id, actual_value_to_store, area.data.get(d_key_type, "Generic"))
        
        spinbox.valueChanged.connect(on_value_changed_from_control)
        return slider, spinbox
    
    def _get_palette_button_style(self, button_data: dict, palette_kind: str) -> str:
        base_style = """
            QPushButton {{
                font-size: 7pt; padding: 2px; border-radius: 3px;
                border: 1px solid #444;
                background-color: {bg_color}; color: {text_color};
            }}
            QPushButton:hover {{ border: 1px solid #888; }}
        """
        
        bg_color_str = "transparent"
        text_color_str = "#A0A0A0"

        if palette_kind == "Color":
            color_hex = button_data.get('color_hex')
            if color_hex:
                q_color = QColor(color_hex)
                if q_color.isValid():
                    bg_color_str = q_color.name()
                    brightness = q_color.valueF()
                    text_color_str = "#000000" if brightness > 0.6 else "#FFFFFF"
        elif palette_kind == "Position":
            if button_data.get('params'):
                bg_color_str = "#353538"
                text_color_str = "#D0D0D0"
            else:
                bg_color_str = "transparent"
        
        return base_style.format(bg_color=bg_color_str, text_color=text_color_str)
    
    def _on_direct_palette_button_clicked(self):
        """Replaces the old 'select' logic. This directly applies the palette item."""
        sender_button = self.sender()
        if not isinstance(sender_button, QPushButton): return

        area_id = sender_button.property("palette_area_id")
        button_index = sender_button.property("palette_button_index")
        
        target_area = next((area for area in self.defined_areas if area.id == area_id), None)
        if not target_area or target_area.function_type != "Color Palette": return
        
        target_fixture_ids = self.parent_tab.globally_selected_fixture_ids_for_controls
        if not target_fixture_ids:
            QMessageBox.information(self.parent_tab, "No Fixture Selected", "Select one or more fixtures to apply a palette item.")
            return

        palette_kind = target_area.data.get('palette_kind', 'Color')
        buttons_data = target_area.data.get('buttons_data', [])

        if 0 <= button_index < len(buttons_data):
            btn_data = buttons_data[button_index]
            item_name = btn_data.get('name', f"Item {button_index+1}")

            if palette_kind == "Color":
                color_hex = btn_data.get('color_hex')
                if color_hex and QColor(color_hex).isValid():
                    color = QColor(color_hex)
                    params = {'red': color.red(), 'green': color.green(), 'blue': color.blue()}
                    for fid in target_fixture_ids:
                        self.main_window.update_fixture_data_and_notify(fid, params)
                else:
                    QMessageBox.warning(self, "No Color Stored", f"Button '{item_name}' has no color stored.")
            elif palette_kind == "Position":
                params = btn_data.get('params')
                if params and isinstance(params, dict):
                    for fid in target_fixture_ids:
                        self.main_window.update_fixture_data_and_notify(fid, params)
                else:
                    QMessageBox.warning(self, "No Position Stored", f"Button '{item_name}' has no position data stored.")

    def _show_palette_button_context_menu(self, global_pos: QPoint, button_widget: QPushButton):
        area_id = button_widget.property("palette_area_id")
        button_index = button_widget.property("palette_button_index")
        
        target_area = next((area for area in self.defined_areas if area.id == area_id), None)
        if not target_area or target_area.function_type != "Color Palette": return

        palette_kind = target_area.data.get('palette_kind', 'Color')
        menu = QMenu(self)
        
        store_action_text = f"Store Current Fixture {palette_kind}"
        store_action = QAction(store_action_text, self)
        store_action.triggered.connect(lambda: self._store_current_selection_to_palette_button(target_area, button_index))
        menu.addAction(store_action)

        clear_action = QAction("Clear This Button's Data", self)
        clear_action.triggered.connect(lambda: self._clear_palette_button_data(target_area, button_index))
        menu.addAction(clear_action)
        
        rename_action = QAction("Rename Button", self)
        rename_action.triggered.connect(lambda: self._rename_palette_button(target_area, button_index))
        menu.addAction(rename_action)

        menu.exec(global_pos)

    def _store_current_selection_to_palette_button(self, target_area: DefinedArea, button_index: int):
        selected_fids = self.parent_tab.globally_selected_fixture_ids_for_controls
        if not selected_fids:
            QMessageBox.information(self.parent_tab, "No Fixture Selected", "Select at least one fixture to store its properties.")
            return
        
        first_fid = selected_fids[0]
        palette_kind = target_area.data.get('palette_kind', 'Color')
        
        try:
            cursor = self.main_window.db_connection.cursor()
            data_to_store = {}
            default_name_prefix = "Item"

            if palette_kind == "Color":
                cursor.execute("SELECT red, green, blue FROM fixtures WHERE id=?", (first_fid,))
                row = cursor.fetchone()
                if not row: QMessageBox.warning(self, "Error", f"Could not fetch color for fixture ID {first_fid}."); return
                current_color = QColor(row[0], row[1], row[2])
                data_to_store = {'color_hex': current_color.name()}
                default_name_prefix = "C"
            elif palette_kind == "Position":
                cursor.execute("SELECT x_pos, y_pos, z_pos, rotation_x, rotation_y, rotation_z FROM fixtures WHERE id=?", (first_fid,))
                row = cursor.fetchone()
                if not row: QMessageBox.warning(self, "Error", f"Could not fetch position for fixture ID {first_fid}."); return
                pos_params = {'x_pos': row[0], 'y_pos': row[1], 'z_pos': row[2],
                              'rotation_x': row[3], 'rotation_y': row[4], 'rotation_z': row[5]}
                data_to_store = {'params': pos_params}
                default_name_prefix = "P"
            else:
                QMessageBox.warning(self, "Error", f"Unknown palette kind: {palette_kind}"); return

            default_name = f"{default_name_prefix} {button_index + 1}"
            buttons_data = target_area.data.get('buttons_data', [])
            if 0 <= button_index < len(buttons_data):
                default_name = buttons_data[button_index].get('name', default_name)

            dialog = NamePromptDialog(title=f"Store {palette_kind} Palette Item", current_name=default_name, parent=self)
            if dialog.exec():
                new_name = dialog.get_name()
                if not new_name: new_name = default_name

                if 0 <= button_index < len(buttons_data):
                    buttons_data[button_index]['name'] = new_name
                    buttons_data[button_index].update(data_to_store)
                
                target_area.data['buttons_data'] = buttons_data
                target_area.data['last_active_palette_button_index'] = button_index
                
                self.parent_tab.save_defined_areas_to_settings()
                self.update_area_widget(target_area)
            
        except Exception as e:
            QMessageBox.critical(self, f"Error Storing {palette_kind}", f"Could not store {palette_kind.lower()} data: {e}")
            print(f"Error storing to palette: {e}")


    def _clear_palette_button_data(self, target_area: DefinedArea, button_index: int):
        buttons_data = target_area.data.get('buttons_data', [])
        palette_kind = target_area.data.get('palette_kind', 'Color')

        if 0 <= button_index < len(buttons_data):
            default_name_prefix = "P" if palette_kind == "Position" else "C"
            buttons_data[button_index] = {'name': f"{default_name_prefix} {button_index + 1}"}
            
            target_area.data['buttons_data'] = buttons_data
            
            if target_area.data.get('last_active_palette_button_index') == button_index:
                target_area.data.pop('last_active_palette_button_index', None)
                palette_container_frame = target_area.embedded_widget
                if isinstance(palette_container_frame, QFrame):
                    if hasattr(palette_container_frame, "_preview_widget"):
                        palette_container_frame._preview_widget.update_preview_content(None, palette_kind)
                    setattr(palette_container_frame, '_active_button_widget', None)


            self.parent_tab.save_defined_areas_to_settings()
            self.update_area_widget(target_area)

    def _rename_palette_button(self, target_area: DefinedArea, button_index: int):
        buttons_data = target_area.data.get('buttons_data', [])
        palette_kind = target_area.data.get('palette_kind', 'Color')
        if not (0 <= button_index < len(buttons_data)): return

        default_name_prefix = "P" if palette_kind == "Position" else "C"
        current_name = buttons_data[button_index].get('name', f"{default_name_prefix} {button_index + 1}")
        
        dialog = NamePromptDialog(title="Rename Palette Button", current_name=current_name, parent=self)
        if dialog.exec():
            new_name = dialog.get_name()
            if new_name:
                buttons_data[button_index]['name'] = new_name
                target_area.data['buttons_data'] = buttons_data
                self.parent_tab.save_defined_areas_to_settings()
                self.update_area_widget(target_area)

    def _populate_fixture_list_widget_for_area(self, list_widget: QListWidget, area: DefinedArea):
        list_widget.blockSignals(True)
        list_widget.clear()
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name, fid, sfi FROM fixtures ORDER BY fid, sfi")
            fixtures = cursor.fetchall()
            if not fixtures: list_widget.addItem("No fixtures available."); list_widget.setEnabled(False)
            else:
                list_widget.setEnabled(True)
                for pk_id, name, fid, sfi in fixtures:
                    item = QListWidgetItem(f"{name} ({fid}.{sfi})")
                    item.setData(Qt.ItemDataRole.UserRole, pk_id)
                    list_widget.addItem(item)
                selected_ids_in_main_tab = self.parent_tab.globally_selected_fixture_ids_for_controls
                if self.parent_tab.globally_selected_group_name_for_display is None:
                    selection_model = list_widget.selectionModel()
                    if selection_model:
                        new_selection = QItemSelection()
                        for i in range(list_widget.count()):
                            item_fid = list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                            if item_fid in selected_ids_in_main_tab:
                                model_index = list_widget.model().index(i, 0)
                                new_selection.select(model_index, model_index)
                        selection_model.select(new_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.NoUpdate)
        except Exception as e:
            print(f"Error populating fixture list in area {area.id}: {e}")
            list_widget.addItem("Error loading fixtures.")
            list_widget.setEnabled(False)
        finally:
            list_widget.blockSignals(False)
    
    def _populate_multi_group_list_widget_for_area(self, list_widget: QListWidget, area: DefinedArea):
        list_widget.blockSignals(True)
        list_widget.clear()
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name FROM fixture_groups ORDER BY name")
            groups = cursor.fetchall()
            if not groups:
                list_widget.addItem("No groups available.")
                list_widget.setEnabled(False)
            else:
                list_widget.setEnabled(True)
                for gid, name in groups:
                    item = QListWidgetItem(f"{name} (ID:{gid})")
                    item.setData(Qt.ItemDataRole.UserRole, gid)
                    item.setData(Qt.ItemDataRole.DisplayRole + 1, name)
                    list_widget.addItem(item)
                
                selected_group_ids_in_area = area.data.get('selected_group_ids_in_list', [])
                if selected_group_ids_in_area:
                    selection_model = list_widget.selectionModel()
                    if selection_model:
                        new_selection = QItemSelection()
                        for i in range(list_widget.count()):
                            item_gid = list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                            if item_gid in selected_group_ids_in_area:
                                model_index = list_widget.model().index(i, 0)
                                new_selection.select(model_index, model_index)
                        selection_model.select(new_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.NoUpdate)
        except Exception as e:
            print(f"Error populating multi-group list in area {area.id}: {e}")
            list_widget.addItem("Error loading groups.")
            list_widget.setEnabled(False)
        finally:
            list_widget.blockSignals(False)

    def _on_embedded_list_item_selection_changed(self, list_widget_source: QListWidget):
        selected_ids = []
        selected_items_list = list_widget_source.selectedItems()
        if selected_items_list:
            for item in selected_items_list:
                fid = item.data(Qt.ItemDataRole.UserRole)
                if fid is not None:
                    selected_ids.append(fid)
        
        for area in self.defined_areas:
            if area.embedded_widget == list_widget_source:
                area.data['selected_fixture_ids_in_list'] = selected_ids
                break
        self.embedded_list_fixture_selected.emit(selected_ids)

    def _on_embedded_multi_group_list_selection_changed(self, list_widget_source: QListWidget):
        selected_group_ids = []
        selected_group_names = []
        selected_items_list = list_widget_source.selectedItems()
        if selected_items_list:
            for item in selected_items_list:
                gid = item.data(Qt.ItemDataRole.UserRole)
                gname = item.data(Qt.ItemDataRole.DisplayRole + 1)
                if gid is not None:
                    selected_group_ids.append(gid)
                    if gname: selected_group_names.append(gname)
        
        for area in self.defined_areas:
            if area.embedded_widget == list_widget_source:
                area.data['selected_group_ids_in_list'] = selected_group_ids
                break
        
        self.embedded_multi_group_list_selected.emit(selected_group_ids)


    def refresh_all_fixture_list_areas(self):
        for area in self.defined_areas:
            if area.function_type == "Fixture Selector List" and isinstance(area.embedded_widget, QListWidget):
                self._populate_fixture_list_widget_for_area(area.embedded_widget, area)

    def refresh_all_multi_group_list_areas(self):
        for area in self.defined_areas:
            if area.function_type == "Multi-Group Selector List" and isinstance(area.embedded_widget, QListWidget):
                self._populate_multi_group_list_widget_for_area(area.embedded_widget, area)
        
        self._update_tooltips_for_keybinds() # Also refresh tooltips on buttons

    def _update_tooltips_for_keybinds(self):
        """Iterate through all areas and update tooltips based on current keybind map."""
        for area in self.defined_areas:
            widget = area.embedded_widget
            if not widget: continue

            if area.function_type == "Loop Palette" and isinstance(widget, QFrame):
                if hasattr(widget, "_loop_buttons_map"):
                    for lp_db_id, button in widget._loop_buttons_map.items():
                        base_tooltip = f"Toggle Loop: {button.property('loop_name')}"
                        action_id = f"loop.toggle.{lp_db_id}".replace('.', '_')
                        keybind_str = self.main_window.keybind_map.get(action_id)
                        if keybind_str:
                            button.setToolTip(f"{base_tooltip} ({keybind_str})")
                        else:
                            button.setToolTip(base_tooltip)
            elif isinstance(widget, QPushButton):
                action_id = ""
                tooltip_base_text = widget.toolTip().split(' (')[0] # Get base tooltip without old keybind
                
                if area.function_type == "Preset Trigger":
                    preset_number = area.data.get('preset_number')
                    if preset_number:
                        action_id = f"preset.apply.{preset_number}".replace('.', '_')
                # Add other button types here if they get keybinds...
                
                if action_id:
                    keybind_str = self.main_window.keybind_map.get(action_id)
                    if keybind_str:
                        widget.setToolTip(f"{tooltip_base_text} ({keybind_str})")
                    else:
                        widget.setToolTip(tooltip_base_text)


    def _handle_embedded_fixture_intensity_change(self, area_id: str, fixture_id: int, intensity: int):
        for area_item in self.defined_areas:
            if area_item.id == area_id: area_item.data['fixture_intensity'] = intensity; self.parent_tab.save_defined_areas_to_settings(); self.parent_tab.fixture_parameter_changed_from_area.emit(fixture_id, {"brightness": intensity}); break

    def _handle_embedded_fixture_color_request(self, area_id: str, fixture_id: int):
        for area_item in self.defined_areas:
            if area_item.id == area_id:
                current_color_name = area_item.data.get('fixture_color', "#FFFFFF"); dialog_color = QColorDialog.getColor(QColor(current_color_name), self, f"Select Color for Fixture {area_item.data.get('fixture_name', fixture_id)}")
                if dialog_color.isValid(): area_item.data['fixture_color'] = dialog_color.name();
                if isinstance(area_item.embedded_widget, FixtureControlWidget): area_item.embedded_widget.update_color_button_appearance(dialog_color)
                self.parent_tab.save_defined_areas_to_settings(); params = {"red": dialog_color.red(), "green": dialog_color.green(), "blue": dialog_color.blue()}; self.parent_tab.fixture_parameter_changed_from_area.emit(fixture_id, params)
                break

    def _handle_embedded_color_change(self, target_area: DefinedArea, new_color: QColor):
        if target_area and new_color.isValid():
            target_area.data['current_color'] = new_color.name()
            self.parent_tab.generic_color_activated.emit(target_area.id, new_color, "ColorPicker")
            self.parent_tab.save_defined_areas_to_settings()

    def _handle_apply_gradient_to_selection(self, area_id: str):
        target_area = next((area for area in self.defined_areas if area.id == area_id and area.function_type == "Gradient Editor"), None)
        if not target_area or not isinstance(target_area.embedded_widget, GradientEditorWidget):
            return

        gradient_widget: GradientEditorWidget = target_area.embedded_widget
        selected_fixture_ids = sorted(self.parent_tab.globally_selected_fixture_ids_for_controls)

        if not selected_fixture_ids:
            QMessageBox.information(self.parent_tab, "No Selection", "No fixtures selected to apply gradient.")
            return

        num_selected = len(selected_fixture_ids)
        updated_count = 0

        if num_selected == 1:
            color_at_pos = gradient_widget.getColorAt(0.5)
            params = {'red': color_at_pos.red(), 'green': color_at_pos.green(), 'blue': color_at_pos.blue()}
            self.main_window.update_fixture_data_and_notify(selected_fixture_ids[0], params)
            updated_count = 1
        else:
            for i, fixture_id in enumerate(selected_fixture_ids):
                norm_pos = i / (num_selected - 1.0)
                color_at_pos = gradient_widget.getColorAt(norm_pos)
                params = {'red': color_at_pos.red(), 'green': color_at_pos.green(), 'blue': color_at_pos.blue()}
                self.main_window.update_fixture_data_and_notify(fixture_id, params)
                updated_count +=1
        
        if updated_count > 0:
            QMessageBox.information(self.parent_tab, "Gradient Applied", f"Gradient applied to {updated_count} selected fixture(s).")


    def _handle_embedded_gradient_changed(self, area_id: str, stops: list[tuple[float, QColor]]):
        for area_item in self.defined_areas:
            if area_item.id == area_id:
                area_item.data['gradient_stops'] = [(pos, color.name()) for pos, color in stops]
                self.parent_tab.save_defined_areas_to_settings()
                self.viewOrContentChanged.emit()
                break


    def _update_area_data_from_widget(self,target_area:DefinedArea,data_key:str,value):
        if target_area:
            target_area.data[data_key]=value
            self.parent_tab.save_defined_areas_to_settings()
            self.viewOrContentChanged.emit()

    def update_area_widget(self, area_item: DefinedArea):
        area_item.clear_embedded_widget(self.main_window)
        
        padding = 4
        rect_on_canvas = area_item.rect.translated(int(-self.canvas_offset_x), int(-self.canvas_offset_y))
        widget_area_rect_on_canvas = QRect(rect_on_canvas).adjusted(padding, padding, -padding, -padding)

        func_type = area_item.function_type
        area_data = area_item.data
        label_text_from_area = area_item.display_text
        
        types_needing_label_above = [ 
            "Programmer View", "Master Cue List", "Slider Control", "Master Intensity", "Embedded Stage View", "Embedded Timeline",
            "Color Picker", "Color Palette", "Loop Palette", "Gradient Editor",
            "Fixture Selector List", "Multi-Group Selector List", "Executor Fader"
        ]

        if func_type in types_needing_label_above or func_type in self.parent_tab.custom_layout_widgets:
            area_item.label_widget = QLabel(label_text_from_area.split('\n')[0], self)
            area_item.label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            area_item.label_widget.setStyleSheet("font-size: 8pt; color: #A0A0A0; padding: 1px 0;")
        
        if func_type == "None":
            pass

        elif func_type == "Slider Control":
            orientation = Qt.Orientation.Vertical if area_item.rect.height() > area_item.rect.width() * 1.2 else Qt.Orientation.Horizontal
            s1_type = area_data.get('slider1_type', 'Generic')
            min1, max1, is_d1 = self._get_slider_params_from_type(s1_type)
            area_item.embedded_widget, area_item.input_widget = self._create_slider_with_input(
                area_item, widget_area_rect_on_canvas, orientation,
                'slider1_value', 'slider1_type', self.parent_tab.generic_slider_activated, min1, max1, is_d1
            )
            if area_data.get('enable_dual_sliders'):
                s2_type = area_data.get('slider2_type', 'Generic')
                min2, max2, is_d2 = self._get_slider_params_from_type(s2_type)
                area_item.embedded_widget_2, area_item.input_widget_2 = self._create_slider_with_input(
                    area_item, widget_area_rect_on_canvas, orientation,
                    'slider2_value', 'slider2_type', self.parent_tab.generic_slider_activated, min2, max2, is_d2
                )
        
        elif func_type == "Executor Fader":
            slider = QSlider(Qt.Orientation.Vertical, self)
            slider.setRange(0, 100)
            slider.setValue(area_data.get('value', 100))
            group_id = area_data.get('group_id')
            if group_id is not None:
                slider.valueChanged.connect(lambda value, gid=group_id: self.parent_tab.executor_fader_changed.emit(gid, value))
            area_item.embedded_widget = slider
            
        elif func_type == "Fixture Control":
            fix_id = area_data.get('fixture_id')
            fix_name = area_data.get('fixture_name', 'N/A')
            initial_intensity = area_data.get('fixture_intensity', 100)
            initial_color = area_data.get('fixture_color', "#FFFFFF")
            widget = FixtureControlWidget(fix_id, fix_name, initial_intensity, initial_color, area_item.id, self)
            widget.intensityChanged.connect(lambda f_id, intensity, aid=area_item.id: self._handle_embedded_fixture_intensity_change(aid, f_id, intensity))
            widget.colorButtonClicked.connect(lambda f_id, aid=area_item.id: self._handle_embedded_fixture_color_request(aid, f_id))
            widget.locateFixture.connect(lambda fid, is_on, aid=area_item.id: self.parent_tab.flash_fixture_signal.emit(aid, fid, is_on))
            area_item.embedded_widget = widget
            area_item.label_widget = None

        elif func_type == "Fixture Selector List" or func_type == "Multi-Group Selector List":
            widget = QListWidget(self)
            widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            if func_type == "Fixture Selector List":
                self._populate_fixture_list_widget_for_area(widget, area_item)
                widget.itemSelectionChanged.connect(lambda lw=widget: self._on_embedded_list_item_selection_changed(lw))
            else: # Multi-Group
                self._populate_multi_group_list_widget_for_area(widget, area_item)
                widget.itemSelectionChanged.connect(lambda lw=widget: self._on_embedded_multi_group_list_selection_changed(lw))
            area_item.embedded_widget = widget
        
        elif func_type == "Master Cue List":
            timeline_tab = self.main_window.timeline_tab
            if timeline_tab:
                widget = CueListWidget(self.main_window, timeline_tab, self)
                widget.cue_selected.connect(timeline_tab.go_to_cue_by_number)
                area_item.embedded_widget = widget
            else:
                area_item.set_function("None", {}, "Timeline Unavailable")
        
        elif func_type == "Color Palette":
            container_frame = QFrame(self)
            container_frame.setObjectName(f"PaletteContainer_{area_item.id}")
            container_layout = QVBoxLayout(container_frame)
            container_layout.setContentsMargins(2,2,2,2); container_layout.setSpacing(3)
            
            button_container_frame = QFrame(container_frame)
            button_container_frame.setObjectName(f"PaletteButtonsArea_{area_item.id}")
            container_frame._palette_button_container = button_container_frame

            num_buttons = area_item.data.get('num_buttons', 8)
            buttons_data = area_item.data.get('buttons_data', [])
            palette_kind = area_item.data.get('palette_kind', 'Color')
            cols = area_data.get('num_cols', 4)
            grid_layout = QGridLayout(button_container_frame)
            grid_layout.setSpacing(2)

            container_frame._palette_buttons = []

            for i in range(num_buttons):
                btn_data = buttons_data[i] if i < len(buttons_data) else {'name': f'Item {i+1}'}
                button_text = btn_data.get('name', f'Item {i+1}')
                btn = QPushButton(button_text[:6] + ".." if len(button_text) > 6 else button_text)
                btn.setToolTip(button_text)
                btn.setProperty("palette_area_id", area_item.id)
                btn.setProperty("palette_button_index", i)
                btn._is_palette_button = True
                btn.setMinimumHeight(22)
                btn.setStyleSheet(self._get_palette_button_style(btn_data, palette_kind))
                btn.clicked.connect(self._on_direct_palette_button_clicked)
                
                grid_layout.addWidget(btn, i // cols, i % cols)
                container_frame._palette_buttons.append(btn)
            
            button_container_frame.setLayout(grid_layout)
            container_layout.addWidget(button_container_frame, 1)

            area_item.embedded_widget = container_frame

        elif func_type == "Loop Palette":
            container_frame = QFrame(self)
            container_frame.setObjectName(f"LoopPaletteContainer_{area_item.id}")
            container_layout = QVBoxLayout(container_frame)
            container_layout.setContentsMargins(2,2,2,2)
            container_layout.setSpacing(3)

            button_container_inner = QFrame(container_frame)
            button_container_inner.setObjectName(f"LoopPaletteButtonsInner_{area_item.id}")
            container_frame._loop_button_container = button_container_inner

            selected_loop_configs = area_data.get('selected_loop_palette_configs', [])
            
            num_buttons = len(selected_loop_configs)
            cols = area_data.get('num_cols', 2)
            grid_layout = QGridLayout(button_container_inner)
            grid_layout.setSpacing(3)

            container_frame._loop_buttons_map = {}

            for i, loop_config_item in enumerate(selected_loop_configs):
                loop_db_id = loop_config_item.get("id")
                loop_name = loop_config_item.get("name", f"LoopDB_{loop_db_id}")
                display_text = loop_config_item.get("display_text", loop_name[:10])
                
                btn = QPushButton(display_text)
                base_tooltip = f"Toggle Loop: {loop_name}"
                action_id = f"loop.toggle.{loop_db_id}".replace('.', '_')
                keybind_str = self.main_window.keybind_map.get(action_id)
                if keybind_str:
                    base_tooltip += f" ({keybind_str})"
                btn.setToolTip(base_tooltip)

                btn.setCheckable(True)
                btn.setProperty("area_id", area_item.id)
                btn.setProperty("loop_palette_db_id", loop_db_id)
                btn.setProperty("loop_name", loop_name)
                btn._is_loop_palette_button = True
                btn.setMinimumHeight(25)

                is_active = area_item.data.get('active_loops', {}).get(str(loop_db_id), False)
                btn.setChecked(is_active)
                
                btn.toggled.connect(lambda checked, area_id_prop=area_item.id, lp_db_id=loop_db_id:
                                    self.parent_tab.loop_palette_triggered.emit(area_id_prop, lp_db_id, checked))
                
                grid_layout.addWidget(btn, i // cols, i % cols)
                container_frame._loop_buttons_map[loop_db_id] = btn
            
            button_container_inner.setLayout(grid_layout)
            container_layout.addWidget(button_container_inner, 1)
            area_item.embedded_widget = container_frame


        elif func_type == "Gradient Editor":
            widget = GradientEditorWidget(self)
            stops_data = area_data.get('gradient_stops', [(0.0, "#000000"), (1.0, "#FFFFFF")])
            stops_for_widget = [(pos, QColor(hex_col)) for pos, hex_col in stops_data]
            widget.set_gradient_stops(stops_for_widget)
            widget.gradientChanged.connect(lambda stops, aid=area_item.id: self._handle_embedded_gradient_changed(aid, stops))
            widget.applyGradientClicked.connect(lambda aid=area_item.id: self._handle_apply_gradient_to_selection(aid))
            area_item.embedded_widget = widget

        elif func_type == "Color Picker":
            initial_color_str = area_data.get('current_color', QColor(Qt.GlobalColor.white).name())
            widget = CustomColorWheelWidget(QColor(initial_color_str), self)
            widget.colorChanged.connect(lambda color, area=area_item: self._handle_embedded_color_change(area, color))
            area_item.embedded_widget = widget

        elif func_type == "Master Intensity":
            orientation = Qt.Orientation.Vertical if area_item.rect.height() > area_item.rect.width() * 1.2 else Qt.Orientation.Horizontal
            initial_val = area_data.get('current_value', self.main_window.master_fader.value())
            slider, spinbox = self._create_slider_with_input(
                area_item, widget_area_rect_on_canvas, orientation,
                'current_value', 'MasterIntensity', None, 0, 100, False
            )
            spinbox.valueChanged.connect(self.parent_tab.master_intensity_changed)
            area_item.embedded_widget = slider
            area_item.input_widget = spinbox
            if isinstance(area_item.input_widget, QSpinBox): area_item.input_widget.setValue(initial_val)

        elif func_type in ["Preset Trigger", "Toggle Fixture Power", "Flash Fixture", "Sequence Go", "Group Selector", "Executor Button"]:
            widget = QPushButton(label_text_from_area, self)
            tooltip_base_text = label_text_from_area.replace('\n', ' ')
            widget.setProperty("area_id", area_item.id)
            
            if func_type == "Preset Trigger":
                preset_number = area_data.get('preset_number')
                widget.clicked.connect(lambda checked=False, p_num=preset_number: self.parent_tab.preset_triggered.emit(p_num) if p_num else None)
                action_id = f"preset.apply.{preset_number}".replace('.', '_')
                keybind_str = self.main_window.keybind_map.get(action_id)
                if keybind_str:
                    tooltip_base_text += f" ({keybind_str})"
            elif func_type == "Executor Button":
                 # widget.clicked.connect(lambda checked=False, area_id_prop=widget.property("area_id"): self.parent_tab._handle_executor_button_clicked(area_id_prop))
                 pass # No handler yet
            elif func_type == "Toggle Fixture Power":
                widget.setCheckable(True)
                widget.setChecked(area_item.data.get('is_on', False))
                # widget.toggled.connect(
                #    lambda checked, aid=area_item.id, fid=area_data.get('fixture_id'):
                #    self.parent_tab._handle_toggle_fixture_power_button_toggled(aid, fid, checked)
                #)
            elif func_type == "Flash Fixture":
                widget.pressed.connect(lambda aid=area_item.id, fid=area_data.get('fixture_id'): self.parent_tab.flash_fixture_signal.emit(aid, fid, True))
                widget.released.connect(lambda aid=area_item.id, fid=area_data.get('fixture_id'): self.parent_tab.flash_fixture_signal.emit(aid, fid, False))
            elif func_type == "Sequence Go":
                widget.clicked.connect(lambda checked=False, aid=area_item.id: self.parent_tab.sequence_go_signal.emit(aid))
            elif func_type == "Group Selector":
                group_id = area_data.get('group_id')
                group_name = area_data.get('group_name', 'N/A')
                btn_text = group_name[:15] + "..." if len(group_name) > 15 else group_name
                widget.setText(btn_text)
                tooltip_base_text = f"Select Fixture Group: {group_name} (ID: {area_item.data.get('group_id', 'N/A')})"
                widget.setEnabled(group_id is not None)
                widget.clicked.connect(lambda checked=False, gid=group_id: self.parent_tab._handle_group_selector_button_clicked(gid))
            
            widget.setToolTip(tooltip_base_text)
            area_item.embedded_widget = widget
        
        elif func_type == "Embedded Stage View":
            gl_widget_container = EmbeddedStageViewWidget(self.main_window, area_item.id, self)
            # Restore saved camera state
            gl_widget_container.opengl_scene.camera_x_angle = area_data.get('camera_x_angle', 20.0)
            gl_widget_container.opengl_scene.camera_y_angle = area_data.get('camera_y_angle', -45.0)
            gl_widget_container.opengl_scene.camera_zoom_distance = area_data.get('camera_zoom', 20.0)
            gl_widget_container.opengl_scene.camera_target = np.array(area_data.get('camera_target', [0.0, 0.5, 0.0]))

            gl_widget_container.set_show_beams(area_data.get('show_beams', True))
            area_item.embedded_widget = gl_widget_container
            
        elif func_type == "Embedded Timeline":
            timeline_tab = self.main_window.timeline_tab if hasattr(self.main_window, 'timeline_tab') else None
            if timeline_tab:
                widget = EmbeddedTimelineWidget(timeline_tab, area_item.id, self)
                # Connect signals from the embedded widget to the main timeline tab's slots
                widget.go_pressed.connect(timeline_tab.toggle_playback)
                widget.stop_pressed.connect(timeline_tab.stop_playback)
                widget.prev_pressed.connect(timeline_tab._go_to_previous_cue)
                widget.next_pressed.connect(timeline_tab._go_to_next_cue)
                if hasattr(widget, 'view'): # The new view attribute
                    widget.view.playhead_scrubbed.connect(timeline_tab.handle_playhead_seek_by_user)
                # Connect signals from the main timeline tab to the embedded widget's slots
                if hasattr(timeline_tab, 'playback_state_changed_for_embedded'):
                    timeline_tab.playback_state_changed_for_embedded.connect(widget.update_playback_state)
                if hasattr(timeline_tab, 'content_or_playhead_changed_for_embedded'):
                    timeline_tab.content_or_playhead_changed_for_embedded.connect(widget.update_view)
                area_item.embedded_widget = widget
            else:
                area_item.set_function("None", {}, "Timeline Unavailable")
        
        elif func_type == "Clock Display":
            widget = ClockWidget(self)
            show_24h = area_data.get('show_24_hour', True)
            show_ms = area_data.get('show_milliseconds', False)
            widget.setConfig(show_24h, show_ms)
            area_item.embedded_widget = widget
            area_item.label_widget = None
            
        elif func_type == "Programmer View":
            widget = ProgrammerViewWidget(self.main_window, area_item.id, self)
            widget.parent_tab = self.parent_tab
            self.parent_tab.global_fixture_selection_changed.connect(widget.update_view)
            self.main_window.fixture_data_globally_changed.connect(widget.handle_single_fixture_update)
            widget.update_view(self.parent_tab.globally_selected_fixture_ids_for_controls)
            area_item.embedded_widget = widget

        else: # Check for custom plugin widgets
            if func_type in self.parent_tab.custom_layout_widgets:
                creation_callback = self.parent_tab.custom_layout_widgets[func_type]
                try:
                    widget = creation_callback(self, area_item.data)
                    area_item.embedded_widget = widget
                except Exception as e:
                    print(f"Error creating plugin widget '{func_type}': {e}")
                    area_item.set_function("None", {}, f"Plugin Error:\n{func_type}")


        if area_item.label_widget:
            area_item.label_widget.setParent(self)
            area_item.label_widget.setVisible(True)
        if area_item.embedded_widget:
            area_item.embedded_widget.setParent(self)
            area_item.embedded_widget.setVisible(True)
        if area_item.input_widget:
            area_item.input_widget.setParent(self)
            area_item.input_widget.setVisible(True)
        if area_item.embedded_widget_2:
            area_item.embedded_widget_2.setParent(self)
            area_item.embedded_widget_2.setVisible(True)
        if area_item.input_widget_2:
            area_item.input_widget_2.setParent(self)
            area_item.input_widget_2.setVisible(True)
            
        self.update_all_embedded_widget_geometries()
        self.parent_tab.overview_widget.raise_()
        self.update()
    
    def update_area_properties_and_widget(self,area_id,func_type,data):
        for current_area_obj in self.defined_areas:
            if current_area_obj.id==area_id:
                old_func_type=current_area_obj.function_type
                old_palette_kind = current_area_obj.data.get('palette_kind') if old_func_type == "Color Palette" else None
                old_num_buttons = current_area_obj.data.get('num_buttons') if old_func_type == "Color Palette" else None
                
                old_data_copy_for_comparison = current_area_obj.data.copy() # Get copy BEFORE set_function

                old_dual_state = current_area_obj.data.get('enable_dual_sliders',False)
                
                types_needing_label_above = [ 
                    "Programmer View", "Master Cue List", "Slider Control", "Master Intensity", "Embedded Stage View", "Embedded Timeline",
                    "Color Picker", "Color Palette", "Loop Palette", "Gradient Editor",
                    "Fixture Selector List", "Multi-Group Selector List", "Executor Fader"
                ]
                
                current_area_obj.set_function(func_type,data)
                
                widget_type_matches=False;expected_types=self.get_widget_type_for_function(func_type)
                if current_area_obj.embedded_widget and expected_types:
                    if type(current_area_obj.embedded_widget) in expected_types:widget_type_matches=True
                
                is_now_dual=func_type=="Slider Control" and data.get('enable_dual_sliders',False); was_dual_for_comparison = old_dual_state
                
                new_loop_palette_selection = data.get('selected_loop_palette_configs') if func_type == "Loop Palette" else None
                new_loop_palette_num_cols = data.get('num_cols') if func_type == "Loop Palette" else 2
                
                loop_palette_config_changed = (func_type == "Loop Palette" and
                                              (old_data_copy_for_comparison.get('selected_loop_palette_configs') != new_loop_palette_selection or
                                               old_data_copy_for_comparison.get('num_cols', 2) != new_loop_palette_num_cols))


                recreate_widget = (
                    func_type != old_func_type or
                    not current_area_obj.embedded_widget or
                    (not current_area_obj.label_widget and func_type in (types_needing_label_above + list(self.parent_tab.custom_layout_widgets.keys())) ) or
                    not widget_type_matches or
                    (func_type == "Slider Control" and is_now_dual != was_dual_for_comparison) or
                    (func_type == "Fixture Control" and old_func_type == "Fixture Control" and data.get('fixture_id') != old_data_copy_for_comparison.get('fixture_id')) or
                    (func_type == "Color Palette" and (data.get('palette_kind') != old_palette_kind or data.get('num_buttons') != old_num_buttons )) or
                    (func_type == "Loop Palette" and (old_func_type != "Loop Palette" or loop_palette_config_changed))
                )
                                
                if recreate_widget:
                    self.update_area_widget(current_area_obj)
                else: # Only update properties, don't recreate the whole widget
                    if current_area_obj.label_widget:
                         current_area_obj.label_widget.setText(current_area_obj.display_text.split('\n')[0])

                    if isinstance(current_area_obj.embedded_widget, QSlider) and current_area_obj.input_widget:
                        val = data.get('slider1_value')
                        if val is not None:
                            current_area_obj.embedded_widget.blockSignals(True)
                            current_area_obj.input_widget.blockSignals(True)
                            s1_type = current_area_obj.data.get('slider1_type', 'Generic')
                            _m, _x, is_d = self._get_slider_params_from_type(s1_type)
                            if is_d:
                                current_area_obj.input_widget.setValue(float(val))
                            else:
                                current_area_obj.input_widget.setValue(int(val))
                            current_area_obj.embedded_widget.blockSignals(False)
                            current_area_obj.input_widget.blockSignals(False)
                    if isinstance(current_area_obj.embedded_widget_2,QSlider) and current_area_obj.input_widget_2:
                        val = data.get('slider2_value')
                        if val is not None:
                            current_area_obj.embedded_widget_2.blockSignals(True)
                            current_area_obj.input_widget_2.blockSignals(True)
                            s2_type = current_area_obj.data.get('slider2_type', 'Generic')
                            _m, _x, is_d = self._get_slider_params_from_type(s2_type)
                            if is_d:
                                current_area_obj.input_widget_2.setValue(float(val))
                            else:
                                current_area_obj.input_widget_2.setValue(int(val))
                            current_area_obj.embedded_widget_2.blockSignals(False)
                            current_area_obj.input_widget_2.blockSignals(False)
                    elif isinstance(current_area_obj.embedded_widget,CustomColorWheelWidget):
                        if 'current_color' in data: current_area_obj.embedded_widget.setColor(QColor(data.get('current_color')))
                    elif isinstance(current_area_obj.embedded_widget,FixtureControlWidget):
                        if 'fixture_intensity' in data: current_area_obj.embedded_widget.set_intensity(data.get('fixture_intensity',100),True)
                        if 'fixture_color' in data: current_area_obj.embedded_widget.update_color_button_appearance(QColor(data.get('fixture_color',"#FFFFFF")))
                        if data.get('fixture_name') and hasattr(current_area_obj.embedded_widget, 'name_label'): current_area_obj.embedded_widget.name_label.setText(data.get('fixture_name','N/A')[:12]); current_area_obj.embedded_widget.name_label.setToolTip(data.get('fixture_name','N/A'))
                    elif isinstance(current_area_obj.embedded_widget, GradientEditorWidget):
                        if 'gradient_stops' in data:
                            stops_for_widget = [(pos, QColor(hex_col)) for pos, hex_col in data.get('gradient_stops', [])]
                            current_area_obj.embedded_widget.set_gradient_stops(stops_for_widget)
                    elif isinstance(current_area_obj.embedded_widget, QPushButton) and func_type == "Group Selector":
                        group_name = data.get('group_name', "N/A Group")
                        btn_text = group_name[:15] + "..." if len(group_name) > 15 else group_name
                        current_area_obj.embedded_widget.setText(btn_text)
                        current_area_obj.embedded_widget.setToolTip(f"Select Fixture Group: {group_name} (ID: {current_area_obj.data.get('group_id', 'N/A')})")
                        current_area_obj.embedded_widget.setEnabled(current_area_obj.data.get('group_id') is not None)
                    elif isinstance(current_area_obj.embedded_widget, EmbeddedStageViewWidget):
                        current_area_obj.embedded_widget.update_all_fixtures()
                        if 'show_beams' in data:
                            current_area_obj.embedded_widget.set_show_beams(data.get('show_beams', True))
                    elif isinstance(current_area_obj.embedded_widget, ClockWidget):
                        show_24h = data.get('show_24_hour', True)
                        show_ms = data.get('show_milliseconds', False)
                        current_area_obj.embedded_widget.setConfig(show_24h, show_ms)
                    elif isinstance(current_area_obj.embedded_widget, QPushButton):
                        current_area_obj.embedded_widget.setText(current_area_obj.display_text)
                        current_area_obj.embedded_widget.setToolTip(current_area_obj.display_text.replace('\n', ' '))


                self.update()
                self.viewOrContentChanged.emit()
                return True
        return False

    def get_widget_type_for_function(self,func_type_str):
        if func_type_str == "Programmer View": return [ProgrammerViewWidget]
        if func_type_str == "Master Cue List": return [CueListWidget]
        if func_type_str in ["Slider Control","Master Intensity", "Executor Fader"]:return[QSlider]
        if func_type_str=="Color Picker":return[CustomColorWheelWidget]
        if func_type_str=="Fixture Control": return [FixtureControlWidget]
        if func_type_str=="Fixture Selector List": return [QListWidget]
        if func_type_str=="Multi-Group Selector List": return [QListWidget]
        if func_type_str=="Color Palette": return [QFrame]
        if func_type_str=="Loop Palette": return [QFrame]
        if func_type_str=="Gradient Editor": return [GradientEditorWidget]
        if func_type_str=="Embedded Stage View": return[EmbeddedStageViewWidget]
        if func_type_str=="Embedded Timeline": return[EmbeddedTimelineWidget]
        if func_type_str == "Clock Display": return [ClockWidget] 
        if func_type_str in["Preset Trigger","Toggle Fixture Power","Flash Fixture","Sequence Go", "Group Selector", "Executor Button"]:return[QPushButton]
        
        # Check for plugin widgets
        if func_type_str in self.parent_tab.custom_layout_widgets:
            # We can't know the exact type, so we return a generic QWidget.
            # This is a reasonable fallback for type checking.
            return [QWidget]

        return[]

    def remove_area_and_widget(self,area_to_remove:DefinedArea):
        if QMessageBox.question(self,"Confirm Removal",f"Remove '{area_to_remove.display_text}'?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.No:return
        area_to_remove.clear_embedded_widget(self.main_window)
        self.defined_areas=[a for a in self.defined_areas if a.id!=area_to_remove.id]
        
        if area_to_remove in self.multi_selected_areas:
            self.multi_selected_areas.remove(area_to_remove)

        if self.currently_selected_area_for_panel and self.currently_selected_area_for_panel.id==area_to_remove.id:
            self.select_area_for_panel(None)
        
        if not self.multi_selected_areas and not self.currently_selected_area_for_panel:
            self.parent_tab.handle_area_selected_for_panel(None)

        self.parent_tab.save_defined_areas_to_settings()
        self.update()
        self.viewOrContentChanged.emit()

    def prompt_and_remove_multiple_areas(self):
        if not self.multi_selected_areas:
            return
        
        num_to_delete = len(self.multi_selected_areas)
        reply = QMessageBox.question(self, "Confirm Multiple Removal",
                                     f"Are you sure you want to remove these {len(self.multi_selected_areas)} selected areas?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            areas_to_delete_copy = list(self.multi_selected_areas)
            for area in areas_to_delete_copy:
                area.clear_embedded_widget(self.main_window)
                if area in self.defined_areas:
                    self.defined_areas.remove(area)
            
            self.multi_selected_areas.clear()
            if self.currently_selected_area_for_panel in areas_to_delete_copy:
                 self.select_area_for_panel(None)
            
            self.parent_tab.save_defined_areas_to_settings()
            self.update()
            self.viewOrContentChanged.emit()


    def get_all_areas_data_for_saving(self)->dict:
        areas_list = []
        for a in self.defined_areas:
            # For EmbeddedStageViewWidget, ensure camera state is current before saving
            if a.function_type == "Embedded Stage View" and isinstance(a.embedded_widget, EmbeddedStageViewWidget):
                scene = a.embedded_widget.opengl_scene
                if scene:
                    a.data['camera_x_angle'] = scene.camera_x_angle
                    a.data['camera_y_angle'] = scene.camera_y_angle
                    a.data['camera_zoom'] = scene.camera_zoom_distance
                    a.data['camera_target'] = scene.camera_target.tolist()

            areas_list.append({
                'id': a.id,
                'rect_tuple': (a.rect.x(), a.rect.y(), a.rect.width(), a.rect.height()),
                'grid_cells_list': list(a.grid_cells),
                'function_type': a.function_type,
                'data': a.data
            })
        
        return {
            'areas': areas_list,
            'canvas_offset_x': self.canvas_offset_x,
            'canvas_offset_y': self.canvas_offset_y
        }


    def load_areas_from_data(self,areas_data_list:list[dict]):
        for current_area_obj in self.defined_areas:
            current_area_obj.clear_embedded_widget(self.main_window)
        self.defined_areas.clear()
        self.multi_selected_areas.clear()

        for item in areas_data_list:
            try:
                r_t=item['rect_tuple']
                g_c_l=item.get('grid_cells_list',[])
                rect_val=QRect(r_t[0],r_t[1],r_t[2],r_t[3])
                cells_val=set(map(tuple,g_c_l))
                if not cells_val and rect_val.isValid():
                    cells_val=self._get_occupied_cells_for_rect(rect_val)
                loaded_area_obj=DefinedArea(rect_val,area_id=item['id'],grid_cells=cells_val)
                
                data_to_load = item.get('data', {})
                if item.get('function_type') == 'Color Palette':
                    current_data_dict = item.get('data', {})
                    if 'palette_kind' not in current_data_dict:
                        current_data_dict['palette_kind'] = 'Color'
                    data_to_load = current_data_dict
                elif item.get('function_type') == 'Loop Palette':
                     current_data_dict = item.get('data',{})
                     if 'selected_loop_palette_configs' not in current_data_dict:
                         if 'loops' in current_data_dict and isinstance(current_data_dict['loops'], list):
                              current_data_dict['selected_loop_palette_configs'] = [
                                  {"id": None, "name": loop.get("name"), "display_text": loop.get("display_text"), "config": {}}
                                  for loop in current_data_dict['loops']
                              ]
                              current_data_dict.pop('loops', None)
                         else:
                            current_data_dict['selected_loop_palette_configs'] = []
                     if 'active_loops' not in current_data_dict:
                         current_data_dict['active_loops'] = {}
                     if 'num_cols' not in current_data_dict:
                        current_data_dict['num_cols'] = 2
                     data_to_load = current_data_dict


                loaded_area_obj.set_function(item.get('function_type',"None"), data_to_load)
                self.defined_areas.append(loaded_area_obj)
                self.update_area_widget(loaded_area_obj)
            except Exception as e:
                print(f"Error loading area item {item.get('id','UNKNOWN')}:{e}")
        
        self.select_area_for_panel(None)
        self.update()
        self.viewOrContentChanged.emit()
