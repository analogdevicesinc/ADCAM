#!/bin/bash

# Patch Validation Script for NVIDIA Jetson Orin Nano
# This script validates that all patches from apply_patch.sh were applied successfully
# Version: 1.0
# Date: 2026-01-27

# Exit on error, but allow individual checks to fail gracefully
set -o pipefail

# Set a timeout for hanging commands (30 seconds per command)
export TMOUT=30

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Log file
LOG_FILE="/var/log/adi-patch-validation.log"
VALIDATION_REPORT="/boot/adi-patch-validation-report.txt"

# Configuration
extlinux_conf_file="/boot/extlinux/extlinux.conf"

# Device validation configuration
I2C_BUS=2
I2C_ADDRESSES=(0x38 0x58 0x68)
GPIO_LIST=("ISP_RST" "EN_1P8" "EN_0P8" "P2" "I2CM_SEL" "ISP_BS3" "NET_HOST_IO_SEL" "ISP_BS0" "ISP_BS1" "HOST_IO_DIR" "ISP_BS4" "ISP_BS5" "FSYNC_DIR" "EN_VAUX" "EN_VAUX_LS" "EN_SYS")
declare -gA GPIO_MAP

##############################################################################
# Logging Functions
##############################################################################

function log_message() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "unknown")
    echo "[${timestamp}] [${level}] ${message}" 2>/dev/null | sudo tee -a "${LOG_FILE}" > /dev/null 2>&1 || true
}

function print_header() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}  ADI ToF Patch Validation Script${NC}"
    echo -e "${BLUE}  Date: $(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo 'unknown')${NC}"
    echo -e "${BLUE}================================================================${NC}"
    log_message "INFO" "Starting patch validation"
}

function print_check() {
    local check_name="$1"
    echo -e "\n${BLUE}[CHECK]${NC} ${check_name}"
    ((TOTAL_CHECKS++))
}

function print_pass() {
    local message="$1"
    echo -e "${GREEN}[PASS]${NC} ${message}"
    log_message "PASS" "${message}"
    ((PASSED_CHECKS++))
}

function print_fail() {
    local message="$1"
    echo -e "${RED}[FAIL]${NC} ${message}"
    log_message "FAIL" "${message}"
    ((FAILED_CHECKS++))
}

function print_warning() {
    local message="$1"
    echo -e "${YELLOW}[WARN]${NC} ${message}"
    log_message "WARN" "${message}"
    ((WARNING_CHECKS++))
}

##############################################################################
# Validation Functions
##############################################################################

function validate_boot_device_detection() {
    print_check "Boot Device Detection"

    if [[ ! -f "$extlinux_conf_file" ]]; then
        print_fail "Extlinux configuration file not found: ${extlinux_conf_file}"
        return 1
    fi

    if grep -q "PARTUUID" "${extlinux_conf_file}"; then
        boot_device_type="ssd"
        partuuid=$(grep -oP '(?<=PARTUUID=).{36}' "${extlinux_conf_file}" | head -n 1)
        print_pass "Boot device: SSD (NVMe) with PARTUUID: ${partuuid}"
    elif grep -q "root=/dev/mmcblk0p1" "${extlinux_conf_file}"; then
        boot_device_type="sdcard"
        print_pass "Boot device: microSD card (root=/dev/mmcblk0p1)"
    else
        print_fail "Unable to determine boot device type"
        return 1
    fi

    return 0
}

function validate_extlinux_config() {
    print_check "Extlinux Configuration"

    # Check if default label is set correctly
    if grep -q "^DEFAULT ADSD3500-DUAL+ADSD3100" "${extlinux_conf_file}"; then
        print_pass "Default boot label set to ADSD3500-DUAL+ADSD3100"
    else
        print_fail "Default boot label not set correctly"
    fi

    # Check for required boot labels
    local required_labels=("backup" "ADSD3500+ADSD3100" "ADSD3500-DUAL+ADSD3100" "ADSD3500-DUAL+ADSD3100+AR0234")
    for label in "${required_labels[@]}"; do
        if grep -q "LABEL ${label}" "${extlinux_conf_file}"; then
            print_pass "Boot label '${label}' exists"
        else
            print_warning "Boot label '${label}' not found"
        fi
    done

    # Verify correct root device in APPEND lines
    local expected_root_pattern
    if [[ "${boot_device_type}" == "ssd" ]]; then
        expected_root_pattern="root=PARTUUID="
    else
        expected_root_pattern="root=/dev/mmcblk0p1"
    fi

    if grep "APPEND" "${extlinux_conf_file}" | grep -q "${expected_root_pattern}"; then
        print_pass "Root device correctly configured in APPEND lines"
    else
        print_fail "Root device not correctly configured in APPEND lines"
    fi
}

