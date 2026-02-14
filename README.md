# Rhubarb Lip Sync GUI

A user-friendly graphical interface for [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync), a powerful tool for generating lip sync data from audio files. This application simplifies the process of analyzing speech and generating mouth shape information for animation and video projects.

## Features

- **Cross-Platform Support**: Runs on Windows, macOS, and Linux with automatic platform detection
- **Intuitive GUI**: Clean, tabbed interface organized into basic, optional, and advanced settings
- **Real-Time Preview**: Shows the exact command that will be executed before running
- **Progress Tracking**: Live progress bar and status updates during processing
- **Multiple Output Formats**: Support for TSV, XML, JSON, and DAT formats
- **Flexible Speech Recognition**: Choose between `pocketSphinx` (English-only) and `phonetic` (language-independent) recognizers
- **Extended Mouth Shapes**: Support for G, H, and X extended shapes
- **DAT Format Options**: Frame rate customization and Preston Blair mouth shape names for OpenToonz/Moho
- **Advanced Logging**: Configurable console and file logging with multiple verbosity levels
- **Multi-threading Support**: Configurable thread count for faster processing

## Requirements

### System Requirements

- Python 3.6+
- PyQt5 (`pip install PyQt5`)

### Rhubarb Binaries

**Important**: The Rhubarb Lip Sync binaries **must be included in the project** for the application to work.

The application automatically detects your operating system and looks for the appropriate executable:

- **Windows**: `rhubarb_win/rhubarb.exe`
- **macOS**: `rhubarb_mac/rhubarb`
- **Linux**: `rhubarb_linux/rhubarb`

These folders are already included in the project with the necessary binaries and resource files (acoustic models, dictionaries, etc.).

**Alternative**: If you want to use a custom Rhubarb installation, you can modify the `get_rhubarb_executable()` method in `main.py` to point to your custom executable path.

## Installation

1. **Clone or download** this repository
2. **Install Python dependencies**:
   ```bash
   pip install PyQt5
   ```
3. **Verify Rhubarb binaries** are present in the project directory:
   - `rhubarb_win/rhubarb.exe` (for Windows)
   - `rhubarb_mac/rhubarb` (for macOS)
   - `rhubarb_linux/rhubarb` (for Linux)

## Usage

### Running the Application

**Windows**:

```bash
python main.py
```

**macOS/Linux**:

```bash
python main.py
```

Or if Python 3 is not the default:

```bash
python3 main.py
```

### Basic Workflow

1. **Select Input Audio File**: Click "Browse..." next to "Input Audio File" and select a WAV or OGG audio file
2. **Specify Output File**: Click "Browse..." next to "Output File" and choose output location and filename
3. **Configure Settings**:
   - Adjust recognizer, export format, and other options as needed
   - The export format auto-detects from file extension (e.g., `.json` → JSON format)
4. **Preview Command**: Check the "Command Preview" section to verify the exact command
5. **Run**: Click "Run Rhubarb Lip Sync" to start processing
6. **Monitor Progress**: Watch the progress bar and status messages

## Interface Overview

### Basic Settings Tab

- **Input Audio File**: WAV or OGG audio file containing the speech (required)
- **Output File**: Path and filename for the generated lip sync data (required)
- **Speech Recognizer**:
  - `pocketSphinx`: English only, faster
  - `phonetic`: Language-independent, slower
- **Export Format**: Output data format (auto-detected from file extension)
  - `tsv`: Tab-separated values (most compact)
  - `xml`: XML format
  - `json`: JSON format
  - `dat`: For Moho/OpenToonz
- **Extended Shapes**: Additional mouth shape categories (leave empty for basic shapes only)
  - Default: `GHX`
  - Available: `G`, `H`, `X`

### Optional Settings Tab

- **Dialog Text File**: Plain text file with the exact dialog (optional but recommended)
- **DAT Frame Rate**: Frame rate for DAT format output (default: 24 fps)
- **DAT Preston Blair**: Use Preston Blair mouth shape naming conventions for OpenToonz compatibility

### Advanced Settings Tab

