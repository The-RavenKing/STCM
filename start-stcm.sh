#!/bin/bash
# SillyTavern Campaign Manager - Linux Startup Script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "========================================"
echo "  SillyTavern Campaign Manager"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo "Install with: sudo apt install python3 python3-pip"
    exit 1
fi

echo "Python found: $(python3 --version)"
echo ""

# Check if config exists — run setup if not
if [ ! -f "config.yaml" ]; then
    echo "First-time setup detected..."
    echo ""
    python3 setup.py
    echo ""
fi

echo "Starting STCM..."
echo ""
echo "Dashboard: http://localhost:7847"
echo "Press Ctrl+C to stop"
echo ""

cd backend
exec python3 main.py