function validate_kernel_files() {
    print_check "Kernel Files"

    # Check ADI kernel
    if [[ -f "/boot/adi/Image" ]]; then
        print_pass "ADI kernel image exists: /boot/adi/Image"
    else
        print_fail "ADI kernel image not found: /boot/adi/Image"
    fi

    # Check backup kernel
    if [[ -f "/boot/Image.backup" ]]; then
        print_pass "Backup kernel exists: /boot/Image.backup"
    else
        print_warning "Backup kernel not found: /boot/Image.backup"
    fi

    # Check sw-versions file
    if [[ -f "/boot/sw-versions" ]]; then
        print_pass "Software versions file exists: /boot/sw-versions"
        cat /boot/sw-versions >> "${LOG_FILE}"
    else
        print_warning "Software versions file not found: /boot/sw-versions"
    fi
}

function validate_device_tree_overlays() {
    print_check "Device Tree Overlays"

    local dtbo_files=(
        "/boot/adi/tegra234-p3767-camera-p3768-adsd3500.dtbo"
        "/boot/adi/tegra234-p3767-camera-p3768-dual-adsd3500-adsd3100.dtbo"
        "/boot/adi/tegra234-p3767-camera-p3768-dual-adsd3500-adsd3100-arducam-ar0234.dtbo"
    )

    for dtbo in "${dtbo_files[@]}"; do
        if [[ -f "${dtbo}" ]]; then
            print_pass "Device tree overlay exists: $(basename ${dtbo})"
        else
            print_fail "Device tree overlay not found: ${dtbo}"
        fi
    done
}

function validate_kernel_modules() {
    print_check "Kernel Modules"

    local module_dir="/lib/modules/5.15.148-adi-tegra"

    if [[ -d "${module_dir}" ]]; then
        print_pass "ADI kernel modules directory exists: ${module_dir}"

        # Check for specific critical modules
        local module_count=$(find "${module_dir}" -name "*.ko" 2>/dev/null | wc -l)
        if [[ ${module_count} -gt 0 ]]; then
            print_pass "Found ${module_count} kernel modules"
        else
            print_warning "No kernel modules (.ko files) found in ${module_dir}"
        fi
    else
        print_fail "ADI kernel modules directory not found: ${module_dir}"
    fi
}

function validate_firmware_directory() {
    print_check "Firmware Directory"

    if [[ -d "/lib/firmware/adi" ]]; then
        print_pass "ADI firmware directory exists: /lib/firmware/adi"
    else
        print_warning "ADI firmware directory not found: /lib/firmware/adi (may be created on first boot)"
    fi
}

function validate_network_configuration() {
    print_check "Network Configuration"

    # Check NetworkManager configuration
    if [[ -f "/etc/NetworkManager/conf.d/10-ignore-interface.conf" ]]; then
        print_pass "NetworkManager configuration exists"
    else
        print_fail "NetworkManager configuration not found"
    fi

    # Check systemd network configuration
    if [[ -f "/etc/systemd/network/10-rndis0.network" ]]; then
        print_pass "Systemd network configuration exists"

        # Check MTU setting
        if grep -q "MTU=15000" "/etc/systemd/network/10-rndis0.network"; then
            print_pass "MTU size configured to 15000"
        else
            print_warning "MTU size not set to 15000"
        fi
    else
        print_fail "Systemd network configuration not found"
    fi

    # Check USB device mode configuration
    if [[ -f "/opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-config.sh" ]]; then
        if grep -q "net_dhcp_lease_time=1500" "/opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-config.sh"; then
            print_pass "DHCP lease time configured to 1500"
        else
            print_warning "DHCP lease time not set to 1500"
        fi
    else
        print_warning "USB device mode configuration not found"
    fi

    if [[ -f "/opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-start.sh" ]]; then
        if grep -q "sudo ip link set l4tbr0 mtu 15000" "/opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-start.sh"; then
            print_pass "L4T bridge MTU size configured"
        else
            print_warning "L4T bridge MTU size not configured"
        fi
    fi
}

