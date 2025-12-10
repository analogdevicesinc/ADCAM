#!/bin/bash
# Uninstallation script for ADI Network Discovery Server service

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

echo -e "${YELLOW}Uninstalling ADI Network Discovery Server service...${NC}"

# Define paths
BINARY_DEST="/usr/local/bin/discovery_server"
CONFIG_DEST="/etc/adi/discovery-server-config.json"
SERVICE_DEST="/etc/systemd/system/discovery-server.service"

# Stop service if running
if systemctl is-active --quiet discovery-server; then
    echo "Stopping discovery-server service..."
    systemctl stop discovery-server
fi

# Disable service if enabled
if systemctl is-enabled --quiet discovery-server 2>/dev/null; then
    echo "Disabling discovery-server service..."
    systemctl disable discovery-server
fi

# Remove service file
if [ -f "$SERVICE_DEST" ]; then
    echo "Removing service file: $SERVICE_DEST"
    rm -f "$SERVICE_DEST"
fi

# Remove binary
if [ -f "$BINARY_DEST" ]; then
    echo "Removing binary: $BINARY_DEST"
    rm -f "$BINARY_DEST"
fi

# Ask about config file
if [ -f "$CONFIG_DEST" ]; then
    read -p "Remove config file $CONFIG_DEST? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing config file: $CONFIG_DEST"
        rm -f "$CONFIG_DEST"
    else
        echo "Keeping config file: $CONFIG_DEST"
    fi
fi

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

echo -e "${GREEN}Uninstallation complete!${NC}"
