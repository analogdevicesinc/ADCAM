#!/bin/bash
# Installation script for ADI Network Discovery Server service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${GREEN}Installing ADI Network Discovery Server service...${NC}"

# Define paths
BINARY_SRC="./discovery_server"
BINARY_DEST="/usr/local/bin/discovery_server"
CONFIG_SRC="./config.json"
CONFIG_DIR="/etc/adi"
CONFIG_DEST="${CONFIG_DIR}/discovery-server-config.json"
SERVICE_SRC="./discovery-server.service"
SERVICE_DEST="/etc/systemd/system/discovery-server.service"

# Check if binary exists
if [ ! -f "$BINARY_SRC" ]; then
    echo -e "${RED}Error: Binary '$BINARY_SRC' not found${NC}"
    echo "Please build the project first and run this script from the build/apps/discovery_server directory"
    exit 1
fi

# Create config directory if it doesn't exist
if [ ! -d "$CONFIG_DIR" ]; then
    echo "Creating config directory: $CONFIG_DIR"
    mkdir -p "$CONFIG_DIR"
fi

# Copy binary
echo "Installing binary to $BINARY_DEST"
cp "$BINARY_SRC" "$BINARY_DEST"
chmod +x "$BINARY_DEST"

# Copy config file (only if it doesn't exist to preserve user settings)
if [ ! -f "$CONFIG_DEST" ]; then
    echo "Installing config file to $CONFIG_DEST"
    cp "$CONFIG_SRC" "$CONFIG_DEST"
    echo -e "${YELLOW}Note: Edit $CONFIG_DEST to customize your settings${NC}"
else
    echo -e "${YELLOW}Config file already exists at $CONFIG_DEST (not overwriting)${NC}"
fi

# Copy service file
echo "Installing systemd service to $SERVICE_DEST"
cp "$SERVICE_SRC" "$SERVICE_DEST"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable service
echo "Enabling discovery-server service..."
systemctl enable discovery-server.service

echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Usage:"
echo "  Start service:   sudo systemctl start discovery-server"
echo "  Stop service:    sudo systemctl stop discovery-server"
echo "  Restart service: sudo systemctl restart discovery-server"
echo "  Check status:    sudo systemctl status discovery-server"
echo "  View logs:       sudo journalctl -u discovery-server -f"
echo ""
echo "Configuration file: $CONFIG_DEST"
echo ""
echo -e "${YELLOW}Note: Edit the configuration file and restart the service to apply changes${NC}"
