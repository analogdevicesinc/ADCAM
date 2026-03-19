#!/bin/bash
#===============================================================================
# Script Name: runme.sh
# Description: Production-grade Raspberry Pi 5 ToF ADSD3500 build automation
# Author: Analog Devices Inc.
# Version: 2.0
# Date: March 2026
#
# Purpose:
#   Automates the complete build process for Raspberry Pi 5 with ADSD3500 ToF
#   sensor support, including kernel compilation, module packaging, and
#   distribution archive creation.
#
# Usage:
#   ./runme.sh <sdk_version> <tof_branch_name>
#
# Exit Codes:
#   0 - Success
#   1 - General error
#   2 - Missing dependencies
#   3 - Build failure
#   4 - Archive creation error
#===============================================================================

set -euo pipefail

#===============================================================================
# CONFIGURATION
#===============================================================================

# Repository configuration
readonly REPO_URL="https://github.com/raspberrypi/linux.git"
readonly REPO_DIR="linux"
readonly STABLE_TAG="stable_20250916"

# Build configuration (ARCH, CROSS_COMPILE, and KERNEL are exported, so not readonly)
ARCH="arm64"
CROSS_COMPILE="aarch64-linux-gnu-"
KERNEL="kernel_2712"
readonly DEFCONFIG="bcm2712_defconfig"

# Script metadata
readonly SCRIPT_VERSION="2.0"
readonly KERNEL_VERSION="6.12.47-adi+"

# Debug mode (set to 1 to enable debug logging, 0 to disable)
DEBUG="${DEBUG:-1}"

#===============================================================================
# GLOBAL VARIABLES (initialized later)
#===============================================================================

ROOTDIR=""
BR_COMMIT=""
SDK_VERSION=""
BRANCH=""
PATCH_DIR=""
LOG_FILE="/tmp/rpi_build_$(date +%Y%m%d_%H%M%S).log"
START_TIME=""

#===============================================================================
# EXIT CODES
#===============================================================================

readonly EXIT_SUCCESS=0
readonly EXIT_GENERAL_ERROR=1
readonly EXIT_MISSING_DEPS=2
readonly EXIT_BUILD_FAILURE=3
readonly EXIT_ARCHIVE_ERROR=4

#===============================================================================
# COLOR CODES FOR OUTPUT
#===============================================================================

readonly COLOR_RED='\033[0;31m'
readonly COLOR_GREEN='\033[0;32m'
readonly COLOR_YELLOW='\033[1;33m'
readonly COLOR_BLUE='\033[0;34m'
readonly COLOR_CYAN='\033[0;36m'
readonly COLOR_RESET='\033[0m'

#===============================================================================
# LOGGING FUNCTIONS
#===============================================================================

# Function to strip ANSI color codes from text
strip_colors() {
    sed 's/\x1b\[[0-9;]*m//g'
}

# Log informational message
log_info() {
    local msg="$*"
    if [[ -n "${LOG_FILE}" ]]; then
        echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} ${msg}" | tee -a >(strip_colors >> "${LOG_FILE}" 2>/dev/null || cat)
    else
        echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} ${msg}"
    fi
}

# Log success message
log_success() {
    local msg="$*"
    if [[ -n "${LOG_FILE}" ]]; then
        echo -e "${COLOR_GREEN}[SUCCESS]${COLOR_RESET} ${msg}" | tee -a >(strip_colors >> "${LOG_FILE}" 2>/dev/null || cat)
    else
        echo -e "${COLOR_GREEN}[SUCCESS]${COLOR_RESET} ${msg}"
    fi
}

# Log warning message
log_warning() {
    local msg="$*"
    if [[ -n "${LOG_FILE}" ]]; then
        echo -e "${COLOR_YELLOW}[WARNING]${COLOR_RESET} ${msg}" | tee -a >(strip_colors >> "${LOG_FILE}" 2>/dev/null || cat)
    else
        echo -e "${COLOR_YELLOW}[WARNING]${COLOR_RESET} ${msg}"
    fi
}

# Log error message
log_error() {
    local msg="$*"
    if [[ -n "${LOG_FILE}" ]]; then
        echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} ${msg}" | tee -a >(strip_colors >> "${LOG_FILE}" 2>/dev/null || cat)
    else
        echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} ${msg}"
    fi
}

