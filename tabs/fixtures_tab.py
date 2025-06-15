# tabs/fixtures_tab.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QPushButton, QHBoxLayout, QDialog, QFormLayout, QLineEdit,
                             QSpinBox, QDoubleSpinBox, QMessageBox, QDialogButtonBox,
                             QFileDialog, QSplitter, QSizePolicy, QComboBox, QTextEdit,
                             QGroupBox, QTreeWidget, QTreeWidgetItem, QHeaderView)
from PyQt6.QtCore import pyqtSignal, Qt
import sqlite3
import json

class ProfileAttributeEditor(QDialog):
    """A dialog to edit the JSON attributes of a fixture profile."""
    def __init__(self, attributes_json, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Profile Attributes")
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Attributes (JSON format):"))
        
        self.json_edit = QTextEdit()
        self.json_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.json_edit.setAcceptRichText(False)
        # Pretty-print the JSON for readability
        try:
            parsed_json = json.loads(attributes_json)
            self.json_edit.setText(json.dumps(parsed_json, indent=2))
        except (json.JSONDecodeError, TypeError):
            self.json_edit.setText(attributes_json if isinstance(attributes_json, str) else "[]")
        
        layout.addWidget(self.json_edit)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def validate_and_accept(self):
        try:
            # Test if the JSON is valid before accepting
            json.loads(self.get_attributes_json())
            self.accept()
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Invalid JSON", f"The attribute data is not valid JSON.\n\nError: {e}")

    def get_attributes_json(self):
        # Return a compact JSON string
        try:
            parsed = json.loads(self.json_edit.toPlainText())
            return json.dumps(parsed)
        except json.JSONDecodeError:
            # If user input is not valid json, return it as is, validation will catch it.
            return self.json_edit.toPlainText()


class ProfileManagementDialog(QDialog):
    """A dialog to manage fixture profiles."""
    profiles_changed = pyqtSignal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Manage Fixture Profiles")
        self.setMinimumSize(600, 450)

        main_h_layout = QHBoxLayout()

        # Left side: List of profiles
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.addWidget(QLabel("Fixture Profiles:"))
        self.profiles_list = QListWidget()
        self.profiles_list.itemSelectionChanged.connect(self.on_profile_selected)
        left_layout.addWidget(self.profiles_list)
        
        list_buttons = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_profile)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_profile)
        list_buttons.addWidget(self.add_button)
        list_buttons.addWidget(self.delete_button)
        left_layout.addLayout(list_buttons)
        
        # Right side: Editor for selected profile
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        self.editor_group = QGroupBox("Profile Details")
        self.editor_group.setEnabled(False)
        editor_form_layout = QFormLayout(self.editor_group)
        
        self.name_edit = QLineEdit()
        self.creator_edit = QLineEdit()
        self.edit_attrs_button = QPushButton("Edit Attributes (JSON)...")
        self.edit_attrs_button.clicked.connect(self.edit_attributes)
        
        editor_form_layout.addRow("Name:", self.name_edit)
        editor_form_layout.addRow("Creator:", self.creator_edit)
        editor_form_layout.addRow(self.edit_attrs_button)
        right_layout.addWidget(self.editor_group)
        right_layout.addStretch()

        dialog_buttons = QDialogButtonBox()
        self.save_button = dialog_buttons.addButton("Save Changes", QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_button.clicked.connect(self.save_changes)
        dialog_buttons.addButton(QDialogButtonBox.StandardButton.Close).clicked.connect(self.reject)
        right_layout.addWidget(dialog_buttons)
        
        # Splitter to hold left and right sides
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setSizes([200, 380])
        
        main_h_layout.addWidget(splitter)
        self.setLayout(main_h_layout)

        self.load_profiles()

    def load_profiles(self):
        current_selection_id = None
        if self.profiles_list.currentItem():
            data = self.profiles_list.currentItem().data(Qt.ItemDataRole.UserRole)
            if data:
                current_selection_id = data[0]

        self.profiles_list.clear()
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name, creator, attributes_json FROM fixture_profiles ORDER BY name")
            profiles = cursor.fetchall()
            new_selection_item = None
            for profile_id, name, creator, attrs in profiles:
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, (profile_id, name, creator, attrs))
                self.profiles_list.addItem(item)
                if profile_id == current_selection_id:
                    new_selection_item = item
            
            if new_selection_item:
                self.profiles_list.setCurrentItem(new_selection_item)
            else:
                self.on_profile_selected()

        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not load profiles: {e}")
            
    def on_profile_selected(self):
        item = self.profiles_list.currentItem()
        if item:
            self.editor_group.setEnabled(True)
            profile_id, name, creator, attrs = item.data(Qt.ItemDataRole.UserRole)
            self.name_edit.setText(name)
            self.creator_edit.setText(creator or "")
            self.edit_attrs_button.setProperty("current_attrs", attrs)
        else:
            self.editor_group.setEnabled(False)
            self.name_edit.clear()
            self.creator_edit.clear()
            self.edit_attrs_button.setProperty("current_attrs", "[]")

    def add_profile(self):
        self.profiles_list.setCurrentItem(None)
        self.editor_group.setEnabled(True)
        self.name_edit.setText("New Profile")
        self.creator_edit.setText("User")
        self.edit_attrs_button.setProperty("current_attrs", '[{"name": "Dimmer"}]')
        self.name_edit.selectAll()
        self.name_edit.setFocus()

    def delete_profile(self):
        item = self.profiles_list.currentItem()
        if not item: return
        
        profile_id, name, _, _ = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete profile '{name}'?\nThis cannot be undone and may affect fixtures using it.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("DELETE FROM fixture_profiles WHERE id = ?", (profile_id,))
                self.main_window.db_connection.commit()
                self.profiles_changed.emit()
                self.load_profiles()
            except sqlite3.IntegrityError:
                 QMessageBox.critical(self, "Delete Error", f"Cannot delete profile '{name}' as it is currently in use by one or more fixtures. Please re-assign those fixtures to another profile first.")
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Failed to delete profile: {e}")

    def edit_attributes(self):
        current_attrs = self.edit_attrs_button.property("current_attrs")
        dialog = ProfileAttributeEditor(current_attrs, self)
        if dialog.exec():
            self.edit_attrs_button.setProperty("current_attrs", dialog.get_attributes_json())
            QMessageBox.information(self, "Attributes Updated", "Attributes updated. Click 'Save Changes' to commit to the database.")
            
    def save_changes(self):
        item = self.profiles_list.currentItem()
        is_new = item is None

        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Profile name cannot be empty.")
            return

        creator = self.creator_edit.text().strip()
        attributes = self.edit_attrs_button.property("current_attrs")

        try:
            cursor = self.main_window.db_connection.cursor()
            if is_new:
                cursor.execute("INSERT INTO fixture_profiles (name, creator, attributes_json) VALUES (?, ?, ?)",
                               (name, creator, attributes))
            else:
                profile_id, _, _, _ = item.data(Qt.ItemDataRole.UserRole)
                cursor.execute("UPDATE fixture_profiles SET name = ?, creator = ?, attributes_json = ? WHERE id = ?",
                               (name, creator, attributes, profile_id))
            
            self.main_window.db_connection.commit()
            self.profiles_changed.emit()
            self.load_profiles()
            QMessageBox.information(self, "Success", f"Profile '{name}' saved.")
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "DB Error", f"A profile named '{name}' already exists.")
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Failed to save profile: {e}")


