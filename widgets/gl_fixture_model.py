# widgets/gl_fixture_model.py
import numpy as np
import math

from OpenGL.GL import *
from OpenGL.GLU import *

# This global flag will track if import succeeds, but can be set to False at runtime if a GLUT call fails.
GLUT_FUNCTIONS_USABLE = False
glutSolidSphere, glutSolidCylinder, glutSolidCone, glutSolidCube, glutInit = None, None, None, None, None
try:
    from OpenGL.GLUT import glutSolidSphere, glutSolidCylinder, glutSolidCone, glutSolidCube, glutInit
    GLUT_FUNCTIONS_USABLE = True 
except ImportError:
    print("WARNING: PyOpenGL GLUT bindings not found. 3D shapes will be basic cubes/lines.")
    GLUT_FUNCTIONS_USABLE = False
except Exception as e: # Catches other potential init errors from GLUT
    print(f"WARNING: PyOpenGL GLUT could not be initialized ({e}). 3D shapes will be basic cubes/lines.")
    GLUT_FUNCTIONS_USABLE = False

class Fixture3D:
    def __init__(self, id, profile_id, profile_name, name,
                 x, y, z, rot_x, rot_y, rot_z, 
                 r, g, b, brightness,
                 gobo_index=0, zoom=15.0, focus=50.0, shutter_strobe_rate=0.0, gobo_spin=128.0): 
        self.id = id
        self.profile_id = profile_id
        self.type = profile_name.lower() if profile_name else "generic"
        self.name = name
        self.position = np.array([float(x), float(y), float(z)], dtype=float)
        self.rotation_euler_xyz = np.array([float(rot_x), float(rot_y), float(rot_z)], dtype=float) 
        self.color_rgb = np.array([r/255.0, g/255.0, b/255.0], dtype=float)
        self.intensity = float(brightness) / 100.0 
        
        self.gobo_spin = float(gobo_spin)
        self.zoom_angle_deg = float(zoom) 
        self.focus_percent = float(focus) # 0.0 (soft) to 100.0 (sharp)
        self.shutter_strobe_rate_hz = float(shutter_strobe_rate)

        self.show_beam_global = True 
        self._beam_actually_visible_strobe_state = True 
        self.is_selected = False

    def _draw_cube_primitive(self, size=0.5):
        s = size / 2.0
        glBegin(GL_QUADS)
        glNormal3f(0,0,1); glVertex3f(-s, -s,  s); glVertex3f( s, -s,  s); glVertex3f( s,  s,  s); glVertex3f(-s,  s,  s)
        glNormal3f(0,0,-1); glVertex3f(-s, -s, -s); glVertex3f(-s,  s, -s); glVertex3f( s,  s, -s); glVertex3f( s, -s, -s)
        glNormal3f(0,1,0); glVertex3f(-s,  s, -s); glVertex3f(-s,  s,  s); glVertex3f( s,  s,  s); glVertex3f( s,  s, -s)
        glNormal3f(0,-1,0); glVertex3f(-s, -s, -s); glVertex3f( s, -s, -s); glVertex3f( s, -s,  s); glVertex3f(-s, -s,  s)
        glNormal3f(1,0,0); glVertex3f( s, -s, -s); glVertex3f( s,  s, -s); glVertex3f( s,  s,  s); glVertex3f( s, -s,  s)
        glNormal3f(-1,0,0); glVertex3f(-s, -s, -s); glVertex3f(-s, -s,  s); glVertex3f(-s,  s,  s); glVertex3f(-s,  s, -s)
        glEnd()

    def _draw_wire_cube_primitive(self, size=0.5):
        s = size / 2.0
        glBegin(GL_LINE_LOOP); glVertex3f(s,s,-s); glVertex3f(-s,s,-s); glVertex3f(-s,-s,-s); glVertex3f(s,-s,-s); glEnd()
        glBegin(GL_LINE_LOOP); glVertex3f(s,-s,s); glVertex3f(-s,-s,s); glVertex3f(-s,s,s); glVertex3f(s,s,s); glEnd()
        glBegin(GL_LINES); glVertex3f(s,s,-s); glVertex3f(s,s,s); glVertex3f(-s,s,-s); glVertex3f(-s,s,s); glVertex3f(-s,-s,-s); glVertex3f(-s,-s,s); glVertex3f(s,-s,-s); glVertex3f(s,-s,s); glEnd()

    def _draw_cone_fallback(self, base_radius, height):
        num_segments = 8 
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0, 0, 0)
        for i in range(num_segments + 1): 
            angle = (i / num_segments) * 2 * math.pi
            x = base_radius * math.cos(angle)
            y = base_radius * math.sin(angle)
            glVertex3f(x, y, height)
        glEnd()
        glBegin(GL_POLYGON)
        for i in range(num_segments):
            angle = (i / num_segments) * 2 * math.pi
            x = base_radius * math.cos(angle)
            y = base_radius * math.sin(angle)
            glVertex3f(x, y, height)
        glEnd()


    def draw(self):
        global GLUT_FUNCTIONS_USABLE 
        glPushMatrix()
        
        # Apply fixture's world position
        glTranslatef(self.position[0], self.position[1], self.position[2])
        
        # --- Draw Selection Box (around the base) ---
        if self.is_selected:
            glPushAttrib(GL_LIGHTING_BIT | GL_LINE_BIT | GL_POLYGON_BIT)
            glDisable(GL_LIGHTING)
            glLineWidth(2.5)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE) 
            glColor3f(1.0, 1.0, 0.0) # Yellow
            self._draw_wire_cube_primitive(0.4) 
            glPopAttrib()

        # Apply base rotation (Yaw/Pan)
        glRotatef(self.rotation_euler_xyz[1], 0, 1, 0)
        
        # --- Draw Fixture Body and Head ---
        fixture_body_size = 0.25
        final_color_rgb = self.color_rgb * self.intensity
        
        # Draw Base (common to most types)
        glColor3f(0.2, 0.2, 0.22)
        if GLUT_FUNCTIONS_USABLE and "moving head" in self.type:
             glPushMatrix()
             glScalef(1.2, 0.2, 1.2)
             try:
                 glutSolidCube(fixture_body_size * 1.5)
             except Exception:
                 GLUT_FUNCTIONS_USABLE = False
                 self._draw_cube_primitive(fixture_body_size)
             glPopMatrix()
        elif "moving head" not in self.type:
            pass # No base for static fixtures
        else:
             self._draw_cube_primitive(fixture_body_size)

        # Apply head-specific rotations (Tilt) before drawing head and beam
        glRotatef(self.rotation_euler_xyz[0], 1, 0, 0)
        
        # Head color
        glColor3fv(final_color_rgb.tolist())

        # Save the matrix state before head rotations
        glPushMatrix()

        try:
            if GLUT_FUNCTIONS_USABLE:
                if "moving head" in self.type:
                    glTranslatef(0, fixture_body_size * 0.5, 0)
                    glutSolidSphere(fixture_body_size, 16, 16)
                
                elif self.type == "par can":
                    glPushMatrix()
                    glRotatef(90, 1, 0, 0)
                    glutSolidCylinder(fixture_body_size * 0.9, fixture_body_size * 1.6, 16, 8) 
                    glPopMatrix()

                elif self.type in ["blinder", "led bar"]:
                    glPushMatrix()
                    glScalef(1.8, 1.2, 0.4)
                    glutSolidCube(fixture_body_size)
                    glPopMatrix()

                else: # Generic fallback
                    self._draw_cube_primitive(fixture_body_size * 1.5)
            else: 
                self._draw_cube_primitive(fixture_body_size * 1.5)
        except Exception as e_glut_body:
            if "NULL" not in str(e_glut_body).upper(): 
                print(f"RUNTIME ERROR using GLUT for fixture body (ID: {self.id}): {e_glut_body}. Disabling GLUT drawing.")
            GLUT_FUNCTIONS_USABLE = False
            self._draw_cube_primitive(fixture_body_size * 1.5)

        # --- Draw Gobo/Beam ---
        is_beam_on = self.intensity > 0.01 and self.show_beam_global
        if self.shutter_strobe_rate_hz > 0:
            is_beam_on = is_beam_on and self._beam_actually_visible_strobe_state
        
        if is_beam_on:
            beam_length = 5.0  
            beam_end_radius_at_length = beam_length * math.tan(math.radians(self.zoom_angle_deg / 2.0))
            beam_end_radius_at_length = max(0.01, beam_end_radius_at_length) 
            
            beam_alpha = 0.15 + (self.intensity * 0.35) 
            glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE, [final_color_rgb[0], final_color_rgb[1], final_color_rgb[2], beam_alpha])
            glColor4f(final_color_rgb[0], final_color_rgb[1], final_color_rgb[2], beam_alpha)

            # Apply roll (Z-axis rotation) for the beam/gobo spin
            glRotatef(self.rotation_euler_xyz[2], 0, 0, 1)

            try:
                if GLUT_FUNCTIONS_USABLE:
                    if self.focus_percent > 70: slices, stacks = 24, 10
                    elif self.focus_percent < 30: slices, stacks = 10, 4
                    else: slices, stacks = 16, 8
                    
                    # Translate beam forward from head center
                    if "moving head" in self.type:
                        glTranslatef(0, 0, fixture_body_size * 0.5)
                    else: # Static fixtures shoot straight out
                        glTranslatef(0, 0, 0)
                    
                    glutSolidCone(beam_end_radius_at_length, beam_length, slices, stacks)
                else: 
                    if "moving head" in self.type:
                        glTranslatef(0, 0, fixture_body_size * 0.5)
                    self._draw_cone_fallback(beam_end_radius_at_length, beam_length)

            except Exception as e_glut_beam:
                if "NULL" not in str(e_glut_beam).upper():
                    print(f"RUNTIME ERROR using GLUT for beam (ID: {self.id}): {e_glut_beam}. Disabling GLUT drawing.")
                GLUT_FUNCTIONS_USABLE = False
                if "moving head" in self.type:
                    glTranslatef(0, 0, fixture_body_size * 0.5)
                self._draw_cone_fallback(beam_end_radius_at_length, beam_length)
        
        # Restore matrix state to before head rotations
        glPopMatrix() 
        # Restore matrix state to before fixture world position
        glPopMatrix()
