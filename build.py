"""
Build script for Voice Agent Desktop Application
This script automates the packaging process for Windows
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
import urllib.request
import zipfile
import tarfile

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {description} failed")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def download_vosk_model():
    """Download Vosk model if not present"""
    # Vosk models are now downloaded by the installer, not required for build
    print("\nVosk models will be downloaded by the installer during installation.")
    return "installer"

def check_ollama():
    """Check if Ollama is installed"""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"Ollama found: {result.stdout.strip()}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    print("Ollama not found. Please install from: https://ollama.com/download")
    return False

def check_dependencies():
    """Check if required Python packages are installed"""
    required = ['pyinstaller', 'fastapi', 'uvicorn', 'sounddevice', 'vosk', 'requests']
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print("Installing missing packages...")
        return run_command(f"pip install {' '.join(missing)}", "Installing dependencies")
    
    print("All dependencies satisfied")
    return True

def build_executable():
    """Build the executable using PyInstaller"""
    return run_command(
        "python -m PyInstaller build.spec --clean -y",
        "Building executable with PyInstaller"
    )

def copy_vosk_models_to_dist():
    """Copy Vosk models to the dist directory"""
    dist_dir = Path("dist/VoiceAgent")
    if not dist_dir.exists():
        print(f"Distribution directory not found: {dist_dir}")
        return False
    
    model_dirs = [
        Path("vosk-model-en-us-0.22"),
        Path("vosk-model-small-en-us-0.15"),
        Path("vosk-model-en-us-0.42-gigaspeech"),
    ]
    
    for model_dir in model_dirs:
        if model_dir.exists():
            dest = dist_dir / model_dir.name
            print(f"Copying {model_dir} to {dest}")
            shutil.copytree(model_dir, dest, dirs_exist_ok=True)
            return True
    
    print("No Vosk models found to copy")
    return False

def create_installer_script():
    """Create a simple batch script to run the app"""
    script_content = """@echo off
cd /d "%~dp0"
echo ========================================
echo Voice Agent Desktop Application
echo ========================================
echo.
echo Checking dependencies...
echo.

REM Check if Ollama is installed
where ollama >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Ollama not found!
    echo Please install Ollama from: https://ollama.com/download
    echo.
    echo Voice Agent will start, but AI features will not work.
    echo.
    pause
)

REM Check if Vosk models exist
if not exist "vosk-model-en-us-0.22" (
    if not exist "vosk-model-small-en-us-0.15" (
        if not exist "vosk-model-en-us-0.42-gigaspeech" (
            echo WARNING: No Vosk models found!
            echo Voice recognition will not work.
            echo Download models from: https://alphacephei.com/vosk/models
            echo Extract to this directory.
            echo.
            pause
        )
    )
)

echo Starting Voice Agent...
echo The application will open in your browser.
echo Press Ctrl+C to stop the server
echo.
VoiceAgent.exe
pause
"""
    script_path = Path("dist/VoiceAgent/run.bat")
    script_path.write_text(script_content)
    print(f"Created run script: {script_path}")
    return True

def create_nsis_installer():
    """Create NSIS installer if available"""
    # Check if makensis is available
    try:
        result = subprocess.run(["makensis", "/VERSION"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("NSIS found. Creating professional installer...")
            return run_command(
                "makensis voice_agent_setup.nsi",
                "Building NSIS installer"
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("NSIS (makensis) not found.")
        print("Download from: https://nsis.sourceforge.io/Download")
        print("After installation, run: makensis voice_agent_setup.nsi")
        return False

def create_python_installer():
    """Create Python-based installer package"""
    print("Creating Python-based installer...")
    
    # Copy installer.py to dist directory
    dist_dir = Path("dist")
    installer_dest = dist_dir / "installer.py"
    
    if not Path("installer.py").exists():
        print("installer.py not found in project root")
        return False
    
    import shutil
    shutil.copy("installer.py", installer_dest)
    print(f"Copied installer to: {installer_dest}")
    
    # Create a batch file to run the installer
    run_installer = dist_dir / "run_installer.bat"
    run_installer.write_text("""@echo off
echo ========================================
echo Voice Agent Professional Installer
echo ========================================
echo.
echo This installer will automatically:
echo - Install Ollama (if not already installed)
echo - Download Vosk speech recognition model
echo - Pull the required AI model
echo - Install Voice Agent
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul
echo.
echo Starting installer...
python installer.py
pause
""")
    print(f"Created installer launcher: {run_installer}")
    
    # Create README for the installer
    installer_readme = dist_dir / "INSTALLER_README.txt"
    installer_readme.write_text("""Voice Agent Professional Installer

This installer will automatically set up everything you need to run Voice Agent:

1. Ollama (for AI features) - automatically downloaded and installed if needed
2. Vosk speech recognition model - automatically downloaded (approximately 40MB)
3. Ollama AI model (llama3.1:8b) - automatically pulled (approximately 4GB)
4. Voice Agent application - installed to Program Files

