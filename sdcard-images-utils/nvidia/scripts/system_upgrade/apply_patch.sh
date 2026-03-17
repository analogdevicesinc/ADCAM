#!/bin/bash
#===============================================================================
# NVIDIA Jetson Orin Nano ToF ADSD3500 System Upgrade Script
#
# Description: Applies kernel patches, device tree overlays, and system
#              configuration for ADI ToF camera integration on Jetson Orin Nano
#
# Usage: sudo ./apply_patch.sh
#
# Requirements: Root privileges, JetPack 6.2.1, archive extracted in current directory
#
# Exit Codes:
#   0 - Success
#   1 - General error
#   2 - File operation error
#   3 - Service operation error
#   4 - Configuration error
#
# Author: Analog Devices Inc.
# Version: 2.0
# Date: 2026-03-17
#===============================================================================

set -euo pipefail

#===============================================================================
# CONFIGURATION
#===============================================================================

readonly SCRIPT_VERSION="2.0"
readonly ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly EXTLINUX_CONF="/boot/extlinux/extlinux.conf"
readonly BACKUP_DIR="/root/adi_tof_backup_$(date +%Y%m%d_%H%M%S)"

# Boot configuration labels
readonly DEFAULT_LABEL="ADSD3500-DUAL+ADSD3100"
readonly KERNEL_VERSION="5.15.148-adi-tegra"

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_ERROR=1
readonly EXIT_FILE_ERROR=2
readonly EXIT_SERVICE_ERROR=3
readonly EXIT_CONFIG_ERROR=4

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Global variables
boot_device_type=""
boot_device_info=""

#===============================================================================
# LOGGING FUNCTIONS
#===============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_step() {
    echo ""
    echo -e "${GREEN}=== $* ===${NC}"
    echo ""
}

error_exit() {
    local message="$1"
    local exit_code="${2:-${EXIT_ERROR}}"
    log_error "${message}"
    log_error "System upgrade failed. Check logs and restore from backup if needed: ${BACKUP_DIR}"
    exit "${exit_code}"
}

#===============================================================================
# UTILITY FUNCTIONS
#===============================================================================

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error_exit "This script must be run as root (use sudo)" ${EXIT_ERROR}
    fi
}

validate_environment() {
    log_step "Validating environment"

    # Check for required files
    local required_files=(
        "Image"
        "kernel_supplements.tbz2"
        "sw-versions"
    )

    for file in "${required_files[@]}"; do
        if [[ ! -f "${ROOTDIR}/${file}" ]]; then
            error_exit "Required file not found: ${file}" ${EXIT_FILE_ERROR}
        fi
        log_info "Found: ${file}"
    done

    # Check for DTBOs
    local dtbo_count=$(find "${ROOTDIR}" -name "tegra234-p3767-camera-p3768-*.dtbo" | wc -l)
    if [[ ${dtbo_count} -eq 0 ]]; then
        error_exit "No device tree overlays found" ${EXIT_FILE_ERROR}
    fi
    log_info "Found ${dtbo_count} device tree overlay(s)"

    # Check for ubuntu_overlay if it exists
    if [[ -d "${ROOTDIR}/ubuntu_overlay" ]]; then
        log_info "Found: ubuntu_overlay directory"
    else
        log_warning "ubuntu_overlay directory not found - skipping overlay installation"
    fi

    # Check if extlinux.conf exists
    if [[ ! -f "${EXTLINUX_CONF}" ]]; then
        error_exit "Boot config file not found: ${EXTLINUX_CONF}" ${EXIT_CONFIG_ERROR}
    fi

    # Verify we're on Jetson Orin Nano
    if [[ ! -f /etc/nv_tegra_release ]]; then
        log_warning "Not running on NVIDIA Jetson platform - proceeding anyway"
    else
        log_info "Platform: $(cat /etc/nv_tegra_release | head -1)"
    fi

    log_success "Environment validation completed"
}