class FixtureEditFormWidget(QWidget):
    """
    A form widget to edit the properties of a single fixture.
    """
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.current_fixture_pk_id = None # The unique primary key `id`

        self.layout = QFormLayout(self)
        self.layout.setContentsMargins(10, 5, 10, 5)
        self.layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # --- Input Fields ---
        self.name_edit = QLineEdit()
        self.profile_combo = QComboBox()
        self.populate_profiles()
        
        self.fid_edit = QSpinBox(); self.fid_edit.setRange(1, 10000)
        self.sfi_edit = QSpinBox(); self.sfi_edit.setRange(1, 10000)
        self.instance_count_edit = QSpinBox(); self.instance_count_edit.setRange(1, 256); self.instance_count_edit.setValue(1)

        self.x_pos_edit = QDoubleSpinBox(); self.x_pos_edit.setRange(-10000, 10000); self.x_pos_edit.setDecimals(3)
        self.y_pos_edit = QDoubleSpinBox(); self.y_pos_edit.setRange(-10000, 10000); self.y_pos_edit.setDecimals(3)
        self.z_pos_edit = QDoubleSpinBox(); self.z_pos_edit.setRange(-10000, 10000); self.z_pos_edit.setDecimals(3)
        self.rot_x_edit = QDoubleSpinBox(); self.rot_x_edit.setRange(-360, 360); self.rot_x_edit.setDecimals(2)
        self.rot_y_edit = QDoubleSpinBox(); self.rot_y_edit.setRange(-360, 360); self.rot_y_edit.setDecimals(2)
        self.rot_z_edit = QDoubleSpinBox(); self.rot_z_edit.setRange(-360, 360); self.rot_z_edit.setDecimals(2)
        
        self.focus_edit = QDoubleSpinBox(); self.focus_edit.setRange(0.0, 1.0); self.focus_edit.setDecimals(2); self.focus_edit.setSingleStep(0.05)
        self.zoom_edit = QDoubleSpinBox(); self.zoom_edit.setRange(5.0, 90.0); self.zoom_edit.setDecimals(1); self.zoom_edit.setSuffix(" °")


        # --- Layout Arrangement ---
        self.layout.addRow("Name:", self.name_edit)
        self.layout.addRow("Fixture Profile:", self.profile_combo)
        self.layout.addRow("Fixture ID (FID):", self.fid_edit)
        self.layout.addRow("Sub-Fixture Index (SFI):", self.sfi_edit)
        self.instance_count_label = QLabel("Number of Lens/Instances:")
        self.layout.addRow(self.instance_count_label, self.instance_count_edit)
        self.layout.addRow("X Position:", self.x_pos_edit)
        self.layout.addRow("Y Position:", self.y_pos_edit)
        self.layout.addRow("Z Position:", self.z_pos_edit)
        self.layout.addRow("X Rotation:", self.rot_x_edit)
        self.layout.addRow("Y Rotation:", self.rot_y_edit)
        self.layout.addRow("Z Rotation:", self.rot_z_edit)
        self.layout.addRow("Default Zoom:", self.zoom_edit)
        self.layout.addRow("Default Focus:", self.focus_edit)

    def populate_profiles(self):
        current_id = self.profile_combo.currentData()
        self.profile_combo.clear()
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name FROM fixture_profiles ORDER BY name")
            profiles = cursor.fetchall()
            for profile_id, name in profiles:
                self.profile_combo.addItem(name, userData=profile_id)
            
            if current_id is not None:
                idx = self.profile_combo.findData(current_id)
                if idx != -1:
                    self.profile_combo.setCurrentIndex(idx)

        except Exception as e:
            self.profile_combo.addItem("Error loading profiles")
            print(f"Error populating fixture profiles combo: {e}")


    def set_create_mode(self, is_create: bool):
        """Switches the form between Create and Edit mode."""
        self.fid_edit.setReadOnly(not is_create)
        self.sfi_edit.setReadOnly(True) # SFI is only editable on creation via start index
        
        self.instance_count_edit.setVisible(is_create)
        self.instance_count_label.setVisible(is_create)
        self.sfi_edit.setToolTip("Starting Sub-Fixture Index." if is_create else "Sub-Fixture Index (read-only).")
        if is_create:
            self.layout.labelForField(self.sfi_edit).setText("Starting SFI:")
        else:
            self.layout.labelForField(self.sfi_edit).setText("Sub-Fixture Index (SFI):")

        # Hide position controls in create mode to simplify
        pos_widgets = [self.x_pos_edit, self.y_pos_edit, self.z_pos_edit,
                       self.rot_x_edit, self.rot_y_edit, self.rot_z_edit]
        for widget in pos_widgets:
            widget.setVisible(not is_create)
            self.layout.labelForField(widget).setVisible(not is_create)


    def load_data(self, fixture_data: dict | None):
        """Populates the form with data. Pass None to clear for a new entry."""
        is_new = fixture_data is None
        self.set_create_mode(is_new)
        
        if not is_new:
            self.current_fixture_pk_id = fixture_data.get('id')
            self.name_edit.setText(str(fixture_data.get('name', '')))
            
            profile_id = fixture_data.get('profile_id')
            if profile_id is not None:
                idx = self.profile_combo.findData(profile_id)
                if idx != -1: self.profile_combo.setCurrentIndex(idx)
                else: self.profile_combo.setCurrentIndex(0)
            else: self.profile_combo.setCurrentIndex(0)

            self.fid_edit.setValue(fixture_data.get('fid', 1))
            self.sfi_edit.setValue(fixture_data.get('sfi', 1))

            self.x_pos_edit.setValue(float(fixture_data.get('x_pos', 0)))
            self.y_pos_edit.setValue(float(fixture_data.get('y_pos', 0)))
            self.z_pos_edit.setValue(float(fixture_data.get('z_pos', 0)))
            self.rot_x_edit.setValue(float(fixture_data.get('rotation_x', 0)))
            self.rot_y_edit.setValue(float(fixture_data.get('rotation_y', 0)))
            self.rot_z_edit.setValue(float(fixture_data.get('rotation_z', 0)))
            self.zoom_edit.setValue(float(fixture_data.get('zoom', 15.0)))
            self.focus_edit.setValue(float(fixture_data.get('focus', 50.0)) / 100.0)
            self.setEnabled(True)
        else: # Clear form for new fixture
            self.current_fixture_pk_id = None
            self.name_edit.setText("New Fixture")
            if self.profile_combo.count() > 0: self.profile_combo.setCurrentIndex(0)

            # Suggest the next available FID
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("SELECT MAX(fid) FROM fixtures")
                max_fid = cursor.fetchone()[0]
                self.fid_edit.setValue( (max_fid or 0) + 1 )
            except Exception as e:
                self.fid_edit.setValue(1)
                print(f"Could not fetch max FID: {e}")
            
            self.sfi_edit.setValue(1)
            self.instance_count_edit.setValue(1)

            # Default values for non-visible fields
            self.x_pos_edit.setValue(0); self.y_pos_edit.setValue(0); self.z_pos_edit.setValue(0)
            self.rot_x_edit.setValue(0); self.rot_y_edit.setValue(0); self.rot_z_edit.setValue(0)
            self.zoom_edit.setValue(15.0); self.focus_edit.setValue(0.5)
            self.setEnabled(True)
            self.name_edit.selectAll()
            self.name_edit.setFocus()

    def get_data(self) -> dict | None:
        """Returns a dictionary of the data in the form."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Fixture name cannot be empty.")
            return None
        
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            QMessageBox.warning(self, "Input Error", "A valid fixture profile must be selected.")
            return None

        data = {
            'name': name,
            'profile_id': profile_id,
            'fid': self.fid_edit.value(),
            'sfi': self.sfi_edit.value(),
            'x_pos': self.x_pos_edit.value(),
            'y_pos': self.y_pos_edit.value(),
            'z_pos': self.z_pos_edit.value(),
            'rotation_x': self.rot_x_edit.value(),
            'rotation_y': self.rot_y_edit.value(),
            'rotation_z': self.rot_z_edit.value(),
            'zoom': self.zoom_edit.value(),
            'focus': self.focus_edit.value() * 100.0, # Convert back to 0-100 for DB
            'red': 255, 'green': 255, 'blue': 255, 'brightness': 100,
            'gobo_spin': 128.0, 'shutter_strobe_rate': 0.0,
        }
        if self.current_fixture_pk_id is not None:
            data['id'] = self.current_fixture_pk_id
        else: # For new fixtures
            data['instance_count'] = self.instance_count_edit.value()
        return data

class FixturesTab(QWidget):
    fixture_updated = pyqtSignal(int, dict) 
    fixture_added = pyqtSignal(dict)       
    fixture_deleted = pyqtSignal(list)     

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.db_connection = self.main_window.db_connection # Correctly get DB connection
        self.init_ui()
        self.load_fixtures_into_list()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Top controls ---
        controls_layout = QHBoxLayout()
        self.add_new_button = QPushButton("Add New")
        self.add_new_button.clicked.connect(self._prepare_new_fixture)
        controls_layout.addWidget(self.add_new_button)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setObjectName("DestructiveButton")
        self.delete_button.clicked.connect(self._delete_selected_fixture)
        controls_layout.addWidget(self.delete_button)
        
        self.save_button = QPushButton("Save Changes")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save_changes)
        controls_layout.addWidget(self.save_button)
        
        controls_layout.addStretch()

        manage_profiles_button = QPushButton("Manage Profiles")
        manage_profiles_button.clicked.connect(self.handle_manage_profiles)
        controls_layout.addWidget(manage_profiles_button)
        main_layout.addLayout(controls_layout)

        # --- Main Content Splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        
        # Left Panel: Fixture List
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.addWidget(QLabel("Patched Fixtures:"))
        self.fixtures_tree_widget = QTreeWidget()
        self.fixtures_tree_widget.setHeaderLabels(["FID", "SFI", "Name", "ID"])
        self.fixtures_tree_widget.setSortingEnabled(True)
        self.fixtures_tree_widget.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.fixtures_tree_widget.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.fixtures_tree_widget.itemSelectionChanged.connect(self._on_fixture_selected)
        list_layout.addWidget(self.fixtures_tree_widget)
        splitter.addWidget(list_container)

        # Right Panel: Edit Form
        self.edit_form_widget = FixtureEditFormWidget(self.main_window, self)
        splitter.addWidget(self.edit_form_widget)
        
        splitter.setSizes([350, 450])
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def load_fixtures_into_list(self):
        """Loads/refreshes the fixture list from the database."""
        selected_id = None
        if self.fixtures_tree_widget.currentItem():
            selected_id = self.fixtures_tree_widget.currentItem().data(3, Qt.ItemDataRole.UserRole)
        
        self.fixtures_tree_widget.clear()
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT f.id, f.fid, f.sfi, f.name, p.name 
                FROM fixtures f 
                JOIN fixture_profiles p ON f.profile_id = p.id 
                ORDER BY f.fid, f.sfi
            """)
            fixtures = cursor.fetchall()
            
            parent_items = {}
            item_to_reselect = None
            for pk_id, fid, sfi, name, profile_name in fixtures:
                if fid not in parent_items:
                    parent_item = QTreeWidgetItem(self.fixtures_tree_widget, [str(fid), "", name])
                    parent_items[fid] = parent_item

                child_item = QTreeWidgetItem(parent_items[fid], [str(fid), str(sfi), name, str(pk_id)])
                child_item.setToolTip(2, f"Profile: {profile_name}")
                child_item.setData(3, Qt.ItemDataRole.UserRole, pk_id) # Store primary key ID
                
                if pk_id == selected_id:
                    item_to_reselect = child_item
            
            self.fixtures_tree_widget.expandAll()
            
            if item_to_reselect:
                self.fixtures_tree_widget.setCurrentItem(item_to_reselect)
            elif self.fixtures_tree_widget.topLevelItemCount() > 0:
                first_parent = self.fixtures_tree_widget.topLevelItem(0)
                if first_parent and first_parent.childCount() > 0:
                     self.fixtures_tree_widget.setCurrentItem(first_parent.child(0))
            else:
                self._on_fixture_selected()

        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Error loading fixtures: {e}")

    def _on_fixture_selected(self):
        """Slot for when the list selection changes."""
        current_item = self.fixtures_tree_widget.currentItem()
        if current_item and current_item.childCount() == 0: # It's a sub-item
            fixture_id = current_item.data(3, Qt.ItemDataRole.UserRole)
            try:
                cursor = self.db_connection.cursor()
                cursor.execute("SELECT * FROM fixtures WHERE id = ?", (fixture_id,))
                fixture_row = cursor.fetchone()
                if fixture_row:
                    db_cols = [desc[0] for desc in cursor.description]
                    fixture_data_dict = dict(zip(db_cols, fixture_row))
                    self.edit_form_widget.load_data(fixture_data_dict)
                    self.save_button.setText("Save Changes")
                else:
                    QMessageBox.warning(self, "Error", f"Fixture ID {fixture_id} not found in database.")
                    self.load_fixtures_into_list()
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Error fetching fixture details: {e}")
        else: # No item selected or a parent item is selected
            self.edit_form_widget.setEnabled(False)
            self.save_button.setText("Save Changes")

    def _prepare_new_fixture(self):
        """Clears the selection and form to prepare for a new fixture entry."""
        self.fixtures_tree_widget.clearSelection()
        self.edit_form_widget.load_data(None)
        self.save_button.setText("Create New Fixture(s)")

    def _save_changes(self):
        """Saves data from the form, either creating or updating a fixture."""
        fixture_data = self.edit_form_widget.get_data()
        if not fixture_data:
            return # Validation failed in get_data()

        is_new = self.edit_form_widget.current_fixture_pk_id is None
        
        try:
            cursor = self.db_connection.cursor()
            
            if is_new:
                instance_count = fixture_data.pop('instance_count')
                start_sfi = fixture_data['sfi']
                fid = fixture_data['fid']
                
                # Check for FID/SFI collisions before creating any instances
                for i in range(instance_count):
                    sfi_to_check = start_sfi + i
                    cursor.execute("SELECT id FROM fixtures WHERE fid = ? AND sfi = ?", (fid, sfi_to_check))
                    if cursor.fetchone():
                        QMessageBox.warning(self, "ID Collision", f"Fixture ID {fid}.{sfi_to_check} already exists. Please choose a different starting FID or SFI.")
                        return
                
                # Create the instances
                for i in range(instance_count):
                    fixture_data['sfi'] = start_sfi + i
                    columns = [col for col in fixture_data.keys() if col != 'id']
                    placeholders = ', '.join(['?'] * len(columns))
                    values = tuple(fixture_data[col] for col in columns)
                    cursor.execute(f"INSERT INTO fixtures ({', '.join(columns)}) VALUES ({placeholders})", values)
                    new_id = cursor.lastrowid
                    created_fixture_data = fixture_data.copy()
                    created_fixture_data['id'] = new_id
                    self.fixture_added.emit(created_fixture_data)
                
                QMessageBox.information(self, "Success", f"{instance_count} fixture instance(s) created.")

            else: # Update existing
                fixture_id = fixture_data.pop('id')
                set_clauses = [f"{col} = ?" for col in fixture_data.keys() if col not in ['fid', 'sfi']]
                values = [fixture_data[col] for col in fixture_data.keys() if col not in ['fid', 'sfi']] + [fixture_id]
                cursor.execute(f"UPDATE fixtures SET {', '.join(set_clauses)} WHERE id = ?", tuple(values))
                self.fixture_updated.emit(fixture_id, fixture_data)
                QMessageBox.information(self, "Success", f"Fixture '{fixture_data['name']}' updated.")
            
            self.db_connection.commit()
            self.load_fixtures_into_list()

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save fixture changes: {e}")

    def _delete_selected_fixture(self):
        selected_items = self.fixtures_tree_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a fixture or fixture group to delete.")
            return

        item = selected_items[0]
        ids_to_delete = []
        
        if item.childCount() > 0: # Is a parent item
            fid = int(item.text(0))
            reply = QMessageBox.question(self, "Confirm Delete", 
                                     f"Are you sure you want to delete ALL instances of Fixture {fid}?\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                for i in range(item.childCount()):
                    ids_to_delete.append(item.child(i).data(3, Qt.ItemDataRole.UserRole))
        else: # Is a child item
            fixture_id = item.data(3, Qt.ItemDataRole.UserRole)
            fixture_name = f"{item.text(0)}.{item.text(1)} ({item.text(2)})"
            reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete fixture '{fixture_name}'?\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                ids_to_delete.append(fixture_id)

        if not ids_to_delete:
            return

        try:
            cursor = self.db_connection.cursor()
            placeholders = ','.join(['?'] * len(ids_to_delete))
            cursor.execute(f"DELETE FROM fixtures WHERE id IN ({placeholders})", tuple(ids_to_delete))
            self.db_connection.commit()
            
            self.fixture_deleted.emit(ids_to_delete)
            self.load_fixtures_into_list()
            QMessageBox.information(self, "Success", f"{len(ids_to_delete)} fixture(s) deleted.")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to delete fixture(s): {e}")

    def handle_manage_profiles(self):
        """Opens the dialog to manage fixture profiles."""
        dialog = ProfileManagementDialog(self.main_window, self)
        dialog.profiles_changed.connect(self.edit_form_widget.populate_profiles)
        dialog.exec()
        # Refresh the main list to update tooltips in case names changed
        self.load_fixtures_into_list()

    def refresh_fixtures(self):
        """Public method to be called from outside to refresh the list."""
        self.load_fixtures_into_list()
        self.edit_form_widget.populate_profiles()
