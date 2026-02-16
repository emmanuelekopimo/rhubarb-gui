import sys
import os
import subprocess
import json
import platform
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QSpinBox, QFileDialog, QTextEdit, QTabWidget, QFormLayout, QProgressBar,
    QMessageBox, QDialog, QSlider
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent


class RhubarbWorker(QThread):
    """Worker thread to run Rhubarb Lip Sync without blocking UI"""
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            # Prepare kwargs for subprocess
            popen_kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True
            }
            
            # Suppress the window on Windows
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                popen_kwargs["startupinfo"] = startupinfo
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(
                self.command,
                **popen_kwargs
            )

            for line in process.stderr:
                try:
                    data = json.loads(line)
                    if data.get("type") == "progress":
                        progress = int(data.get("value", 0) * 100)
                        self.progress_updated.emit(progress)
                    if data.get("type") == "success":
                        self.status_updated.emit("✓ Processing completed successfully!")
                    if data.get("type") == "failure":
                        reason = data.get("reason", "Unknown error")
                        self.error_occurred.emit(f"Error: {reason}")
                    if "log" in data:
                        message = data["log"].get("message", "")
                        if message:
                            self.status_updated.emit(message)
                except json.JSONDecodeError:
                    self.status_updated.emit(line.strip())

            process.wait()
            if process.returncode == 0:
                self.finished.emit()
            else:
                self.error_occurred.emit(f"Process failed with exit code {process.returncode}")

        except Exception as e:
            self.error_occurred.emit(f"Exception: {str(e)}")


