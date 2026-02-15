#!/bin/bash
# SillyTavern Campaign Manager - Linux Service Installer
# Run this once to install STCM as a systemd service.

set -e

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="stcm"
CURRENT_USER="$(whoami)"
PORT=7847

echo ""
echo "========================================"
echo "  STCM - Service Installer"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo "Install with: sudo apt install python3 python3-pip"
    exit 1
fi
echo "✓ Python found: $(python3 --version)"

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r "$INSTALL_DIR/backend/requirements.txt" --quiet
echo "✓ Dependencies installed"

# Create data directories
mkdir -p "$INSTALL_DIR/data/backups" "$INSTALL_DIR/data/logs"
echo "✓ Data directories created"

# Create config if missing
if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
    cp "$INSTALL_DIR/config.example.yaml" "$INSTALL_DIR/config.yaml"
    echo "✓ Created config.yaml from template"
fi

# Read port from config if it differs
CONFIG_PORT=$(python3 -c "
import yaml
with open('$INSTALL_DIR/config.yaml') as f:
    c = yaml.safe_load(f)
    print(c.get('server', {}).get('port', $PORT))
" 2>/dev/null || echo "$PORT")
PORT=$CONFIG_PORT

# Generate and install systemd service
echo ""
echo "Installing systemd service..."

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=SillyTavern Campaign Manager
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}/backend
ExecStart=$(which python3) main.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

echo "✓ Service installed and started"

# Get the machine's IP for remote access
IP_ADDR=$(hostname -I | awk '{print $1}')

echo ""
echo "========================================"
echo "  ✓ STCM is now running!"
echo "========================================"
echo ""
echo "  Access from this machine:"
echo "    http://localhost:${PORT}"
echo ""
echo "  Access from other devices:"
echo "    http://${IP_ADDR}:${PORT}"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status ${SERVICE_NAME}   # Check status"
echo "    sudo systemctl stop ${SERVICE_NAME}     # Stop"
echo "    sudo systemctl restart ${SERVICE_NAME}  # Restart"
echo "    journalctl -u ${SERVICE_NAME} -f        # View live logs"
echo ""
echo "  If this is your first time, open the URL above"
echo "  in a browser to complete the Setup Wizard."
echo ""
