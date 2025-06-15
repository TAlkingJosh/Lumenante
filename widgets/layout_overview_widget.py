# widgets/layout_overview_widget.py

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QMouseEvent, QPaintEvent, QPalette, QWheelEvent

import math

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..tabs.main_tab import InteractiveGridCanvas, DefinedArea


class LayoutOverviewWidget(QWidget):
    viewportChangedByOverview = pyqtSignal(float, float)

    def __init__(self, interactive_canvas: 'InteractiveGridCanvas', parent: QWidget | None = None):
        super().__init__(parent)
        self.interactive_canvas = interactive_canvas
        self.setFixedSize(180, 120)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(40, 40, 45, 0.85); border: 1px solid #1A1A1A;")

        self._content_bounding_rect_virtual = QRectF()

        self._base_scale_to_fit = 0.1 # Scale to fit content initially
        self._centering_offset = QPointF(0,0) # Offset to center the base-scaled content

        self._user_scale_multiplier = 1.0 # User-controlled zoom on top of base_scale_to_fit
        self._user_pan_offset = QPointF(0.0, 0.0) # User-controlled pan, in widget coordinates

        self._is_dragging_viewport = False # For left-click drag of viewport rect
        self._drag_start_mouse_pos_overview_virtual = QPointF() # virtual coords
        self._drag_start_canvas_offset_virtual = QPointF()

        self._is_panning_overview_content = False # For middle-mouse pan of overview's own view
        self._pan_start_mouse_pos_widget = QPointF()
        self._pan_start_user_pan_offset = QPointF()

        self.show_overview_grid = True

        self.setMouseTracking(True)

    def _calculate_base_transformations(self):
        # Calculate the bounding box of all defined areas on the main canvas
        if not self.interactive_canvas or not self.interactive_canvas.defined_areas:
            self._content_bounding_rect_virtual = QRectF(0,0,
                float(self.interactive_canvas.GRID_CELL_WIDTH),
                float(self.interactive_canvas.GRID_CELL_HEIGHT))
        else:
            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = float('-inf'), float('-inf')
            for area in self.interactive_canvas.defined_areas:
                min_x = min(min_x, area.rect.left())
                min_y = min(min_y, area.rect.top())
                max_x = max(max_x, area.rect.right())
                max_y = max(max_y, area.rect.bottom())

            if min_x == float('inf'): # No areas
                 self._content_bounding_rect_virtual = QRectF(0,0,
                    float(self.interactive_canvas.GRID_CELL_WIDTH),
                    float(self.interactive_canvas.GRID_CELL_HEIGHT))
            else:
                self._content_bounding_rect_virtual = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

        content_width = self._content_bounding_rect_virtual.width()
        content_height = self._content_bounding_rect_virtual.height()
        if content_width < 1.0: content_width = 1.0
        if content_height < 1.0: content_height = 1.0

        margin = 10
        available_width = self.width() - 2 * margin
        available_height = self.height() - 2 * margin

        scale_x = available_width / content_width if content_width > 0 else 1.0
        scale_y = available_height / content_height if content_height > 0 else 1.0

        self._base_scale_to_fit = min(scale_x, scale_y, 0.8) # Cap max base scale
        self._base_scale_to_fit = max(self._base_scale_to_fit, 0.01) # Minimum base scale

        # Calculate offset to center the content IF it were scaled by base_scale_to_fit * user_scale_multiplier
        current_display_scale = self._base_scale_to_fit * self._user_scale_multiplier
        scaled_content_width = content_width * current_display_scale
        scaled_content_height = content_height * current_display_scale

        # Centering offset considers the effectively scaled content
        self._centering_offset.setX((self.width() - scaled_content_width) / 2)
        self._centering_offset.setY((self.height() - scaled_content_height) / 2)


    def _get_current_display_scale(self) -> float:
        return self._base_scale_to_fit * self._user_scale_multiplier

    def _map_widget_to_virtual(self, widget_point: QPointF) -> QPointF:
        current_display_scale = self._get_current_display_scale()
        if abs(current_display_scale) < 1e-6 : return QPointF() # Avoid division by zero

        # Reverse the paint event transformations
        # 1. Undo centering offset and user pan
        pt = widget_point - self._centering_offset - self._user_pan_offset
        # 2. Undo display scale
        pt /= current_display_scale
        # 3. Add content origin (because drawings are relative to this)
        pt += self._content_bounding_rect_virtual.topLeft()
        return pt

    def _map_virtual_to_widget(self, virtual_point: QPointF) -> QPointF:
        current_display_scale = self._get_current_display_scale()
        # 1. Make relative to content origin
        pt = virtual_point - self._content_bounding_rect_virtual.topLeft()
        # 2. Apply display scale
        pt *= current_display_scale
        # 3. Add user pan and centering offset
        pt += self._user_pan_offset + self._centering_offset
        return pt

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._calculate_base_transformations() # Recalculates _base_scale_to_fit and _centering_offset

        current_display_scale = self._get_current_display_scale()

        painter.translate(self._centering_offset)
        painter.translate(self._user_pan_offset)
        painter.scale(current_display_scale, current_display_scale)
        painter.translate(-self._content_bounding_rect_virtual.topLeft())

        # Draw Grid (if enabled)
        if self.show_overview_grid:
            grid_pen = QPen(QColor(100, 100, 100, 70))
            grid_pen_width = max(0.5, 0.5 / current_display_scale) # Keep lines thin
            grid_pen.setWidthF(grid_pen_width)
            painter.setPen(grid_pen)

            gcw = self.interactive_canvas.GRID_CELL_WIDTH
            gch = self.interactive_canvas.GRID_CELL_HEIGHT

            # Determine grid bounds based on _content_bounding_rect_virtual
            grid_left = math.floor(self._content_bounding_rect_virtual.left() / gcw) * gcw
            grid_right = math.ceil(self._content_bounding_rect_virtual.right() / gcw) * gcw
            grid_top = math.floor(self._content_bounding_rect_virtual.top() / gch) * gch
            grid_bottom = math.ceil(self._content_bounding_rect_virtual.bottom() / gch) * gch

            for x in range(int(grid_left), int(grid_right) + 1, gcw):
                painter.drawLine(QPointF(x, grid_top), QPointF(x, grid_bottom))
            for y in range(int(grid_top), int(grid_bottom) + 1, gch):
                painter.drawLine(QPointF(grid_left, y), QPointF(grid_right, y))

        # Draw Defined Areas
        for area in self.interactive_canvas.defined_areas:
            area_color = QColor(80, 80, 80, 150)
            if area == self.interactive_canvas.currently_selected_area_for_panel:
                area_color = QColor(0,122,255, 200)
            painter.setBrush(QBrush(area_color))
            pen_width_area = max(1.0, 0.5 / current_display_scale)
            painter.setPen(QPen(area_color.darker(120), pen_width_area))
            painter.drawRect(area.rect) # Draw using original virtual rect

        # Draw Viewport Rectangle (from main canvas)
        canvas_virtual_viewport = QRectF(
            self.interactive_canvas.canvas_offset_x,
            self.interactive_canvas.canvas_offset_y,
            float(self.interactive_canvas.width()) / self.interactive_canvas.zoom_level if hasattr(self.interactive_canvas, 'zoom_level') else float(self.interactive_canvas.width()),
            float(self.interactive_canvas.height()) / self.interactive_canvas.zoom_level if hasattr(self.interactive_canvas, 'zoom_level') else float(self.interactive_canvas.height())
        )

        pen_width_viewport = max(1.0, 2.0 / current_display_scale)
        pen_viewport = QPen(QColor("white"), pen_width_viewport)
        pen_viewport.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen_viewport)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(canvas_virtual_viewport) # Draw using its virtual rect


    def mousePressEvent(self, event: QMouseEvent):
        widget_pos = event.position()

        if event.button() == Qt.MouseButton.LeftButton:
            self._is_panning_overview_content = False # Ensure middle mouse pan stops

            # Convert click in overview to virtual grid coordinates
            clicked_pos_virtual = self._map_widget_to_virtual(widget_pos)

            canvas_main_zoom = self.interactive_canvas.zoom_level if hasattr(self.interactive_canvas, 'zoom_level') else 1.0
            canvas_virtual_viewport_rect = QRectF(
                self.interactive_canvas.canvas_offset_x,
                self.interactive_canvas.canvas_offset_y,
                float(self.interactive_canvas.width()) / canvas_main_zoom,
                float(self.interactive_canvas.height()) / canvas_main_zoom
            )

            if canvas_virtual_viewport_rect.contains(clicked_pos_virtual):
                self._is_dragging_viewport = True
                # Store the virtual click position, not the widget position for drag delta calculation
                self._drag_start_mouse_pos_overview_virtual = clicked_pos_virtual
                self._drag_start_canvas_offset_virtual = QPointF(
                    self.interactive_canvas.canvas_offset_x,
                    self.interactive_canvas.canvas_offset_y
                )
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else: # Clicked outside viewport rect -> center main canvas there
                new_center_x_virtual = clicked_pos_virtual.x()
                new_center_y_virtual = clicked_pos_virtual.y()

                new_offset_x = new_center_x_virtual - (self.interactive_canvas.width() / canvas_main_zoom) / 2.0
                new_offset_y = new_center_y_virtual - (self.interactive_canvas.height() / canvas_main_zoom) / 2.0
                self.viewportChangedByOverview.emit(new_offset_x, new_offset_y)

        elif event.button() == Qt.MouseButton.MiddleButton:
            self._is_dragging_viewport = False # Ensure left-click drag stops
            self._is_panning_overview_content = True
            self._pan_start_mouse_pos_widget = widget_pos
            self._pan_start_user_pan_offset = QPointF(self._user_pan_offset) # Copy
            self.setCursor(Qt.CursorShape.SizeAllCursor)


    def mouseMoveEvent(self, event: QMouseEvent):
        widget_pos = event.position()

        if self._is_dragging_viewport and event.buttons() & Qt.MouseButton.LeftButton:
            current_mouse_pos_virtual = self._map_widget_to_virtual(widget_pos)
            delta_virtual = current_mouse_pos_virtual - self._drag_start_mouse_pos_overview_virtual

            new_offset_x = self._drag_start_canvas_offset_virtual.x() + delta_virtual.x()
            new_offset_y = self._drag_start_canvas_offset_virtual.y() + delta_virtual.y()

            self.viewportChangedByOverview.emit(new_offset_x, new_offset_y)
            self.update() # Repaint overview to show viewport moving

        elif self._is_panning_overview_content and event.buttons() & Qt.MouseButton.MiddleButton:
            delta_widget = widget_pos - self._pan_start_mouse_pos_widget
            self._user_pan_offset = self._pan_start_user_pan_offset + delta_widget
            self.update() # Repaint overview to show its content panned

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_viewport:
            self._is_dragging_viewport = False
            self.unsetCursor()
        elif event.button() == Qt.MouseButton.MiddleButton and self._is_panning_overview_content:
            self._is_panning_overview_content = False
            self.unsetCursor()

    def wheelEvent(self, event: QWheelEvent):
        if not self.rect().contains(event.position().toPoint()):
             super().wheelEvent(event)
             return

        num_degrees = event.angleDelta().y() / 8
        num_steps = num_degrees / 15
        zoom_factor_delta = 1.2 if num_steps > 0 else 1 / 1.2

        mouse_pos_widget = event.position()
        point_in_virtual_coords_before_zoom = self._map_widget_to_virtual(mouse_pos_widget)

        old_user_scale_multiplier = self._user_scale_multiplier
        self._user_scale_multiplier *= zoom_factor_delta
        self._user_scale_multiplier = max(0.1, min(self._user_scale_multiplier, 10.0)) # Clamp zoom

        # Re-calculate base transformations as effective scale for centering has changed
        self._calculate_base_transformations()

        # Calculate where the point under mouse *would be* with new scale & old pan
        new_widget_pos_of_point = self._map_virtual_to_widget(point_in_virtual_coords_before_zoom)

        # Adjust pan offset to keep the point under mouse stationary
        pan_correction = mouse_pos_widget - new_widget_pos_of_point
        self._user_pan_offset += pan_correction

        self.update()
        event.accept()

    def force_repaint(self):
        self.update()
