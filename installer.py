"""
Voice Agent Professional Installer
Automatically installs Ollama, Vosk models, and the Voice Agent application
"""
import os
import sys
import subprocess
import urllib.request
import zipfile
import tarfile
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

class VoiceAgentInstaller:
    def __init__(self):
        self.install_dir = Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')) / 'VoiceAgent'
        self.ollama_installers = {
            'win32': 'https://ollama.com/download/OllamaSetup.exe',
            'darwin': 'https://ollama.com/download/Ollama-darwin.zip',
            'linux': 'https://ollama.com/download/ollama-linux-amd64'
        }
        self.vosk_model_url = 'https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip'
        self.ollama_installed = False
        self.vosk_downloaded = False
        self.app_installed = False
        
    def log(self, message):
        """Log a message to the UI"""
        if hasattr(self, 'log_text'):
            self.log_text.insert(tk.END, message + '\n')
            self.log_text.see(tk.END)
            self.root.update()
        print(message)
        
    def check_admin(self):
        """Check if running as administrator"""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
            
    def request_admin(self):
        """Request administrator privileges"""
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit()
        except:
            pass
            
    def check_ollama(self):
        """Check if Ollama is installed"""
        self.log("Checking for Ollama installation...")
        
        ollama_paths = [
            Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')) / 'Ollama' / 'ollama.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Ollama' / 'ollama.exe',
        ]
        
        for path in ollama_paths:
            if path.exists():
                self.log(f"✓ Ollama found at: {path}")
                self.ollama_installed = True
                return str(path.parent)
        
        self.log("✗ Ollama not found")
        return None
        
    def download_ollama(self):
        """Download and install Ollama"""
        self.log("Downloading Ollama installer...")
        
        import platform
        system = platform.system().lower()
        
        if system not in self.ollama_installers:
            self.log(f"✗ Unsupported platform: {system}")
            return False
            
        url = self.ollama_installers[system]
        filename = url.split('/')[-1]
        temp_dir = Path(os.environ.get('TEMP', '/tmp'))
        installer_path = temp_dir / filename
        
        try:
            def download_progress(count, block_size, total_size):
                if total_size > 0:
                    percent = int(count * block_size * 100 / total_size)
                    self.log(f"Download progress: {percent}%")
                    
            urllib.request.urlretrieve(url, installer_path, download_progress)
            self.log(f"✓ Downloaded: {installer_path}")
            
            # Install Ollama
            self.log("Installing Ollama...")
            if system == 'win32':
                subprocess.run([str(installer_path), '/S'], check=True)
                self.log("✓ Ollama installer launched")
                self.log("Please wait for Ollama installation to complete...")
                time.sleep(10)  # Wait for installation
            elif system == 'darwin':
                with zipfile.ZipFile(installer_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                # Copy to Applications
                app_path = Path('/Applications/Ollama.app')
                if app_path.exists():
                    self.log("✓ Ollama installed for macOS")
            elif system == 'linux':
                os.chmod(installer_path, 0o755)
                subprocess.run([str(installer_path)], check=True)
                self.log("✓ Ollama installed for Linux")
            
            self.ollama_installed = True
            return True
            
        except Exception as e:
            self.log(f"✗ Failed to install Ollama: {e}")
            return False
            
    def download_vosk_model(self, dest_dir):
        """Download Vosk model"""
        self.log("Downloading Vosk speech recognition model...")
        
        model_zip = dest_dir / 'vosk-model.zip'
        
        try:
            def download_progress(count, block_size, total_size):
                if total_size > 0:
                    percent = int(count * block_size * 100 / total_size)
                    if percent % 10 == 0:
                        self.log(f"Download progress: {percent}%")
                        
            urllib.request.urlretrieve(self.vosk_model_url, model_zip, download_progress)
            self.log("✓ Vosk model downloaded")
            
            # Extract
            self.log("Extracting Vosk model...")
            with zipfile.ZipFile(model_zip, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)
            
            # Cleanup
            model_zip.unlink()
            self.log("✓ Vosk model extracted")
            self.vosk_downloaded = True
            return True
            
        except Exception as e:
            self.log(f"✗ Failed to download Vosk model: {e}")
            return False
            
    def pull_ollama_model(self):
        """Pull the required Ollama model"""
        self.log("Pulling Ollama model llama3.1:8b...")
        self.log("This may take several minutes on first run...")
        
        try:
            # Find ollama executable
            ollama_path = self.check_ollama()
            if not ollama_path:
                self.log("✗ Ollama not found")
                return False
                
            ollama_exe = Path(ollama_path) / 'ollama.exe'
            if not ollama_exe.exists():
                ollama_exe = Path(ollama_path) / 'ollama'
                
            # Pull model
            process = subprocess.Popen(
                [str(ollama_exe), 'pull', 'llama3.1:8b'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            for line in process.stdout:
                self.log(line.strip())
                
            process.wait()
            
            if process.returncode == 0:
                self.log("✓ Ollama model pulled successfully")
                return True
            else:
                self.log(f"✗ Failed to pull model (exit code: {process.returncode})")
                return False
                
        except Exception as e:
            self.log(f"✗ Error pulling model: {e}")
            return False
            
    def install_app(self, source_dir):
        """Install Voice Agent application"""
        self.log(f"Installing Voice Agent to: {self.install_dir}")
        
        try:
            # Create installation directory
            self.install_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy files from source directory
            if source_dir and source_dir.exists():
                import shutil
                for item in source_dir.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, self.install_dir / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, self.install_dir / item.name)
                self.log("✓ Application files copied")
            else:
                self.log("⚠ No source directory specified, skipping file copy")
            
            # Create shortcuts
            self.create_shortcuts()
            
            self.app_installed = True
            return True
            
        except Exception as e:
            self.log(f"✗ Failed to install application: {e}")
            return False
            
    def create_shortcuts(self):
        """Create desktop and start menu shortcuts"""
        try:
            import win32com.client
            
            # Desktop shortcut
            desktop = Path(os.environ['USERPROFILE']) / 'Desktop'
            shortcut_path = desktop / 'Voice Agent.lnk'
            self.create_shortcut(shortcut_path, str(self.install_dir / 'VoiceAgent.exe'))
            
            # Start menu shortcut
            start_menu = Path(os.environ['APPDATA']) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
            shortcut_path = start_menu / 'Voice Agent' / 'Voice Agent.lnk'
            shortcut_path.parent.mkdir(parents=True, exist_ok=True)
            self.create_shortcut(shortcut_path, str(self.install_dir / 'VoiceAgent.exe'))
            
            self.log("✓ Shortcuts created")
            
        except ImportError:
            self.log("⚠ Could not create shortcuts (pywin32 not available)")
        except Exception as e:
            self.log(f"⚠ Could not create shortcuts: {e}")
            
    def create_shortcut(self, path, target):
        """Create a Windows shortcut"""
        import win32com.client
        shell = win32com.client.Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(str(path))
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = str(self.install_dir)
        shortcut.save()
        
    def run_installation(self, source_dir=None):
        """Run the complete installation process"""
        self.log("="*60)
        self.log("Voice Agent Professional Installer")
        self.log("="*60)
        
        # Step 1: Check Ollama
        if not self.check_ollama():
            response = messagebox.askyesno(
                "Ollama Required",
                "Ollama is required for AI features. Would you like the installer to download and install it automatically?"
            )
            if response:
                if not self.download_ollama():
                    messagebox.showerror("Error", "Failed to install Ollama. Please install manually from https://ollama.com/download")
                    return False
            else:
                messagebox.showwarning("Warning", "Voice Agent will be installed without AI features.")
        
        # Step 2: Install application
        if not self.install_app(source_dir):
            return False
            
        # Step 3: Download Vosk model (automatic)
        if not self.vosk_downloaded:
            self.log("Downloading Vosk speech recognition model (this is required)...")
            if not self.download_vosk_model(self.install_dir):
                messagebox.showwarning("Warning", "Failed to download Vosk model. Voice recognition will not work. You can download it manually from https://alphacephei.com/vosk/models")
        
        # Step 4: Pull Ollama model (automatic)
        if self.ollama_installed:
            self.log("Pulling Ollama AI model llama3.1:8b (this may take several minutes)...")
            self.pull_ollama_model()
        
        self.log("="*60)
        self.log("Installation Complete!")
        self.log("="*60)
        
        messagebox.showinfo(
            "Installation Complete",
            "Voice Agent has been installed successfully!\n\nYou can launch it from the desktop shortcut or Start Menu."
        )
        
        return True
        
    def create_gui(self):
        """Create the installer GUI"""
        self.root = tk.Tk()
        self.root.title("Voice Agent Installer")
        self.root.geometry("600x400")
        
        # Title
        title_label = ttk.Label(self.root, text="Voice Agent Professional Installer", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Progress frame
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(pady=10, padx=20, fill='x')
        
        # Progress bar
        self.progress = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress.pack(fill='x', pady=5)
        
        # Log text
        log_frame = ttk.Frame(self.root)
        log_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=70)
        self.log_text.pack(fill='both', expand=True)
        
        # Install button
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)
        
        self.install_button = ttk.Button(button_frame, text="Install", command=self.start_installation)
        self.install_button.pack(side='left', padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.root.quit)
        cancel_button.pack(side='left', padx=5)
        
        return self.root
        
    def start_installation(self):
        """Start the installation in a separate thread"""
        self.install_button.config(state='disabled')
        self.progress.start()
        
        def run():
            source_dir = Path(__file__).parent / 'dist' / 'VoiceAgent'
            success = self.run_installation(source_dir)
            self.progress.stop()
            if success:
                self.install_button.config(text="Complete", state='disabled')
            else:
                self.install_button.config(state='normal')
                
        threading.Thread(target=run, daemon=True).start()
        
    def run(self):
        """Run the installer with GUI"""
        if not self.check_admin():
            self.request_admin()
            return
            
        root = self.create_gui()
        root.mainloop()

def main():
    installer = VoiceAgentInstaller()
    
    # Check if running with --no-gui flag
    if '--no-gui' in sys.argv:
        # Run in command-line mode
        source_dir = Path(__file__).parent / 'dist' / 'VoiceAgent'
        installer.run_installation(source_dir)
    else:
        # Run with GUI
        installer.run()

if __name__ == "__main__":
    main()
