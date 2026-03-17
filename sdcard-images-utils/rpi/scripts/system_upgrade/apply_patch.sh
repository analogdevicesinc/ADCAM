#!/bin/bash
#===============================================================================
# Raspberry Pi ToF ADSD3500 System Upgrade Script
#
# Description: Applies kernel patches, device tree overlays, and system
#              configuration for ADI ToF camera integration on Raspberry Pi 5
#
# Usage: sudo ./apply_patch.sh
#
# Requirements: Root privileges, archive extracted in current directory
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
# Date: 2026-03-12
#===============================================================================

set -euo pipefail

#===============================================================================
# CONFIGURATION
#===============================================================================

readonly SCRIPT_VERSION="2.0"
readonly ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly CONFIG_FILE="/boot/firmware/config.txt"
readonly OVERLAY_ENTRY="dtoverlay=adsd3500-adsd3100"
readonly KERNEL_ENTRY="kernel=kernel_adi.img"
readonly BACKUP_DIR="/root/adi_tof_backup_$(date +%Y%m%d_%H%M%S)"

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
        "Image.gz"
        "adsd3500-adsd3100.dtbo"
        "modules.tar.gz"
        "sw-versions"
    )

    for file in "${required_files[@]}"; do
        if [[ ! -f "${ROOTDIR}/${file}" ]]; then
            error_exit "Required file not found: ${file}" ${EXIT_FILE_ERROR}
        fi
        log_info "Found: ${file}"
    done

    # Check for ubuntu_overlay if it exists
    if [[ -d "${ROOTDIR}/ubuntu_overlay" ]]; then
        log_info "Found: ubuntu_overlay directory"
    else
        log_warning "ubuntu_overlay directory not found - skipping overlay installation"
    fi

    # Check if config file exists
    if [[ ! -f "${CONFIG_FILE}" ]]; then
        error_exit "Boot config file not found: ${CONFIG_FILE}" ${EXIT_CONFIG_ERROR}
    fi

    log_success "Environment validation completed"
}

create_backup() {
    log_step "Creating backup"

    mkdir -p "${BACKUP_DIR}" || error_exit "Failed to create backup directory" ${EXIT_FILE_ERROR}
    log_info "Backup directory: ${BACKUP_DIR}"

    # Backup current kernel and dtb
    if [[ -f /boot/firmware/kernel_adi.img ]]; then
        cp /boot/firmware/kernel_adi.img "${BACKUP_DIR}/" || log_warning "Failed to backup kernel_adi.img"
        log_info "Backed up: kernel_adi.img"
    fi

    if [[ -f /boot/firmware/bcm2712-rpi-5-b.dtb ]]; then
        cp /boot/firmware/bcm2712-rpi-5-b.dtb "${BACKUP_DIR}/" || log_warning "Failed to backup bcm2712-rpi-5-b.dtb"
        log_info "Backed up: bcm2712-rpi-5-b.dtb"
    fi

    # Backup config.txt
    if [[ -f "${CONFIG_FILE}" ]]; then
        cp "${CONFIG_FILE}" "${BACKUP_DIR}/config.txt.bak" || log_warning "Failed to backup config.txt"
        log_info "Backed up: config.txt"
    fi

    log_success "Backup completed: ${BACKUP_DIR}"
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

    # Copy Tools directory
    if [[ -d "${ROOTDIR}/ubuntu_overlay/Tools" ]]; then
        log_info "Installing Tools directory..."
        mkdir -p /opt/adi
        cp -r "${ROOTDIR}/ubuntu_overlay/Tools" /opt/adi/ || log_warning "Failed to copy Tools directory"
        find /opt/adi/Tools -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
    fi

    log_success "Ubuntu overlay applied"
}

