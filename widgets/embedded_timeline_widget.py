# widgets/embedded_timeline_widget.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStyle, 
                             QSizePolicy, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent, QPaintEvent, QFont, QFontMetrics

import math

# Import for type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..tabs.timeline_tab import TimelineTab, TimelineWidget

class _EmbeddedTimelineView(QWidget):
    """The custom-painted view part of the widget, replacing the simple scrub bar."""
    playhead_scrubbed = pyqtSignal(float)

    def __init__(self, parent_widget: 'EmbeddedTimelineWidget'):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.track_label_width = 80 # Width for the track names on the left

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        painter.fillRect(self.rect(), QColor("#2A2A2E"))

        timeline_tab = self.parent_widget.timeline_tab
        timeline_widget: 'TimelineWidget' | None = getattr(timeline_tab, 'timeline_widget', None)

        if not timeline_widget:
            painter.setPen(Qt.GlobalColor.gray)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Timeline Unavailable")
            return

        total_duration_s = timeline_widget._get_effective_total_duration()
        if total_duration_s <= 0: total_duration_s = 1.0

        timeline_area_x_start = self.track_label_width
        padding = 5
        bar_width = self.width() - timeline_area_x_start - padding
        pixels_per_second = bar_width / total_duration_s if bar_width > 0 and total_duration_s > 0 else 0

        # Define vertical layout
        audio_track_height = 15
        cue_marker_height = 10
        event_track_height = self.height() - audio_track_height - cue_marker_height - 6

        audio_y_start = self.height() - audio_track_height - 3
        cue_y_start = audio_y_start - cue_marker_height
        event_y_start = 3

        # 0. Draw Track Labels and Separators
        num_tracks = len(timeline_widget.tracks) if timeline_widget.tracks else 1
        height_per_track = event_track_height / num_tracks if num_tracks > 0 else event_track_height
        
        track_font = QFont(); track_font.setPointSize(7)
        painter.setFont(track_font)
        painter.setPen(QColor("#A0A0A0"))
        
        for i, track_info in enumerate(timeline_widget.tracks):
            track_y_pos = event_y_start + i * height_per_track
            label_rect = QRectF(0, track_y_pos, self.track_label_width - 3, height_per_track)
            
            # Shorten very long names
            display_name = track_info['name']
            if len(display_name) > 15: display_name = display_name[:14] + "…"
            
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, display_name)
            # Draw separator line
            if i > 0:
                painter.setPen(QColor(60, 60, 65))
                painter.drawLine(QPointF(0, track_y_pos), QPointF(self.width(), track_y_pos))

        # 1. Draw Audio Waveform (simplified)
        if timeline_widget.audio_duration > 0 and len(timeline_widget.simulated_waveform_data) > 0:
            waveform_pen_color = QColor(70, 90, 120)
            painter.setPen(QPen(waveform_pen_color, 1))
            y_center = audio_y_start + audio_track_height / 2
            max_amplitude = (audio_track_height / 2) * 0.9
            
            points_per_sec_data = len(timeline_widget.simulated_waveform_data) / timeline_widget.audio_duration
            for px in range(bar_width):
                time_at_px = px / pixels_per_second
                data_idx = int(time_at_px * points_per_sec_data)
                if 0 <= data_idx < len(timeline_widget.simulated_waveform_data):
                    amplitude = timeline_widget.simulated_waveform_data[data_idx]
                    line_height = amplitude * max_amplitude
                    painter.drawLine(QPointF(timeline_area_x_start + px, y_center - line_height), QPointF(timeline_area_x_start + px, y_center + line_height))

        # 2. Draw Event Blocks
        event_font = QFont(); event_font.setPointSize(6)
        painter.setFont(event_font)
        for ev in timeline_widget.events:
            track_index = timeline_widget._get_track_index_for_event(ev)
            y_pos = event_y_start + track_index * height_per_track
            start_x = timeline_area_x_start + timeline_widget._get_effective_event_start_time(ev) * pixels_per_second
            duration_px = timeline_widget._get_event_visual_duration_s(ev) * pixels_per_second
            
            event_rect = QRectF(start_x, y_pos, max(1.0, duration_px), max(1.0, height_per_track - 1))
            
            base_event_color = QColor("#2196f3"); text_color = Qt.GlobalColor.white
            if ev.get('target_type') == 'master': base_event_color = QColor("#707075")
            elif ev.get('target_type') == 'group': base_event_color = QColor(230, 126, 34)
            if ev['type'] == 'preset': base_event_color = base_event_color.lighter(115)
            elif ev['type'] == 'blackout': base_event_color = QColor("#f44336")
            elif ev['type'] == 'brightness': base_event_color = QColor("#ffc107"); text_color = Qt.GlobalColor.black
            elif ev['type'] == 'color': base_event_color = QColor(ev.get('data',{}).get('color_hex', '#800080'))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(base_event_color)
            painter.drawRect(event_rect)

            # Draw event name
            painter.setPen(text_color)
            fm = QFontMetrics(event_font)
            # Corrected line: cast float width to int
            elided_text = fm.elidedText(ev['name'], Qt.TextElideMode.ElideRight, int(event_rect.width() - 4))
            painter.drawText(event_rect.adjusted(2, 0, -2, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_text)

        # 3. Draw Cue Markers
        painter.setPen(QPen(QColor("#FFA500"), 1.5))
        for cue in timeline_widget.cues:
            cue_x = timeline_area_x_start + cue['trigger_time_s'] * pixels_per_second
            if timeline_area_x_start <= cue_x <= self.width() - padding:
                painter.drawLine(QPointF(cue_x, cue_y_start), QPointF(cue_x, cue_y_start + cue_marker_height))

        # 4. Draw Playhead
        playhead_time_s = timeline_widget.get_current_playhead_time()
        playhead_x = timeline_area_x_start + playhead_time_s * pixels_per_second
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        painter.drawLine(QPointF(playhead_x, 0), QPointF(playhead_x, self.height()))


    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._handle_scrub(event.position())

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._handle_scrub(event.position())

    def _handle_scrub(self, pos: QPointF):
        timeline_tab = self.parent_widget.timeline_tab
        timeline_widget = getattr(timeline_tab, 'timeline_widget', None)
        if not timeline_widget: return

        total_duration_s = timeline_widget._get_effective_total_duration()
        if total_duration_s <= 0: return

        timeline_area_x_start = self.track_label_width
        padding = 5
        bar_width = self.width() - timeline_area_x_start - padding
        if bar_width <= 0: return

        relative_x = pos.x() - timeline_area_x_start
        time_s = (relative_x / bar_width) * total_duration_s
        clamped_time_s = max(0.0, min(time_s, total_duration_s))
        
        self.playhead_scrubbed.emit(clamped_time_s)


class EmbeddedTimelineWidget(QWidget):
    go_pressed = pyqtSignal()
    stop_pressed = pyqtSignal()
    prev_pressed = pyqtSignal()
    next_pressed = pyqtSignal()
    
    def __init__(self, timeline_tab: 'TimelineTab', parent_area_id: str, parent=None):
        super().__init__(parent)
        self.timeline_tab = timeline_tab
        self.parent_area_id = parent_area_id
        
        self.setObjectName(f"EmbeddedTimeline_{parent_area_id[:4]}")
        self._init_ui()
    
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(3, 3, 3, 3)
        main_layout.setSpacing(4)
        
        self.view = _EmbeddedTimelineView(self)
        main_layout.addWidget(self.view)
        
        controls_layout = QHBoxLayout()
        
        self.prev_button = QPushButton()
        self.prev_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.prev_button.setToolTip("Go to Previous Cue")
        self.prev_button.clicked.connect(self.prev_pressed)
        
        self.go_button = QPushButton()
        self.go_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.go_button.setToolTip("Play / Pause")
        self.go_button.setCheckable(True)
        self.go_button.clicked.connect(self.go_pressed)

        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.setToolTip("Stop and Reset")
        self.stop_button.clicked.connect(self.stop_pressed)

        self.next_button = QPushButton()
        self.next_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.next_button.setToolTip("Go to Next Cue")
        self.next_button.clicked.connect(self.next_pressed)
        
        controls_layout.addWidget(self.prev_button)
        controls_layout.addWidget(self.go_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.next_button)
        
        main_layout.addLayout(controls_layout)

    def update_playback_state(self, is_playing: bool):
        """Public slot to update the play/pause button state."""
        self.go_button.setChecked(is_playing)
        self.go_button.setIcon(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaPause if is_playing else QStyle.StandardPixmap.SP_MediaPlay
        ))

    def update_view(self):
        """Public slot to trigger a repaint."""
        if self.view:
            self.view.update()
