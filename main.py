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
    QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon


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
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
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


class RhubarbGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.rhubarb_exe = self.get_rhubarb_executable()
        self.worker = None
        self.init_ui()
        self.setWindowTitle("Rhubarb Lip Sync GUI")
        self.setWindowIcon(self.get_window_icon())
        self.setGeometry(100, 100, 800, 700)

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

        # Quiet mode
        self.quiet_mode = QCheckBox("Quiet mode (suppress progress messages)")
        advanced_layout.addRow("", self.quiet_mode)

        # Machine readable
        self.machine_readable = QCheckBox("Machine readable output (JSON format)")
        self.machine_readable.setChecked(True)
        self.machine_readable.setToolTip("Enables parsing of progress data")
        advanced_layout.addRow("", self.machine_readable)

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
        self.command_preview = QTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(80)
        self.command_preview.setPlaceholderText("Command preview will appear here...")
        self.command_preview.setStyleSheet("background-color: #f5f5f5; font-family: monospace; font-size: 9pt;")
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
        self.run_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        button_layout.addWidget(self.run_btn)

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
        self.quiet_mode.toggled.connect(self.update_command_preview)
        self.machine_readable.toggled.connect(self.update_command_preview)
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
        
        if self.quiet_mode.isChecked():
            command.append("--quiet")
        
        if self.machine_readable.isChecked():
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

        # Add quiet mode
        if self.quiet_mode.isChecked():
            command.append("--quiet")

        # Add machine readable (for progress tracking)
        if self.machine_readable.isChecked():
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

    def on_error(self, error_msg):
        """Called when an error occurs"""
        self.run_btn.setEnabled(True)
        self.status_text.append(f"\n❌ {error_msg}")

    def clear_output(self):
        """Clear the status output"""
        self.status_text.clear()
        self.progress_bar.setValue(0)


def main():
    app = QApplication(sys.argv)
    gui = RhubarbGUI()
    gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
