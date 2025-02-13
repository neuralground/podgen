#!/usr/bin/env python3
"""Install dependencies for selected model providers."""

import argparse
import subprocess
import sys
import os
from enum import Enum
import platform

class Provider(str, Enum):
    OLLAMA = "ollama"
    COQUI = "coqui"
    BARK = "bark"
    ALL = "all"

def install_ollama():
    """Install Ollama and basic models."""
    system = platform.system().lower()
    
    if system == "darwin":
        print("Installing Ollama via Homebrew...")
        subprocess.run(["brew", "install", "ollama"], check=True)
    elif system == "linux":
        print("Installing Ollama...")
        subprocess.run([
            "curl", "-fsSL", 
            "https://ollama.ai/install.sh", 
            "|", "sh"
        ], check=True)
    else:
        print("Please install Ollama manually from: https://ollama.ai")
        return
    
    print("Pulling basic models...")
    subprocess.run(["ollama", "pull", "mistral:latest"], check=True)
    subprocess.run(["ollama", "pull", "llama2:7b"], check=True)

def install_coqui():
    """Install Coqui TTS."""
    print("Installing Coqui TTS dependencies...")
    
    # Install base dependencies first
    subprocess.run([
        sys.executable, "-m", "pip", "install",
        "numpy",
        "scipy",
        "librosa",
        "unidecode",
        "phonemizer",
        "torch",
        "torchaudio"
    ], check=True)
    
    print("Installing Coqui TTS from GitHub...")
    subprocess.run([
        sys.executable, "-m", "pip", "install",
        "git+https://github.com/coqui-ai/TTS.git@main"
    ], check=True)
    
    print("Verifying installation...")
    try:
        subprocess.run([
            sys.executable, "-c",
            "import TTS; print(f'Successfully installed TTS version {TTS.__version__}')"
        ], check=True)
        
        print("Downloading default model...")
        # Import and download default model
        subprocess.run([
            sys.executable, "-c",
            "from TTS.utils.manage import ModelManager; "
            "ModelManager().download_model('tts_models/en/vctk/vits')"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error verifying installation: {e}")
        raise

def install_bark():
    """Install Bark TTS."""
    print("Installing Bark...")
    subprocess.run([
        sys.executable, "-m", "pip", "install",
        "git+https://github.com/suno-ai/bark.git",
        "torch", "torchaudio"
    ], check=True)

def main():
    parser = argparse.ArgumentParser(description="Install model dependencies")
    parser.add_argument(
        "provider",
        type=Provider,
        choices=list(Provider),
        help="Which provider to install"
    )
    
    args = parser.parse_args()
    
    try:
        if args.provider in [Provider.OLLAMA, Provider.ALL]:
            install_ollama()
        
        if args.provider in [Provider.COQUI, Provider.ALL]:
            install_coqui()
            
        if args.provider in [Provider.BARK, Provider.ALL]:
            install_bark()
            
        print("\nInstallation complete!")
        
    except subprocess.CalledProcessError as e:
        print(f"Error during installation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