function validate_systemd_services() {
    print_check "Systemd Services"

    local services=("adi-tof" "jetson-performance" "systemd-networkd")

    for service in "${services[@]}"; do
        # Check if systemctl is available
        if ! command -v systemctl &> /dev/null; then
            print_warning "systemctl command not available, skipping service checks"
            break
        fi

        if systemctl is-enabled "${service}" &>/dev/null; then
            print_pass "Service '${service}' is enabled"

            if systemctl is-active "${service}" &>/dev/null; then
                print_pass "Service '${service}' is running"
            else
                print_warning "Service '${service}' is not running (may start on next boot)"
            fi
        else
            # Check if service file exists at least
            if systemctl list-unit-files "${service}.service" &>/dev/null | grep -q "${service}"; then
                print_warning "Service '${service}' exists but is not enabled"
            else
                print_fail "Service '${service}' is not found"
            fi
        fi
    done
}

function validate_udev_rules() {
    print_check "Udev Rules"

    if [[ -f "/etc/udev/rules.d/99-gpio.rules" ]]; then
        print_pass "GPIO udev rules exist"
    else
        print_fail "GPIO udev rules not found"
    fi
}

function validate_shell_scripts() {
    print_check "Shell Scripts"

    local script_dir="/usr/share/systemd"
    local script_count=$(find "${script_dir}" -maxdepth 1 -name "*.sh" -type f 2>/dev/null | wc -l)

    if [[ ${script_count} -gt 0 ]]; then
        print_pass "Found ${script_count} shell scripts in ${script_dir}"
    else
        print_warning "No shell scripts found in ${script_dir}"
    fi
}

function validate_system_info() {
    print_check "System Information"

    # Kernel version
    local kernel_version=$(uname -r 2>/dev/null || echo "unknown")
    print_pass "Current kernel: ${kernel_version}"
    log_message "INFO" "Kernel version: ${kernel_version}"

    # Check if running on Jetson
    if [[ -f "/etc/nv_tegra_release" ]]; then
        local tegra_version=$(cat /etc/nv_tegra_release 2>/dev/null | head -n 1 || echo "unknown")
        print_pass "NVIDIA Tegra platform detected: ${tegra_version}"
        log_message "INFO" "Tegra version: ${tegra_version}"
    else
        print_warning "Not running on NVIDIA Tegra platform"
    fi

    # Check boot device
    local current_root=$(findmnt -n -o SOURCE / 2>/dev/null || echo "unknown")
    if [[ "${current_root}" != "unknown" ]]; then
        print_pass "Current root filesystem: ${current_root}"
        log_message "INFO" "Root filesystem: ${current_root}"
    else
        print_warning "Unable to determine root filesystem (findmnt not available)"
        current_root=$(mount | grep ' / ' | cut -d' ' -f1 || echo "unknown")
        if [[ "${current_root}" != "unknown" ]]; then
            print_pass "Current root filesystem: ${current_root}"
            log_message "INFO" "Root filesystem: ${current_root}"
        fi
    fi
}

function validate_camera_devices() {
    print_check "Camera Devices (V4L2)"

    # Check if v4l2-ctl is available
    if ! command -v v4l2-ctl &> /dev/null; then
        print_warning "v4l2-ctl not available, skipping detailed camera check"
        # Still check for video devices
        if ls /dev/video* &>/dev/null; then
            local video_devices=$(ls -1 /dev/video* 2>/dev/null | wc -l)
            print_pass "Found ${video_devices} video device(s)"
        else
            print_warning "No video devices found (camera may need to be connected or system rebooted)"
        fi
        return 0
    fi

    local video_devices=$(ls -1 /dev/video* 2>/dev/null | wc -l)

    if [[ ${video_devices} -gt 0 ]]; then
        print_pass "Found ${video_devices} video device(s)"

        # List video devices
        for dev in /dev/video*; do
            if [[ -c "${dev}" ]]; then
                local dev_name=$(v4l2-ctl --device="${dev}" --info 2>/dev/null | grep "Card type" | cut -d ':' -f 2 | xargs || echo "Unknown")
                log_message "INFO" "Video device: ${dev} - ${dev_name}"
            fi
        done
    else
        print_warning "No video devices found (camera may need to be connected or system rebooted)"
    fi
}

