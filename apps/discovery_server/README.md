# ADI Network Discovery Server

The Network Discovery Server enables clients to discover and configure ADI Time-of-Flight devices on the network.

## Overview

This directory contains the discovery server application and all necessary files to run it as a systemd service:

- **`discovery_server`** - Main server binary (built from `main.cpp`)
- **`discovery-server.service`** - Systemd service file for automatic startup
- **`config.json`** - Configuration template with serial number, interface, and network settings
- **`install-service.sh`** - Installation script to set up the systemd service
- **`uninstall-service.sh`** - Uninstallation script to remove the service
- **`README.md`** - This documentation file

All files (except the binary) are automatically copied to `build/apps/discovery_server/` during the build process.

## Features

- Network device discovery via UDP broadcast
- Query device information (serial number, IP address, network interface)
- Configure network settings (DHCP, Static IP, DHCP Server mode)
- Systemd service integration for automatic startup

## Building

The discovery server is built as part of the main ADCAM project:

```bash
cd /path/to/ADCAM
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DNVIDIA=ON ..
cmake --build . -j$(nproc)
```

The binary will be located at: `build/apps/discovery_server/discovery_server`

## Running Manually

```bash
# Run with default settings (auto-detect interface, default port 5000)
./discovery_server

# Run with custom port
./discovery_server -p 5001

# Run with config file
./discovery_server -c config.json

# Run with specific network interface
./discovery_server -i eth0

# Show help
./discovery_server --help
```

### Command-line Options

- `-p, --port PORT` - Port to listen on (default: 5000)
- `-c, --config FILE` - JSON config file with serial_number and network settings
- `-i, --interface IFACE` - Network interface to use (default: auto-detect)
- `-h, --help` - Show help message

## Configuration File

The server can read configuration from a JSON file. See `config.json` for an example:

```json
{
  "serial_number": "DISCOVERY0123456789",
  "interface": "eth0",
  "network_mode": "dhcp",
  "static_ip": {
    "ip_address": "192.168.1.100",
    "netmask": "255.255.255.0",
    "gateway": "192.168.1.1"
  },
  "dhcp_server": {
    "range_start": "192.168.1.100",
    "range_end": "192.168.1.200"
  }
}
```

### Network Modes

- **`dhcp`** - Use DHCP client to obtain IP address (default)
- **`static`** - Use static IP address configuration
- **`dhcp_server`** - Act as DHCP server (requires dnsmasq)

## Installing as a System Service

### Installation

1. Build the project
2. Navigate to the build directory:
   ```bash
   cd build/apps/discovery_server
   ```
3. Install the service (requires root):
   ```bash
   sudo ./install-service.sh
   ```

The installation script will:
- Copy the binary to `/usr/local/bin/discovery_server`
- Create config directory `/etc/adi/`
- Copy config file to `/etc/adi/discovery-server-config.json`
- Install systemd service file
- Enable the service for automatic startup

### Service Management

```bash
# Start the service
sudo systemctl start discovery-server

# Stop the service
sudo systemctl stop discovery-server

# Restart the service
sudo systemctl restart discovery-server

# Check service status
sudo systemctl status discovery-server

# View logs (follow mode)
sudo journalctl -u discovery-server -f

# View recent logs
sudo journalctl -u discovery-server -n 50

# Enable service at boot (already done by install script)
sudo systemctl enable discovery-server

# Disable service at boot
sudo systemctl disable discovery-server
```

### Configuration

After installation, edit the configuration file:

```bash
sudo nano /etc/adi/discovery-server-config.json
```

Then restart the service to apply changes:

```bash
sudo systemctl restart discovery-server
```

### Uninstallation

```bash
cd build/apps/discovery_server
sudo ./uninstall-service.sh
```

## Network Requirements

- **Root privileges**: Required for applying network configuration changes
- **UDP Port**: Default 5000 (configurable via `-p` option)
- **Network Interface**: Must be active and configured

## Troubleshooting

### Service won't start

Check the service status and logs:
```bash
sudo systemctl status discovery-server
sudo journalctl -u discovery-server -n 50
```

### Permission issues

The service runs as root to allow network configuration changes. Ensure the binary has correct permissions:
```bash
ls -l /usr/local/bin/discovery_server
```

### Network configuration not applying

- Verify you're running with root privileges
- Check that the network interface exists: `ip link show`
- For DHCP server mode, ensure `dnsmasq` is installed
- Review logs for error messages

### Port already in use

If port 5000 is already in use, either:
1. Edit `/etc/adi/discovery-server-config.json` to use a different port
2. Or edit `/etc/systemd/system/discovery-server.service` to add `-p PORT` to ExecStart
3. Reload and restart: `sudo systemctl daemon-reload && sudo systemctl restart discovery-server`

## Architecture

The discovery server:
- Listens for UDP broadcast packets on the configured port
- Responds to discovery requests with device information
- Handles network configuration requests (requires root)
- Supports Linux (systemd) and Windows platforms

For more details, see the main ADCAM documentation.
