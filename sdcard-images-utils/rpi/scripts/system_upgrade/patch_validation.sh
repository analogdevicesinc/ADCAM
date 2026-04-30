#!/usr/bin/env bash
#===============================================================================
# Raspberry Pi 5 ToF ADSD3500 Patch Validation Script
#
# Description: Validates that all patches from apply_patch.sh were applied
#              successfully on Raspberry Pi 5 with ADI ToF camera integration.
#              Checks boot config, kernel/DTB/DT overlay files, kernel modules,
#              services, and hardware (I2C + GPIO) readiness.
#
# Usage: sudo ./patch_validation.sh
#
# Requirements: Root privileges
#
# Exit Codes:
#   0 - All critical checks passed
#   1 - One or more critical checks failed
#
# Author: Analog Devices Inc.
# Version: 1.0
# Date: 2026-04-30
#===============================================================================

set -Eeuo pipefail

trap 'on_error $? $LINENO' ERR

#===============================================================================
# CONFIGURATION
#===============================================================================

readonly KERNEL_VERSION_PATTERN="6.12.47-adi+"
readonly KERNEL_EXPECTED="6.12.47-adi+"
readonly CONFIG_FILE="/boot/firmware/config.txt"
readonly OVERLAY_ENTRY="dtoverlay=adsd3500-adsd3100"
readonly KERNEL_ENTRY="kernel=kernel_adi.img"

# I2C configuration — Raspberry Pi 5 uses i2c-10 for the CSI camera connector
readonly I2C_BUS=10
readonly -a I2C_ADDRESSES=(0x38 0x58 0x68)

# Kernel modules expected to be loaded after a successful patch + reboot
readonly -a KERNEL_MODULES=("adsd3500")

# GPIO labels — ADSD3500 camera board signals (same as NVIDIA platform)
readonly -a GPIO_LIST=(
    "ISP_RST" "EN_1P8" "EN_0P8" "P2" "I2CM_SEL" "ISP_BS3"
    "NET_HOST_IO_SEL" "ISP_BS0" "ISP_BS1" "HOST_IO_DIR"
    "ISP_BS4" "ISP_BS5" "FSYNC_DIR" "EN_VAUX" "EN_VAUX_LS" "EN_SYS"
)
declare -gA GPIO_MAP

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Counters (mutable — not readonly)
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Output files
LOG_FILE="/var/log/adi-patch-validation-$(date '+%Y%m%d-%H%M%S').log"
VALIDATION_REPORT="/boot/firmware/adi-patch-validation-report.txt"

#===============================================================================
# ERROR HANDLER
#===============================================================================

on_error() {
    local exit_code="$1"
    local line_no="$2"
    log_message "FATAL" "Script failed at line ${line_no} with exit code ${exit_code}"
    echo -e "${RED}[FATAL]${NC} Unexpected error at line ${line_no} (exit code: ${exit_code})" >&2
}

#===============================================================================
# LOGGING FUNCTIONS
#===============================================================================

log_message() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "unknown")
    echo "[${timestamp}] [${level}] ${message}" 2>/dev/null | tee -a "${LOG_FILE}" > /dev/null 2>&1 || true
}

print_header() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}  ADI ToF Patch Validation Script — Raspberry Pi 5${NC}"
    echo -e "${BLUE}  Date: $(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo 'unknown')${NC}"
    echo -e "${BLUE}================================================================${NC}"
    log_message "INFO" "Starting patch validation for Raspberry Pi 5"
}

print_check() {
    local check_name="$1"
    echo -e "\n${BLUE}[CHECK]${NC} ${check_name}"
    (( TOTAL_CHECKS += 1 ))
}

print_pass() {
    local message="$1"
    echo -e "${GREEN}[PASS]${NC} ${message}"
    log_message "PASS" "${message}"
    (( PASSED_CHECKS += 1 ))
}

print_fail() {
    local message="$1"
    echo -e "${RED}[FAIL]${NC} ${message}"
    log_message "FAIL" "${message}"
    (( FAILED_CHECKS += 1 ))
}

print_warning() {
    local message="$1"
    echo -e "${YELLOW}[WARN]${NC} ${message}"
    log_message "WARN" "${message}"
    (( WARNING_CHECKS += 1 ))
}

##############################################################################
# Helper Functions
##############################################################################

