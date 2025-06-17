# widgets/programmer_view_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt

from typing import TYPE_CHECKING, List, Dict, Any

if TYPE_CHECKING:
    from ..lumenante_main import Lumenante

class ProgrammerViewWidget(QWidget):
    """
    A widget that displays the live parameter values for selected fixtures
    in a spreadsheet-style grid.
    """
    # Define the order and names of parameters to display
    PARAMETER_COLUMNS = [
        # Key in fixture_state dict, Display Name, is_editable, is_float
        ("name", "Name", False, False),
        ("brightness", "Dim", True, False),
        ("red", "R", True, False),
        ("green", "G", True, False),
        ("blue", "B", True, False),
        ("rotation_y", "Pan", True, True),
        ("rotation_x", "Tilt", True, True),
        ("zoom", "Zoom", True, True),
        ("focus", "Focus", True, True),
        ("shutter_strobe_rate", "Strobe", True, True),
        ("gobo_spin", "Gobo Spin", True, True),
    ]

    def __init__(self, main_window: 'Lumenante', parent_area_id: str, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.parent_area_id = parent_area_id
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.table_widget = QTableWidget()
        self.table_widget.setObjectName("ProgrammerViewTable")
        self.layout.addWidget(self.table_widget)

        self._setup_table()

    def _setup_table(self):
        self.table_widget.setColumnCount(len(self.PARAMETER_COLUMNS))
        self.table_widget.setHorizontalHeaderLabels([col[1] for col in self.PARAMETER_COLUMNS])
        
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Name column
        for i in range(1, self.table_widget.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.cellChanged.connect(self._on_cell_changed)

    def update_view(self, selected_fixture_ids: List[int]):
        self.table_widget.blockSignals(True)
        self.table_widget.setRowCount(0)

        if not selected_fixture_ids:
            self.table_widget.blockSignals(False)
            return

        self.table_widget.setRowCount(len(selected_fixture_ids))
        
        for row_idx, fixture_id in enumerate(selected_fixture_ids):
            fixture_state = self.main_window.live_fixture_states.get(fixture_id)
            if not fixture_state:
                continue
            
            # Use a helper to populate the row
            self._populate_row(row_idx, fixture_id, fixture_state)
            
        self.table_widget.blockSignals(False)
        
    def handle_single_fixture_update(self, fixture_id: int, new_data: Dict[str, Any]):
        """A slot to efficiently update a single row when a fixture's data changes."""
        for row_idx in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row_idx, 0) # Check first column for fixture ID
            if item and item.data(Qt.ItemDataRole.UserRole) == fixture_id:
                # Found the row for the updated fixture
                fixture_state = self.main_window.live_fixture_states.get(fixture_id)
                if fixture_state:
                    self.table_widget.blockSignals(True)
                    self._populate_row(row_idx, fixture_id, fixture_state)
                    self.table_widget.blockSignals(False)
                break

    def _populate_row(self, row_idx: int, fixture_id: int, fixture_state: Dict[str, Any]):
        """Helper function to fill a single row of the table."""
        for col_idx, (key, name, is_editable, is_float) in enumerate(self.PARAMETER_COLUMNS):
            value = fixture_state.get(key, "")
            
            # Format value for display
            if is_float and isinstance(value, (float, int)):
                item_text = f"{value:.2f}"
            else:
                item_text = str(value)

            item = self.table_widget.item(row_idx, col_idx)
            if item:
                # Update existing item to avoid losing focus during edits
                if item.text() != item_text:
                    item.setText(item_text)
            else:
                # Create new item if it doesn't exist
                item = QTableWidgetItem(item_text)
                self.table_widget.setItem(row_idx, col_idx, item)

            item.setData(Qt.ItemDataRole.UserRole, fixture_id)

            if not is_editable:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def _on_cell_changed(self, row: int, column: int):
        item = self.table_widget.item(row, column)
        if not item: return

        fixture_id = item.data(Qt.ItemDataRole.UserRole)
        param_key, _, _, is_float = self.PARAMETER_COLUMNS[column]
        new_value_str = item.text()
        
        try:
            if is_float:
                new_value = float(new_value_str)
            else:
                new_value = int(new_value_str)
        except ValueError:
            # Revert to old value if conversion fails
            old_state = self.main_window.live_fixture_states.get(fixture_id, {})
            old_value = old_state.get(param_key, "")
            self.table_widget.blockSignals(True)
            item.setText(str(old_value))
            self.table_widget.blockSignals(False)
            return

        # Notify main window of the change
        self.main_window.update_fixture_data_and_notify(fixture_id, {param_key: new_value})
