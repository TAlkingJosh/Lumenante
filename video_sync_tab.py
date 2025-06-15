# tabs/video_sync_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget,
    QSlider, QFileDialog, QStyle, QListWidgetItem, QMessageBox,
    QSizePolicy
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, pyqtSignal

class VideoSyncTab(QWidget):
    request_add_cue_to_timeline = pyqtSignal(float) # Sends timestamp in seconds

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.media_player = None
        self.audio_output = None
        self.video_widget = None
        self.marked_cues = [] # List to store timestamps in milliseconds

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # Top controls
        top_controls_layout = QHBoxLayout()
        self.load_video_button = QPushButton("Load Video")
        self.load_video_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.load_video_button.clicked.connect(self._load_video)
        top_controls_layout.addWidget(self.load_video_button)
        top_controls_layout.addStretch()
        main_layout.addLayout(top_controls_layout)

        # Video display area
        self.video_widget = QVideoWidget()
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_widget.setMinimumSize(320, 180) 
        main_layout.addWidget(self.video_widget, 1) 

        # Playback controls
        playback_controls_layout = QHBoxLayout()
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self._play_pause_video)
        playback_controls_layout.addWidget(self.play_button)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self._set_position)
        self.position_slider.setEnabled(False)
        playback_controls_layout.addWidget(self.position_slider)

        self.time_label = QLabel("00:00:000 / 00:00:000") # Updated format
        playback_controls_layout.addWidget(self.time_label)
        main_layout.addLayout(playback_controls_layout)

        # Cue marking section
        cue_section_layout = QHBoxLayout()
        self.mark_cue_button = QPushButton("Mark Cue Point")
        self.mark_cue_button.setEnabled(False)
        self.mark_cue_button.clicked.connect(self._mark_cue)
        cue_section_layout.addWidget(self.mark_cue_button)
        
        self.send_cues_button = QPushButton("Send Marked Cues to Timeline")
        self.send_cues_button.setEnabled(False)
        self.send_cues_button.clicked.connect(self._send_cues_to_timeline)
        cue_section_layout.addWidget(self.send_cues_button)
        cue_section_layout.addStretch()
        main_layout.addLayout(cue_section_layout)

        self.marked_cues_list_widget = QListWidget()
        self.marked_cues_list_widget.setToolTip("Double-click to remove a marked cue.")
        self.marked_cues_list_widget.itemDoubleClicked.connect(self._remove_marked_cue)
        main_layout.addWidget(self.marked_cues_list_widget, 1) 

        self.setLayout(main_layout)
        self._initialize_media_player()

    def _initialize_media_player(self):
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput() 
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        self.media_player.playbackStateChanged.connect(self._media_state_changed)
        self.media_player.positionChanged.connect(self._position_changed)
        self.media_player.durationChanged.connect(self._duration_changed)
        self.media_player.errorOccurred.connect(self._handle_error)
        
    def _load_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Video File", "", 
                                                   "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*)")
        if file_path:
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            self.play_button.setEnabled(True)
            self.mark_cue_button.setEnabled(True)
            self.marked_cues.clear()
            self._update_cue_list_widget()
            # Video will typically auto-play or be ready once duration is known

    def _play_pause_video(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def _media_state_changed(self, state: QMediaPlayer.PlaybackState):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def _position_changed(self, position_ms: int):
        self.position_slider.setValue(position_ms)
        self._update_time_label()

    def _duration_changed(self, duration_ms: int):
        self.position_slider.setRange(0, duration_ms)
        self.position_slider.setEnabled(duration_ms > 0)
        self._update_time_label()

    def _set_position(self, position_ms: int):
        self.media_player.setPosition(position_ms)

    def _format_time(self, time_ms: int) -> str:
        seconds = (time_ms // 1000) % 60
        minutes = (time_ms // (1000 * 60)) % 60
        hours = (time_ms // (1000 * 60 * 60)) % 24
        milliseconds = time_ms % 1000
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        else:
            return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def _update_time_label(self):
        current_ms = self.media_player.position()
        duration_ms = self.media_player.duration()
        self.time_label.setText(f"{self._format_time(current_ms)} / {self._format_time(duration_ms)}")

    def _handle_error(self, error: QMediaPlayer.Error, error_string: str):
        print(f"MediaPlayer Error: {error}, {error_string}") # Keep for debugging
        # More user-friendly error string if available
        user_error_string = self.media_player.errorString()
        if not user_error_string: # Fallback if empty
             user_error_string = "An unknown error occurred with the media player."
        QMessageBox.critical(self, "Media Player Error", 
                             f"Could not play media: {user_error_string}")
        self.play_button.setEnabled(False)
        self.mark_cue_button.setEnabled(False)

    def _mark_cue(self):
        if self.media_player and self.media_player.source().isValid():
            current_pos_ms = self.media_player.position()
            if current_pos_ms not in self.marked_cues:
                self.marked_cues.append(current_pos_ms)
                self.marked_cues.sort()
                self._update_cue_list_widget()
                self.send_cues_button.setEnabled(bool(self.marked_cues))

    def _update_cue_list_widget(self):
        self.marked_cues_list_widget.clear()
        for i, cue_ms in enumerate(self.marked_cues):
            item = QListWidgetItem(f"Cue {i+1}: {self._format_time(cue_ms)}")
            item.setData(Qt.ItemDataRole.UserRole, cue_ms) 
            self.marked_cues_list_widget.addItem(item)
        self.send_cues_button.setEnabled(bool(self.marked_cues))


    def _remove_marked_cue(self, item: QListWidgetItem):
        cue_ms_to_remove = item.data(Qt.ItemDataRole.UserRole)
        if cue_ms_to_remove in self.marked_cues:
            self.marked_cues.remove(cue_ms_to_remove)
            self._update_cue_list_widget() 
            
    def _send_cues_to_timeline(self):
        if not self.marked_cues:
            QMessageBox.information(self, "No Cues", "No cue points marked to send.")
            return

        if not self.main_window.timeline_tab:
            QMessageBox.warning(self, "Error", "Timeline Tab is not available.")
            return

        num_sent = 0
        for cue_ms in self.marked_cues:
            timestamp_s = cue_ms / 1000.0
            self.request_add_cue_to_timeline.emit(timestamp_s)
            num_sent += 1
        
        if num_sent > 0:
            reply = QMessageBox.question(self, "Cues Sent", 
                                    f"{num_sent} cue point(s) sent to Timeline Tab for processing.\n"
                                    "The 'Add Event' dialog will open for each cue.\n\n"
                                    "Clear marked cues from this Video Sync list?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.marked_cues.clear()
                self._update_cue_list_widget()


    def shutdown_player(self):
        if self.media_player:
            self.media_player.stop()
            self.media_player.setSource(QUrl()) 
            print("VideoSyncTab: Media player stopped and source cleared.")

    def showEvent(self, event):
        super().showEvent(event)
        # Ensure player is initialized if it wasn't or got deleted
        if not self.media_player:
            self._initialize_media_player()
            print("VideoSyncTab: Re-initialized media player on show.")


    def hideEvent(self, event):
        if self.media_player and self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            print("VideoSyncTab: Media player paused on hide.")
        super().hideEvent(event)