# check_kernel_module <module_name>
# Returns: 0 = loaded and in use, 1 = not loaded, 2 = invalid argument
function check_kernel_module() {
    local module="$1"

    if [[ -z "${module}" ]]; then
        print_fail "check_kernel_module: no module name provided"
        return 2
    fi

    local mod_info
    mod_info=$(lsmod | awk -v mod="${module}" '$1 == mod {print $0}')

    if [[ -z "${mod_info}" ]]; then
        print_fail "Kernel module '${module}' is NOT loaded"
        log_message "FAIL" "Kernel module '${module}' not loaded"
        return 1
    fi

    local size used
    size=$(echo "${mod_info}" | awk '{print $2}')
    used=$(echo "${mod_info}" | awk '{print $3}')

    print_pass "Kernel module '${module}' is loaded (size: ${size} bytes, usage count: ${used})"
    log_message "PASS" "Module '${module}': size=${size}, used=${used}"

    if [[ "${used}" -gt 0 ]]; then
        print_pass "Module '${module}' is currently in use"
        log_message "INFO" "Module '${module}' is in use"
    else
        print_warning "Module '${module}' is loaded but not currently in use"
        log_message "WARN" "Module '${module}' loaded but usage count is 0"
    fi

    return 0
}

##############################################################################
# Validation Functions
##############################################################################

function validate_system_info() {
    print_check "System Information"

    # Kernel version
    local kernel_version
    kernel_version=$(uname -r 2>/dev/null || echo "unknown")
    log_message "INFO" "Kernel version: ${kernel_version}"

    if [[ "${kernel_version}" == "${KERNEL_EXPECTED}" ]]; then
        print_pass "Running ADI kernel: ${kernel_version}"
    else
        print_warning "Kernel is '${kernel_version}', expected '${KERNEL_EXPECTED}' — system may need a reboot"
    fi

    # Confirm Raspberry Pi platform
    if [[ -f "/proc/device-tree/model" ]]; then
        local rpi_model
        rpi_model=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo "unknown")
        if echo "${rpi_model}" | grep -qi "raspberry pi"; then
            print_pass "Raspberry Pi platform detected: ${rpi_model}"
            log_message "INFO" "Platform: ${rpi_model}"
        else
            print_warning "Unexpected platform model: ${rpi_model}"
        fi
    elif [[ -f "/etc/rpi-issue" ]]; then
        print_pass "Raspberry Pi platform detected (via /etc/rpi-issue)"
    else
        print_warning "Unable to confirm Raspberry Pi platform"
    fi

    # Check root filesystem source
    local current_root
    current_root=$(findmnt -n -o SOURCE / 2>/dev/null || echo "unknown")
    if [[ "${current_root}" != "unknown" ]]; then
        print_pass "Current root filesystem: ${current_root}"
        log_message "INFO" "Root filesystem: ${current_root}"
    else
        current_root=$(mount | grep ' / ' | cut -d' ' -f1 || echo "unknown")
        if [[ "${current_root}" != "unknown" ]]; then
            print_pass "Current root filesystem: ${current_root}"
        else
            print_warning "Unable to determine root filesystem"
        fi
    fi

    # OS info
    if [[ -f "/etc/os-release" ]]; then
        local os_name
        os_name=$(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "unknown")
        print_pass "OS: ${os_name}"
        log_message "INFO" "OS: ${os_name}"
    fi
}

function validate_boot_config() {
    print_check "Boot Configuration (${CONFIG_FILE})"

    if [[ ! -f "${CONFIG_FILE}" ]]; then
        print_fail "Boot config file not found: ${CONFIG_FILE}"
        return 1
    fi

    print_pass "Boot config file exists: ${CONFIG_FILE}"

    # Validate ADI kernel entry
    if grep -q "^${KERNEL_ENTRY}" "${CONFIG_FILE}"; then
        print_pass "ADI kernel entry present: ${KERNEL_ENTRY}"
    else
        print_fail "ADI kernel entry missing from config.txt: ${KERNEL_ENTRY}"
    fi

    # Validate device tree overlay entry
    if grep -q "^${OVERLAY_ENTRY}" "${CONFIG_FILE}"; then
        print_pass "Device tree overlay entry present: ${OVERLAY_ENTRY}"
    else
        print_fail "Device tree overlay entry missing from config.txt: ${OVERLAY_ENTRY}"
    fi

    # Check that the ADI entries appear under the [all] section
    if grep -A 20 "^\[all\]" "${CONFIG_FILE}" | grep -qE "^${KERNEL_ENTRY}|^${OVERLAY_ENTRY}"; then
        print_pass "ADI entries found under [all] section"
    else
        print_warning "ADI entries may not be under the [all] section — verify config.txt manually"
    fi
}