# Log debug message (only if DEBUG=1)
log_debug() {
    if [[ "${DEBUG}" == "1" ]]; then
        local msg="$*"
        if [[ -n "${LOG_FILE}" ]]; then
            echo -e "${COLOR_CYAN}[DEBUG]${COLOR_RESET} ${msg}" | tee -a >(strip_colors >> "${LOG_FILE}" 2>/dev/null || cat)
        else
            echo -e "${COLOR_CYAN}[DEBUG]${COLOR_RESET} ${msg}"
        fi
    fi
}

# Log step message
log_step() {
    local msg="$*"
    if [[ -n "${LOG_FILE}" ]]; then
        echo -e "\n${COLOR_GREEN}=== ${msg} ===${COLOR_RESET}\n" | tee -a >(strip_colors >> "${LOG_FILE}" 2>/dev/null || cat)
    else
        echo -e "\n${COLOR_GREEN}=== ${msg} ===${COLOR_RESET}\n"
    fi
}

# Error exit function
error_exit() {
    local msg="$1"
    local exit_code="${2:-$EXIT_GENERAL_ERROR}"
    log_error "${msg}"
    log_error "Build failed. Check log: ${LOG_FILE}"
    exit "${exit_code}"
}

#===============================================================================
# UTILITY FUNCTIONS
#===============================================================================

# Check if required commands exist
check_dependencies() {
    log_step "Checking required dependencies"

    local missing_deps=0
    local required_commands=(
        "git"
        "make"
        "aarch64-linux-gnu-gcc"
        "tar"
        "zip"
        "bc"
    )

    for cmd in "${required_commands[@]}"; do
        if ! command -v "${cmd}" &> /dev/null; then
            log_error "Required command not found: ${cmd}"
            ((missing_deps++))
        else
            log_debug "Found: ${cmd} at $(command -v ${cmd})"
        fi
    done

    if [[ ${missing_deps} -gt 0 ]]; then
        error_exit "Missing ${missing_deps} required dependencies. Install them and try again." ${EXIT_MISSING_DEPS}
    fi

    log_success "All dependencies are available"
}

# Validate command-line arguments
validate_arguments() {
    log_step "Validating command-line arguments"

    if [[ "$#" -ne 2 ]]; then
        echo "Usage: $0 <sdk_version> <tof_branch_name>"
        echo ""
        echo "Arguments:"
        echo "  sdk_version       SDK version identifier (e.g., 1.0.0)"
        echo "  tof_branch_name   ToF branch name (e.g., main, develop)"
        echo ""
        echo "Example:"
        echo "  $0 1.0.0 main"
        exit ${EXIT_GENERAL_ERROR}
    fi

    SDK_VERSION="$1"
    BRANCH="$2"

    if [[ -z "${SDK_VERSION}" ]]; then
        error_exit "SDK version cannot be empty" ${EXIT_GENERAL_ERROR}
    fi

    if [[ -z "${BRANCH}" ]]; then
        error_exit "Branch name cannot be empty" ${EXIT_GENERAL_ERROR}
    fi

    log_info "SDK Version: ${SDK_VERSION}"
    log_info "Branch: ${BRANCH}"
    log_success "Arguments validated successfully"
}

# Initialize environment
init_environment() {
    log_step "Initializing build environment"

    ROOTDIR="$(pwd)"
    START_TIME=$(date +%s)

    # Create logs directory
    mkdir -p "${ROOTDIR}/build/logs"
    LOG_FILE="${ROOTDIR}/build/logs/rpi_build_$(date +%Y%m%d_%H%M%S).log"

    log_info "Root directory: ${ROOTDIR}"
    log_info "Log file: ${LOG_FILE}"

    # Get git commit hash
    if git rev-parse --git-dir > /dev/null 2>&1; then
        BR_COMMIT=$(git log -1 --pretty=format:%h 2>/dev/null || echo "unknown")
        log_info "Git commit: ${BR_COMMIT}"
    else
        BR_COMMIT="unknown"
        log_warning "Not in a git repository, commit hash unavailable"
    fi

    # Create patch directory
    PATCH_DIR="${ROOTDIR}/build/RPI_ToF_ADSD3500_REL_PATCH_$(date +"%d%b%y")"
    mkdir -p "${PATCH_DIR}" || error_exit "Failed to create patch directory" ${EXIT_GENERAL_ERROR}
    log_info "Patch directory: ${PATCH_DIR}"

    log_success "Environment initialized"
}

#===============================================================================
# BUILD FUNCTIONS
#===============================================================================

