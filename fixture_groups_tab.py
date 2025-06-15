# fixture_groups_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QMessageBox, QDialog, QDialogButtonBox,
    QFormLayout, QSplitter, QAbstractItemView, QSizePolicy # Added QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
import sqlite3

class GroupNameDialog(QDialog):
    def __init__(self, current_name="", parent=None, existing_names=None):
        super().__init__(parent)
        self.setWindowTitle("Group Name")
        self.existing_names = existing_names if existing_names else []
        
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(current_name)
        self.name_edit.setPlaceholderText("Enter a unique group name")
        layout.addRow("Group Name:", self.name_edit)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
    def validate_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Group name cannot be empty.")
            return
        if name in self.existing_names:
            QMessageBox.warning(self, "Input Error", f"A group named '{name}' already exists. Please choose a different name.")
            return
        self.accept()

    def get_group_name(self):
        return self.name_edit.text().strip()

class FixtureGroupsTab(QWidget):
    fixture_groups_changed = pyqtSignal() # Emitted when groups are added, removed, or fixtures assigned

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_selected_group_id = None
        self.init_ui()
        self.load_groups()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Top controls for groups
        group_controls_layout = QHBoxLayout()
        self.add_group_button = QPushButton("Add Group")
        self.add_group_button.clicked.connect(self.add_group)
        group_controls_layout.addWidget(self.add_group_button)

        self.rename_group_button = QPushButton("Rename Group")
        self.rename_group_button.clicked.connect(self.rename_group)
        group_controls_layout.addWidget(self.rename_group_button)

        self.delete_group_button = QPushButton("Delete Group")
        self.delete_group_button.setStyleSheet("background-color: #c62828;")
        self.delete_group_button.clicked.connect(self.delete_group)
        group_controls_layout.addWidget(self.delete_group_button)
        group_controls_layout.addStretch()
        main_layout.addLayout(group_controls_layout)

        # Splitter for group list and fixture assignment areas
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Group List
        group_list_widget_container = QWidget() # Use a container for better control if needed
        group_list_layout = QVBoxLayout(group_list_widget_container)
        group_list_layout.addWidget(QLabel("Fixture Groups:"))
        self.groups_list_widget = QListWidget()
        self.groups_list_widget.setSortingEnabled(True)
        self.groups_list_widget.itemSelectionChanged.connect(self.on_group_selected)
        self.groups_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        group_list_layout.addWidget(self.groups_list_widget)
        splitter.addWidget(group_list_widget_container)

        # Right side: Fixture assignment
        fixture_assignment_widget_container = QWidget() # Use a container
        fixture_assignment_layout = QVBoxLayout(fixture_assignment_widget_container)
        
        fixture_assignment_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top-Right: Fixtures in Selected Group
        in_group_widget = QWidget()
        in_group_layout = QVBoxLayout(in_group_widget)
        in_group_layout.addWidget(QLabel("Fixtures in Selected Group:"))
        self.fixtures_in_group_list = QListWidget()
        self.fixtures_in_group_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.fixtures_in_group_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        in_group_layout.addWidget(self.fixtures_in_group_list)
        remove_fixture_button = QPushButton("<< Remove Selected from Group")
        remove_fixture_button.clicked.connect(self.remove_fixtures_from_group)
        in_group_layout.addWidget(remove_fixture_button)
        fixture_assignment_splitter.addWidget(in_group_widget)

        # Bottom-Right: Available Fixtures
        available_fixtures_widget = QWidget()
        available_fixtures_layout = QVBoxLayout(available_fixtures_widget)
        available_fixtures_layout.addWidget(QLabel("Available Fixtures (Not in Group):"))
        self.available_fixtures_list = QListWidget()
        self.available_fixtures_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.available_fixtures_list.setSortingEnabled(True)
        self.available_fixtures_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        available_fixtures_layout.addWidget(self.available_fixtures_list)
        add_fixture_button = QPushButton("Add Selected to Group >>")
        add_fixture_button.clicked.connect(self.add_fixtures_to_group)
        available_fixtures_layout.addWidget(add_fixture_button)
        fixture_assignment_splitter.addWidget(available_fixtures_widget)
        
        # Adjust initial sizes for the vertical splitter to give more balanced space
        # These are just suggestions; adjust based on desired look.
        fixture_assignment_splitter.setSizes([self.height() // 2, self.height() // 2]) 
        fixture_assignment_layout.addWidget(fixture_assignment_splitter)
        splitter.addWidget(fixture_assignment_widget_container)
        
        # Adjust initial sizes for the main horizontal splitter
        # Give less space to group list, more to fixture assignment area
        # For example, 1/4 to groups list, 3/4 to fixture assignment.
        # These are initial sizes, user can still drag.
        initial_group_list_width = self.width() // 4 
        initial_assignment_width = 3 * self.width() // 4
        if initial_group_list_width < 150: # Ensure a minimum reasonable width
            initial_group_list_width = 150
            initial_assignment_width = max(200, self.width() - initial_group_list_width - splitter.handleWidth())

        splitter.setSizes([initial_group_list_width, initial_assignment_width]) 
        main_layout.addWidget(splitter)

        self.setLayout(main_layout)
        self.update_fixture_related_widgets_enabled_state()

    def update_fixture_related_widgets_enabled_state(self):
        enabled = self.current_selected_group_id is not None
        self.fixtures_in_group_list.setEnabled(enabled)
        self.available_fixtures_list.setEnabled(enabled)
        
        # Iterate through children of the fixture_assignment_widget_container's layout
        # This assumes the buttons are direct children of layouts within fixture_assignment_splitter's widgets.
        
        # For buttons related to "Fixtures in Group" list
        if self.fixtures_in_group_list.parentWidget():
            for child in self.fixtures_in_group_list.parentWidget().findChildren(QPushButton):
                 if child.text().startswith("<< Remove"):
                    child.setEnabled(enabled)
        
        # For buttons related to "Available Fixtures" list
        if self.available_fixtures_list.parentWidget():
            for child in self.available_fixtures_list.parentWidget().findChildren(QPushButton):
                if child.text().startswith("Add Selected"):
                    child.setEnabled(enabled)


    def load_groups(self):
        self.groups_list_widget.clear()
        self.current_selected_group_id = None
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT id, name FROM fixture_groups ORDER BY name")
            groups = cursor.fetchall()
            for group_id, name in groups:
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, group_id)
                self.groups_list_widget.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Error loading groups: {e}")
        self.on_group_selected() 

    def get_all_group_names(self):
        names = []
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT name FROM fixture_groups")
            names = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching all group names: {e}")
        return names

    def add_group(self):
        existing_names = self.get_all_group_names()
        dialog = GroupNameDialog(parent=self, existing_names=existing_names)
        if dialog.exec():
            name = dialog.get_group_name()
            if name:
                try:
                    cursor = self.main_window.db_connection.cursor()
                    cursor.execute("INSERT INTO fixture_groups (name) VALUES (?)", (name,))
                    self.main_window.db_connection.commit()
                    self.load_groups()
                    self.fixture_groups_changed.emit()
                except sqlite3.IntegrityError: 
                     QMessageBox.warning(self, "Error", f"Group '{name}' already exists or database constraint failed.")
                except Exception as e:
                    QMessageBox.critical(self, "DB Error", f"Error adding group: {e}")

    def rename_group(self):
        current_item = self.groups_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Selection Error", "Please select a group to rename.")
            return
        
        group_id = current_item.data(Qt.ItemDataRole.UserRole)
        old_name = current_item.text()
        
        existing_names = [name for name in self.get_all_group_names() if name != old_name]
        dialog = GroupNameDialog(current_name=old_name, parent=self, existing_names=existing_names)
        if dialog.exec():
            new_name = dialog.get_group_name()
            if new_name and new_name != old_name:
                try:
                    cursor = self.main_window.db_connection.cursor()
                    cursor.execute("UPDATE fixture_groups SET name = ? WHERE id = ?", (new_name, group_id))
                    self.main_window.db_connection.commit()
                    self.load_groups()
                    self.fixture_groups_changed.emit()
                except sqlite3.IntegrityError:
                     QMessageBox.warning(self, "Error", f"Group '{new_name}' already exists or database constraint failed.")
                except Exception as e:
                    QMessageBox.critical(self, "DB Error", f"Error renaming group: {e}")

    def delete_group(self):
        current_item = self.groups_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Selection Error", "Please select a group to delete.")
            return

        group_id = current_item.data(Qt.ItemDataRole.UserRole)
        group_name = current_item.text()
        reply = QMessageBox.question(self, "Confirm Delete", 
                                     f"Are you sure you want to delete group '{group_name}'? "
                                     "This will also remove all fixtures from this group.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cursor = self.main_window.db_connection.cursor()
                cursor.execute("DELETE FROM fixture_groups WHERE id = ?", (group_id,))
                self.main_window.db_connection.commit()
                self.load_groups() 
                self.fixture_groups_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Error deleting group: {e}")
    
    def on_group_selected(self):
        self.fixtures_in_group_list.clear()
        self.available_fixtures_list.clear()
        
        current_item = self.groups_list_widget.currentItem()
        if not current_item:
            self.current_selected_group_id = None
            self.update_fixture_related_widgets_enabled_state()
            return

        self.current_selected_group_id = current_item.data(Qt.ItemDataRole.UserRole)
        self.update_fixture_related_widgets_enabled_state()

        try:
            cursor = self.main_window.db_connection.cursor()
            
            cursor.execute("""
                SELECT f.id, f.name FROM fixtures f
                JOIN fixture_group_mappings fgm ON f.id = fgm.fixture_id
                WHERE fgm.group_id = ? ORDER BY f.name
            """, (self.current_selected_group_id,))
            fixtures_in_group = cursor.fetchall()
            for fix_id, name in fixtures_in_group:
                item = QListWidgetItem(f"{name} (ID: {fix_id})")
                item.setData(Qt.ItemDataRole.UserRole, fix_id)
                self.fixtures_in_group_list.addItem(item)
            
            cursor.execute("""
                SELECT id, name FROM fixtures 
                WHERE id NOT IN (SELECT fixture_id FROM fixture_group_mappings WHERE group_id = ?)
                ORDER BY name
            """, (self.current_selected_group_id,))
            available_fixtures = cursor.fetchall()
            for fix_id, name in available_fixtures:
                item = QListWidgetItem(f"{name} (ID: {fix_id})")
                item.setData(Qt.ItemDataRole.UserRole, fix_id)
                self.available_fixtures_list.addItem(item)

        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Error loading fixtures for group: {e}")
            self.current_selected_group_id = None 
            self.update_fixture_related_widgets_enabled_state()

    def add_fixtures_to_group(self):
        if self.current_selected_group_id is None:
            QMessageBox.warning(self, "No Group Selected", "Please select a group first.")
            return
        
        selected_items = self.available_fixtures_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Fixtures Selected", "Select fixtures from 'Available Fixtures' list to add.")
            return

        fixture_ids_to_add = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        
        try:
            cursor = self.main_window.db_connection.cursor()
            for fix_id in fixture_ids_to_add:
                cursor.execute("INSERT OR IGNORE INTO fixture_group_mappings (group_id, fixture_id) VALUES (?, ?)",
                               (self.current_selected_group_id, fix_id))
            self.main_window.db_connection.commit()
            self.on_group_selected() 
            self.fixture_groups_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Error adding fixtures to group: {e}")

    def remove_fixtures_from_group(self):
        if self.current_selected_group_id is None:
            QMessageBox.warning(self, "Error", "No group selected (internal error).") 
            return

        selected_items = self.fixtures_in_group_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Fixtures Selected", "Select fixtures from 'Fixtures in Group' list to remove.")
            return
        
        fixture_ids_to_remove = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]

        try:
            cursor = self.main_window.db_connection.cursor()
            for fix_id in fixture_ids_to_remove:
                cursor.execute("DELETE FROM fixture_group_mappings WHERE group_id = ? AND fixture_id = ?",
                               (self.current_selected_group_id, fix_id))
            self.main_window.db_connection.commit()
            self.on_group_selected() 
            self.fixture_groups_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Error removing fixtures from group: {e}")

    def refresh_all_data_and_ui(self):
        selected_group_item = self.groups_list_widget.currentItem()
        selected_group_id_before_refresh = self.current_selected_group_id
        
        self.load_groups() 
        
        if selected_group_id_before_refresh:
            for i in range(self.groups_list_widget.count()):
                item = self.groups_list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == selected_group_id_before_refresh:
                    self.groups_list_widget.setCurrentItem(item) 
                    # on_group_selected will be called automatically by setCurrentItem if selection changes
                    # or if it's the same item, we might need to manually call it if content *within* that selection needs refresh.
                    # Since load_groups calls on_group_selected at the end if nothing is selected,
                    # and setCurrentItem calls it if selection changes, this should mostly be covered.
                    # However, explicitly calling if it's the *same* item might be safer if underlying data changed.
                    if self.groups_list_widget.currentItem() and self.groups_list_widget.currentItem().data(Qt.ItemDataRole.UserRole) == selected_group_id_before_refresh:
                        self.on_group_selected() 
                    break
            else: 
                self.on_group_selected()
        else:
            self.on_group_selected()