function validate_kernel_files() {
    print_check "Kernel and Device Tree Files"

    # ADI kernel image
    if [[ -f "/boot/firmware/kernel_adi.img" ]]; then
        print_pass "ADI kernel image exists: /boot/firmware/kernel_adi.img"
    else
        print_fail "ADI kernel image not found: /boot/firmware/kernel_adi.img"
    fi

    # Device tree blob
    if [[ -f "/boot/firmware/bcm2712-rpi-5-b.dtb" ]]; then
        print_pass "Device tree blob exists: /boot/firmware/bcm2712-rpi-5-b.dtb"
    else
        print_fail "Device tree blob not found: /boot/firmware/bcm2712-rpi-5-b.dtb"
    fi

    # Software versions file
    if [[ -f "/boot/sw-versions" ]]; then
        print_pass "Software versions file exists: /boot/sw-versions"
        cat /boot/sw-versions >> "${LOG_FILE}" 2>/dev/null || true
    else
        print_warning "Software versions file not found: /boot/sw-versions"
    fi
}

function validate_device_tree_overlay() {
    print_check "Device Tree Overlay"

    local dtbo="/boot/firmware/overlays/adsd3500-adsd3100.dtbo"

    if [[ -f "${dtbo}" ]]; then
        print_pass "Device tree overlay exists: ${dtbo}"
    else
        print_fail "Device tree overlay not found: ${dtbo}"
    fi
}

function validate_kernel_modules() {
    print_check "Kernel Modules"

    local module_dirs
    module_dirs=$(find /lib/modules -maxdepth 1 -type d -name "${KERNEL_VERSION_PATTERN}" 2>/dev/null || true)

    if [[ -z "${module_dirs}" ]]; then
        print_fail "No ADI kernel modules directory found matching: /lib/modules/${KERNEL_VERSION_PATTERN}"
        return 1
    fi

    while IFS= read -r module_dir; do
        local version
        version=$(basename "${module_dir}")
        print_pass "ADI kernel modules directory exists: ${module_dir}"

        local module_count
        module_count=$(find "${module_dir}" -name "*.ko" 2>/dev/null | wc -l)

        if [[ ${module_count} -gt 0 ]]; then
            print_pass "Found ${module_count} kernel module(s) in ${version}"
        else
            print_warning "No kernel modules (.ko files) found in ${module_dir}"
        fi

        if [[ -f "${module_dir}/modules.dep" ]]; then
            print_pass "Module dependency file (modules.dep) exists for ${version}"
        else
            print_warning "modules.dep not found for ${version} — depmod may need to be re-run"
        fi
    done <<< "${module_dirs}"
}

function validate_loaded_kernel_modules() {
    print_check "Loaded Kernel Modules"

    if ! command -v lsmod &>/dev/null; then
        print_warning "lsmod not available, skipping loaded module checks"
        return 0
    fi

    local all_loaded=0

    for module in "${KERNEL_MODULES[@]}"; do
        check_kernel_module "${module}" || all_loaded=1
    done

    if [[ ${all_loaded} -eq 0 ]]; then
        print_pass "All expected kernel modules are loaded"
    else
        print_fail "One or more expected kernel modules are not loaded"
    fi

    return ${all_loaded}
}

function validate_ubuntu_overlay() {
    print_check "Ubuntu Overlay Components"

    # ADI Tools directory
    if [[ -d "/opt/adi/Tools" ]]; then
        print_pass "ADI Tools directory exists: /opt/adi/Tools"
    else
        print_warning "ADI Tools directory not found: /opt/adi/Tools (check ubuntu_overlay installation)"
    fi

    # Systemd scripts
    local script_dir="/usr/share/systemd"
    local script_count
    script_count=$(find "${script_dir}" -maxdepth 1 -name "*.sh" -type f 2>/dev/null | wc -l || echo 0)

    if [[ ${script_count} -gt 0 ]]; then
        print_pass "Found ${script_count} shell script(s) in ${script_dir}"
    else
        print_warning "No shell scripts found in ${script_dir}"
    fi
}

