#!/usr/bin/env python3
"""
SillyTavern Campaign Manager - Setup Script
"""

import os
import sys
import subprocess
from pathlib import Path

def print_header(text):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")

def check_python_version():
    """Ensure Python 3.9+"""
    if sys.version_info < (3, 9):
        print("❌ Python 3.9 or higher is required!")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")

def install_requirements():
    """Install Python dependencies"""
    print("Installing Python dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r",
            "backend/requirements.txt"
        ])
        print("✓ Dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        sys.exit(1)

def create_config():
    """Create config.yaml from example if it doesn't exist"""
    if Path("config.yaml").exists():
        print("⚠ config.yaml already exists, skipping...")
        return False  # Not a fresh setup

    import shutil
    shutil.copy("config.example.yaml", "config.yaml")
    print("✓ Created config.yaml from template")
    return True  # Fresh setup — wizard needed

def initialize_database():
    """Initialize SQLite database"""
    print("Initializing database...")
    try:
        from backend.init_db import init_database
        init_database()
        print("✓ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1)

def create_directories():
    """Create required directories"""
    dirs = [
        "data",
        "data/backups",
        "data/logs"
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print("✓ Created data directories")

def check_ollama():
    """Check if Ollama is running"""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            print("✓ Ollama is running")
            return True
    except:
        pass
    
    print("⚠ Ollama doesn't seem to be running")
    print("   Install from: https://ollama.ai")
    print("   Then run: ollama serve")
    return False

def main():
    print_header("SillyTavern Campaign Manager - Setup")
    
    # Check Python version
    check_python_version()
    
    # Install dependencies
    install_requirements()
    
    # Create directories
    create_directories()
    
    # Create config
    is_fresh = create_config()
    
    # Initialize database
    initialize_database()
    
    # Check Ollama
    check_ollama()
    
    print_header("Setup Complete!")
    
    if is_fresh:
        print("The server will now start and open the Setup Wizard")
        print("in your browser to complete configuration.\n")
    else:
        print("Configuration already exists.")
        print("The server will now start.\n")

if __name__ == "__main__":
    main()