update_kernel() {
    log_step "Updating kernel and modules"

    # Copy sw-versions
    log_info "Installing sw-versions..."
    cp "${ROOTDIR}/sw-versions" /boot/ || error_exit "Failed to copy sw-versions" ${EXIT_FILE_ERROR}

    # Copy device tree blob
    log_info "Installing device tree blob..."
    chmod 755 "${ROOTDIR}/bcm2712-rpi-5-b.dtb" || log_warning "Failed to set permissions on dtb"
    cp "${ROOTDIR}/bcm2712-rpi-5-b.dtb" /boot/firmware/ || error_exit "Failed to copy device tree blob" ${EXIT_FILE_ERROR}

    # Copy device tree overlay
    log_info "Installing device tree overlay..."
    mkdir -p /boot/firmware/overlays
    cp "${ROOTDIR}/adsd3500-adsd3100.dtbo" /boot/firmware/overlays/ || error_exit "Failed to copy device tree overlay" ${EXIT_FILE_ERROR}

    # Copy kernel image
    log_info "Installing kernel image..."
    cp "${ROOTDIR}/Image.gz" /boot/firmware/kernel_adi.img || error_exit "Failed to copy kernel image" ${EXIT_FILE_ERROR}

    # Extract and install kernel modules
    log_info "Installing kernel modules..."
    local temp_dir="${ROOTDIR}/temp_modules"
    mkdir -p "${temp_dir}"

    tar -xzf "${ROOTDIR}/modules.tar.gz" -C "${temp_dir}" > /dev/null 2>&1 || error_exit "Failed to extract modules" ${EXIT_FILE_ERROR}

    # Find and copy module directory
    local module_dir=$(find "${temp_dir}" -type d -name "6.12.47*" | head -1)
    if [[ -n "${module_dir}" ]]; then
        log_info "Installing modules from: $(basename "${module_dir}")"
        cp -rf "${module_dir}" /lib/modules/ || error_exit "Failed to copy modules" ${EXIT_FILE_ERROR}

        # Run depmod to update module dependencies
        local kernel_version=$(basename "${module_dir}")
        log_info "Updating module dependencies for ${kernel_version}..."
        depmod -a "${kernel_version}" || log_warning "depmod failed for ${kernel_version}"
    else
        error_exit "No kernel modules found in archive" ${EXIT_FILE_ERROR}
    fi

    # Cleanup temporary directory
    rm -rf "${temp_dir}" || log_warning "Failed to remove temporary directory"

    log_success "Kernel and modules updated"
}

configure_services() {
    log_step "Configuring services"

    # Check if adi-tof service exists
    if [[ ! -f /etc/systemd/system/adi-tof.service ]]; then
        log_warning "adi-tof.service not found - skipping service configuration"
        return 0
    fi

    log_info "Reloading systemd daemon..."
    systemctl daemon-reload || error_exit "Failed to reload systemd daemon" ${EXIT_SERVICE_ERROR}

    log_info "Enabling adi-tof service..."
    systemctl enable adi-tof || error_exit "Failed to enable adi-tof service" ${EXIT_SERVICE_ERROR}

    log_success "Services configured (will start after reboot)"
}

update_config_file() {
    log_step "Updating boot configuration"

    log_info "Backing up current config.txt..."
    cp "${CONFIG_FILE}" "${CONFIG_FILE}.pre_adi_$(date +%Y%m%d_%H%M%S)" || log_warning "Failed to create config backup"

    log_info "Checking for existing ADI entries..."

    # Remove existing ADI entries if present
    if grep -q "^${OVERLAY_ENTRY}" "${CONFIG_FILE}"; then
        log_info "Removing existing overlay entry..."
        sed -i "/^${OVERLAY_ENTRY}/d" "${CONFIG_FILE}"
    fi

    if grep -q "^${KERNEL_ENTRY}" "${CONFIG_FILE}"; then
        log_info "Removing existing kernel entry..."
        sed -i "/^${KERNEL_ENTRY}/d" "${CONFIG_FILE}"
    fi

    log_info "Adding ADI configuration entries..."

    # Ensure [all] section exists
    if ! grep -q "^\[all\]" "${CONFIG_FILE}"; then
        echo "" >> "${CONFIG_FILE}"
        echo "[all]" >> "${CONFIG_FILE}"
    fi

    # Append new entries after [all] section
    sed -i "/^\[all\]/a ${OVERLAY_ENTRY}" "${CONFIG_FILE}"
    sed -i "/^\[all\]/a ${KERNEL_ENTRY}" "${CONFIG_FILE}"

    log_info "Verifying configuration..."
    if grep -q "^${OVERLAY_ENTRY}" "${CONFIG_FILE}" && grep -q "^${KERNEL_ENTRY}" "${CONFIG_FILE}"; then
        log_success "Boot configuration updated successfully"
    else
        error_exit "Failed to verify configuration entries" ${EXIT_CONFIG_ERROR}
    fi
}

display_summary() {
    log_step "Installation Summary"

    echo "Installed components:"
    echo "  - Kernel: kernel_adi.img (6.12.47-adi+)"
    echo "  - Device Tree: bcm2712-rpi-5-b.dtb"
    echo "  - Overlay: adsd3500-adsd3100.dtbo"
    echo "  - Kernel modules: /lib/modules/6.12.47*"
    echo ""
    echo "Configuration:"
    echo "  - Boot config updated: ${CONFIG_FILE}"
    echo "  - Services configured: adi-tof"
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
    log_step "ADI ToF ADSD3500 System Upgrade"
    log_info "Script version: ${SCRIPT_VERSION}"

    # Pre-flight checks
    check_root
    validate_environment
    create_backup

    # Installation steps
    apply_ubuntu_overlay
    update_kernel
    configure_services
    update_config_file

    # Summary and reboot
    display_summary

    sleep 10

    log_step "Rebooting system"
    reboot
}

# Execute main function
main