# Download Linux kernel source
download_linux_kernel() {
    log_step "Downloading Raspberry Pi Linux kernel source"

    local build_dir="${ROOTDIR}/build"
    mkdir -p "${build_dir}" || error_exit "Failed to create build directory" ${EXIT_GENERAL_ERROR}

    cd "${build_dir}" || error_exit "Failed to enter build directory" ${EXIT_GENERAL_ERROR}

    if [[ -d "${REPO_DIR}" ]]; then
        log_warning "Directory '${REPO_DIR}' already exists. Skipping clone."
        cd "${REPO_DIR}" || error_exit "Failed to enter ${REPO_DIR}" ${EXIT_GENERAL_ERROR}
    else
        log_info "Cloning repository: ${REPO_URL}"
        if ! git clone "${REPO_URL}" 2>&1 | tee -a "${LOG_FILE}" | strip_colors | tail -5; then
            error_exit "Failed to clone repository" ${EXIT_GENERAL_ERROR}
        fi
        cd "${REPO_DIR}" || error_exit "Failed to enter ${REPO_DIR}" ${EXIT_GENERAL_ERROR}
    fi

    log_info "Fetching all tags..."
    if ! git fetch --all --tags 2>&1 | tee -a "${LOG_FILE}" | strip_colors | tail -5; then
        error_exit "Failed to fetch tags" ${EXIT_GENERAL_ERROR}
    fi

    log_info "Checking out stable tag: ${STABLE_TAG}"
    if git rev-parse --verify "${STABLE_TAG}" >/dev/null 2>&1; then
        log_info "Branch ${STABLE_TAG} already exists, checking it out"
        if ! git checkout "${STABLE_TAG}" 2>&1 | tee -a "${LOG_FILE}"; then
            error_exit "Failed to checkout existing branch ${STABLE_TAG}" ${EXIT_GENERAL_ERROR}
        fi
    else
        if ! git checkout "tags/${STABLE_TAG}" -b "${STABLE_TAG}" 2>&1 | tee -a "${LOG_FILE}"; then
            error_exit "Failed to checkout tag ${STABLE_TAG}" ${EXIT_GENERAL_ERROR}
        fi
    fi

    log_success "Repository is now at tag ${STABLE_TAG}"
}

