# tabs/visualization_3d_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMessageBox, QHBoxLayout, QSlider, QCheckBox
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from OpenGL.GL import *
from OpenGL.GLU import *
import sqlite3

# Import shared components from the new independent module
from widgets.gl_fixture_model import Fixture3D, GLUT_FUNCTIONS_USABLE

import numpy as np
import math 


class OpenGLScene(QOpenGLWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.fixtures_3d_objects = {} 
        self.camera_x_angle = 25.0
        self.camera_y_angle = -45.0
        self.camera_zoom_distance = 20.0
        self.camera_target = np.array([0.0, 1.0, 0.0]) 
        self.last_mouse_drag_pos = QPoint()
        
        self.draw_grid = True
        self.draw_axes = False
        self.show_all_beams = True

        self.strobe_timer = QTimer(self)
        self.strobe_timer.timeout.connect(self.update_strobe_effects)
        
        self.setMinimumSize(600, 400)

    def initializeGL(self):
        global GLUT_FUNCTIONS_USABLE 
        
        # The global glutInit in main.py is preferred, but this is a fallback.
        # The actual robust check is now inside Fixture3D.draw()
        if GLUT_FUNCTIONS_USABLE:
            try:
                from OpenGL.GLUT import glutInit
                # This call can sometimes fail if a context isn't fully ready,
                # which is why the draw() method has the final say.
                glutInit([])
            except Exception as e_glut_init_gl:
                print(f"OpenGLScene.initializeGL: Fallback GLUT init failed ({e_glut_init_gl}).")
                # Don't disable here, let the draw method handle it.
        
        glClearColor(0.12, 0.12, 0.15, 1.0) 
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glEnable(GL_CULL_FACE) 
        glShadeModel(GL_SMOOTH)
        
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.4, 0.4, 0.4, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.9, 0.9, 0.9, 1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [0.7, 0.7, 0.7, 1.0])
        
        glEnable(GL_COLOR_MATERIAL) 
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, [0.5, 0.5, 0.5, 1.0]) 
        glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 50.0) 
        
        glEnable(GL_BLEND) 
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        self.load_all_fixtures_from_db()

        if not GLUT_FUNCTIONS_USABLE:
             QTimer.singleShot(100, lambda: QMessageBox.warning(self, "3D View Warning", 
                                         "PyOpenGL GLUT features are unavailable or causing errors. Fixture shapes and beams will use simplified rendering."))


    def showEvent(self, event): 
        super().showEvent(event)
        if not self.strobe_timer.isActive():
            self.strobe_timer.start(50) 
        self.load_all_fixtures_from_db() 

    def hideEvent(self, event): 
        super().hideEvent(event)
        if self.strobe_timer.isActive():
            self.strobe_timer.stop() 

    def resizeGL(self, width, height):
        height = 1 if height == 0 else height
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, float(width) / float(height), 0.1, 500.0) 
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        eye_x = self.camera_target[0] + self.camera_zoom_distance * math.sin(math.radians(self.camera_y_angle)) * math.cos(math.radians(self.camera_x_angle))
        eye_y = self.camera_target[1] + self.camera_zoom_distance * math.sin(math.radians(self.camera_x_angle))
        eye_z = self.camera_target[2] + self.camera_zoom_distance * math.cos(math.radians(self.camera_y_angle)) * math.cos(math.radians(self.camera_x_angle))
        
        gluLookAt(eye_x, eye_y, eye_z, self.camera_target[0], self.camera_target[1], self.camera_target[2], 0, 1, 0)
        glLightfv(GL_LIGHT0, GL_POSITION, [eye_x, eye_y + 5, eye_z, 1.0]) 

        if self.draw_grid: self._draw_ground_grid()
        if self.draw_axes: self._draw_world_axes()

        for fixture_obj in self.fixtures_3d_objects.values():
            fixture_obj.show_beam_global = self.show_all_beams 
            fixture_obj.draw()

    def update_strobe_effects(self):
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

    def _draw_ground_grid(self, size=20, subdivisions=20):
        glPushAttrib(GL_LIGHTING_BIT)
        glDisable(GL_LIGHTING)
        glColor3f(0.3, 0.3, 0.32)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        step = size * 2 / subdivisions
        for i in np.arange(-size, size + step/2, step):
            glVertex3f(i, 0, -size); glVertex3f(i, 0, size)
            glVertex3f(-size, 0, i); glVertex3f(size, 0, i)
        glEnd()
        glPopAttrib() 

    def _draw_world_axes(self, length=2):
        glPushAttrib(GL_LIGHTING_BIT)
        glDisable(GL_LIGHTING)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        glColor3f(1,0,0); glVertex3f(0,0.01,0); glVertex3f(length,0.01,0)
        glColor3f(0,1,0); glVertex3f(0,0.01,0); glVertex3f(0,length+0.01,0)
        glColor3f(0,0,1); glVertex3f(0,0.01,0); glVertex3f(0,0.01,length)
        glEnd()
        glLineWidth(1.0)
        glPopAttrib()

    def mousePressEvent(self, event):
        self.last_mouse_drag_pos = event.position()

    def mouseMoveEvent(self, event):
        dx = event.position().x() - self.last_mouse_drag_pos.x()
        dy = event.position().y() - self.last_mouse_drag_pos.y()

        if event.buttons() & Qt.MouseButton.LeftButton: 
            self.camera_y_angle += dx * 0.25
            self.camera_x_angle += dy * 0.25
            self.camera_x_angle = max(-89.0, min(89.0, self.camera_x_angle)) 
        elif event.buttons() & Qt.MouseButton.RightButton: 
            pan_speed = 0.01 * (self.camera_zoom_distance / 10.0) 
            cam_right_x = math.cos(math.radians(self.camera_y_angle))
            cam_right_z = -math.sin(math.radians(self.camera_y_angle))
            self.camera_target[0] -= dx * cam_right_x * pan_speed
            self.camera_target[2] -= dx * cam_right_z * pan_speed
            self.camera_target[1] += dy * pan_speed 

        self.last_mouse_drag_pos = event.position()
        self.update()

    def wheelEvent(self, event):
        delta_degrees = event.angleDelta().y() / 8  
        delta_steps = delta_degrees / 15 
        
        zoom_speed = 0.5
        self.camera_zoom_distance -= delta_steps * zoom_speed
        self.camera_zoom_distance = max(1.0, min(150.0, self.camera_zoom_distance))
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
            print(f"Error loading all fixtures for 3D visualization: {e}")
            if "no such table" in str(e).lower() or "no such column" in str(e).lower():
                QMessageBox.warning(self, "3D View Error",
                                    "Database schema might be outdated.\n"
                                    "Please restart the application. If the issue persists, your show file may be from a much older version.\n"
                                    f"Details: {e}")

    def update_single_fixture_visualization(self, fixture_id, data_dict_from_signal):
        if fixture_id in self.fixtures_3d_objects:
            f_obj = self.fixtures_3d_objects[fixture_id]
            f_obj.position = np.array([data_dict_from_signal.get('x_pos', f_obj.position[0]), 
                                       data_dict_from_signal.get('y_pos', f_obj.position[1]), 
                                       data_dict_from_signal.get('z_pos', f_obj.position[2])], dtype=float)
            
            # Correctly read individual rotation values
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
                except Exception as e:
                    print(f"Error fetching new profile name for fixture {fixture_id}: {e}")
            
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

    def set_draw_grid(self, state):
        self.draw_grid = bool(state)
        self.update()
    
    def set_draw_axes(self, state):
        self.draw_axes = bool(state)
        self.update()

    def set_show_all_beams(self, state):
        self.show_all_beams = bool(state)
        self.update()
        
    def set_selection(self, selected_fixture_ids: list[int]):
        for fix_id, fix_obj in self.fixtures_3d_objects.items():
            fix_obj.is_selected = (fix_id in selected_fixture_ids)
        self.update()


