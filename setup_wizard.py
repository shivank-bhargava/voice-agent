"""
Setup Wizard for Voice Agent
Handles automatic installation of dependencies (Ollama, Vosk models)
"""
import os
import sys
import subprocess
import threading
import urllib.request
import zipfile
import tarfile
from pathlib import Path
import json
import time

class SetupWizard:
    def __init__(self):
        self.app_dir = Path(__file__).parent
        self.status_callback = None
        
    def set_status_callback(self, callback):
        """Set callback function for status updates"""
        self.status_callback = callback
        
    def log(self, message):
        """Log a message"""
        if self.status_callback:
            self.status_callback(message)
        print(message)
        
    def check_ollama(self):
        """Check if Ollama is installed and running"""
        self.log("Checking Ollama installation...")
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.log(f"✓ Ollama found: {result.stdout.strip()}")
                
                # Check if Ollama service is running
                try:
                    import requests
                    response = requests.get("http://127.0.0.1:11434/api/version", timeout=2)
                    if response.status_code == 200:
                        self.log("✓ Ollama service is running")
                        return True
                    else:
                        self.log("⚠ Ollama is installed but service is not running")
                        return False
                except:
                    self.log("⚠ Ollama is installed but service is not running")
                    return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        self.log("✗ Ollama not found")
        return False
    
    def get_ollama_download_url(self):
        """Get the appropriate Ollama download URL for the current platform"""
        import platform
        system = platform.system()
        machine = platform.machine()
        
        if system == "Windows":
            if machine in ["AMD64", "x86_64"]:
                return "https://ollama.com/download/OllamaSetup.exe"
            else:
                return None
        elif system == "Darwin":  # macOS
            return "https://ollama.com/download/Ollama-darwin.zip"
        elif system == "Linux":
            return "https://ollama.com/download/ollama-linux-amd64"
        
        return None
    
    def download_ollama(self, download_dir):
        """Download Ollama installer"""
        url = self.get_ollama_download_url()
        if not url:
            self.log("✗ Unsupported platform for automatic Ollama download")
            return False
        
        self.log(f"Downloading Ollama from {url}")
        filename = url.split("/")[-1]
        dest_path = download_dir / filename
        
        try:
            def download_progress(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                if percent % 10 == 0:
                    self.log(f"Download progress: {percent}%")
            
            urllib.request.urlretrieve(url, dest_path, download_progress)
            self.log(f"✓ Downloaded to {dest_path}")
            return dest_path
        except Exception as e:
            self.log(f"✗ Download failed: {e}")
            return False
    
    def check_vosk_models(self):
        """Check if Vosk models are present"""
        self.log("Checking Vosk models...")
        model_candidates = [
            self.app_dir / "vosk-model-en-us-0.22",
            self.app_dir / "vosk-model-small-en-us-0.15",
            self.app_dir / "vosk-model-en-us-0.42-gigaspeech",
        ]
        
        found_models = []
        for model_path in model_candidates:
            if model_path.exists() and model_path.is_dir():
                self.log(f"✓ Found model: {model_path.name}")
                found_models.append(model_path.name)
        
        if found_models:
            return True, found_models
        else:
            self.log("✗ No Vosk models found")
            return False, []
    
    def download_vosk_model(self, model_name="vosk-model-small-en-us-0.15"):
        """Download a Vosk model"""
        self.log(f"Downloading Vosk model: {model_name}")
        
        # Model URLs
        model_urls = {
            "vosk-model-small-en-us-0.15": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            "vosk-model-en-us-0.22": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
        }
        
        if model_name not in model_urls:
            self.log(f"✗ Unknown model: {model_name}")
            return False
        
        url = model_urls[model_name]
        zip_path = self.app_dir / f"{model_name}.zip"
        
        try:
            self.log(f"Downloading from {url}")
            urllib.request.urlretrieve(url, zip_path)
            self.log("✓ Download complete")
            
            # Extract
            self.log("Extracting model...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.app_dir)
            
            # Cleanup
            zip_path.unlink()
            self.log(f"✓ Model extracted to {self.app_dir / model_name}")
            return True
        except Exception as e:
            self.log(f"✗ Download failed: {e}")
            if zip_path.exists():
                zip_path.unlink()
            return False
    
    def pull_ollama_model(self, model_name="llama3.1:8b"):
        """Pull an Ollama model"""
        self.log(f"Pulling Ollama model: {model_name}")
        try:
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            for line in process.stdout:
                self.log(line.strip())
            
            process.wait()
            
            if process.returncode == 0:
                self.log(f"✓ Model {model_name} pulled successfully")
                return True
            else:
                self.log(f"✗ Failed to pull model")
                return False
        except Exception as e:
            self.log(f"✗ Error pulling model: {e}")
            return False
    
    def run_setup(self, auto_download=False):
        """Run the complete setup process"""
        self.log("="*60)
        self.log("Voice Agent Setup Wizard")
        self.log("="*60)
        
        # Check Ollama
        ollama_installed = self.check_ollama()
        
        if not ollama_installed:
            if auto_download:
                self.log("\nAttempting to download Ollama...")
                download_dir = self.app_dir / "downloads"
                download_dir.mkdir(exist_ok=True)
                installer = self.download_ollama(download_dir)
                if installer:
                    self.log(f"\nPlease run the installer at: {installer}")
                    self.log("After installation, restart this setup wizard.")
                    return False
            else:
                self.log("\nPlease install Ollama from: https://ollama.com/download")
                self.log("After installation, restart this setup wizard.")
                return False
        
        # Check Vosk models
        models_found, model_names = self.check_vosk_models()
        
        if not models_found:
            if auto_download:
                self.log("\nAttempting to download Vosk model...")
                if self.download_vosk_model("vosk-model-small-en-us-0.15"):
                    models_found = True
            else:
                self.log("\nPlease download a Vosk model from: https://alphacephei.com/vosk/models")
                self.log("Recommended: vosk-model-small-en-us-0.15")
                self.log("Extract it to the application directory.")
                return False
        
        # Pull Ollama model if Ollama is running
        if ollama_installed:
            self.log("\nChecking if Ollama model is available...")
            try:
                import requests
                response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    if "llama3.1:8b" in model_names or "llama3.1:8b" in " ".join(model_names):
                        self.log("✓ Ollama model llama3.1:8b already available")
                    else:
                        self.log("Model llama3.1:8b not found, pulling...")
                        self.pull_ollama_model("llama3.1:8b")
                else:
                    self.log("⚠ Could not check Ollama models (service may not be running)")
            except:
                self.log("⚠ Could not check Ollama models")
        
        self.log("\n" + "="*60)
        self.log("Setup Complete!")
        self.log("="*60)
        self.log("You can now run the Voice Agent application.")
        return True


def main():
    """Run setup wizard from command line"""
    wizard = SetupWizard()
    wizard.run_setup(auto_download=True)


if __name__ == "__main__":
    main()