# Apply git format patches
apply_git_format_patches() {
    log_step "Applying git format patches"

    local kernel_dir="${ROOTDIR}/build/${REPO_DIR}"
    local patches_dir="${ROOTDIR}/patches/linux"

    cd "${kernel_dir}" || error_exit "Failed to enter kernel directory" ${EXIT_GENERAL_ERROR}

    log_info "Resetting to clean state: tags/${STABLE_TAG}"
    if ! git reset --hard "tags/${STABLE_TAG}" 2>&1 | tee -a "${LOG_FILE}"; then
        error_exit "Failed to reset to tag ${STABLE_TAG}" ${EXIT_GENERAL_ERROR}
    fi

    if [[ ! -d "${patches_dir}" ]]; then
        error_exit "Patches directory not found: ${patches_dir}" ${EXIT_GENERAL_ERROR}
    fi

    local patch_count=$(find "${patches_dir}" -name "*.patch" | wc -l)
    if [[ ${patch_count} -eq 0 ]]; then
        log_warning "No patches found in ${patches_dir}"
        return 0
    fi

    log_info "Applying ${patch_count} patches from ${patches_dir}"
    if ! git am "${patches_dir}"/*.patch 2>&1 | tee -a "${LOG_FILE}" | strip_colors | tail -10; then
        log_error "Failed to apply patches"
        log_info "Attempting to show conflict details..."
        git am --show-current-patch 2>&1 | tee -a "${LOG_FILE}" || true
        error_exit "Patch application failed. Resolve conflicts manually." ${EXIT_BUILD_FAILURE}
    fi

    log_success "All patches applied successfully"
}

# Build kernel, modules, and device trees
build_kernel() {
    log_step "Building Raspberry Pi 5 kernel (${KERNEL})"

    local build_dir="${ROOTDIR}/build/${REPO_DIR}"
    cd "${build_dir}" || error_exit "Failed to enter build directory" ${EXIT_BUILD_FAILURE}

    # Export build variables
    export ARCH="${ARCH}"
    export CROSS_COMPILE="${CROSS_COMPILE}"
    export KERNEL="${KERNEL}"

    log_info "Build configuration:"
    log_info "  ARCH: ${ARCH}"
    log_info "  CROSS_COMPILE: ${CROSS_COMPILE}"
    log_info "  KERNEL: ${KERNEL}"
    log_info "  DEFCONFIG: ${DEFCONFIG}"
    log_info "  Parallel jobs: $(nproc)"

    # Clean previous builds
    log_info "Cleaning previous builds..."
    if ! make distclean 2>&1 | tee -a "${LOG_FILE}" | strip_colors | tail -5; then
        log_warning "distclean had warnings, continuing..."
    fi

    # Configure kernel
    log_info "Configuring kernel with ${DEFCONFIG}..."
    if ! make "${DEFCONFIG}" 2>&1 | tee -a "${LOG_FILE}" | strip_colors | tail -5; then
        error_exit "Kernel configuration failed" ${EXIT_BUILD_FAILURE}
    fi

    # Build kernel image, modules, and device trees
    log_info "Building kernel Image.gz, modules, and device trees..."
    if ! make -j"$(nproc)" Image.gz modules dtbs KERNEL="${KERNEL}" 2>&1 | tee -a "${LOG_FILE}" | strip_colors | tail -20; then
        error_exit "Kernel build failed" ${EXIT_BUILD_FAILURE}
    fi

    log_success "Kernel build completed"

    # Prepare and install modules
    log_info "Preparing kernel modules..."
    rm -rf modules
    mkdir -p modules || error_exit "Failed to create modules directory" ${EXIT_BUILD_FAILURE}

    if ! make modules_install INSTALL_MOD_PATH=./modules KERNEL="${KERNEL}" 2>&1 | tee -a "${LOG_FILE}" | strip_colors | tail -10; then
        error_exit "Module installation failed" ${EXIT_BUILD_FAILURE}
    fi

    # Package modules
    log_info "Creating modules archive..."
    if ! tar czf modules.tar.gz -C modules . 2>&1 | tee -a "${LOG_FILE}"; then
        error_exit "Failed to create modules archive" ${EXIT_BUILD_FAILURE}
    fi

    # Copy build artifacts to patch directory
    log_info "Copying build artifacts to patch directory..."

    cp -v modules.tar.gz "${PATCH_DIR}/" || error_exit "Failed to copy modules.tar.gz" ${EXIT_BUILD_FAILURE}
    log_info "  Copied: modules.tar.gz"

    cp -v arch/arm64/boot/Image.gz "${PATCH_DIR}/" || error_exit "Failed to copy Image.gz" ${EXIT_BUILD_FAILURE}
    log_info "  Copied: Image.gz"

    cp -v arch/arm64/boot/dts/broadcom/bcm2712-rpi-5-b.dtb "${PATCH_DIR}/" || error_exit "Failed to copy DTB" ${EXIT_BUILD_FAILURE}
    log_info "  Copied: bcm2712-rpi-5-b.dtb"

    if [[ -f arch/arm/boot/dts/overlays/adsd3500-adsd3100.dtbo ]]; then
        cp -v arch/arm/boot/dts/overlays/adsd3500-adsd3100.dtbo "${PATCH_DIR}/" || log_warning "Failed to copy device tree overlay"
        log_info "  Copied: adsd3500-adsd3100.dtbo"
    else
        log_warning "Device tree overlay not found: arch/arm/boot/dts/overlays/adsd3500-adsd3100.dtbo"
    fi

    log_success "Build kernel completed successfully"
}

# Generate software version information
sw_version_info() {
    log_step "Generating software version information"

    local version_file="${PATCH_DIR}/sw-versions"

    {
        echo "SDK    Version : ${SDK_VERSION}"
        echo "Branch Name    : ${BRANCH}"
        echo "Branch Commit  : ${BR_COMMIT}"
        echo "Build  Date    : $(date)"
        echo "Kernel Version : ${KERNEL_VERSION}"
        echo "Script Version : ${SCRIPT_VERSION}"
    } > "${version_file}" || error_exit "Failed to create version file" ${EXIT_GENERAL_ERROR}

    log_info "Version information:"
    cat "${version_file}" | tee -a "${LOG_FILE}"

    log_success "Software version file created: ${version_file}"
}

# Copy Ubuntu overlay files
copy_ubuntu_overlay() {
    log_step "Copying Ubuntu overlay files"

    local overlay_src="${ROOTDIR}/patches/ubuntu_overlay"

    if [[ ! -d "${overlay_src}" ]]; then
        log_warning "Ubuntu overlay directory not found: ${overlay_src}"
        log_warning "Skipping overlay copy"
        return 0
    fi

    if ! cp -rf "${overlay_src}" "${PATCH_DIR}/" 2>&1 | tee -a "${LOG_FILE}"; then
        error_exit "Failed to copy Ubuntu overlay" ${EXIT_GENERAL_ERROR}
    fi

    log_success "Ubuntu overlay copied successfully"
}

# Create distribution package
create_package() {
    log_step "Creating distribution package"

    cd "${ROOTDIR}" || error_exit "Failed to return to root directory" ${EXIT_ARCHIVE_ERROR}

    # Copy apply_patch.sh script
    local apply_script="${ROOTDIR}/scripts/system_upgrade/apply_patch.sh"
    if [[ -f "${apply_script}" ]]; then
        cp "${apply_script}" "${PATCH_DIR}/" || log_warning "Failed to copy apply_patch.sh"
        log_info "Copied: apply_patch.sh"
    else
        log_warning "apply_patch.sh not found at ${apply_script}"
    fi

    local archive_name="RPI_ToF_ADSD3500_REL_PATCH_$(date +"%d%b%y").zip"
    local patch_dir_name=$(basename "${PATCH_DIR}")
    local build_dir=$(dirname "${PATCH_DIR}")

    log_info "Creating archive: ${archive_name}"
    log_info "Archiving directory: ${patch_dir_name}"

    # Change to build directory where patch directory is located
    cd "${build_dir}" || error_exit "Failed to change to build directory" ${EXIT_ARCHIVE_ERROR}

    # Create ZIP archive (capture output to avoid SIGPIPE from head)
    local zip_output
    zip_output=$(zip -r "${archive_name}" "${patch_dir_name}" 2>&1)
    local zip_status=$?

    # Log the output (first 20 lines to console, full output to log file)
    echo "${zip_output}" >> "${LOG_FILE}"
    echo "${zip_output}" | head -20

    if [[ ${zip_status} -ne 0 ]]; then
        error_exit "Failed to create archive (zip exit code: ${zip_status})" ${EXIT_ARCHIVE_ERROR}
    fi

    # Verify archive was created
    if [[ ! -f "${archive_name}" ]]; then
        error_exit "Archive file not found after creation: ${archive_name}" ${EXIT_ARCHIVE_ERROR}
    fi

    local archive_size=$(stat -c%s "${archive_name}" 2>/dev/null || stat -f%z "${archive_name}" 2>/dev/null)
    log_success "Archive created: ${archive_name} ($(numfmt --to=iec-i --suffix=B ${archive_size} 2>/dev/null || echo "${archive_size} bytes"))"

    # Move archive to root directory
    mv "${archive_name}" "${ROOTDIR}/" || error_exit "Failed to move archive to root directory" ${EXIT_ARCHIVE_ERROR}
    log_info "Archive moved to: ${ROOTDIR}/${archive_name}"

    # Return to root directory
    cd "${ROOTDIR}" || error_exit "Failed to return to root directory" ${EXIT_ARCHIVE_ERROR}

    # Cleanup patch directory
    log_info "Cleaning up temporary patch directory..."
    rm -rf "${PATCH_DIR}" || log_warning "Failed to remove temporary patch directory"

    log_success "Package creation completed: ${archive_name}"
}


#===============================================================================
# MAIN EXECUTION
#===============================================================================

main() {
    log_step "Starting Raspberry Pi ToF ADSD3500 Build Process"
    log_info "Script version: ${SCRIPT_VERSION}"

    # Validate arguments first
    validate_arguments "$@"

    # Check dependencies
    check_dependencies

    # Initialize environment
    init_environment

    # Execute build steps
    download_linux_kernel
    apply_git_format_patches
    build_kernel
    copy_ubuntu_overlay
    sw_version_info
    create_package

    # Calculate execution time
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local hours=$((duration / 3600))
    local minutes=$(((duration % 3600) / 60))
    local seconds=$((duration % 60))

    log_step "Build Process Completed Successfully"
    log_success "Total execution time: ${hours}h ${minutes}m ${seconds}s"
    log_info "Log file: ${LOG_FILE}"

}

# Trap errors and interrupts
trap 'error_exit "Script interrupted or error occurred" ${EXIT_GENERAL_ERROR}' ERR INT TERM

# Execute main function
main "$@"

exit ${EXIT_SUCCESS}