class Visualization3DTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0) 

        self.opengl_widget = OpenGLScene(self.main_window)
        main_layout.addWidget(self.opengl_widget, 1) 

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(5,5,5,5)

        grid_checkbox = QCheckBox("Show Grid")
        grid_checkbox.setChecked(self.opengl_widget.draw_grid)
        grid_checkbox.stateChanged.connect(self.opengl_widget.set_draw_grid)
        controls_layout.addWidget(grid_checkbox)

        axes_checkbox = QCheckBox("Show Axes")
        axes_checkbox.setChecked(self.opengl_widget.draw_axes)
        axes_checkbox.stateChanged.connect(self.opengl_widget.set_draw_axes)
        controls_layout.addWidget(axes_checkbox)

        beams_checkbox = QCheckBox("Show Beams")
        beams_checkbox.setChecked(self.opengl_widget.show_all_beams)
        beams_checkbox.stateChanged.connect(self.opengl_widget.set_show_all_beams)
        controls_layout.addWidget(beams_checkbox)
        
        controls_layout.addStretch()
        main_layout.addLayout(controls_layout)

        self.setLayout(main_layout)

    def update_fixture(self, fixture_id, data_dict):
        self.opengl_widget.update_single_fixture_visualization(fixture_id, data_dict)

    def update_all_fixtures(self):
        self.opengl_widget.load_all_fixtures_from_db()
        
    def update_selection_visuals(self, selected_fixture_ids: list[int]):
        if self.opengl_widget:
            self.opengl_widget.set_selection(selected_fixture_ids)