function validate_systemd_services() {
    print_check "Systemd Services"

    local services=("adi-tof" "systemd-networkd")

    if ! command -v systemctl &>/dev/null; then
        print_warning "systemctl not available, skipping service checks"
        return 0
    fi

    for service in "${services[@]}"; do
        if systemctl is-enabled "${service}" &>/dev/null; then
            print_pass "Service '${service}' is enabled"

            if systemctl is-active "${service}" &>/dev/null; then
                print_pass "Service '${service}' is running"
            else
                print_warning "Service '${service}' is not running (may start after reboot)"
            fi
        else
            if systemctl list-unit-files "${service}.service" 2>/dev/null | grep -q "${service}"; then
                print_warning "Service '${service}' exists but is not enabled"
            else
                print_fail "Service '${service}' not found"
            fi
        fi
    done
}

function validate_camera_devices() {
    print_check "Camera Devices (V4L2)"

    if ! command -v v4l2-ctl &>/dev/null; then
        print_warning "v4l2-ctl not available, skipping detailed camera check"
        print_warning "Install with: sudo apt install v4l-utils"

        if ls /dev/video* &>/dev/null 2>&1; then
            local video_devices
            video_devices=$(ls -1 /dev/video* 2>/dev/null | wc -l)
            print_pass "Found ${video_devices} video device(s)"
        else
            print_warning "No video devices found (camera may need to be connected or system rebooted)"
        fi
        return 0
    fi

    if ls /dev/video* &>/dev/null 2>&1; then
        local video_devices
        video_devices=$(ls -1 /dev/video* 2>/dev/null | wc -l)
        print_pass "Found ${video_devices} video device(s)"

        for dev in /dev/video*; do
            if [[ -c "${dev}" ]]; then
                local dev_name
                dev_name=$(v4l2-ctl --device="${dev}" --info 2>/dev/null | grep "Card type" | cut -d ':' -f 2 | xargs || echo "Unknown")
                log_message "INFO" "Video device: ${dev} - ${dev_name}"
            fi
        done
    else
        print_warning "No video devices found (camera may need to be connected or system rebooted)"
    fi
}

##############################################################################
# Hardware Device Validation Functions
##############################################################################

function validate_adsd3500_subdev() {
    print_check "ADSD3500 Media Subdevice"

    if ! command -v media-ctl &>/dev/null; then
        print_warning "media-ctl not available, skipping ADSD3500 subdev check"
        print_warning "Install with: sudo apt install v4l-utils"
        return 0
    fi

    local found=0

    for media in /dev/media*; do
        [[ -e "${media}" ]] || continue

        local dot
        dot=$(media-ctl --device "${media}" --print-dot 2>/dev/null) || continue

        if echo "${dot}" | grep -qi "adsd3500"; then
            local subdev
            subdev=$(echo "${dot}" | grep -i "adsd3500" -A5 | grep -o '/dev/v4l-subdev[0-9]\+' | head -n1)

            print_pass "ADSD3500 found in media device: ${media}"
            log_message "INFO" "ADSD3500 found on media device: ${media}"

            if [[ -n "${subdev}" ]]; then
                print_pass "ADSD3500 linked subdev node: ${subdev}"
                log_message "INFO" "ADSD3500 subdev: ${subdev}"
            else
                print_warning "ADSD3500 found but no v4l-subdev node detected in media graph"
                log_message "WARN" "ADSD3500 on ${media}: no v4l-subdev node found"
            fi

            found=1
        fi
    done

    if [[ ${found} -eq 0 ]]; then
        print_fail "ADSD3500 not found in any media device"
        log_message "FAIL" "ADSD3500 not found in any /dev/media* device"
        return 1
    fi

    return 0
}