create_backup() {
    log_step "Creating backup"

    mkdir -p "${BACKUP_DIR}" || error_exit "Failed to create backup directory" ${EXIT_FILE_ERROR}
    log_info "Backup directory: ${BACKUP_DIR}"

    # Backup current kernel
    if [[ -f /boot/Image ]]; then
        cp /boot/Image "${BACKUP_DIR}/" || log_warning "Failed to backup /boot/Image"
        log_info "Backed up: /boot/Image"
    fi

    # Backup extlinux.conf
    if [[ -f "${EXTLINUX_CONF}" ]]; then
        cp "${EXTLINUX_CONF}" "${BACKUP_DIR}/extlinux.conf.bak" || log_warning "Failed to backup extlinux.conf"
        log_info "Backed up: extlinux.conf"
    fi

    # Backup existing ADI kernel if present
    if [[ -d /boot/adi ]]; then
        cp -r /boot/adi "${BACKUP_DIR}/" || log_warning "Failed to backup /boot/adi"
        log_info "Backed up: /boot/adi"
    fi

    log_success "Backup completed: ${BACKUP_DIR}"
}

get_boot_device_type() {
    log_step "Detecting boot device type"

    if [[ ! -f "${EXTLINUX_CONF}" ]]; then
        error_exit "Extlinux config not found: ${EXTLINUX_CONF}" ${EXIT_CONFIG_ERROR}
    fi

    # Check for PARTUUID (SSD/NVMe boot)
    if grep -q "PARTUUID" "${EXTLINUX_CONF}"; then
        boot_device_type="ssd"
        boot_device_info=$(grep -oP '(?<=PARTUUID=)[a-fA-F0-9-]{36}' "${EXTLINUX_CONF}" | head -n 1)
        log_info "Boot device: SSD/NVMe"
        log_info "PARTUUID: ${boot_device_info}"
        return 0
    # Check for microSD card boot
    elif grep -q "root=/dev/mmcblk0p1" "${EXTLINUX_CONF}"; then
        boot_device_type="sdcard"
        boot_device_info="/dev/mmcblk0p1"
        log_info "Boot device: microSD card"
        log_info "Root device: /dev/mmcblk0p1"
        return 0
    else
        boot_device_type="unknown"
        boot_device_info=""
        error_exit "Unable to determine boot device type from ${EXTLINUX_CONF}" ${EXIT_CONFIG_ERROR}
    fi
}

#===============================================================================
# INSTALLATION FUNCTIONS
#===============================================================================

