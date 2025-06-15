
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QLineEdit, QDoubleSpinBox, QColorDialog, QSizePolicy,
                             QFormLayout, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QLineF, QMarginsF
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QPen, QBrush, QMouseEvent, QPalette

import math

class GradientStop:
    def __init__(self, position: float, color: QColor):
        self.position = max(0.0, min(1.0, position)) # Clamp position to 0.0-1.0
        self.color = color

    def __lt__(self, other):
        if not isinstance(other, GradientStop):
            return NotImplemented
        return self.position < other.position

class _GradientDisplayWidget(QWidget):
    # Internal signals for interaction
    stopSelected = pyqtSignal(GradientStop, int) # stop_object, index
    newStopRequested = pyqtSignal(float) # position
    stopMoved = pyqtSignal(int, float) # index, new_position

    def __init__(self, editor_widget: 'GradientEditorWidget', parent=None):
        super().__init__(parent)
        self.editor_widget = editor_widget
        self.setMinimumHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

        self._gradient_bar_rect = QRectF()
        self._stop_width = 6.0  
        self._stop_height_factor = 1.4 
        self._selected_stop_index: int | None = None
        self._dragging_stop_index: int | None = None
        self._drag_offset_x: float = 0.0

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, palette.color(QPalette.ColorRole.Base))
        self.setAutoFillBackground(True)
        self.setPalette(palette)


    def _calculate_geometry(self):
        padding_y = int(self._stop_width) 
        padding_x = int(self._stop_width / 2 + 3)
        
        temp_rect = self.rect() 
        adjusted_rect = temp_rect.adjusted(padding_x, padding_y + 3, -padding_x, -(padding_y + 3) )
        self._gradient_bar_rect = QRectF(adjusted_rect) 
        self._gradient_bar_rect.setHeight(max(10.0, self.height() - 2 * float(padding_y + 3) ))


    def select_stop(self, index: int | None):
        old_selection = self._selected_stop_index
        self._selected_stop_index = index # Update internal state first

        if old_selection != index: # Only proceed if selection actually changed
            if index is not None and 0 <= index < len(self.editor_widget.get_stops()):
                # A valid stop is selected, emit its details
                self.stopSelected.emit(self.editor_widget.get_stops()[index], index)
            else:
                # No valid stop is selected (index is None or out of bounds)
                # Directly inform the editor widget to handle deselection.
                self.editor_widget._on_stop_selected_from_display(None, -1)
            self.update()
    
    def get_selected_stop_index(self) -> int | None:
        return self._selected_stop_index

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._calculate_geometry()
        if not self._gradient_bar_rect.isValid() or self._gradient_bar_rect.width() <= 0:
            return

        gradient = QLinearGradient(self._gradient_bar_rect.topLeft(), self._gradient_bar_rect.topRight())
        stops_list = self.editor_widget.get_stops()
        for stop_item in stops_list:
            gradient.setColorAt(stop_item.position, stop_item.color)
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen) 
        painter.drawRoundedRect(self._gradient_bar_rect, 5.0, 5.0)

        stop_display_height = self._gradient_bar_rect.height() * self._stop_height_factor
        stop_display_half_width = self._stop_width / 2.0

        for i, stop_item in enumerate(stops_list):
            cx = self._gradient_bar_rect.left() + stop_item.position * self._gradient_bar_rect.width()
            rect_top = self._gradient_bar_rect.center().y() - (stop_display_height / 2.0)
            
            stop_rect = QRectF(cx - stop_display_half_width, 
                               rect_top,
                               self._stop_width, 
                               stop_display_height)

            painter.setBrush(QBrush(stop_item.color))
            
            if i == self._selected_stop_index:
                pen = QPen(QColor("white"), 2.0) 
                painter.setPen(pen)
            else:
                pen = QPen(QColor(50,50,50), 1.0)
                painter.setPen(pen)
            
            painter.drawRoundedRect(stop_rect, 2.0, 2.0)


    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            clicked_stop_index = self._get_stop_at_point(pos)

            if clicked_stop_index is not None:
                self.select_stop(clicked_stop_index) # This will emit if selection changes to a valid stop
                if clicked_stop_index != 0 and clicked_stop_index != len(self.editor_widget.get_stops()) - 1:
                    self._dragging_stop_index = clicked_stop_index
                    stop_x_pos = self._gradient_bar_rect.left() + self.editor_widget.get_stops()[clicked_stop_index].position * self._gradient_bar_rect.width()
                    self._drag_offset_x = stop_x_pos - pos.x()
                else:
                    self._dragging_stop_index = None 
            elif self._gradient_bar_rect.contains(pos): 
                if self._gradient_bar_rect.width() > 0:
                    relative_pos = (pos.x() - self._gradient_bar_rect.left()) / self._gradient_bar_rect.width()
                    relative_pos = max(0.0, min(1.0, relative_pos)) 
                    self.newStopRequested.emit(relative_pos)
            else: 
                 if self._selected_stop_index is not None: # If something was selected
                    self.select_stop(None) # Trigger deselection logic


    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging_stop_index is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if self._gradient_bar_rect.width() > 0:
                new_x = event.position().x() + self._drag_offset_x
                new_relative_pos = (new_x - self._gradient_bar_rect.left()) / self._gradient_bar_rect.width()
                
                stops = self.editor_widget.get_stops()
                lower_bound = 0.001 
                upper_bound = 0.999
                
                if self._dragging_stop_index > 0:
                    lower_bound = stops[self._dragging_stop_index - 1].position + 0.001
                if self._dragging_stop_index < len(stops) - 2: 
                    upper_bound = stops[self._dragging_stop_index + 1].position - 0.001
                
                clamped_pos = max(lower_bound, min(upper_bound, new_relative_pos))
                clamped_pos = max(0.0, min(1.0, clamped_pos)) 

                self.stopMoved.emit(self._dragging_stop_index, clamped_pos)
                self.update() 

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragging_stop_index is not None:
                self._dragging_stop_index = None


    def _get_stop_at_point(self, point: QPointF) -> int | None:
        if not self._gradient_bar_rect.isValid(): return None
        
        stop_display_height = self._gradient_bar_rect.height() * self._stop_height_factor
        stop_display_half_width = self._stop_width / 2.0
        clickable_half_width = stop_display_half_width * 1.5 
        clickable_height = stop_display_height * 1.2


        for i, stop in enumerate(self.editor_widget.get_stops()):
            stop_center_x = self._gradient_bar_rect.left() + stop.position * self._gradient_bar_rect.width()
            stop_display_center_y = self._gradient_bar_rect.center().y() 

            clickable_rect = QRectF(stop_center_x - clickable_half_width,
                                    stop_display_center_y - (clickable_height / 2.0),
                                    clickable_half_width * 2,
                                    clickable_height)
            
            if clickable_rect.contains(point):
                return i
        return None

