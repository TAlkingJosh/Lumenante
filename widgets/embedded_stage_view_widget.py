# widgets/embedded_stage_view_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QApplication
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, QPoint, QTimer, QPointF
from PyQt6.QtGui import QMouseEvent, QWheelEvent
import sqlite3

from OpenGL.GL import *
from OpenGL.GLU import *

# Import the shared components from the new independent module
from .gl_fixture_model import Fixture3D, GLUT_FUNCTIONS_USABLE

import numpy as np
import math


class EmbeddedOpenGLScene(QOpenGLWidget):
    def __init__(self, main_window, parent_area_id, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.parent_area_id = parent_area_id 
        self.fixtures_3d_objects = {}
        
        # Dynamic camera attributes, similar to main 3D view
        self.camera_x_angle = 20.0    # Initial pitch
        self.camera_y_angle = -45.0   # Initial yaw
        self.camera_zoom_distance = 20.0 # Initial zoom
        self.camera_target = np.array([0.0, 0.5, 0.0]) # Initial look-at point
        self.last_mouse_drag_pos = QPointF() # Use QPointF for consistency with event.position()

        self.show_beams_in_embedded = True 

        self.strobe_timer_embedded = QTimer(self)
        self.strobe_timer_embedded.timeout.connect(self.update_strobe_effects_embedded)
        
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus) # Allow widget to receive keyboard/wheel events if clicked


    def initializeGL(self):
        glClearColor(0.15, 0.15, 0.18, 1.0) 
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glEnable(GL_CULL_FACE)
        glShadeModel(GL_SMOOTH)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0) 
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.5, 0.5, 0.5, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        self.load_all_fixtures_from_db()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.strobe_timer_embedded.isActive():
            self.strobe_timer_embedded.start(60) 
        self.load_all_fixtures_from_db()


    def hideEvent(self, event):
        super().hideEvent(event)
        if self.strobe_timer_embedded.isActive():
            self.strobe_timer_embedded.stop()

    def resizeGL(self, width, height):
        height = 1 if height == 0 else height
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, float(width) / float(height), 0.1, 200.0) 
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # Dynamic camera calculation based on angles and zoom
        eye_x = self.camera_target[0] + self.camera_zoom_distance * math.sin(math.radians(self.camera_y_angle)) * math.cos(math.radians(self.camera_x_angle))
        eye_y = self.camera_target[1] + self.camera_zoom_distance * math.sin(math.radians(self.camera_x_angle))
        eye_z = self.camera_target[2] + self.camera_zoom_distance * math.cos(math.radians(self.camera_y_angle)) * math.cos(math.radians(self.camera_x_angle))
        
        gluLookAt(eye_x, eye_y, eye_z, 
                  self.camera_target[0], self.camera_target[1], self.camera_target[2], 
                  0, 1, 0)

        glLightfv(GL_LIGHT0, GL_POSITION, [eye_x, eye_y + 2, eye_z, 1.0]) 

        glDisable(GL_LIGHTING)
        glColor3f(0.2, 0.2, 0.22)
        glBegin(GL_QUADS)
        glVertex3f(-10, 0, -10); glVertex3f( 10, 0, -10)
        glVertex3f( 10, 0,  10); glVertex3f(-10, 0,  10)
        glEnd()
        glEnable(GL_LIGHTING)

        for fixture_obj in self.fixtures_3d_objects.values():
            fixture_obj.show_beam_global = self.show_beams_in_embedded 
            fixture_obj.draw()

    def mousePressEvent(self, event: QMouseEvent):
        self.last_mouse_drag_pos = event.position() # event.position() is QPointF
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        dx = event.position().x() - self.last_mouse_drag_pos.x()
        dy = event.position().y() - self.last_mouse_drag_pos.y()

        if event.buttons() & Qt.MouseButton.LeftButton: 
            self.camera_y_angle += dx * 0.35 
            self.camera_x_angle += dy * 0.35
            self.camera_x_angle = max(-89.0, min(89.0, self.camera_x_angle)) 
        elif event.buttons() & Qt.MouseButton.RightButton: 
            pan_speed = 0.015 * (self.camera_zoom_distance / 10.0) 
            cam_right_x = math.cos(math.radians(self.camera_y_angle))
            cam_right_z = -math.sin(math.radians(self.camera_y_angle))
            self.camera_target[0] -= dx * cam_right_x * pan_speed
            self.camera_target[2] -= dx * cam_right_z * pan_speed
            self.camera_target[1] += dy * pan_speed 

        self.last_mouse_drag_pos = event.position() # Update with QPointF
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent): # Added this method
        # No specific action needed on release other than what press/move handle,
        # but accepting the event can prevent it from propagating further if that's causing issues.
        event.accept()


    def wheelEvent(self, event: QWheelEvent):
        delta_degrees = event.angleDelta().y() / 8  
        delta_steps = delta_degrees / 15 
        
        zoom_speed = 0.6 
        self.camera_zoom_distance -= delta_steps * zoom_speed
        self.camera_zoom_distance = max(1.0, min(100.0, self.camera_zoom_distance)) 
        self.update()
        event.accept()

    def update_strobe_effects_embedded(self):
        needs_repaint = False
        for fixture_obj in self.fixtures_3d_objects.values():
            if fixture_obj.shutter_strobe_rate_hz > 0 and fixture_obj.intensity > 0.01:
                fixture_obj._beam_actually_visible_strobe_state = not fixture_obj._beam_actually_visible_strobe_state
                needs_repaint = True
            elif fixture_obj.shutter_strobe_rate_hz == 0:
                if not fixture_obj._beam_actually_visible_strobe_state:
                    fixture_obj._beam_actually_visible_strobe_state = True
                    needs_repaint = True
        if needs_repaint and self.isVisible():
            self.update()

    def _create_fixture3d_from_db_row(self, data_tuple, column_names):
        data = dict(zip(column_names, data_tuple))
        return Fixture3D(
            data['id'], data['profile_id'], data.get('profile_name', 'Generic'), data['name'],
            data['x_pos'], data['y_pos'], data['z_pos'],
            data['rotation_x'], data['rotation_y'], data['rotation_z'],
            data['red'], data['green'], data['blue'], data['brightness'],
            data.get('gobo_index', 0), data['zoom'], data['focus'], data['shutter_strobe_rate'], data.get('gobo_spin', 128.0)
        )

    def load_all_fixtures_from_db(self):
        try:
            self.fixtures_3d_objects.clear()
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("""
                SELECT f.*, p.name as profile_name 
                FROM fixtures f 
                JOIN fixture_profiles p ON f.profile_id = p.id
            """)
            all_fixtures_data = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            for data_row in all_fixtures_data:
                fixture_obj = self._create_fixture3d_from_db_row(data_row, column_names)
                self.fixtures_3d_objects[fixture_obj.id] = fixture_obj
            if self.isVisible(): self.update()
        except Exception as e:
            print(f"Error loading fixtures for embedded view (Area {self.parent_area_id}): {e}")

    def update_fixture_visualization(self, fixture_id, data_dict_from_signal):
        if fixture_id in self.fixtures_3d_objects:
            f_obj = self.fixtures_3d_objects[fixture_id]
            f_obj.position = np.array([data_dict_from_signal.get('x_pos', f_obj.position[0]), 
                                       data_dict_from_signal.get('y_pos', f_obj.position[1]), 
                                       data_dict_from_signal.get('z_pos', f_obj.position[2])], dtype=float)
            
            f_obj.rotation_euler_xyz = np.array([
                data_dict_from_signal.get('rotation_x', f_obj.rotation_euler_xyz[0]), 
                data_dict_from_signal.get('rotation_y', f_obj.rotation_euler_xyz[1]), 
                data_dict_from_signal.get('rotation_z', f_obj.rotation_euler_xyz[2])
            ], dtype=float)

            f_obj.color_rgb = np.array([data_dict_from_signal.get('red', f_obj.color_rgb[0]*255)/255.0, 
                                       data_dict_from_signal.get('green', f_obj.color_rgb[1]*255)/255.0, 
                                       data_dict_from_signal.get('blue', f_obj.color_rgb[2]*255)/255.0], dtype=float)
            f_obj.intensity = data_dict_from_signal.get('brightness', f_obj.intensity*100) / 100.0
            f_obj.name = data_dict_from_signal.get('name', f_obj.name)
            
            if 'profile_id' in data_dict_from_signal and data_dict_from_signal['profile_id'] != f_obj.profile_id:
                try:
                    cursor = self.main_window.db_connection.cursor()
                    cursor.execute("SELECT name FROM fixture_profiles WHERE id = ?", (data_dict_from_signal['profile_id'],))
                    result = cursor.fetchone()
                    if result:
                        f_obj.type = result[0].lower()
                        f_obj.profile_id = data_dict_from_signal['profile_id']
                except sqlite3.Error as e:
                     print(f"DB Error fetching new profile name for fixture {fixture_id} in embedded view: {e}")

            f_obj.gobo_spin = float(data_dict_from_signal.get('gobo_spin', f_obj.gobo_spin))
            f_obj.zoom_angle_deg = float(data_dict_from_signal.get('zoom', f_obj.zoom_angle_deg))
            f_obj.focus_percent = float(data_dict_from_signal.get('focus', f_obj.focus_percent))
            new_strobe_rate = float(data_dict_from_signal.get('shutter_strobe_rate', f_obj.shutter_strobe_rate_hz))
            if f_obj.shutter_strobe_rate_hz == 0 and new_strobe_rate > 0:
                f_obj._beam_actually_visible_strobe_state = True
            f_obj.shutter_strobe_rate_hz = new_strobe_rate
        else: 
            self.load_all_fixtures_from_db() 
        
        if self.isVisible(): self.update()
        
    def set_selection(self, selected_fixture_ids: list[int]):
        for fix_id, fix_obj in self.fixtures_3d_objects.items():
            fix_obj.is_selected = (fix_id in selected_fixture_ids)
        self.update()

