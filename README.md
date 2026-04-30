# Voice Grocery/To-do Agent (Local)

A fully local voice-powered grocery and to-do list manager that runs entirely on your machine. No cloud services required.

## Features

- **Continuous microphone listening** (local/offline speech-to-text with Vosk)
- **Local AI intent extraction** (Ollama on your machine)
- **Smart list categorization** (automatically sorts items as groceries or to-dos)
- **Review queue** (low-confidence items queued for manual review)
- **Persistent storage** (lists saved locally in JSON format)
- **Desktop application** (downloadable executable for Windows)

## Installation

### Option 1: Professional Installer (Recommended - One-Click Setup)

**This is the easiest installation method - everything is automated!**

1. Download the latest `VoiceAgent-Installer.zip` from the releases
2. Extract the zip file
3. Right-click `run_installer.bat` and select "Run as administrator"
4. The installer will automatically:
   - ✅ Install Ollama (if not already installed)
   - ✅ Download Vosk speech recognition model (~40MB)
   - ✅ Pull the required AI model llama3.1:8b (~4GB)
   - ✅ Install Voice Agent to Program Files
   - ✅ Create desktop and Start Menu shortcuts
5. Launch Voice Agent from the desktop shortcut

**System Requirements:**
- Windows 10 or later (64-bit)
- Administrator privileges (required for installation)
- Internet connection (for downloading dependencies)
- 8GB RAM minimum (16GB recommended for AI features)

**No manual setup required!** The installer handles everything automatically.

### Option 2: Download Pre-built Application (Portable)

1. Download the latest `VoiceAgent-Portable.zip` from the releases
2. Extract the zip file to any location
3. Double-click `run.bat` to start the application
4. The app will open in your browser at http://127.0.0.1:8000

**Required Dependencies:**
- **Ollama**: Download from [ollama.com/download](https://ollama.com/download)
  - After installation, run: `ollama pull llama3.1:8b`
- **Vosk Model**: The installer will automatically download the required speech recognition model (vosk-model-en-us-0.22, ~1.8GB)

### Option 3: Build from Source

#### Prerequisites

1. **Python 3.10+**
2. **Ollama** installed and running:
   - [https://ollama.com/download](https://ollama.com/download)
   - After installation, run: `ollama pull llama3.1:8b`
3. **Vosk model**: The installer will automatically download vosk-model-en-us-0.22 during first run

#### Setup

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Run Development Version

```bash
python app.py
```

Open: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Option 3: Build Desktop Application

To build a distributable desktop application:

```bash
# Install build dependencies
pip install -r requirements-build.txt

# Run the build script
python build.py
```

The built application will be in `dist/VoiceAgent/`. You can:
- Zip this folder for distribution
- Or run `create_installer.bat` to create an installer (requires Inno Setup)

## Usage

### Voice Commands

Press **Start Listening** and speak naturally:

- "Add milk and eggs to groceries"
- "Remind me to call the dentist tomorrow"
- "I need to buy bread"
- "Don't forget to pay the electric bill"

The local AI agent will parse speech and automatically categorize items.

### Manual Entry

Use the manual add form to:
- Add items directly to grocery or to-do lists
- Use "Auto" mode to let Ollama categorize the item

### Review Queue

Items with low confidence are queued for review. You can:
- Confirm items to the appropriate list
- Remove items that don't belong
- Bulk confirm all items to a specific list

## Troubleshooting

### Microphone not working
- Check OS microphone permissions
- Ensure no other application is using the microphone
- Verify microphone is selected in system settings

### Ollama not connected
- Make sure Ollama is running (check system tray)
- Verify Ollama is installed correctly
- Try restarting the Ollama application
- Check that the model is pulled: `ollama pull llama3.1:8b`

### ASR model missing
- The app includes Vosk models in the distribution folder
- If models are missing, download from [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models)
- Extract the model folder next to the executable

### Port already in use
- The app uses port 8000 by default
- Change the port in `app.py` if needed: modify the `uvicorn.run()` call

## Privacy

This application runs entirely locally on your machine:

- **No data is sent to cloud services**
- **Voice processing happens on your device**
- **Lists are stored locally in JSON format**
- **AI inference runs locally with Ollama**

## System Requirements

- **Windows 10 or later** (for pre-built executable)
- **4GB RAM minimum** (8GB recommended)
- **Microphone**
- **Ollama** (for AI features)
- **Vosk model** (for speech recognition)

## Development

### Project Structure

```
voice-agent-app/
├── app.py                 # Main application
├── setup_wizard.py        # Setup wizard for dependencies
├── build.py              # Build script for packaging
├── build.spec            # PyInstaller configuration
├── templates/            # HTML templates
├── static/              # CSS and JavaScript
├── vosk-model-*/         # Speech recognition models
└── list_data.json        # Persistent data storage
```

### Configuration

Edit these constants in `app.py`:

- `OLLAMA_MODEL`: Change the Ollama model (default: `llama3.1:8b`)
- `OLLAMA_MIN_CONFIDENCE`: Adjust confidence threshold (default: `0.72`)
- `INTENT_MODE`: `"ambient"` or `"strict"` (default: `"ambient"`)
- `SAMPLE_RATE`: Audio sample rate (default: `16000`)

## License

This project is open source and available for personal and commercial use.