apply_ubuntu_overlay() {
    log_step "Applying Ubuntu overlay"

    if [[ ! -d "${ROOTDIR}/ubuntu_overlay" ]]; then
        log_warning "ubuntu_overlay directory not found - skipping"
        return 0
    fi

    # Configure MTU size
    log_info "Configuring network MTU size to 15000..."
    if [[ -f "${ROOTDIR}/ubuntu_overlay/etc/NetworkManager/conf.d/10-ignore-interface.conf" ]]; then
        cp "${ROOTDIR}/ubuntu_overlay/etc/NetworkManager/conf.d/10-ignore-interface.conf" /etc/NetworkManager/conf.d/ || log_warning "Failed to copy NetworkManager config"
    fi

    if [[ -f "${ROOTDIR}/ubuntu_overlay/etc/systemd/network/10-rndis0.network" ]]; then
        cp "${ROOTDIR}/ubuntu_overlay/etc/systemd/network/10-rndis0.network" /etc/systemd/network/ || log_warning "Failed to copy systemd network config"
    fi

    # Update USB device mode configuration
    log_info "Updating USB device mode configuration..."
    local usb_config="/opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-config.sh"
    if [[ -f "${usb_config}" ]]; then
        sed -i 's/^net_dhcp_lease_time=15$/net_dhcp_lease_time=1500/' "${usb_config}" || log_warning "Failed to update DHCP lease time"
    fi

    local usb_start="/opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-start.sh"
    if [[ -f "${usb_start}" ]]; then
        if ! grep -Fxq 'sudo ip link set l4tbr0 mtu 15000' "${usb_start}"; then
            sed -i '255i sudo ip link set l4tbr0 mtu 15000' "${usb_start}" || log_warning "Failed to update MTU in USB start script"
        fi
    fi

    # Copy systemd service files
    if [[ -d "${ROOTDIR}/ubuntu_overlay/etc/systemd/system" ]]; then
        log_info "Installing systemd service files..."
        cp -v "${ROOTDIR}/ubuntu_overlay/etc/systemd/system/"*.service /etc/systemd/system/ 2>/dev/null || log_warning "No service files found"
    fi

    # Copy systemd scripts
    if [[ -d "${ROOTDIR}/ubuntu_overlay/usr/share/systemd" ]]; then
        log_info "Installing systemd scripts..."
        mkdir -p /usr/share/systemd
        cp -v "${ROOTDIR}/ubuntu_overlay/usr/share/systemd/"*.sh /usr/share/systemd/ 2>/dev/null || log_warning "No systemd scripts found"
        chmod +x /usr/share/systemd/*.sh 2>/dev/null || true
    fi

    # Copy udev rules
    if [[ -f "${ROOTDIR}/ubuntu_overlay/etc/udev/rules.d/99-gpio.rules" ]]; then
        log_info "Installing udev GPIO rules..."
        cp "${ROOTDIR}/ubuntu_overlay/etc/udev/rules.d/99-gpio.rules" /etc/udev/rules.d/ || log_warning "Failed to copy udev rules"
        udevadm control --reload-rules || log_warning "Failed to reload udev rules"
        udevadm trigger || log_warning "Failed to trigger udev"
    fi

    log_success "Ubuntu overlay applied"
}

update_kernel() {
    log_step "Updating kernel and modules"

    # Copy sw-versions
    log_info "Installing sw-versions..."
    cp "${ROOTDIR}/sw-versions" /boot/ || error_exit "Failed to copy sw-versions" ${EXIT_FILE_ERROR}

    # Backup original kernel if not already done
    if [[ ! -f /boot/Image.backup ]]; then
        log_info "Creating backup of original kernel..."
        cp /boot/Image /boot/Image.backup || error_exit "Failed to backup original kernel" ${EXIT_FILE_ERROR}
    else
        log_info "Original kernel backup already exists"
    fi

    # Create ADI boot directory
    log_info "Setting up ADI boot directory..."
    rm -rf /boot/adi
    mkdir -p /boot/adi || error_exit "Failed to create /boot/adi" ${EXIT_FILE_ERROR}
    mkdir -p /lib/firmware/adi || true

    # Copy kernel image
    log_info "Installing ADI kernel image..."
    cp "${ROOTDIR}/Image" /boot/adi/Image || error_exit "Failed to copy kernel Image" ${EXIT_FILE_ERROR}
    local image_size=$(stat -c%s /boot/adi/Image 2>/dev/null || echo "0")
    log_info "Kernel Image size: $((image_size / 1024 / 1024)) MB"

    # Copy device tree overlays
    log_info "Installing device tree overlays..."
    local dtbo_count=0
    for dtbo in "${ROOTDIR}"/tegra234-p3767-camera-p3768-*.dtbo; do
        if [[ -f "${dtbo}" ]]; then
            cp "${dtbo}" /boot/adi/ || error_exit "Failed to copy $(basename "${dtbo}")" ${EXIT_FILE_ERROR}
            log_info "Installed: $(basename "${dtbo}")"
            dtbo_count=$((dtbo_count + 1))
        fi
    done
    log_info "Installed ${dtbo_count} device tree overlay(s)"

    # Extract and install kernel modules
    log_info "Installing kernel modules..."
    local temp_dir="${ROOTDIR}/temp_modules"
    mkdir -p "${temp_dir}"

    tar -xjf "${ROOTDIR}/kernel_supplements.tbz2" -C "${temp_dir}" || error_exit "Failed to extract modules" ${EXIT_FILE_ERROR}

    if [[ -d "${temp_dir}/lib/modules/${KERNEL_VERSION}" ]]; then
        log_info "Installing modules for ${KERNEL_VERSION}..."
        cp -rf "${temp_dir}/lib/modules/${KERNEL_VERSION}" /lib/modules/ || error_exit "Failed to copy modules" ${EXIT_FILE_ERROR}

        # Run depmod to update module dependencies
        log_info "Updating module dependencies..."
        depmod -a "${KERNEL_VERSION}" || log_warning "depmod failed for ${KERNEL_VERSION}"
    else
        log_warning "Kernel modules directory not found for ${KERNEL_VERSION}"
        # Try to find any 5.15.148* directory
        local module_dir=$(find "${temp_dir}/lib/modules" -type d -name "5.15.148*" | head -1)
        if [[ -n "${module_dir}" ]]; then
            local kernel_ver=$(basename "${module_dir}")
            log_info "Found modules for ${kernel_ver}, installing..."
            cp -rf "${module_dir}" /lib/modules/ || error_exit "Failed to copy modules" ${EXIT_FILE_ERROR}
            depmod -a "${kernel_ver}" || log_warning "depmod failed for ${kernel_ver}"
        fi
    fi

    # Cleanup temporary directory
    rm -rf "${temp_dir}" || log_warning "Failed to remove temporary directory"

    log_success "Kernel and modules updated"
}

update_extlinux_config() {
    log_step "Updating boot configuration"

    log_info "Backing up extlinux.conf..."
    cp "${EXTLINUX_CONF}" "${EXTLINUX_CONF}.pre_adi_$(date +%Y%m%d_%H%M%S)" || log_warning "Failed to create extlinux backup"

    # Determine DTB file
    local dtb_file=$(basename "$(ls /boot/dtb/*.dtb 2>/dev/null | head -n 1)")
    if [[ -z "${dtb_file}" ]]; then
        error_exit "No DTB file found in /boot/dtb" ${EXIT_CONFIG_ERROR}
    fi
    log_info "Using DTB: ${dtb_file}"

    # Determine root device
    local root_device
    if [[ "${boot_device_type}" == "ssd" ]]; then
        root_device="root=PARTUUID=${boot_device_info}"
    else
        root_device="root=/dev/mmcblk0p1"
    fi
    log_info "Root device: ${root_device}"

    # Truncate extlinux.conf after line 30 and set default to primary
    log_info "Cleaning extlinux.conf..."
    sed -i '30,$d' "${EXTLINUX_CONF}" || error_exit "Failed to truncate extlinux.conf" ${EXIT_CONFIG_ERROR}
    sed -i "s/^DEFAULT .*/DEFAULT primary/" "${EXTLINUX_CONF}" || error_exit "Failed to set default label" ${EXIT_CONFIG_ERROR}

    # Add boot labels
    log_info "Adding boot menu entries..."

    cat >> "${EXTLINUX_CONF}" <<EOF

LABEL backup
      MENU LABEL backup kernel
      LINUX /boot/Image.backup
      FDT /boot/dtb/${dtb_file}
      INITRD /boot/initrd
      APPEND \${cbootargs} ${root_device} rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0

LABEL ADSD3500+ADSD3100
      MENU LABEL ADSD3500: <CSI ToF Camera ADSD3100>
      LINUX /boot/adi/Image
      FDT /boot/dtb/${dtb_file}
      OVERLAYS /boot/adi/tegra234-p3767-camera-p3768-adsd3500.dtbo
      INITRD /boot/initrd
      APPEND \${cbootargs} ${root_device} rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0

LABEL ADSD3500-DUAL+ADSD3100
      MENU LABEL ADSD3500-DUAL: <CSI ToF Camera ADSD3100>
      LINUX /boot/adi/Image
      FDT /boot/dtb/${dtb_file}
      OVERLAYS /boot/adi/tegra234-p3767-camera-p3768-dual-adsd3500-adsd3100.dtbo
      INITRD /boot/initrd
      APPEND \${cbootargs} ${root_device} rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0

LABEL ADSD3500-DUAL+ADSD3100+AR0234
      MENU LABEL ADSD3500-DUAL+AR0234: <CSI ToF+RGB Camera>
      LINUX /boot/adi/Image
      FDT /boot/dtb/${dtb_file}
      OVERLAYS /boot/adi/tegra234-p3767-camera-p3768-dual-adsd3500-adsd3100-arducam-ar0234.dtbo
      INITRD /boot/initrd
      APPEND \${cbootargs} ${root_device} rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0

EOF

    # Set default boot label
    log_info "Setting default boot label to ${DEFAULT_LABEL}..."
    sed -i "s/^DEFAULT .*/DEFAULT ${DEFAULT_LABEL}/" "${EXTLINUX_CONF}" || error_exit "Failed to set default boot label" ${EXIT_CONFIG_ERROR}

    log_success "Boot configuration updated"
}