- **Quiet Mode**: Suppress progress messages from Rhubarb
- **Machine Readable Output**: Enable JSON-formatted machine-readable output (enabled by default for progress tracking)
- **Console Log Level**: Verbosity level for console output (`error`, `warning`, `info`, `debug`, `trace`)
- **Log File**: Save detailed diagnostic logs to a file (optional)
- **Log Level**: Verbosity for file logging (`debug`, `info`, `warning`, `error`, `fatal`, `trace`)
- **Number of Threads**: CPU threads to use for processing (0 = auto-detect, recommended)

## Output Formats

### TSV (Tab-Separated Values)

The most compact format, suitable for most animation software.

### XML

Structured XML format with detailed mouth shape information.

### JSON

Machine-readable JSON format for programmatic processing.

### DAT

Format for Moho and OpenToonz:

- **Standard**: Uses numeric mouth shape codes
- **Preston Blair**: Uses Preston Blair mouth shape naming system

## Examples

### Basic Usage

1. Input: `video_audio.wav`
2. Output: `output.tsv`
3. Run with default settings

### Advanced Animation Export

1. Input: `dialogue.ogg`
2. Output: `mouth_shapes.json`
3. Recognizer: `phonetic` (supports non-English)
4. Console Level: `info`
5. Threads: 8 (for faster processing)

### OpenToonz/Moho Export

1. Input: `character_voice.wav`
2. Output: `lip_sync.dat`
3. DAT Frame Rate: 24 (or 30 for NTSC)
4. Enable "DAT Preston Blair" checkbox
5. Dialog File: `script.txt`

## Troubleshooting

### "Rhubarb executable not found"

- **Problem**: The Rhubarb binary is missing or in the wrong location
- **Solution**:
  1. Verify the appropriate folder exists (`rhubarb_win`, `rhubarb_mac`, or `rhubarb_linux`)
  2. Ensure the executable file is present and has execute permissions
  3. On Linux/macOS, run: `chmod +x rhubarb_linux/rhubarb` or `chmod +x rhubarb_mac/rhubarb`

### "Input file not found"

- **Problem**: The selected audio file doesn't exist
- **Solution**: Re-select the input file using the Browse button

### Process fails with "exit code 1"

- **Problem**: Various errors (bad audio, missing recognizer data, etc.)
- **Solution**:
  1. Check the status output for specific error messages
  2. Enable higher console/log level (e.g., `debug`) for more details
  3. Verify the audio file is valid and in a supported format
  4. Check that Rhubarb resource files exist in `res/sphinx/` subdirectories

### Application crashes or hangs

- **Problem**: GUI freezes during processing
- **Solution**: This shouldn't happen as processing runs in a separate thread. If it does:
  1. Close and reopen the application
  2. Try with fewer threads
  3. Check system resources (free disk space, RAM)

## File Structure

```
lipsynk/
├── main.py                 # Main application
├── README.md              # This file
├── res/                   # Resource files
│   └── icon.ico          # Window icon (optional)
├── rhubarb_win/           # Windows binary and resources
│   ├── rhubarb.exe
│   ├── res/
│   │   └── sphinx/        # Acoustic models and dictionaries
│   └── extras/            # Plugin integrations
├── rhubarb_mac/           # macOS binary and resources
│   ├── rhubarb
│   ├── res/
│   │   └── sphinx/
│   └── extras/
└── rhubarb_linux/         # Linux binary and resources
    ├── rhubarb
    ├── res/
    │   └── sphinx/
    └── extras/
```

## About Rhubarb Lip Sync

This GUI application is a wrapper around Rhubarb Lip Sync, developed by Daniel S. Wolf. Learn more about Rhubarb at:

- [GitHub Repository](https://github.com/DanielSWolf/rhubarb-lip-sync)
- [Official Documentation](https://github.com/DanielSWolf/rhubarb-lip-sync/wiki)

## License

This GUI application is provided as-is. Please refer to the Rhubarb Lip Sync LICENSE files in the `rhubarb_*` directories for the terms of the Rhubarb binary distributions.

## Support

For issues with this GUI application, check the troubleshooting section above. For issues with Rhubarb Lip Sync itself, visit the official [GitHub Issues](https://github.com/DanielSWolf/rhubarb-lip-sync/issues) page.

---

**Version**: 1.0  
**Last Updated**: February 2026
