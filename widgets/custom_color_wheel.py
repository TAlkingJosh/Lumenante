# widgets/custom_color_wheel.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QSlider, QSpinBox, QComboBox, QGridLayout, QSizePolicy, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QPointF, QRect, QRectF, QSize
from PyQt6.QtGui import (QColor, QPainter, QConicalGradient, QRadialGradient, 
                         QLinearGradient, QPixmap, QImage, QPen, QBrush, 
                         QFontMetrics, QMouseEvent, QPaintEvent)
import math

class CustomColorWheelWidget(QWidget):
    colorChanged = pyqtSignal(QColor)

    def __init__(self, initial_color=QColor(255,0,0), parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 200) 
        
        self._color = QColor(initial_color)

        h, s, v, a = self._color.getHsvF()
        self._hue_norm: float = h if h != -1 else 0.0 
        self._saturation_norm: float = s
        self._value_norm: float = v if v != -1 else 1.0
        self._alpha_norm: float = a if a != -1 else 1.0

        self.wheel_rect_f = QRectF()
        self.value_slider_rect_f = QRectF()
        self.preview_rect_f = QRectF()

        # This will store the calculated picker position based on H/S,
        # but we'll only draw it if not dragging.
        # During drag, we'll draw at the mouse cursor's projection onto the wheel.
        self.static_hue_sat_picker_pos_f = QPointF() 
        self.current_mouse_drag_on_wheel_pos_f = QPointF() # Stores actual mouse pos during wheel drag for picker

        self.value_picker_pos_y_f = 0.0

        self.wheel_radius_f = 0.0
        self.slider_width_f = 25.0 
        self.preview_size_f = 50.0 
        self.picker_radius_f = 7.0 

        self.is_dragging_wheel = False
        self.is_dragging_value_slider = False

        self.value_slider_pixmap = QPixmap()

        self.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Preferred)
        
        main_h_layout = QHBoxLayout(self)
        main_h_layout.setContentsMargins(5,5,5,5)
        main_h_layout.setSpacing(8)

        self.paint_area_widget=QWidget() 
        self.paint_area_widget.paintEvent=self._draw_color_controls_on_paint_area
        self.paint_area_widget.mousePressEvent=self._area_mouse_press
        self.paint_area_widget.mouseMoveEvent=self._area_mouse_move
        self.paint_area_widget.mouseReleaseEvent=self._area_mouse_release
        self.paint_area_widget.setMouseTracking(True) # Enable mouse tracking for paint_area_widget
        
        self.paint_area_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_h_layout.addWidget(self.paint_area_widget,1) 

        input_fields_group = QFrame() 
        input_layout=QGridLayout(input_fields_group)
        input_layout.setContentsMargins(0,0,0,0)

        self.r_spin=QSpinBox(); self.r_spin.setRange(0,255); self.r_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.g_spin=QSpinBox(); self.g_spin.setRange(0,255); self.g_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.b_spin=QSpinBox(); self.b_spin.setRange(0,255); self.b_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.hex_edit=QLineEdit(); self.hex_edit.setMaxLength(7); self.hex_edit.setFixedWidth(70)
        
        input_layout.addWidget(QLabel("R:"),0,0); input_layout.addWidget(self.r_spin,0,1)
        input_layout.addWidget(QLabel("G:"),1,0); input_layout.addWidget(self.g_spin,1,1)
        input_layout.addWidget(QLabel("B:"),2,0); input_layout.addWidget(self.b_spin,2,1)
        input_layout.addWidget(QLabel("#:"),3,0); input_layout.addWidget(self.hex_edit,3,1)
        input_fields_group.setLayout(input_layout)
        
        main_h_layout.addWidget(input_fields_group, 0) 
        self.setLayout(main_h_layout)

        self.r_spin.valueChanged.connect(self._rgb_inputs_changed_slot)
        self.g_spin.valueChanged.connect(self._rgb_inputs_changed_slot)
        self.b_spin.valueChanged.connect(self._rgb_inputs_changed_slot)
        self.hex_edit.editingFinished.connect(self._hex_input_changed_slot)
        
        self._update_color_from_hsv() 
        self._update_all_visuals()    
        self._regenerate_value_slider_pixmap() 

    def resizeEvent(self, event: QPaintEvent): 
        super().resizeEvent(event)
        self._calculate_geometry() 
        self._regenerate_value_slider_pixmap() 
        if hasattr(self, 'paint_area_widget') and self.paint_area_widget:
             self.paint_area_widget.update()

    def _calculate_geometry(self):
        pa_w=float(self.paint_area_widget.width())
        pa_h=float(self.paint_area_widget.height())
        padding=5.0 
        spacing = 8.0 

        element_h = pa_h - 2 * padding
        element_h = max(30.0, element_h) 

        self.wheel_radius_f = element_h / 2.0
        wheel_diameter = element_h
        
        needed_width_for_slider_preview = self.slider_width_f + spacing + self.preview_size_f
        if wheel_diameter + needed_width_for_slider_preview > (pa_w - 2 * padding):
             wheel_diameter = (pa_w - 2 * padding) - needed_width_for_slider_preview
             wheel_diameter = max(30.0, wheel_diameter) 
             self.wheel_radius_f = wheel_diameter / 2.0
             element_h = wheel_diameter 

        current_x = padding
        self.wheel_rect_f = QRectF(current_x, padding, wheel_diameter, element_h)
        current_x += wheel_diameter + spacing

        self.value_slider_rect_f = QRectF(current_x, padding, self.slider_width_f, element_h)
        current_x += self.slider_width_f + spacing
        
        self.preview_rect_f = QRectF(current_x, padding + (element_h - self.preview_size_f)/2.0 , 
                                     self.preview_size_f, self.preview_size_f)
        
        self._update_picker_positions_from_hsv() 

    def _regenerate_value_slider_pixmap(self):
        if not self.value_slider_rect_f.isValid() or self.value_slider_rect_f.width() <=0 or self.value_slider_rect_f.height() <=0:
            return
            
        self.value_slider_pixmap = QPixmap(self.value_slider_rect_f.size().toSize())
        self.value_slider_pixmap.fill(Qt.GlobalColor.transparent) 
        painter = QPainter(self.value_slider_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        grad = QLinearGradient(0, 0, 0, self.value_slider_rect_f.height())
        grad.setColorAt(0, QColor.fromHsvF(self._hue_norm, self._saturation_norm, 1.0, self._alpha_norm))
        grad.setColorAt(1, QColor.fromHsvF(self._hue_norm, self._saturation_norm, 0.0, self._alpha_norm))
        
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen) 
        painter.drawRoundedRect(QRectF(0,0, self.value_slider_rect_f.width(), self.value_slider_rect_f.height()), 3,3)
        painter.end()
        if hasattr(self, 'paint_area_widget') and self.paint_area_widget:
            self.paint_area_widget.update() 


    def _draw_color_controls_on_paint_area(self,event:QPaintEvent):
        painter=QPainter(self.paint_area_widget)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not self.wheel_rect_f.isValid() or self.wheel_radius_f<=0:
            self._calculate_geometry() 
            self._regenerate_value_slider_pixmap() 
            if not self.wheel_rect_f.isValid() or self.wheel_radius_f<=0: return

        wheel_center_qpointf=self.wheel_rect_f.center()
        
        gradient=QConicalGradient(wheel_center_qpointf,0) 
        for i in range(361): gradient.setColorAt(i/360.0,QColor.fromHsvF(i/360.0,1.0,1.0))
        painter.setBrush(QBrush(gradient)); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(self.wheel_rect_f)
        
        sat_gradient=QRadialGradient(wheel_center_qpointf,self.wheel_radius_f)
        sat_gradient.setColorAt(0,QColor(255,255,255,255)); sat_gradient.setColorAt(1,QColor(255,255,255,0))
        painter.setBrush(QBrush(sat_gradient)); painter.drawEllipse(self.wheel_rect_f)
        
        if not self.value_slider_pixmap.isNull():
            painter.drawPixmap(self.value_slider_rect_f.topLeft().toPoint(), self.value_slider_pixmap)
        
        painter.setBrush(QBrush(self._color)) 
        painter.setPen(QPen(QColor(80,80,80), 1)) 
        painter.drawRect(self.preview_rect_f)
        
        # Draw Hue/Saturation Picker
        picker_pos_to_draw = QPointF()
        if self.is_dragging_wheel:
            # Clamp mouse drag position to be within the wheel radius
            dx = self.current_mouse_drag_on_wheel_pos_f.x() - wheel_center_qpointf.x()
            dy = self.current_mouse_drag_on_wheel_pos_f.y() - wheel_center_qpointf.y()
            dist_from_center = math.sqrt(dx*dx + dy*dy)
            if dist_from_center > self.wheel_radius_f:
                # Clamp to edge
                picker_pos_to_draw.setX(wheel_center_qpointf.x() + (dx / dist_from_center) * self.wheel_radius_f)
                picker_pos_to_draw.setY(wheel_center_qpointf.y() + (dy / dist_from_center) * self.wheel_radius_f)
            else:
                picker_pos_to_draw = self.current_mouse_drag_on_wheel_pos_f
        else: # Not dragging, use the static position derived from H/S
            picker_pos_to_draw = self.static_hue_sat_picker_pos_f
        
        painter.setPen(QPen(Qt.GlobalColor.black,1.5)); painter.setBrush(Qt.BrushStyle.NoBrush) 
        painter.drawEllipse(picker_pos_to_draw, self.picker_radius_f, self.picker_radius_f)
        
        # Draw Value Picker Line
        picker_line_y = self.value_slider_rect_f.top() + self.value_picker_pos_y_f
        painter.setPen(QPen(Qt.GlobalColor.white if self._value_norm<0.5 else Qt.GlobalColor.black, 2)) 
        painter.drawLine(QPointF(self.value_slider_rect_f.left() - 3, picker_line_y), QPointF(self.value_slider_rect_f.right() + 3, picker_line_y))
    
    def _area_mouse_press(self,event:QMouseEvent):
        pos_f=QPointF(event.position())
        self.current_mouse_drag_on_wheel_pos_f = pos_f # Store for drawing if drag starts
        
        if self.wheel_rect_f.isValid() and self.wheel_rect_f.contains(pos_f):
            self.is_dragging_wheel=True
            self._update_from_wheel_pos(pos_f)
        elif self.value_slider_rect_f.isValid() and self.value_slider_rect_f.adjusted(-3, -5, 3, 5).contains(pos_f): 
            self.is_dragging_value_slider=True
            self._update_from_value_slider_pos(pos_f.y())
    
    def _area_mouse_move(self,event:QMouseEvent):
        pos_f=QPointF(event.position())
        if self.is_dragging_wheel:
            self.current_mouse_drag_on_wheel_pos_f = pos_f # Update for drawing
            self._update_from_wheel_pos(pos_f)
            self.paint_area_widget.update() # Force repaint to show picker moving with mouse
        elif self.is_dragging_value_slider:
            self._update_from_value_slider_pos(pos_f.y())
            self.paint_area_widget.update() # Force repaint for slider line

    def _area_mouse_release(self,event:QMouseEvent):
        if self.is_dragging_wheel:
            self.is_dragging_wheel=False
            self.paint_area_widget.update() # Final repaint to draw static picker
        if self.is_dragging_value_slider:
            self.is_dragging_value_slider=False
            self.paint_area_widget.update() # Final repaint for slider line

    def _update_from_wheel_pos(self,pos_f:QPointF):
        center=self.wheel_rect_f.center()
        dx=pos_f.x()-center.x(); dy=pos_f.y()-center.y()
        
        hue_rad = math.atan2(-dy, dx) 
        current_angle_deg = math.degrees(hue_rad) 
        self._hue_norm = ((current_angle_deg + 360.0) % 360.0) / 360.0

        dist=math.sqrt(dx**2+dy**2)
        self._saturation_norm=min(1.0,dist/self.wheel_radius_f if self.wheel_radius_f>0 else 0)
        
        self._regenerate_value_slider_pixmap() 
        self._update_color_from_hsv()
        self._update_all_visuals()
    
    def _update_from_value_slider_pos(self,y_pos_float:float): 
        slider_h_val=self.value_slider_rect_f.height() 
        if slider_h_val<=0: return
        
        rel_y=max(0.0,min(slider_h_val,y_pos_float-self.value_slider_rect_f.top()))
        self._value_norm =1.0-(rel_y/slider_h_val)
        
        self._update_color_from_hsv()
        self._update_all_visuals()

    def _update_color_from_hsv(self):
        self._color = QColor.fromHsvF(self._hue_norm, self._saturation_norm, self._value_norm, self._alpha_norm)

    def _update_hsv_from_color(self):
        h, s, v, a = self._color.getHsvF()
        self._hue_norm = h if h != -1 else self._hue_norm 
        if h == -1 and (self._hue_norm < 0 or self._hue_norm >1): self._hue_norm = 0.0

        self._saturation_norm = s
        self._value_norm = v if v != -1 else self._value_norm
        if v == -1 and (self._value_norm < 0 or self._value_norm > 1): self._value_norm = 0.0
        self._alpha_norm = a if a != -1 else self._alpha_norm


    def _update_picker_positions_from_hsv(self): 
        if not self.wheel_rect_f.isValid() or self.wheel_radius_f<=0:return
        
        display_angle_rad = self._hue_norm * 2 * math.pi 
        dist=self._saturation_norm*self.wheel_radius_f
        center=self.wheel_rect_f.center()
        
        # This is the "static" picker position based on current H/S
        self.static_hue_sat_picker_pos_f=QPointF(center.x()+dist*math.cos(display_angle_rad),center.y()+dist*math.sin(display_angle_rad))
        self.value_picker_pos_y_f=(1.0-self._value_norm)*self.value_slider_rect_f.height()
    
    def _block_input_signals(self,block:bool):
        self.r_spin.blockSignals(block); self.g_spin.blockSignals(block)
        self.b_spin.blockSignals(block); self.hex_edit.blockSignals(block)
    
    def _rgb_inputs_changed_slot(self):
        if self.r_spin.signalsBlocked():return 
        self._block_input_signals(True)
        
        self._color.setRgb(self.r_spin.value(),self.g_spin.value(),self.b_spin.value())
        self._update_hsv_from_color() 
        self._regenerate_value_slider_pixmap() 
        
        self.hex_edit.setText(self._color.name().upper())
        self._update_all_visuals() 
        self._block_input_signals(False)
    
    def _hex_input_changed_slot(self):
        if self.hex_edit.signalsBlocked():return
        self._block_input_signals(True)
        
        new_c=QColor(self.hex_edit.text())
        if new_c.isValid(): self._color=new_c
        else: self.hex_edit.setText(self._color.name().upper())
        
        self._update_hsv_from_color()
        self._regenerate_value_slider_pixmap()

        self.r_spin.setValue(self._color.red())
        self.g_spin.setValue(self._color.green())
        self.b_spin.setValue(self._color.blue())
        self._update_all_visuals()
        self._block_input_signals(False)
    
    def _update_rgb_hex_inputs_from_color(self):
        self._block_input_signals(True)
        self.r_spin.setValue(self._color.red())
        self.g_spin.setValue(self._color.green())
        self.b_spin.setValue(self._color.blue())
        self.hex_edit.setText(self._color.name().upper())
        self._block_input_signals(False)
    
    def _update_all_visuals(self):
        self._update_picker_positions_from_hsv() 
        self._update_rgb_hex_inputs_from_color()   
        self.colorChanged.emit(QColor(self._color))
        if hasattr(self, 'paint_area_widget') and self.paint_area_widget:
            self.paint_area_widget.update() 
    
    def setColor(self,color:QColor):
        if color.isValid() and color!=self._color:
            self._color=QColor(color)
            self._update_hsv_from_color() 
            self._regenerate_value_slider_pixmap()
            self._update_all_visuals()
    
    def color(self)->QColor:
        return QColor(self._color)