##############################################################################
# Device Hardware Validation Functions
##############################################################################

function validate_i2c_devices() {
    print_check "I2C Device Detection"

    # Check if i2cdetect is available
    if ! command -v i2cdetect &> /dev/null; then
        print_warning "i2cdetect not available (install i2c-tools), skipping I2C checks"
        return 0
    fi

    # Check if I2C bus exists
    if [[ ! -e "/dev/i2c-${I2C_BUS}" ]]; then
        print_fail "I2C bus ${I2C_BUS} not found (/dev/i2c-${I2C_BUS})"
        return 1
    fi

    print_pass "I2C bus ${I2C_BUS} exists"

    # Scan I2C bus
    local output
    output=$(i2cdetect -y -r "$I2C_BUS" 2>/dev/null)

    if [[ -z "$output" ]]; then
        print_fail "Unable to scan I2C bus ${I2C_BUS}"
        return 1
    fi

    local all_present=0

    for addr in "${I2C_ADDRESSES[@]}"; do
        local row=$(printf "%02x" $((addr & 0xF0)))
        local col=$((addr & 0x0F))

        local value=$(echo "$output" | awk -v row="$row" -v col="$col" '
            $1 == row ":" { print $(col + 2) }
        ')

        if [[ "$value" != "--" && -n "$value" ]]; then
            print_pass "I2C device present at address 0x$(printf "%02x" $addr)"
            log_message "INFO" "I2C device at 0x$(printf "%02x" $addr): ${value}"
        else
            print_fail "I2C device NOT present at address 0x$(printf "%02x" $addr)"
            log_message "ERROR" "I2C device missing at 0x$(printf "%02x" $addr)"
            all_present=1
        fi
    done

    if [[ $all_present -eq 0 ]]; then
        print_pass "All required I2C devices detected"
    else
        print_fail "One or more I2C devices missing"
    fi

    return $all_present
}

function validate_gpio_labels() {
    print_check "GPIO Label Detection"

    # Check if debugfs gpio is available
    if [[ ! -f "/sys/kernel/debug/gpio" ]]; then
        print_warning "GPIO debugfs not available (/sys/kernel/debug/gpio), skipping GPIO label checks"
        return 0
    fi

    local gpio_data
    gpio_data=$(cat /sys/kernel/debug/gpio 2>/dev/null)

    if [[ -z "$gpio_data" ]]; then
        print_fail "Unable to read GPIO information from debugfs"
        return 1
    fi

    local all_found=0
    local found_count=0

    for label in "${GPIO_LIST[@]:1}"; do
        local result=$(echo "$gpio_data" | grep -i "\b$label\b" || true)

        if [[ -n "$result" ]]; then
            local gpio_num=$(echo "$result" | sed -E 's/.*gpio-([0-9]+).*/\1/' || echo "")

            if [[ -n "$gpio_num" ]]; then
                GPIO_MAP["$label"]=$gpio_num
                print_pass "GPIO label '${label}' found -> gpio-${gpio_num}"
                log_message "INFO" "GPIO: ${label} = gpio-${gpio_num}"
                ((found_count++))
            else
                print_warning "GPIO label '${label}' found, but GPIO number extraction failed"
                log_message "WARN" "GPIO ${label}: number extraction failed"
            fi
        else
            print_fail "GPIO label '${label}' not found in debugfs"
            log_message "ERROR" "GPIO label '${label}' not found"
            all_found=1
        fi
    done

    if [[ $all_found -eq 0 ]]; then
        print_pass "All ${found_count} GPIO labels detected successfully"
    else
        print_fail "One or more GPIO labels not found"
    fi

    return $all_found
}

function validate_tof_service() {
    print_check "ToF Service Execution"

    # Check if journalctl is available
    if ! command -v journalctl &> /dev/null; then
        print_warning "journalctl not available, skipping ToF service validation"
        return 0
    fi

    local service="adi-tof.service"
    local logs

    # Get logs for this boot only
    logs=$(journalctl -u "$service" -b --no-pager 2>/dev/null || echo "")

    if [[ -z "$logs" ]]; then
        print_warning "No logs found for ${service} (service may not have run yet)"
        return 0
    fi

    # Explicit skip case (not an error)
    if echo "$logs" | grep -q "Skipping ToF power sequence"; then
        print_pass "ToF power sequence intentionally skipped (as configured)"
        log_message "INFO" "ToF power sequence skipped by configuration"
        return 0
    fi

    # Hard failure indicators
    if echo "$logs" | grep -qiE "not found|not extracted correctly|GPIO detection failed|I2C check failed"; then
        print_fail "GPIO/I2C detection failure found in service logs"
        log_message "ERROR" "ToF service reported GPIO/I2C failures"
        echo "$logs" | tail -n 20 >> "${LOG_FILE}" 2>/dev/null || true
        return 1
    fi

    # Expected execution checkpoints
    local required_msgs=(
        "Matched MODULE:"
        "Configuring GPIOs via sysfs..."
        "GPIO configuration complete."
        "Starting ToF power sequence..."
        "ToF power sequence completed."
    )

    local all_msgs_found=0

    for msg in "${required_msgs[@]}"; do
        if echo "$logs" | grep -q "$msg"; then
            print_pass "Found checkpoint: ${msg}"
            log_message "INFO" "ToF service checkpoint: ${msg}"
        else
            print_fail "Missing checkpoint: ${msg}"
            log_message "ERROR" "ToF service missing checkpoint: ${msg}"
            all_msgs_found=1
        fi
    done

    if [[ $all_msgs_found -eq 0 ]]; then
        print_pass "ToF power/reset sequence validated successfully"
    else
        print_fail "ToF service validation incomplete"
        echo "$logs" | tail -n 30 >> "${LOG_FILE}" 2>/dev/null || true
    fi

    return $all_msgs_found
}

##############################################################################
# Report Generation
##############################################################################

function generate_validation_report() {
    local report_file="${VALIDATION_REPORT}"

    # Create report directory if needed
    mkdir -p "$(dirname ${report_file})" 2>/dev/null || true

    {
        echo "================================================================"
        echo "  ADI ToF Patch Validation Report"
        echo "  Generated: $(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo 'unknown')"
        echo "================================================================"
        echo ""
        echo "SUMMARY:"
        echo "  Total Checks:   ${TOTAL_CHECKS}"
        echo "  Passed:         ${PASSED_CHECKS}"
        echo "  Failed:         ${FAILED_CHECKS}"
        echo "  Warnings:       ${WARNING_CHECKS}"
        echo ""

        if [[ ${FAILED_CHECKS} -eq 0 ]]; then
            echo "RESULT: PASS (All critical checks passed)"
        else
            echo "RESULT: FAIL (${FAILED_CHECKS} critical check(s) failed)"
        fi

        echo ""
        echo "BOOT DEVICE:"
        echo "  Type: ${boot_device_type:-unknown}"
        echo ""
        echo "SYSTEM INFO:"
        echo "  Kernel: $(uname -r 2>/dev/null || echo 'unknown')"
        echo "  Architecture: $(uname -m 2>/dev/null || echo 'unknown')"
        if [[ -f /etc/os-release ]]; then
            echo "  OS: $(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d '=' -f 2 | tr -d '\"' || echo 'unknown')"
        fi
        echo ""
        echo "HARDWARE DEVICES:"
        echo "  I2C Bus: ${I2C_BUS}"
        echo "  Expected I2C Devices: ${#I2C_ADDRESSES[@]}"
        echo "  Expected GPIO Labels: ${#GPIO_LIST[@]}"
        if [[ ${#GPIO_MAP[@]} -gt 0 ]]; then
            echo "  Detected GPIO Labels: ${#GPIO_MAP[@]}"
        fi
        echo ""
        echo "For detailed logs, see: ${LOG_FILE}"
        echo "================================================================"
    } > "${report_file}" 2>/dev/null || {
        echo -e "${YELLOW}Warning: Cannot write validation report to ${report_file}${NC}"
    }

    if [[ -f "${report_file}" ]]; then
        echo -e "\n${BLUE}Validation report saved to: ${report_file}${NC}"
    fi
}

function print_summary() {
    echo -e "\n${BLUE}================================================================${NC}"
    echo -e "${BLUE}  VALIDATION SUMMARY${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo -e "  Total Checks:   ${TOTAL_CHECKS}"
    echo -e "  ${GREEN}Passed:         ${PASSED_CHECKS}${NC}"
    echo -e "  ${RED}Failed:         ${FAILED_CHECKS}${NC}"
    echo -e "  ${YELLOW}Warnings:       ${WARNING_CHECKS}${NC}"
    echo -e "${BLUE}================================================================${NC}\n"

    if [[ ${FAILED_CHECKS} -eq 0 ]]; then
        echo -e "${GREEN}✓ All critical checks passed!${NC}\n"
        log_message "INFO" "Validation completed successfully"
        return 0
    else
        echo -e "${RED}✗ ${FAILED_CHECKS} critical check(s) failed!${NC}\n"
        echo -e "${YELLOW}Please review the errors above and the log file: ${LOG_FILE}${NC}\n"
        log_message "ERROR" "Validation failed with ${FAILED_CHECKS} errors"
        return 1
    fi
}

##############################################################################
# Main Execution
##############################################################################

function main() {
    # Check if running as root or with sudo
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}This script must be run as root or with sudo${NC}"
        exit 1
    fi

    # Create log directory if needed
    mkdir -p "$(dirname ${LOG_FILE})" 2>/dev/null || true
    touch "${LOG_FILE}" 2>/dev/null || {
        echo -e "${YELLOW}Warning: Cannot create log file ${LOG_FILE}, continuing without logging${NC}"
        LOG_FILE="/dev/null"
    }

    print_header

    echo -e "\n${BLUE}Starting validation checks...${NC}\n"

    # Run all validations with error handling
    validate_system_info || echo -e "${YELLOW}System info check encountered issues${NC}"
    validate_boot_device_detection || echo -e "${YELLOW}Boot device detection encountered issues${NC}"
    validate_extlinux_config || echo -e "${YELLOW}Extlinux config check encountered issues${NC}"
    validate_kernel_files || echo -e "${YELLOW}Kernel files check encountered issues${NC}"
    validate_device_tree_overlays || echo -e "${YELLOW}Device tree overlay check encountered issues${NC}"
    validate_kernel_modules || echo -e "${YELLOW}Kernel modules check encountered issues${NC}"
    validate_firmware_directory || echo -e "${YELLOW}Firmware directory check encountered issues${NC}"
    validate_network_configuration || echo -e "${YELLOW}Network configuration check encountered issues${NC}"
    validate_systemd_services || echo -e "${YELLOW}Systemd services check encountered issues${NC}"
    validate_udev_rules || echo -e "${YELLOW}Udev rules check encountered issues${NC}"
    validate_shell_scripts || echo -e "${YELLOW}Shell scripts check encountered issues${NC}"
    validate_camera_devices || echo -e "${YELLOW}Camera devices check encountered issues${NC}"

    echo -e "\n${BLUE}================================================================${NC}"
    echo -e "${BLUE}  HARDWARE DEVICE VALIDATION${NC}"
    echo -e "${BLUE}================================================================${NC}\n"

    # Run hardware device validations
    validate_i2c_devices || echo -e "${YELLOW}I2C device check encountered issues${NC}"
    validate_gpio_labels || echo -e "${YELLOW}GPIO label check encountered issues${NC}"
    validate_tof_service || echo -e "${YELLOW}ToF service check encountered issues${NC}"

    # Generate report and print summary
    generate_validation_report
    print_summary

    # Exit with appropriate code
    if [[ ${FAILED_CHECKS} -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"