configure_services() {
    log_step "Configuring services"

    # Reload systemd daemon
    log_info "Reloading systemd daemon..."
    systemctl daemon-reload || error_exit "Failed to reload systemd daemon" ${EXIT_SERVICE_ERROR}

    # Network services
    log_info "Configuring network services..."
    systemctl reload NetworkManager || log_warning "Failed to reload NetworkManager"
    systemctl enable systemd-networkd || log_warning "Failed to enable systemd-networkd"
    systemctl start systemd-networkd || log_warning "Failed to start systemd-networkd"

    # ADI ToF service
    if [[ -f /etc/systemd/system/adi-tof.service ]]; then
        log_info "Enabling adi-tof service..."
        systemctl enable adi-tof || error_exit "Failed to enable adi-tof service" ${EXIT_SERVICE_ERROR}
        log_success "adi-tof service will start after reboot"
    else
        log_warning "adi-tof.service not found - skipping"
    fi

    # Jetson performance service
    if systemctl list-unit-files | grep -q jetson-performance; then
        log_info "Enabling jetson-performance service..."
        systemctl enable jetson-performance || log_warning "Failed to enable jetson-performance"
        systemctl start jetson-performance || log_warning "Failed to start jetson-performance"
    fi

    log_success "Services configured"
}

display_summary() {
    log_step "Installation Summary"

    echo "Installed components:"
    echo "  - Kernel: /boot/adi/Image (${KERNEL_VERSION})"
    echo "  - Original kernel backup: /boot/Image.backup"
    echo "  - Kernel modules: /lib/modules/${KERNEL_VERSION}"

    local dtbo_count=$(ls -1 /boot/adi/*.dtbo 2>/dev/null | wc -l)
    echo "  - Device tree overlays: ${dtbo_count} file(s) in /boot/adi/"

    echo ""
    echo "Boot configuration:"
    echo "  - Config file: ${EXTLINUX_CONF}"
    echo "  - Default boot: ${DEFAULT_LABEL}"
    echo "  - Available labels: backup, ADSD3500+ADSD3100, ADSD3500-DUAL+ADSD3100, ADSD3500-DUAL+ADSD3100+AR0234"

    echo ""
    echo "Services configured:"
    echo "  - adi-tof (enabled, starts after reboot)"
    echo "  - systemd-networkd (enabled)"
    echo "  - jetson-performance (enabled)"

    echo ""
    echo "Backup location: ${BACKUP_DIR}"
    echo ""
    log_warning "System will reboot in 10 seconds..."
    log_warning "Press Ctrl+C to cancel reboot"
}

#===============================================================================
# MAIN EXECUTION
#===============================================================================

main() {
    log_step "ADI ToF ADSD3500 System Upgrade for NVIDIA Jetson Orin Nano"
    log_info "Script version: ${SCRIPT_VERSION}"
    log_info "Target kernel: ${KERNEL_VERSION}"

    # Pre-flight checks
    check_root
    validate_environment
    create_backup
    get_boot_device_type

    # Installation steps
    apply_ubuntu_overlay
    update_kernel
    update_extlinux_config
    configure_services

    # Summary and reboot
    display_summary

    sleep 10

    log_step "Rebooting system"
    reboot
}

# Execute main function
main