class LipsPreviewDialog(QDialog):
    """Dialog to preview audio with optional synchronized lip animation"""
    
    def __init__(self, parent=None, audio_file=None, sync_data=None, mouth_dir=None):
        super().__init__(parent)
        self.audio_file = audio_file
        self.mouth_dir = mouth_dir or os.path.join(os.path.dirname(__file__), "res", "mouth")
        self.mouth_shapes = ["A", "B", "C", "D", "E", "F", "G", "H", "X"]
        self.current_shape_index = 0
        
        # Sync data: list of (time_ms, mouth_shape) tuples
        self.sync_data = sync_data or []
        self.show_sync = len(self.sync_data) > 0
        
        # Media player
        self.media_player = QMediaPlayer()
        self.media_player.positionChanged.connect(self.on_position_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)
        self.media_player.stateChanged.connect(self.on_state_changed)
        
        # Animation timer for playback
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.on_timer_tick)
        
        self.init_ui()
        self.setWindowTitle("Audio Preview" + (" with Lip Sync" if self.show_sync else ""))
        
        if self.show_sync: self.setFixedSize(520,330)
        else: self.setFixedSize(400,120)
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        if audio_file and os.path.exists(audio_file):
            self.load_audio(audio_file)

    def init_ui(self):
        """Initialize the UI"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title_text = "Audio Preview" + (" with Lip Sync" if self.show_sync else "")
        title = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        # Lip display area with white background (only if showing sync)
        if self.show_sync:
            display_group = QGroupBox("Mouth Animation")
            display_layout = QVBoxLayout()
            display_layout.setContentsMargins(15, 15, 15, 15)
            display_layout.setSpacing(0)
            
            # White background container for mouth image
            self.mouth_label = QLabel()
            self.mouth_label.setStyleSheet("background-color: white; border: 2px solid #ddd; border-radius: 5px;")
            self.mouth_label.setAlignment(Qt.AlignCenter)
            self.mouth_label.setMinimumSize(280, 120)
            self.mouth_label.setMaximumSize(280, 120)
            
            display_layout.addWidget(self.mouth_label)
            display_group.setLayout(display_layout)
            main_layout.addWidget(display_group)

        # Audio info
        info_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFont(QFont("Courier", 10))
        info_layout.addWidget(QLabel("Time:"))
        info_layout.addWidget(self.time_label)
        info_layout.addStretch()
        
        if self.show_sync:
            self.shape_label = QLabel("Shape: X")
            self.shape_label.setFont(QFont("Arial", 10))
            info_layout.addWidget(self.shape_label)
        
        main_layout.addLayout(info_layout)

        # Seek slider
        slider_layout = QHBoxLayout()
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 100)
        self.seek_slider.sliderMoved.connect(self.on_seek)
        slider_layout.addWidget(self.seek_slider)
        main_layout.addLayout(slider_layout)

        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setMaximumWidth(70)
        self.play_btn.clicked.connect(self.toggle_playback)
        button_layout.addWidget(self.play_btn)
        
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setMaximumWidth(70)
        self.pause_btn.clicked.connect(self.pause_playback)
        button_layout.addWidget(self.pause_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setMaximumWidth(70)
        self.stop_btn.clicked.connect(self.stop_playback)
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setMaximumWidth(70)
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)
        
        if self.show_sync:
            self.load_mouth_image("X")  # Start with neutral shape

    def load_audio(self, file_path):
        """Load an audio file"""
        if os.path.exists(file_path):
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))

    def load_mouth_image(self, shape):
        """Load and display a mouth shape image"""
        mouth_image_path = os.path.join(self.mouth_dir, f"{shape}.png")
        
        if os.path.exists(mouth_image_path):
            pixmap = QPixmap(mouth_image_path)
            # Scale to fit within the label while maintaining aspect ratio
            label_width = self.mouth_label.width() - 20
            label_height = self.mouth_label.height() - 20
            if label_width > 0 and label_height > 0:
                scaled_pixmap = pixmap.scaledToHeight(label_height, Qt.SmoothTransformation)
                # If still too wide, scale to width instead
                if scaled_pixmap.width() > label_width:
                    scaled_pixmap = pixmap.scaledToWidth(label_width, Qt.SmoothTransformation)
                self.mouth_label.setPixmap(scaled_pixmap)
            else:
                self.mouth_label.setPixmap(pixmap)
            self.shape_label.setText(f"Shape: {shape}")
        else:
            # Fallback: show a placeholder
            self.mouth_label.setText(f"Mouth shape '{shape}' not found")
            self.shape_label.setText(f"Shape: {shape}")

    def toggle_playback(self):
        """Toggle play/pause"""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.pause_playback()
        else:
            self.play_playback()

    def play_playback(self):
        """Start playing audio"""
        self.animation_timer.start(16)  # ~60fps for smooth updates during playback
        self.media_player.play()

    def pause_playback(self):
        """Pause audio playback"""
        self.animation_timer.stop()
        self.media_player.pause()

    def stop_playback(self):
        """Stop audio and reset"""
        self.animation_timer.stop()
        self.media_player.stop()
        self.media_player.setPosition(0)
        self.seek_slider.setValue(0)
        if self.show_sync:
            self.load_mouth_image("X")

    def on_position_changed(self, position):
        """Update UI when audio position changes"""
        # The timer handles updates during playback for smooth sync
        # This signal might fire irregularly, so we just ensure slider is in sync
        duration = self.media_player.duration()
        if duration > 0:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int((position / duration) * 100))
            self.seek_slider.blockSignals(False)

    def update_position_display(self, position_ms):
        """Update the time display based on current position"""
        duration = self.media_player.duration()
        if duration > 0:
            # Update time display
            current_sec = position_ms // 1000
            total_sec = duration // 1000
            self.time_label.setText(
                f"{current_sec // 60:02d}:{current_sec % 60:02d} / {total_sec // 60:02d}:{total_sec % 60:02d}"
            )

    def on_duration_changed(self, duration):
        """Called when audio duration is determined"""
        pass

    def on_state_changed(self, state):
        """Handle state changes"""
        if state != QMediaPlayer.PlayingState:
            self.animation_timer.stop()

    def on_timer_tick(self):
        """Called by animation timer - update position and sync display"""
        # Directly query current position from media player to ensure smooth updates
        position = self.media_player.position()
        self.update_position_display(position)
        
        if self.show_sync:
            self.update_mouth_from_sync(position)

    def on_seek(self, value):
        """Handle seek slider movement"""
        duration = self.media_player.duration()
        if duration > 0:
            position = int((value / 100) * duration)
            self.media_player.setPosition(position)
            # Update mouth immediately when scrubbing
            if self.show_sync:
                self.update_position_display(position)
                self.update_mouth_from_sync(position)

    def update_mouth_from_sync(self, position_ms):
        """Update mouth shape based on current position using sync data"""
        if not self.sync_data:
            return
        
        # Find the mouth shape for the current time
        current_shape = "X"  # Default to neutral
        for time_ms, shape in reversed(self.sync_data):
            if position_ms >= time_ms:
                current_shape = shape
                break
        
        self.load_mouth_image(current_shape)

    def closeEvent(self, event):
        """Clean up when dialog closes"""
        self.animation_timer.stop()
        self.stop_playback()
        super().closeEvent(event)



class RhubarbGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.rhubarb_exe = self.get_rhubarb_executable()
        self.worker = None
        self.sync_data = []  # Store parsed sync data: [(time_ms, mouth_shape), ...]
        self.last_output_file = None  # Track last output file for re-parsing
        self.current_preview_dialog = None  # Track currently open preview dialog
        self.init_ui()
        self.setWindowTitle("Rhubarb Lip Sync GUI")
        self.setWindowIcon(self.get_window_icon())
        self.setGeometry(50, 100, 800, 600)
        self.setMinimumSize(600, 400)

    def get_window_icon(self):
        """Get the window icon from res/icon.ico"""
        base_dir = os.path.dirname(__file__)
        icon_path = os.path.join(base_dir, "res", "icon.ico")
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return QIcon()  # Return empty icon if file not found

    def get_rhubarb_executable(self):
        """Get the appropriate Rhubarb executable based on the OS"""
        system = platform.system()
        base_dir = os.path.dirname(__file__)
        
        if system == "Windows":
            exe_path = os.path.join(base_dir, "rhubarb_win", "rhubarb.exe")
        elif system == "Darwin":  # macOS
            exe_path = os.path.join(base_dir, "rhubarb_mac", "rhubarb")
        elif system == "Linux":
            exe_path = os.path.join(base_dir, "rhubarb_linux", "rhubarb")
        else:
            exe_path = os.path.join(base_dir, "rhubarb_win", "rhubarb.exe")  # Default fallback
        
        return exe_path

    def get_format_from_extension(self, file_path):
        """Determine output format from file extension"""
        if not file_path:
            return "tsv"
        
        ext = Path(file_path).suffix.lower()
        format_map = {
            ".tsv": "tsv",
            ".txt": "tsv",  # TSV files often use .txt extension
            ".xml": "xml",
            ".json": "json",
            ".dat": "dat",
        }
        return format_map.get(ext, "tsv")  # Default to tsv if extension not recognized

    def init_ui(self):
        """Initialize the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Title
        title = QLabel("Rhubarb Lip Sync")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        # Tab Widget for organized sections
        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # Tab 1: Basic Settings
        basic_tab = QWidget()
        basic_layout = QFormLayout()
        tabs.addTab(basic_tab, "Basic Settings")

        # Input file
        input_layout = QHBoxLayout()
        self.input_file = QLineEdit()
        self.input_file.setPlaceholderText("Select audio file (WAV or OGG)")
        input_btn = QPushButton("Browse...")
        input_btn.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_file)
        input_layout.addWidget(input_btn)
        basic_layout.addRow("Input Audio File:", input_layout)

        # Output file
        output_layout = QHBoxLayout()
        self.output_file = QLineEdit()
        self.output_file.setPlaceholderText("Select output file location")
        output_btn = QPushButton("Browse...")
        output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_file)
        output_layout.addWidget(output_btn)
        basic_layout.addRow("Output File:", output_layout)

        # Recognizer
        self.recognizer = QComboBox()
        self.recognizer.addItems(["pocketSphinx", "phonetic"])
        self.recognizer.setToolTip("pocketSphinx: English only\nphonetic: Language-independent")
        basic_layout.addRow("Speech Recognizer:", self.recognizer)

        # Export Format (auto-detected from output file extension)
        self.export_format = QComboBox()
        self.export_format.addItems(["tsv", "xml", "json", "dat"])
        self.export_format.setToolTip("Auto-detected from output file extension\ntsv: Tab-separated values (most compact)\nxml: XML format\njson: JSON format\ndat: For Moho/OpenToonz")
        basic_layout.addRow("Export Format (auto):", self.export_format)

        # Extended Shapes
        self.extended_shapes = QLineEdit()
        self.extended_shapes.setText("GHX")
        self.extended_shapes.setToolTip("Available: G, H, X (leave empty for basic shapes only)")
        basic_layout.addRow("Extended Shapes:", self.extended_shapes)

        basic_tab.setLayout(basic_layout)

        # Tab 2: Optional Settings
        optional_tab = QWidget()
        optional_layout = QFormLayout()
        tabs.addTab(optional_tab, "Optional Settings")

        # Dialog file
        dialog_layout = QHBoxLayout()
        self.dialog_file = QLineEdit()
        self.dialog_file.setPlaceholderText("(Optional) Text file with dialog")
        dialog_btn = QPushButton("Browse...")
        dialog_btn.clicked.connect(self.browse_dialog)
        dialog_layout.addWidget(self.dialog_file)
        dialog_layout.addWidget(dialog_btn)
        optional_layout.addRow("Dialog Text File:", dialog_layout)

        # DAT specific options
        optional_layout.addRow(QLabel("DAT Format Options:"), QLabel(""))

        # DAT Frame Rate
        self.dat_frame_rate = QSpinBox()
        self.dat_frame_rate.setValue(24)
        self.dat_frame_rate.setMinimum(1)
        self.dat_frame_rate.setMaximum(60)
        optional_layout.addRow("DAT Frame Rate:", self.dat_frame_rate)

        # DAT Use Preston Blair
        self.dat_preston_blair = QCheckBox("Use Preston Blair mouth shape names (for OpenToonz)")
        optional_layout.addRow("", self.dat_preston_blair)

        optional_tab.setLayout(optional_layout)

        # Tab 3: Advanced Settings
        advanced_tab = QWidget()
        advanced_layout = QFormLayout()
        tabs.addTab(advanced_tab, "Advanced Settings")



        # Console level
        self.console_level = QComboBox()
        self.console_level.addItems(["error", "warning", "info", "debug", "trace"])
        self.console_level.setCurrentIndex(0)
        advanced_layout.addRow("Console Log Level:", self.console_level)

        # Log file
        log_layout = QHBoxLayout()
        self.log_file = QLineEdit()
        self.log_file.setPlaceholderText("(Optional) Path for diagnostic log")
        log_btn = QPushButton("Browse...")
        log_btn.clicked.connect(self.browse_log_file)
        log_layout.addWidget(self.log_file)
        log_layout.addWidget(log_btn)
        advanced_layout.addRow("Log File:", log_layout)

        # Log level
        self.log_level = QComboBox()
        self.log_level.addItems(["debug", "info", "warning", "error", "fatal", "trace"])
        self.log_level.setCurrentIndex(0)
        advanced_layout.addRow("Log Level:", self.log_level)

        # Threads
        self.threads = QSpinBox()
        self.threads.setValue(0)
        self.threads.setMinimum(0)
        self.threads.setMaximum(64)
        self.threads.setToolTip("0 = auto-detect (recommended)")
        advanced_layout.addRow("Number of Threads:", self.threads)

        advanced_tab.setLayout(advanced_layout)

        # Command Preview Section
        preview_group = QGroupBox("Command Preview")
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(5, 5, 5, 5)
        preview_layout.setSpacing(0)
        preview_group.setMaximumHeight(100)
        self.command_preview = QTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(80)
        self.command_preview.setPlaceholderText("Command preview will appear here...")
        self.command_preview.setStyleSheet("background-color: #f5f5f5; font-family: monospace; font-size: 9pt;")
        self.command_preview.setContentsMargins(0, 0, 0, 0)
        self.command_preview.document().setDocumentMargin(0)
        self.command_preview.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        preview_layout.addWidget(self.command_preview)
        preview_group.setLayout(preview_layout)
        main_layout.addWidget(preview_group)

        # Progress and Status Section
        progress_group = QGroupBox("Progress")
        progress_layout = QFormLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addRow(self.progress_bar)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        progress_layout.addRow(self.status_text)

        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # Control buttons
        button_layout = QHBoxLayout()
        
        self.run_btn = QPushButton("Run Rhubarb Lip Sync")
        self.run_btn.clicked.connect(self.run_rhubarb)
        button_layout.addWidget(self.run_btn)

        self.preview_audio_btn = QPushButton("Preview Audio")
        self.preview_audio_btn.clicked.connect(self.open_audio_preview)
        button_layout.addWidget(self.preview_audio_btn)

        self.preview_sync_btn = QPushButton("Preview with Lip Sync")
        self.preview_sync_btn.clicked.connect(self.open_sync_preview)
        self.preview_sync_btn.setEnabled(False)  # Disabled until sync data is available
        button_layout.addWidget(self.preview_sync_btn)

        self.clear_btn = QPushButton("Clear Output")
        self.clear_btn.clicked.connect(self.clear_output)
        button_layout.addWidget(self.clear_btn)

        main_layout.addLayout(button_layout)

        # Connect signals to update command preview
        self.input_file.textChanged.connect(self.update_command_preview)
        self.output_file.textChanged.connect(self.update_command_preview)
        self.recognizer.currentTextChanged.connect(self.update_command_preview)
        self.extended_shapes.textChanged.connect(self.update_command_preview)
        self.dialog_file.textChanged.connect(self.update_command_preview)
        self.dat_frame_rate.valueChanged.connect(self.update_command_preview)
        self.dat_preston_blair.toggled.connect(self.update_command_preview)
        self.console_level.currentTextChanged.connect(self.update_command_preview)
        self.log_file.textChanged.connect(self.update_command_preview)
        self.log_level.currentTextChanged.connect(self.update_command_preview)
        self.threads.valueChanged.connect(self.update_command_preview)

    def browse_input(self):
        """Browse for input audio file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", "",
            "Audio Files (*.wav *.ogg);;WAV Files (*.wav);;OGG Files (*.ogg);;All Files (*)"
        )
        if file_path:
            self.input_file.setText(file_path)
            self.update_command_preview()

    def browse_output(self):
        """Browse for output file location"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output As", "",
            "TSV Files (*.txt);;XML Files (*.xml);;JSON Files (*.json);;DAT Files (*.dat);;All Files (*)"
        )
        if file_path:
            self.output_file.setText(file_path)
            # Auto-detect format from file extension
            detected_format = self.get_format_from_extension(file_path)
            self.export_format.setCurrentText(detected_format)
            # Update command preview
            self.update_command_preview()

    def browse_dialog(self):
        """Browse for dialog text file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Dialog Text File", "",
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.dialog_file.setText(file_path)

    def browse_log_file(self):
        """Browse for log file location"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Log File As", "",
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.log_file.setText(file_path)

    def update_command_preview(self):
        """Update the command preview display without validation"""
        input_file = self.input_file.text().strip()
        output_file = self.output_file.text().strip()
        
        if not input_file or not output_file:
            self.command_preview.setText("")
            return
        
        # Auto-detect format from output file extension
        detected_format = self.get_format_from_extension(output_file)
        self.export_format.setCurrentText(detected_format)
        
        # Build preview command
        command = [os.path.basename(self.rhubarb_exe)]
        
        recognizer = self.recognizer.currentText()
        if recognizer != "pocketSphinx":
            command.extend(["-r", recognizer])
        
        if detected_format != "tsv":
            command.extend(["-f", detected_format])
        
        extended = self.extended_shapes.text().strip()
        if extended and extended != "GHX":
            command.extend(["--extendedShapes", extended])
        
        dialog = self.dialog_file.text().strip()
        if dialog:
            command.extend(["-d", dialog])
        
        if detected_format == "dat":
            frame_rate = self.dat_frame_rate.value()
            if frame_rate != 24:
                command.extend(["--datFrameRate", str(frame_rate)])
            if self.dat_preston_blair.isChecked():
                command.append("--datUsePrestonBlair")
        
        command.extend(["-o", output_file])
        
        # Machine readable is always enabled for progress tracking
        command.append("--machineReadable")
        
        console_level = self.console_level.currentText()
        if console_level != "error":
            command.extend(["--consoleLevel", console_level])
        
        log_file = self.log_file.text().strip()
        if log_file:
            command.extend(["--logFile", log_file])
        
        log_level = self.log_level.currentText()
        if log_level != "debug":
            command.extend(["--logLevel", log_level])
        
        threads = self.threads.value()
        if threads > 0:
            command.extend(["--threads", str(threads)])
        
        command.append(input_file)
        
        # Display the preview
        self.command_preview.setText(" ".join(command))

    def build_command(self):
        """Build the rhubarb command from GUI inputs"""
        # Check if executable exists
        if not os.path.exists(self.rhubarb_exe):
            return None, f"Rhubarb executable not found at: {self.rhubarb_exe}"
        
        # Validate input file
        if not self.input_file.text().strip():
            return None, "Please select an input audio file"
        
        input_file = self.input_file.text().strip()
        if not os.path.exists(input_file):
            return None, f"Input file not found: {input_file}"
        
        # Validate output file
        if not self.output_file.text().strip():
            return None, "Please specify an output file location"

        # Start building command
        command = [self.rhubarb_exe]

        # Add recognizer
        recognizer = self.recognizer.currentText()
        if recognizer != "pocketSphinx":  # Default is pocketSphinx
            command.extend(["-r", recognizer])

        # Auto-detect export format from output file extension
        output = self.output_file.text().strip()
        export_format = self.get_format_from_extension(output)
        if export_format != "tsv":  # Default is tsv
            command.extend(["-f", export_format])

        # Add extended shapes
        extended = self.extended_shapes.text().strip()
        if extended != "GHX":  # Default is GHX
            command.extend(["--extendedShapes", extended])

        # Add dialog file if provided
        dialog = self.dialog_file.text().strip()
        if dialog:
            if not os.path.exists(dialog):
                return None, f"Dialog file not found: {dialog}"
            command.extend(["-d", dialog])

        # Add DAT options if format is DAT
        if export_format == "dat":
            frame_rate = self.dat_frame_rate.value()
            if frame_rate != 24:
                command.extend(["--datFrameRate", str(frame_rate)])
            
            if self.dat_preston_blair.isChecked():
                command.append("--datUsePrestonBlair")

        # Add output file (required)
        output = self.output_file.text().strip()
        command.extend(["-o", output])

        # Add machine readable (required for progress tracking)
        command.append("--machineReadable")

        # Add console level
        console_level = self.console_level.currentText()
        if console_level != "error":  # Default is error
            command.extend(["--consoleLevel", console_level])

        # Add log file
        log_file = self.log_file.text().strip()
        if log_file:
            command.extend(["--logFile", log_file])

        # Add log level
        log_level = self.log_level.currentText()
        if log_level != "debug":  # Default is debug
            command.extend(["--logLevel", log_level])

        # Add threads
        threads = self.threads.value()
        if threads > 0:
            command.extend(["--threads", str(threads)])

        # Add input file (must be last)
        command.append(input_file)

        return command, None

    def run_rhubarb(self):
        """Run Rhubarb Lip Sync with the configured options"""
        # Check if input file is specified
        if not self.input_file.text().strip():
            QMessageBox.critical(self, "Input File Required", 
                               "Please select an input audio file before running.")
            return
        
        # Check if output file is specified
        if not self.output_file.text().strip():
            QMessageBox.critical(self, "Output File Required", 
                               "Please specify an output file location before running.")
            return
        
        command, error = self.build_command()
        
        if error:
            self.status_text.append(f"❌ {error}")
            return

        # Disable run button during processing
        self.run_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_text.clear()

        # Display command
        self.status_text.append(f"Command: {' '.join(command)}\n")
        self.status_text.append("Starting process...\n")

        # Create and start worker thread
        self.worker = RhubarbWorker(command)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.status_updated.connect(self.update_status)
        self.worker.finished.connect(self.on_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def update_status(self, message):
        """Update status text"""
        self.status_text.append(message)

    def on_finished(self):
        """Called when process finishes successfully"""
        self.run_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        
        # Parse the output file to extract sync data
        output_file = self.output_file.text().strip()
        if output_file and os.path.exists(output_file):
            self.parse_sync_data(output_file)
            # Enable the sync preview button if we have sync data
            if self.sync_data:
                self.preview_sync_btn.setEnabled(True)
                self.status_text.append("\n✓ Sync data loaded. You can now preview with lip sync!")

    def on_error(self, error_msg):
        """Called when an error occurs"""
        self.run_btn.setEnabled(True)
        self.status_text.append(f"\n❌ {error_msg}")

    def clear_output(self):
        """Clear the status output"""
        self.status_text.clear()
        self.progress_bar.setValue(0)

    def open_audio_preview(self):
        """Open audio-only preview dialog"""
        audio_file = self.input_file.text().strip()
        
        if not audio_file:
            QMessageBox.warning(self, "No Audio File", 
                              "Please select an audio file to preview.")
            return
        
        if not os.path.exists(audio_file):
            QMessageBox.critical(self, "File Not Found", 
                               f"Audio file not found:\n{audio_file}")
            return
        
        # Close existing preview dialog if any
        if self.current_preview_dialog is not None:
            self.current_preview_dialog.close()
            self.current_preview_dialog = None
        
        # Open preview dialog (audio only, no sync data)
        preview_dialog = LipsPreviewDialog(self, audio_file, sync_data=None)
        preview_dialog.destroyed.connect(lambda: self.on_dialog_closed())
        self.current_preview_dialog = preview_dialog
        preview_dialog.show()

    def open_sync_preview(self):
        """Open preview dialog with lip sync data"""
        audio_file = self.input_file.text().strip()
        
        if not audio_file:
            QMessageBox.warning(self, "No Audio File", 
                              "Please select an audio file to preview.")
            return
        
        if not os.path.exists(audio_file):
            QMessageBox.critical(self, "File Not Found", 
                               f"Audio file not found:\n{audio_file}")
            return
        
        if not self.sync_data:
            QMessageBox.warning(self, "No Sync Data", 
                              "Please run Rhubarb Lip Sync first to generate sync data.")
            return
        
        # Close existing preview dialog if any
        if self.current_preview_dialog is not None:
            self.current_preview_dialog.close()
            self.current_preview_dialog = None
        
        # Open preview dialog with sync data
        preview_dialog = LipsPreviewDialog(self, audio_file, sync_data=self.sync_data)
        preview_dialog.destroyed.connect(lambda: self.on_dialog_closed())
        self.current_preview_dialog = preview_dialog
        preview_dialog.show()

    def parse_sync_data(self, output_file):
        """Parse the output file and extract sync data"""
        self.sync_data = []
        file_format = self.get_format_from_extension(output_file)
        
        try:
            if file_format == "tsv":
                self.parse_tsv_sync(output_file)
            elif file_format == "json":
                self.parse_json_sync(output_file)
            elif file_format == "xml":
                self.parse_xml_sync(output_file)
            elif file_format == "dat":
                self.parse_dat_sync(output_file)
        except Exception as e:
            self.status_text.append(f"\n⚠ Warning: Could not parse sync data: {str(e)}")

    def parse_tsv_sync(self, file_path):
        """Parse TSV format sync data"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        try:
                            # TSV format: start_time (float in seconds) shape (character)
                            start_time = float(parts[0])
                            shape = parts[1].strip().upper()
                            # Convert to milliseconds and validate shape
                            if shape in "ABCDEFGHX":
                                self.sync_data.append((int(start_time * 1000), shape))
                        except (ValueError, IndexError):
                            continue
        except Exception as e:
            raise Exception(f"Error parsing TSV: {str(e)}")

    def parse_json_sync(self, file_path):
        """Parse JSON format sync data"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures
            if isinstance(data, list):
                # Array of mouth shapes
                for item in data:
                    if isinstance(item, dict):
                        start = item.get('start') or item.get('time') or item.get('start_time')
                        shape = item.get('shape') or item.get('mouth') or item.get('character')
                        if start is not None and shape:
                            try:
                                start_ms = int(float(start) * 1000)
                                shape_str = str(shape).strip().upper()
                                if shape_str in "ABCDEFGHX":
                                    self.sync_data.append((start_ms, shape_str))
                            except (ValueError, TypeError):
                                continue
            elif isinstance(data, dict):
                # Object with metadata, look for mouthShapes or similar
                mouth_shapes = data.get('mouthShapes') or data.get('mouth_shapes') or []
                for item in mouth_shapes:
                    if isinstance(item, dict):
                        start = item.get('start') or item.get('time')
                        shape = item.get('shape') or item.get('value')
                        if start is not None and shape:
                            try:
                                start_ms = int(float(start) * 1000)
                                shape_str = str(shape).strip().upper()
                                if shape_str in "ABCDEFGHX":
                                    self.sync_data.append((start_ms, shape_str))
                            except (ValueError, TypeError):
                                continue
        except Exception as e:
            raise Exception(f"Error parsing JSON: {str(e)}")

    def parse_xml_sync(self, file_path):
        """Parse XML format sync data"""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Look for mouth shape elements
            for element in root.iter():
                # Handle various XML structure possibilities
                if 'mouth' in element.tag.lower() or 'shape' in element.tag.lower():
                    start = element.get('start') or element.get('time')
                    shape = element.text or element.get('shape') or element.get('value')
                    
                    if start and shape:
                        try:
                            start_ms = int(float(start) * 1000)
                            shape_str = shape.strip().upper()
                            if shape_str in "ABCDEFGHX":
                                self.sync_data.append((start_ms, shape_str))
                        except (ValueError, TypeError):
                            continue
        except Exception as e:
            raise Exception(f"Error parsing XML: {str(e)}")

    def parse_dat_sync(self, file_path):
        """Parse DAT format sync data (for Moho/OpenToonz)"""
        try:
            # Get frame rate from settings
            frame_rate = self.dat_frame_rate.value()
            if frame_rate == 0:
                frame_rate = 24  # Default to 24 if not set
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            frame = int(parts[0])
                            shape = parts[1].strip().upper()
                            # Convert frame number to milliseconds using actual frame rate
                            time_ms = int((frame / float(frame_rate)) * 1000)
                            
                            # Map Preston Blair names to single letter if needed
                            shape_map = {
                                'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E',
                                'F': 'F', 'G': 'G', 'H': 'H', 'X': 'X',
                                'REST': 'X', 'AI': 'A', 'O': 'O', 'U': 'U',
                                'TEETH': 'E', 'LIPS': 'F'
                            }
                            final_shape = shape_map.get(shape, shape[0] if shape else 'X')
                            
                            if final_shape in "ABCDEFGHX":
                                self.sync_data.append((time_ms, final_shape))
                        except (ValueError, IndexError):
                            continue
        except Exception as e:
            raise Exception(f"Error parsing DAT: {str(e)}")

    def open_preview(self):
        """Open the audio preview dialog"""
        self.open_audio_preview()
    
    def on_dialog_closed(self):
        """Called when a preview dialog is closed"""
        if self.current_preview_dialog is not None:
            self.current_preview_dialog = None



def main():
    app = QApplication(sys.argv)
    gui = RhubarbGUI()
    gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
