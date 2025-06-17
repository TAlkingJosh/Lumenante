# widgets/cue_list_widget.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QAbstractItemView)
from PyQt6.QtCore import Qt, pyqtSignal

from typing import TYPE_CHECKING, List, Dict

if TYPE_CHECKING:
    from ..lumenante_main import Lumenante
    from ..tabs.timeline_tab import TimelineTab

class CueListWidget(QWidget):
    """
    A widget that displays a list of all cues in the show, allowing for
    quick navigation and overview.
    """
    cue_selected = pyqtSignal(str) # Emits cue_number

    def __init__(self, main_window: 'Lumenante', timeline_tab: 'TimelineTab', parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.timeline_tab = timeline_tab

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.table_widget = QTableWidget()
        self.table_widget.setObjectName("CueListTable")
        self.layout.addWidget(self.table_widget)
        
        self._setup_table()
        self.refresh_cues()

    def _setup_table(self):
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["#", "Name", "Time", "Comment"])
        
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Cue Number
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Name
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Time
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) # Comment
        
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        # Connect to the timeline's cue changed signal
        if self.timeline_tab:
            self.timeline_tab.cues_changed.connect(self.refresh_cues)

    def refresh_cues(self):
        """Reloads all cues from the database and populates the table."""
        self.table_widget.setRowCount(0)
        self.table_widget.setSortingEnabled(False)
        try:
            cursor = self.main_window.db_connection.cursor()
            cursor.execute("SELECT cue_number, name, trigger_time_s, comment FROM cues ORDER BY trigger_time_s")
            cues = cursor.fetchall()

            self.table_widget.setRowCount(len(cues))
            for row_idx, cue_data in enumerate(cues):
                cue_number, name, trigger_time, comment = cue_data

                # Cue Number Item
                num_item = QTableWidgetItem(str(cue_number))
                num_item.setData(Qt.ItemDataRole.UserRole, str(cue_number)) # Store cue number for signal
                
                # Name Item
                name_item = QTableWidgetItem(name or "")

                # Time Item
                time_item = QTableWidgetItem(f"{trigger_time:.3f}s")
                time_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                # Comment Item
                comment_item = QTableWidgetItem(comment or "")

                self.table_widget.setItem(row_idx, 0, num_item)
                self.table_widget.setItem(row_idx, 1, name_item)
                self.table_widget.setItem(row_idx, 2, time_item)
                self.table_widget.setItem(row_idx, 3, comment_item)
        
        except Exception as e:
            print(f"Error refreshing CueListWidget: {e}")
            self.table_widget.setRowCount(1)
            self.table_widget.setItem(0, 0, QTableWidgetItem("Error loading cues."))
        
        self.table_widget.setSortingEnabled(True)

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """When a row is double-clicked, emit a signal to go to that cue."""
        row = item.row()
        cue_number_item = self.table_widget.item(row, 0)
        if cue_number_item:
            cue_number_str = cue_number_item.data(Qt.ItemDataRole.UserRole)
            self.cue_selected.emit(cue_number_str)
            
    def closeEvent(self, event):
        # Disconnect signals to prevent errors on close
        if self.timeline_tab:
            try:
                self.timeline_tab.cues_changed.disconnect(self.refresh_cues)
            except (TypeError, RuntimeError):
                pass
        super().closeEvent(event)