class GradientEditorWidget(QWidget):
    gradientChanged = pyqtSignal(list) 
    applyGradientClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stops: list[GradientStop] = []
        self._selected_stop_object: GradientStop | None = None
        self._selected_stop_index_in_list: int = -1

        self._init_ui()
        self.set_gradient_stops([
            GradientStop(0.0, QColor(Qt.GlobalColor.black)),
            GradientStop(1.0, QColor(Qt.GlobalColor.white))
        ])
        if self._stops: 
            self._gradient_display.select_stop(0)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5,5,5,5)
        main_layout.setSpacing(8)

        self._gradient_display = _GradientDisplayWidget(self)
        main_layout.addWidget(self._gradient_display)

        controls_widget = QWidget() 
        controls_main_layout = QVBoxLayout(controls_widget)
        controls_main_layout.setContentsMargins(0,0,0,0)
        controls_main_layout.setSpacing(6)

        controls_form_layout = QFormLayout()
        controls_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._color_hex_edit = QLineEdit()
        self._color_hex_edit.setMaxLength(7) 
        self._color_hex_edit.editingFinished.connect(self._on_hex_edited)

        self._color_button = QPushButton("Choose Color...")
        self._color_button.clicked.connect(self._on_choose_color_clicked)
        
        color_layout = QHBoxLayout()
        color_layout.addWidget(self._color_hex_edit)
        color_layout.addWidget(self._color_button)
        controls_form_layout.addRow("Color:", color_layout)

        self._position_spinbox = QDoubleSpinBox()
        self._position_spinbox.setRange(0.0, 100.0)
        self._position_spinbox.setSuffix(" %")
        self._position_spinbox.setDecimals(1)
        self._position_spinbox.valueChanged.connect(self._on_position_changed)
        controls_form_layout.addRow("Position:", self._position_spinbox)
        
        controls_main_layout.addLayout(controls_form_layout)

        self._remove_stop_button = QPushButton("Remove Selected Stop")
        self._remove_stop_button.clicked.connect(self._on_remove_stop_clicked)
        controls_main_layout.addWidget(self._remove_stop_button)

        self._apply_button = QPushButton("Apply Gradient to Selected Fixtures") 
        self._apply_button.setObjectName("PrimaryButton") 
        self._apply_button.clicked.connect(self.applyGradientClicked.emit)
        controls_main_layout.addWidget(self._apply_button)
        
        main_layout.addWidget(controls_widget)
        self.setLayout(main_layout)

        self._gradient_display.stopSelected.connect(self._on_stop_selected_from_display)
        self._gradient_display.newStopRequested.connect(self._on_new_stop_requested)
        self._gradient_display.stopMoved.connect(self._on_stop_moved_on_display)


    def get_stops(self) -> list[GradientStop]:
        return self._stops

    def set_gradient_stops(self, stops_data: list[GradientStop] | list[tuple[float, QColor]]):
        new_stops = []
        if not stops_data: 
             stops_data = [(0.0, QColor(Qt.GlobalColor.black)), (1.0, QColor(Qt.GlobalColor.white))]

        for item in stops_data:
            if isinstance(item, GradientStop):
                new_stops.append(item)
            elif isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], (float, int)) and isinstance(item[1], QColor):
                new_stops.append(GradientStop(float(item[0]), item[1]))
            else:
                print(f"Warning: Invalid stop data item: {item}")
        
        self._stops = sorted(new_stops) 
        
        if not any(s.position == 0.0 for s in self._stops):
            self._stops.insert(0, GradientStop(0.0, QColor(Qt.GlobalColor.black)))
        if not any(s.position == 1.0 for s in self._stops):
            self._stops.append(GradientStop(1.0, QColor(Qt.GlobalColor.white)))
        
        self._stops.sort() 
        self._selected_stop_object = None
        self._selected_stop_index_in_list = -1
        if self._stops:
            self._gradient_display.select_stop(0) 
        
        self._emit_gradient_changed()
        self._gradient_display.update()
        self._update_controls_for_selected()

    def getColorAt(self, position_0_1: float) -> QColor:
        if not self._stops:
            return QColor(Qt.GlobalColor.black) 

        clamped_pos = max(0.0, min(1.0, position_0_1))

        if clamped_pos <= self._stops[0].position:
            return QColor(self._stops[0].color)
        if clamped_pos >= self._stops[-1].position:
            return QColor(self._stops[-1].color)

        stop_before = self._stops[0]
        stop_after = self._stops[-1]

        for i in range(len(self._stops) -1):
            s1 = self._stops[i]
            s2 = self._stops[i+1]
            if s1.position <= clamped_pos <= s2.position:
                stop_before = s1
                stop_after = s2
                break
        
        if abs(stop_before.position - stop_after.position) < 0.00001: # Effectively the same stop or very close
            return QColor(stop_before.color)

        range_len = stop_after.position - stop_before.position
        local_pos_factor = (clamped_pos - stop_before.position) / range_len
        local_pos_factor = max(0.0, min(1.0, local_pos_factor)) # Ensure factor is within 0-1

        r1, g1, b1, a1 = stop_before.color.getRgbF()
        r2, g2, b2, a2 = stop_after.color.getRgbF()

        r = r1 * (1.0 - local_pos_factor) + r2 * local_pos_factor
        g = g1 * (1.0 - local_pos_factor) + g2 * local_pos_factor
        b = b1 * (1.0 - local_pos_factor) + b2 * local_pos_factor
        a = a1 * (1.0 - local_pos_factor) + a2 * local_pos_factor
        
        return QColor.fromRgbF(r, g, b, a)


    def _on_stop_selected_from_display(self, stop_obj: GradientStop | None, index: int):
        self._selected_stop_object = stop_obj
        self._selected_stop_index_in_list = index
        self._update_controls_for_selected()

    def _on_new_stop_requested(self, position: float):
        if len(self._stops) >= 15: 
            QMessageBox.information(self, "Stop Limit", "Maximum number of gradient stops reached.")
            return

        new_color = self.getColorAt(position) 

        new_stop = GradientStop(position, new_color)
        self._stops.append(new_stop)
        self._stops.sort()
        new_index = self._stops.index(new_stop)
        
        self._gradient_display.select_stop(new_index) 
        self._emit_gradient_changed()
        self._gradient_display.update()


    def _on_stop_moved_on_display(self, index: int, new_position: float):
        if 0 <= index < len(self._stops):
            if index == 0: new_position = 0.0
            elif index == len(self._stops) - 1: new_position = 1.0
            
            # Store the object before sorting, as its index might change
            moved_stop_object = self._stops[index]
            moved_stop_object.position = new_position # Update its position directly
            self._stops.sort() 
            
            try:
                self._selected_stop_index_in_list = self._stops.index(moved_stop_object)
                self._selected_stop_object = moved_stop_object # Ensure this is also up to date
            except ValueError: 
                self._selected_stop_index_in_list = -1
                self._selected_stop_object = None
            
            self._gradient_display.select_stop(self._selected_stop_index_in_list) # Updates internal state of display widget

            self._emit_gradient_changed()
            self._update_controls_for_selected() 
            self._gradient_display.update()

    def _update_controls_for_selected(self):
        if self._selected_stop_object and self._selected_stop_index_in_list != -1:
            self._color_hex_edit.setText(self._selected_stop_object.color.name())
            
            palette = self._color_button.palette()
            palette.setColor(QPalette.ColorRole.Button, self._selected_stop_object.color)
            self._color_button.setAutoFillBackground(True)
            self._color_button.setPalette(palette)
            self._color_button.update()

            self._position_spinbox.setValue(self._selected_stop_object.position * 100.0)

            is_end_stop = (self._selected_stop_index_in_list == 0 or
                           self._selected_stop_index_in_list == len(self._stops) - 1)
            
            self._position_spinbox.setEnabled(not is_end_stop)
            self._remove_stop_button.setEnabled(not is_end_stop and len(self._stops) > 2)
            self._color_hex_edit.setEnabled(True)
            self._color_button.setEnabled(True)
        else:
            self._color_hex_edit.setText("")
            
            palette = self._color_button.palette()
            palette.setColor(QPalette.ColorRole.Button, self.palette().color(QPalette.ColorRole.Button)) 
            self._color_button.setAutoFillBackground(True) 
            self._color_button.setPalette(palette)
            self._color_button.update()

            self._position_spinbox.setValue(0)
            self._color_hex_edit.setEnabled(False)
            self._color_button.setEnabled(False)
            self._position_spinbox.setEnabled(False)
            self._remove_stop_button.setEnabled(False)

    def _on_hex_edited(self):
        if self._selected_stop_object and not self._color_hex_edit.isReadOnly():
            new_color = QColor(self._color_hex_edit.text())
            if new_color.isValid():
                self._selected_stop_object.color = new_color
                self._emit_gradient_changed()
                self._gradient_display.update()
                self._update_controls_for_selected() 
            else: 
                self._color_hex_edit.setText(self._selected_stop_object.color.name())


    def _on_choose_color_clicked(self):
        if self._selected_stop_object:
            current_color = self._selected_stop_object.color
            new_color = QColorDialog.getColor(current_color, self, "Select Stop Color")
            if new_color.isValid():
                self._selected_stop_object.color = new_color
                self._emit_gradient_changed()
                self._gradient_display.update()
                self._update_controls_for_selected()

    def _on_position_changed(self, value: float):
        if self._selected_stop_object and \
           self._selected_stop_index_in_list > 0 and \
           self._selected_stop_index_in_list < len(self._stops) - 1 and \
           not self._position_spinbox.isReadOnly(): 
            
            new_pos_0_1 = value / 100.0
            
            prev_stop_pos = self._stops[self._selected_stop_index_in_list - 1].position
            next_stop_pos = self._stops[self._selected_stop_index_in_list + 1].position
            
            clamped_pos = max(prev_stop_pos + 0.001, min(next_stop_pos - 0.001, new_pos_0_1))
            clamped_pos = max(0.0, min(1.0, clamped_pos)) 

            if abs(clamped_pos * 100.0 - value) > 0.01 : 
                 self._position_spinbox.blockSignals(True)
                 self._position_spinbox.setValue(clamped_pos * 100.0)
                 self._position_spinbox.blockSignals(False)

            self._selected_stop_object.position = clamped_pos
            self._stops.sort()
            
            try: self._selected_stop_index_in_list = self._stops.index(self._selected_stop_object)
            except ValueError: pass 

            self._gradient_display.select_stop(self._selected_stop_index_in_list) 
            self._emit_gradient_changed()
            self._gradient_display.update()

    def _on_remove_stop_clicked(self):
        if self._selected_stop_object and self._selected_stop_index_in_list != -1:
            if (self._selected_stop_index_in_list == 0 or
                self._selected_stop_index_in_list == len(self._stops) - 1 or
                len(self._stops) <= 2):
                return

            del self._stops[self._selected_stop_index_in_list]
            new_selection_index = max(0, self._selected_stop_index_in_list -1)
            
            self._selected_stop_object = None 
            self._selected_stop_index_in_list = -1
            self._gradient_display.select_stop(new_selection_index)
            
            self._emit_gradient_changed()
            self._gradient_display.update()


    def _emit_gradient_changed(self):
        gradient_data = [(stop.position, QColor(stop.color)) for stop in self._stops]
        self.gradientChanged.emit(gradient_data)


