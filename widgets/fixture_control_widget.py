# widgets/fixture_control_widget.py


from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QFrame, QColorDialog, QSizePolicy, QSpinBox
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QIcon

class FixtureControlWidget(QFrame): # Renamed from FixtureWidget
      intensityChanged = pyqtSignal(int, int)    # fixture_id, intensity_value
      colorButtonClicked = pyqtSignal(int)       # fixture_id
      locateFixture = pyqtSignal(int, bool)      # fixture_id, is_on

      def __init__(self, fixture_id: int, fixture_name: str, 
                   initial_intensity: int = 100, 
                   initial_color_name: str = "#FFFFFF",
                   parent_area_id: str = "", 
                   parent=None):
          super().__init__(parent)
          self.fixture_id = fixture_id
          self.fixture_name_str = fixture_name
          self.parent_area_id = parent_area_id
          self._current_color_name = initial_color_name
          self.setObjectName(f"FixtureControlWidget_{fixture_id}_{parent_area_id[:4]}")

          main_layout = QVBoxLayout(self)
          main_layout.setContentsMargins(3, 2, 3, 3)
          main_layout.setSpacing(2)

          top_row_layout = QHBoxLayout()
          top_row_layout.setSpacing(3)
          self.name_label = QLabel(f"{fixture_name[:12]}")
          self.name_label.setStyleSheet("font-weight: bold; font-size: 8pt; padding:1px;")
          self.name_label.setToolTip(fixture_name)
          top_row_layout.addWidget(self.name_label, 1)

          self.locate_btn = QPushButton("L") # Placeholder for an icon if available
          # self.locate_btn.setIcon(QIcon("path/to/locate_icon.svg")) # Example
          self.locate_btn.setFixedSize(QSize(18,18))
          self.locate_btn.setToolTip("Locate Fixture (Flash)")
          self.locate_btn.setStyleSheet("font-size: 7pt; padding: 1px;")
          self.locate_btn.pressed.connect(lambda: self.locateFixture.emit(self.fixture_id, True))
          self.locate_btn.released.connect(lambda: self.locateFixture.emit(self.fixture_id, False))
          top_row_layout.addWidget(self.locate_btn)
          main_layout.addLayout(top_row_layout)

          intensity_layout = QHBoxLayout()
          intensity_layout.setSpacing(3)
          self.intensity_slider = QSlider(Qt.Orientation.Horizontal)
          self.intensity_slider.setRange(0, 100)
          self.intensity_slider.setValue(initial_intensity)
          self.intensity_slider.valueChanged.connect(self._on_intensity_slider_changed)
          self.intensity_slider.setFixedHeight(15)
          intensity_layout.addWidget(self.intensity_slider, 1)

          self.intensity_spinbox = QSpinBox()
          self.intensity_spinbox.setRange(0,100)
          self.intensity_spinbox.setValue(initial_intensity)
          self.intensity_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
          self.intensity_spinbox.setFixedWidth(30)
          self.intensity_spinbox.setAlignment(Qt.AlignmentFlag.AlignRight)
          self.intensity_spinbox.setStyleSheet("font-size: 7pt; padding: 1px;")
          self.intensity_slider.valueChanged.connect(self.intensity_spinbox.setValue)
          self.intensity_spinbox.valueChanged.connect(self.intensity_slider.setValue) # type: ignore
          intensity_layout.addWidget(self.intensity_spinbox)
          main_layout.addLayout(intensity_layout)

          self.color_button = QPushButton()
          self.color_button.setFixedHeight(20)
          self.color_button.setToolTip("Change Fixture Color")
          self.color_button.clicked.connect(lambda: self.colorButtonClicked.emit(self.fixture_id))
          self.update_color_button_appearance(QColor(self._current_color_name))
          main_layout.addWidget(self.color_button)
          
          self.setMinimumHeight(65)

      def _on_intensity_slider_changed(self, value):
          self.intensityChanged.emit(self.fixture_id, value)

      def set_intensity(self, value: int, block_signal=False):
          if block_signal: self.intensity_slider.blockSignals(True); self.intensity_spinbox.blockSignals(True)
          self.intensity_slider.setValue(value)
          self.intensity_spinbox.setValue(value)
          if block_signal: self.intensity_slider.blockSignals(False); self.intensity_spinbox.blockSignals(False)

      def update_color_button_appearance(self, color: QColor):
          self._current_color_name = color.name()
          brightness = color.valueF()
          text_color = "white" if brightness < 0.6 else "black"
          # Shorten hex for button display if too long
          display_hex = color.name().upper()
          if len(display_hex) > 4 : display_hex = display_hex[:4]+".." # Example #FF..
          self.color_button.setText(display_hex)
          self.color_button.setStyleSheet(f"QPushButton {{ background-color: {color.name()}; color: {text_color}; font-size: 7pt; padding: 1px; border-radius: 3px; border: 1px solid #333;}} QPushButton:hover {{ border: 1px solid #777; }}")

      def get_fixture_id(self):
          return self.fixture_id