function validate_i2c_devices() {
    print_check "I2C Device Detection"

    if ! command -v i2cdetect &>/dev/null; then
        print_warning "i2cdetect not available (install i2c-tools), skipping I2C checks"
        return 0
    fi

    if [[ ! -e "/dev/i2c-${I2C_BUS}" ]]; then
        print_fail "I2C bus ${I2C_BUS} not found (/dev/i2c-${I2C_BUS})"
        return 1
    fi

    print_pass "I2C bus ${I2C_BUS} exists"

    local output
    output=$(i2cdetect -y -r "${I2C_BUS}" 2>/dev/null)

    if [[ -z "${output}" ]]; then
        print_fail "Unable to scan I2C bus ${I2C_BUS}"
        return 1
    fi

    local all_present=0

    for addr in "${I2C_ADDRESSES[@]}"; do
        local row
        row=$(printf "%02x" $(( addr & 0xF0 )))
        local col
        col=$(( addr & 0x0F ))

        local value
        value=$(echo "${output}" | awk -v row="${row}" -v col="${col}" '
            $1 == row ":" { print $(col + 2) }
        ')

        if [[ "${value}" != "--" && -n "${value}" ]]; then
            print_pass "I2C device present at address 0x$(printf "%02x" "${addr}")"
            log_message "INFO" "I2C device at 0x$(printf "%02x" "${addr}"): ${value}"
        else
            print_fail "I2C device NOT present at address 0x$(printf "%02x" "${addr}")"
            log_message "ERROR" "I2C device missing at 0x$(printf "%02x" "${addr}")"
            all_present=1
        fi
    done

    if [[ ${all_present} -eq 0 ]]; then
        print_pass "All required I2C devices detected"
    else
        print_fail "One or more I2C devices missing"
    fi

    return ${all_present}
}

function validate_gpio_labels() {
    print_check "GPIO Label Detection"

    if [[ ! -f "/sys/kernel/debug/gpio" ]]; then
        print_warning "GPIO debugfs not available (/sys/kernel/debug/gpio), skipping GPIO label checks"
        return 0
    fi

    local gpio_data
    gpio_data=$(cat /sys/kernel/debug/gpio 2>/dev/null)

    if [[ -z "${gpio_data}" ]]; then
        print_fail "Unable to read GPIO information from debugfs"
        return 1
    fi

    local all_found=0
    local found_count=0

    # --- ISP_RST special case ---
    # On Raspberry Pi, ISP_RST is not exposed by label in debugfs.
    # It is mapped via the fixed GPIO34 line (see tof-power-en.sh).
    local isp_rst_result
    isp_rst_result=$(echo "${gpio_data}" | grep -i "\bGPIO34\b" || true)

    if [[ -n "${isp_rst_result}" ]]; then
        local isp_rst_gpio
        isp_rst_gpio=$(echo "${isp_rst_result}" | sed -E 's/.*gpio-([0-9]+).*/\1/' || echo "")

        if [[ -n "${isp_rst_gpio}" ]]; then
            GPIO_MAP["ISP_RST"]="${isp_rst_gpio}"
            print_pass "ISP_RST mapped via GPIO34 -> gpio-${isp_rst_gpio}"
            log_message "INFO" "GPIO: ISP_RST = gpio-${isp_rst_gpio} (via GPIO34)"
            (( found_count += 1 ))
        else
            print_fail "GPIO34 found in debugfs, but GPIO number extraction failed for ISP_RST"
            log_message "ERROR" "ISP_RST: GPIO number extraction from GPIO34 failed"
            all_found=1
        fi
    else
        print_fail "GPIO34 not found in debugfs — ISP_RST cannot be mapped"
        log_message "ERROR" "GPIO34 not found; ISP_RST mapping failed"
        all_found=1
    fi

    # --- All other GPIO labels (skip ISP_RST at index 0) ---
    for label in "${GPIO_LIST[@]:1}"; do
        local result
        result=$(echo "${gpio_data}" | grep -i "\b${label}\b" || true)

        if [[ -n "${result}" ]]; then
            local gpio_num
            gpio_num=$(echo "${result}" | sed -E 's/.*gpio-([0-9]+).*/\1/' || echo "")

            if [[ -n "${gpio_num}" ]]; then
                GPIO_MAP["${label}"]="${gpio_num}"
                print_pass "GPIO label '${label}' found -> gpio-${gpio_num}"
                log_message "INFO" "GPIO: ${label} = gpio-${gpio_num}"
                (( found_count += 1 ))
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

    if [[ ${all_found} -eq 0 ]]; then
        print_pass "All ${found_count} GPIO signals detected successfully"
    else
        print_fail "One or more GPIO signals not found"
    fi

    return ${all_found}
}

function validate_tof_service() {
    print_check "ToF Service Execution"

    if ! command -v journalctl &>/dev/null; then
        print_warning "journalctl not available, skipping ToF service validation"
        return 0
    fi

    local service="adi-tof.service"
    local logs
    logs=$(journalctl -u "${service}" -b --no-pager 2>/dev/null || echo "")

    if [[ -z "${logs}" ]]; then
        print_warning "No logs found for ${service} (service may not have run yet)"
        return 0
    fi

    # Explicit skip case — not an error
    if echo "${logs}" | grep -q "Skipping ToF power sequence"; then
        print_pass "ToF power sequence intentionally skipped (as configured)"
        log_message "INFO" "ToF power sequence skipped by configuration"
        return 0
    fi

    # Hard failure indicators
    if echo "${logs}" | grep -qiE "not found|not extracted correctly|GPIO detection failed|I2C check failed"; then
        print_fail "GPIO/I2C detection failure found in service logs"
        log_message "ERROR" "ToF service reported GPIO/I2C failures"
        echo "${logs}" | tail -n 20 >> "${LOG_FILE}" 2>/dev/null || true
        return 1
    fi

    # Expected execution checkpoints
    local required_msgs=(
        "MODULE matched:"
        "Configuring GPIOs via sysfs..."
        "GPIO configuration complete."
        "Starting ToF power sequence..."
        "ToF power sequence completed."
    )

    local all_msgs_found=0

    for msg in "${required_msgs[@]}"; do
        if echo "${logs}" | grep -q "${msg}"; then
            print_pass "Found checkpoint: ${msg}"
            log_message "INFO" "ToF service checkpoint: ${msg}"
        else
            print_fail "Missing checkpoint: ${msg}"
            log_message "ERROR" "ToF service missing checkpoint: ${msg}"
            all_msgs_found=1
        fi
    done

    if [[ ${all_msgs_found} -eq 0 ]]; then
        print_pass "ToF power/reset sequence validated successfully"
    else
        print_fail "ToF service validation incomplete"
        echo "${logs}" | tail -n 30 >> "${LOG_FILE}" 2>/dev/null || true
    fi

    return ${all_msgs_found}
}

##############################################################################
# Report Generation
##############################################################################

function generate_validation_report() {
    local report_file="${VALIDATION_REPORT}"

    mkdir -p "$(dirname "${report_file}")" 2>/dev/null || true

    {
        echo "================================================================"
        echo "  ADI ToF Patch Validation Report — Raspberry Pi 5"
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
        echo "SYSTEM INFO:"
        echo "  Kernel: $(uname -r 2>/dev/null || echo 'unknown')"
        echo "  Architecture: $(uname -m 2>/dev/null || echo 'unknown')"
        if [[ -f /etc/os-release ]]; then
            echo "  OS: $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d '=' -f 2 | tr -d '"' || echo 'unknown')"
        fi
        if [[ -f "/proc/device-tree/model" ]]; then
            echo "  Platform: $(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo 'unknown')"
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
    if [[ ${EUID} -ne 0 ]]; then
        echo -e "${RED}This script must be run as root or with sudo${NC}"
        exit 1
    fi

    # Set up log file
    mkdir -p "$(dirname "${LOG_FILE}")" 2>/dev/null || true
    touch "${LOG_FILE}" 2>/dev/null || {
        echo -e "${YELLOW}Warning: Cannot create log file ${LOG_FILE}, continuing without logging${NC}"
        LOG_FILE="/dev/null"
    }

    print_header

    echo -e "\n${BLUE}Starting validation checks...${NC}\n"

    # System and boot configuration checks
    validate_system_info         || echo -e "${YELLOW}System info check encountered issues${NC}"
    validate_boot_config         || echo -e "${YELLOW}Boot config check encountered issues${NC}"
    validate_kernel_files        || echo -e "${YELLOW}Kernel files check encountered issues${NC}"
    validate_device_tree_overlay || echo -e "${YELLOW}Device tree overlay check encountered issues${NC}"
    validate_kernel_modules        || echo -e "${YELLOW}Kernel modules check encountered issues${NC}"
    validate_loaded_kernel_modules || echo -e "${YELLOW}Loaded kernel modules check encountered issues${NC}"
    validate_ubuntu_overlay        || echo -e "${YELLOW}Ubuntu overlay check encountered issues${NC}"
    validate_systemd_services    || echo -e "${YELLOW}Systemd services check encountered issues${NC}"
    validate_camera_devices        || echo -e "${YELLOW}Camera devices check encountered issues${NC}"
    validate_adsd3500_subdev       || echo -e "${YELLOW}ADSD3500 subdev check encountered issues${NC}"

    echo -e "\n${BLUE}================================================================${NC}"
    echo -e "${BLUE}  HARDWARE DEVICE VALIDATION${NC}"
    echo -e "${BLUE}================================================================${NC}\n"

    # Hardware device validations
    validate_i2c_devices  || echo -e "${YELLOW}I2C device check encountered issues${NC}"
    validate_gpio_labels  || echo -e "${YELLOW}GPIO label check encountered issues${NC}"
    validate_tof_service  || echo -e "${YELLOW}ToF service check encountered issues${NC}"

    # Generate report and print final summary
    generate_validation_report
    print_summary

    if [[ ${FAILED_CHECKS} -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

main "$@"