if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    
    app.setStyleSheet("""
        QWidget {
            background-color: #2E2E2E;
            color: #E0E0E0;
            font-family: "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
            font-size: 12px;
        }
        QPushButton {
            background-color: #484848;
            border: 1px solid #383838;
            border-radius: 5px;
            padding: 7px 12px;
        }
        QPushButton:hover { background-color: #585858; }
        QPushButton#PrimaryButton { background-color: #007AFF; color: white; font-weight: bold; } 
        QPushButton#PrimaryButton:hover { background-color: #006EE6; }
        QLineEdit, QDoubleSpinBox {
            background-color: #1C1C1E;
            border: 1px solid #3A3A3C;
            border-radius: 5px;
            padding: 6px 8px;
        }
        QLabel { background-color: transparent; }
        QFormLayout QLabel { margin-top: 3px; } 
    """)

    main_window = QMainWindow()
    editor = GradientEditorWidget()
    
    def print_gradient(stops_list):
        print("Gradient Changed:")
        for pos, color in stops_list:
            print(f"  Pos: {pos:.3f}, Color: {color.name()}") 
        print("-" * 20)

    editor.gradientChanged.connect(print_gradient)
    
    main_window.setCentralWidget(editor)
    main_window.setWindowTitle("Gradient Editor Test")
    main_window.resize(450, 250) 
    main_window.show()
    sys.exit(app.exec())