class EmbeddedStageViewWidget(QWidget):
    def __init__(self, main_window, area_id, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.area_id = area_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0) 
        self.opengl_scene = EmbeddedOpenGLScene(main_window, area_id, self)
        layout.addWidget(self.opengl_scene)
        self.setLayout(layout)

    def update_all_fixtures(self):
        if self.opengl_scene:
            self.opengl_scene.load_all_fixtures_from_db()

    def update_fixture(self, fixture_id: int, data: dict):
        if self.opengl_scene:
            self.opengl_scene.update_fixture_visualization(fixture_id, data)
            
    def set_show_beams(self, show: bool):
        if self.opengl_scene:
            self.opengl_scene.show_beams_in_embedded = show
            self.opengl_scene.update()
            
    def set_selection(self, selected_fixture_ids: list[int]):
        if self.opengl_scene:
            self.opengl_scene.set_selection(selected_fixture_ids)

    def mousePressEvent(self, event: QMouseEvent):
        if self.opengl_scene:
            local_pos_qpointf = self.opengl_scene.mapFromParent(event.position()) # event.position() is QPointF
            remapped_event = QMouseEvent(event.type(), local_pos_qpointf, event.globalPosition(), event.button(), event.buttons(), event.modifiers())
            QApplication.sendEvent(self.opengl_scene, remapped_event)
            if remapped_event.isAccepted():
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.opengl_scene:
            local_pos_qpointf = self.opengl_scene.mapFromParent(event.position()) # event.position() is QPointF
            remapped_event = QMouseEvent(event.type(), local_pos_qpointf, event.globalPosition(), event.button(), event.buttons(), event.modifiers())
            QApplication.sendEvent(self.opengl_scene, remapped_event)
            if remapped_event.isAccepted():
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.opengl_scene:
            local_pos_qpointf = self.opengl_scene.mapFromParent(event.position()) # event.position() is QPointF
            remapped_event = QMouseEvent(event.type(), local_pos_qpointf, event.globalPosition(), event.button(), event.buttons(), event.modifiers())
            QApplication.sendEvent(self.opengl_scene, remapped_event)
            if remapped_event.isAccepted():
                event.accept()
                return
        super().mouseReleaseEvent(event)
    
    def wheelEvent(self, event: QWheelEvent):
        if self.opengl_scene:
            local_pos_f = self.opengl_scene.mapFromParent(event.position())
            new_event = QWheelEvent(local_pos_f,                  
                                    event.globalPosition(),       
                                    event.pixelDelta(),           
                                    event.angleDelta(),           
                                    event.buttons(),              
                                    event.modifiers(),            
                                    event.phase(),                
                                    event.inverted(),             
                                    event.source())               

            QApplication.sendEvent(self.opengl_scene, new_event)
            if new_event.isAccepted():
                event.accept() 
                return
        super().wheelEvent(event)