SYSTEM REQUIREMENTS:
- Windows 10 or later (64-bit)
- Administrator privileges (required for installation)
- Internet connection (for downloading dependencies)
- 8GB RAM minimum (16GB recommended for AI features)

TO INSTALL:
1. Right-click "run_installer.bat" and select "Run as administrator"
2. Follow the on-screen instructions
3. The installer will handle everything automatically

PRIVACY:
All data processing happens locally on your machine. No cloud services are used.

TROUBLEbOOTING:
- If the installer fails to download Ollama, install it manually from: https://ollama.com/download
- If Vosk model download fails, download vosk-model-small-en-us-0.15.zip from: https://alphacephei.com/vosk/models
- If AI model pull fails, run: ollama pull llama3.1:8b
""")
    print(f"Created installer README: {installer_readme}")
    
    return True

def create_readme():
    """Create a README for the distributed package"""
    readme_content = """# Voice Agent Desktop Application

A local voice-powered grocery and to-do list manager that runs entirely on your machine.

## First Time Setup

### 1. Install Ollama (Required for AI features)
Download and install Ollama from: https://ollama.com/download

After installation, open a terminal/command prompt and run:
```
ollama pull llama3.1:8b
```

### 2. Run the Application
Double-click `run.bat` or `VoiceAgent.exe`

The application will start and open in your browser at: http://127.0.0.1:8000

## Features

- **Voice Recognition**: Local speech-to-text using Vosk (no internet required)
- **AI Processing**: Local AI intent extraction using Ollama (runs on your machine)
- **Smart Lists**: Automatically categorizes items as groceries or to-dos
- **Review Queue**: Low-confidence items are queued for your review
- **Persistent Storage**: Your lists are saved locally

## Troubleshooting

### Microphone not working
- Check your OS microphone permissions
- Ensure no other application is using the microphone

### Ollama not connected
- Make sure Ollama is running: check the system tray
- Verify Ollama is installed correctly
- Try restarting the Ollama application

### ASR model missing
- The app includes Vosk models in the distribution folder
- If models are missing, download from: https://alphacephei.com/vosk/models
- Extract the model folder next to the executable

## System Requirements

- Windows 10 or later
- 4GB RAM minimum (8GB recommended)
- Microphone
- Ollama (for AI features)

## Privacy

This application runs entirely locally on your machine:
- No data is sent to cloud services
- Voice processing happens on your device
- Lists are stored locally in JSON format
"""
    readme_path = Path("dist/VoiceAgent/README.txt")
    readme_path.write_text(readme_content)
    print(f"Created README: {readme_path}")
    return True

def main():
    print("="*60)
    print("Voice Agent Desktop Application Builder")
    print("="*60)
    
    # Step 1: Check dependencies
    if not check_dependencies():
        print("Failed to install dependencies")
        sys.exit(1)
    
    # Step 2: Check Vosk models
    vosk_model = download_vosk_model()
    if not vosk_model:
        print("WARNING: No Vosk models found. The app may not work without them.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Step 3: Check Ollama
    if not check_ollama():
        print("WARNING: Ollama not found. AI features will not work.")
        print("The app will still work with basic functionality.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Step 4: Build executable
    if not build_executable():
        print("Failed to build executable")
        sys.exit(1)
    
    # Step 5: Copy Vosk models
    copy_vosk_models_to_dist()
    
    # Step 6: Create run script
    create_installer_script()
    
    # Step 7: Create README
    create_readme()
    
    # Step 8: Create Python-based installer
    create_python_installer()
    
    # Step 9: Create professional NSIS installer (if available)
    create_nsis_installer()
    
    print("\n" + "="*60)
    print("BUILD COMPLETE!")
    print("="*60)
    print(f"Distribution folder: {Path('dist').absolute()}")
    print("\nDISTRIBUTION OPTIONS:")
    print("="*60)
    print("\nOPTION 1 - Portable (Simple):")
    print("1. Zip the 'dist/VoiceAgent' folder")
    print("2. Share the zip file with users")
    print("3. Users extract and run run.bat")
    print("Note: Users must manually install Ollama")
    
    print("\nOPTION 2 - Python Installer (Recommended):")
    print("1. Run: dist/run_installer.bat")
    print("2. The installer will automatically:")
    print("   - Install Ollama if needed")
    print("   - Download Vosk models")
    print("   - Pull AI model")
    print("   - Install Voice Agent")
    print("3. Distribute the entire 'dist' folder")
    
    print("\nOPTION 3 - NSIS Professional Installer:")
    print("1. Install NSIS from: https://nsis.sourceforge.io/Download")
    print("2. Run: makensis voice_agent_setup.nsi")
    print("3. Distribute the generated VoiceAgent-Setup.exe")
    print("="*60)

if __name__ == "__main__":
    main()
