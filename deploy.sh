#!/bin/bash

# WebMusic deployment script
# Sets up systemd service running as current user from source directory

set -euo pipefail

USER=$(whoami)
CURRENT_DIR=$(pwd)
SERVICE_NAME="webmusic"
PYTHON_VENV="$CURRENT_DIR/venv"

echo "=== WebMusic Deployment Script ==="
echo "User: $USER"
echo "Directory: $CURRENT_DIR"
echo "Service: $SERVICE_NAME"
echo ""

# Check if we're in the right directory
if [[ ! -f "app.py" ]]; then
    echo "ERROR: app.py not found. Run this script from the webmusic source directory."
    exit 1
fi

# Set up Python virtual environment if it doesn't exist
if [[ ! -d "$PYTHON_VENV" ]]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$PYTHON_VENV"
fi

echo "Installing/updating Python dependencies..."
"$PYTHON_VENV/bin/pip" install -q --upgrade pip
"$PYTHON_VENV/bin/pip" install -q -r requirements.txt

# Get music library path from user
echo ""
read -p "Enter path to your music library [~/Music]: " MUSIC_PATH
MUSIC_PATH=${MUSIC_PATH:-~/Music}
MUSIC_PATH=$(realpath "$MUSIC_PATH")

if [[ ! -d "$MUSIC_PATH" ]]; then
    echo "WARNING: Music directory $MUSIC_PATH does not exist"
    read -p "Continue anyway? [y/N]: " continue_choice
    if [[ ! "$continue_choice" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get port
echo ""
read -p "Enter port to run on [8080]: " PORT
PORT=${PORT:-8080}

# Get base path for reverse proxy (optional)
echo ""
read -p "Enter base path for reverse proxy (optional, e.g., /webmusic): " BASE_PATH

# Build ExecStart command
EXEC_START="$PYTHON_VENV/bin/python app.py --library \"$MUSIC_PATH\" --port $PORT --host 0.0.0.0 --scan-interval 300"
if [[ -n "$BASE_PATH" ]]; then
    EXEC_START="$EXEC_START --base-path \"$BASE_PATH\""
fi

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

echo ""
echo "Creating systemd service file: $SERVICE_FILE"

sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=WebMusic Server
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$EXEC_START
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
echo "Reloading systemd and enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# Test the configuration
echo ""
echo "Testing configuration..."
if "$PYTHON_VENV/bin/python" app.py --help > /dev/null 2>&1; then
    echo "✓ Python application runs successfully"
else
    echo "✗ Error running Python application"
    exit 1
fi

# Start the service
echo ""
read -p "Start the service now? [Y/n]: " start_choice
if [[ ! "$start_choice" =~ ^[Nn]$ ]]; then
    sudo systemctl start "$SERVICE_NAME"
    
    # Wait a moment for startup
    sleep 2
    
    # Check status
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "✓ Service started successfully"
        echo ""
        echo "WebMusic is now running at: http://localhost:$PORT$BASE_PATH"
        echo ""
        echo "Useful commands:"
        echo "  View status: sudo systemctl status $SERVICE_NAME"
        echo "  View logs:   sudo journalctl -u $SERVICE_NAME -f"
        echo "  Restart:     sudo systemctl restart $SERVICE_NAME"
        echo "  Stop:        sudo systemctl stop $SERVICE_NAME"
        echo ""
        echo "To deploy updates:"
        echo "  1. Update source code"
        echo "  2. Run: sudo systemctl restart $SERVICE_NAME"
    else
        echo "✗ Service failed to start"
        echo "Check logs with: sudo journalctl -u $SERVICE_NAME -f"
        exit 1
    fi
else
    echo ""
    echo "Service created but not started."
    echo "Start manually with: sudo systemctl start $SERVICE_NAME"
fi

echo ""
echo "Deployment complete!"
