#!/bin/bash
#===============================================================================
# NVIDIA Jetson Orin Nano ToF ADSD3500 Build Script
#
# Description: Builds custom Linux kernel with ADI ToF camera support for
#              NVIDIA Jetson Orin Nano (JetPack 6.2.1, L4T 36.4.4)
#
# Usage: ./runme.sh <sdk_version> <tof_branch_name>
#        Example: ./runme.sh 0.0.2 main
#
# Requirements: Ubuntu 22.04, ~50GB disk space, internet connection
#
# Exit Codes:
#   0 - Success
#   1 - Invalid arguments
#   2 - Dependency error
#   3 - Download error
#   4 - Build error
#   5 - Archive error
#
# Author: Analog Devices Inc.
# Version: 2.0
# Date: 2026-03-13
#===============================================================================

set -euo pipefail

#===============================================================================
# CONFIGURATION
#===============================================================================

readonly SCRIPT_VERSION="2.0"
readonly ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly START_TIME=$(date +%s)

# Build configuration
readonly TOOLCHAIN_URL="https://developer.download.nvidia.com/embedded/L4T/bootlin/aarch64--glibc--stable-final.tar.gz"
readonly JETSON_LINUX_URL="https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v4.4/release/Jetson_Linux_r36.4.4_aarch64.tbz2"
readonly RELEASE_TAG="jetson_36.4.4"
readonly KERNEL_VERSION="5.15.148-adi-tegra"
readonly JETPACK_VERSION="6.2.1"
readonly L4T_VERSION="36.4.4"

# Component list for patching
readonly COMPONENTS="nv-public kernel-jammy-src nvidia-oot"

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_INVALID_ARGS=1
readonly EXIT_DEPENDENCY_ERROR=2
readonly EXIT_DOWNLOAD_ERROR=3
readonly EXIT_BUILD_ERROR=4
readonly EXIT_ARCHIVE_ERROR=5

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Global variables
SDK_VERSION=""
BRANCH=""
BR_COMMIT=""
PATCH_DIR=""
LOG_FILE=""
BUILD_DIR=""

#===============================================================================
# LOGGING FUNCTIONS
#===============================================================================

# Strip ANSI color codes for log file
strip_colors() {
    sed 's/\x1b\[[0-9;]*m//g'
}

log_info() {
    local message="[INFO] $*"
    echo -e "${BLUE}${message}${NC}"
    [[ -n "${LOG_FILE}" ]] && echo "${message}" | strip_colors >> "${LOG_FILE}" 2>/dev/null || true
}

log_success() {
    local message="[SUCCESS] $*"
    echo -e "${GREEN}${message}${NC}"
    [[ -n "${LOG_FILE}" ]] && echo "${message}" | strip_colors >> "${LOG_FILE}" 2>/dev/null || true
}

log_warning() {
    local message="[WARNING] $*"
    echo -e "${YELLOW}${message}${NC}"
    [[ -n "${LOG_FILE}" ]] && echo "${message}" | strip_colors >> "${LOG_FILE}" 2>/dev/null || true
}

log_error() {
    local message="[ERROR] $*"
    echo -e "${RED}${message}${NC}" >&2
    [[ -n "${LOG_FILE}" ]] && echo "${message}" | strip_colors >> "${LOG_FILE}" 2>/dev/null || true
}

log_debug() {
    local message="[DEBUG] $*"
    echo -e "${CYAN}${message}${NC}"
    [[ -n "${LOG_FILE}" ]] && echo "${message}" | strip_colors >> "${LOG_FILE}" 2>/dev/null || true
}

log_step() {
    echo ""
    local message="=== $* ==="
    echo -e "${GREEN}${message}${NC}"
    echo ""
    [[ -n "${LOG_FILE}" ]] && echo -e "\n${message}\n" | strip_colors >> "${LOG_FILE}" 2>/dev/null || true
}

error_exit() {
    local message="$1"
    local exit_code="${2:-${EXIT_BUILD_ERROR}}"
    log_error "${message}"
    [[ -n "${LOG_FILE}" ]] && log_error "Check log: ${LOG_FILE}"
    exit "${exit_code}"
}

#===============================================================================
# UTILITY FUNCTIONS
#===============================================================================

check_dependencies() {
    log_step "Checking dependencies"

    local required_commands=(
        "git"
        "make"
        "gcc"
        "wget"
        "tar"
        "zip"
        "bc"
    )

    local missing_commands=()

    for cmd in "${required_commands[@]}"; do
        if ! command -v "${cmd}" &> /dev/null; then
            missing_commands+=("${cmd}")
            log_warning "Missing: ${cmd}"
        else
            log_debug "Found: ${cmd}"
        fi
    done

    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        log_error "Missing required commands: ${missing_commands[*]}"
        log_info "Install with: sudo apt install git make gcc wget tar zip bc"
        error_exit "Dependency check failed" ${EXIT_DEPENDENCY_ERROR}
    fi

    log_success "All dependencies satisfied"
}

validate_arguments() {
    log_step "Validating arguments"

    if [[ $# -ne 2 ]]; then
        log_error "Invalid number of arguments"
        echo ""
        echo "Usage: $0 <sdk_version> <tof_branch_name>"
        echo ""
        echo "Arguments:"
        echo "  sdk_version       : SDK version string (e.g., 0.0.2)"
        echo "  tof_branch_name   : Git branch name (e.g., main)"
        echo ""
        echo "Example:"
        echo "  $0 0.0.2 main"
        echo ""
        error_exit "Invalid arguments" ${EXIT_INVALID_ARGS}
    fi

    SDK_VERSION="$1"
    BRANCH="$2"

    if [[ -z "${SDK_VERSION}" ]]; then
        error_exit "SDK version cannot be empty" ${EXIT_INVALID_ARGS}
    fi

    if [[ -z "${BRANCH}" ]]; then
        error_exit "Branch name cannot be empty" ${EXIT_INVALID_ARGS}
    fi

    log_info "SDK Version: ${SDK_VERSION}"
    log_info "Branch: ${BRANCH}"

    log_success "Arguments validated"
}

init_environment() {
    log_step "Initializing build environment"

    # Get current branch commit
    BR_COMMIT=$(git log -1 --pretty=format:%h 2>/dev/null || echo "unknown")
    log_info "Repository commit: ${BR_COMMIT}"

    # Create build directory structure
    BUILD_DIR="${ROOTDIR}/build"
    mkdir -p "${BUILD_DIR}" || error_exit "Failed to create build directory" ${EXIT_BUILD_ERROR}

    # Create patch directory
    PATCH_DIR="${BUILD_DIR}/NVIDIA_ToF_ADSD3500_REL_PATCH_$(date +"%d%b%y")"
    mkdir -p "${PATCH_DIR}" || error_exit "Failed to create patch directory" ${EXIT_BUILD_ERROR}
    log_info "Patch directory: ${PATCH_DIR}"

    # Create logs directory and initialize log file
    local log_dir="${BUILD_DIR}/logs"
    mkdir -p "${log_dir}" || error_exit "Failed to create logs directory" ${EXIT_BUILD_ERROR}
    LOG_FILE="${log_dir}/nvidia_build_$(date +%Y%m%d_%H%M%S).log"
    touch "${LOG_FILE}" || error_exit "Failed to create log file" ${EXIT_BUILD_ERROR}
    log_info "Log file: ${LOG_FILE}"

    log_success "Environment initialized"
}

#===============================================================================
# BUILD FUNCTIONS
#===============================================================================

configure_toolchain() {
    log_step "Configuring cross-compilation toolchain"

    local toolchain_dir="${BUILD_DIR}/aarch64--glibc--stable-final"
    local toolchain_archive="${BUILD_DIR}/aarch64--glibc--stable-final.tar.gz"

    # Check if toolchain already exists
    if [[ -d "${toolchain_dir}/bin" ]] && [[ -f "${toolchain_dir}/bin/aarch64-linux-gcc" ]]; then
        log_info "Toolchain already installed"
        log_success "Toolchain configuration skipped"
        return 0
    fi

    cd "${BUILD_DIR}" || error_exit "Failed to change to build directory" ${EXIT_BUILD_ERROR}

    # Download toolchain if not present
    if [[ ! -f "${toolchain_archive}" ]]; then
        log_info "Downloading toolchain from NVIDIA..."
        log_debug "URL: ${TOOLCHAIN_URL}"
        wget -q --show-progress "${TOOLCHAIN_URL}" || error_exit "Failed to download toolchain" ${EXIT_DOWNLOAD_ERROR}
        log_success "Toolchain downloaded"
    else
        log_info "Toolchain archive already exists"
    fi

    # Extract toolchain
    log_info "Extracting toolchain..."
    mkdir -p "${toolchain_dir}"
    tar -xzf "${toolchain_archive}" -C "${toolchain_dir}" --strip-components=1 || error_exit "Failed to extract toolchain" ${EXIT_BUILD_ERROR}

    # Verify toolchain
    if [[ ! -f "${toolchain_dir}/bin/aarch64-linux-gcc" ]]; then
        error_exit "Toolchain extraction failed: compiler not found" ${EXIT_BUILD_ERROR}
    fi

    # Cleanup archive
    rm -f "${toolchain_archive}" || log_warning "Failed to remove toolchain archive"

    log_success "Toolchain configured: ${toolchain_dir}"
}

download_bsp_source() {
    log_step "Downloading NVIDIA BSP sources"

    local bsp_dir="${BUILD_DIR}/Linux_for_Tegra"

    # Check if BSP already downloaded
    if [[ -d "${bsp_dir}" ]] && [[ -f "${bsp_dir}/source_sync.sh" ]]; then
        log_info "BSP already downloaded"
        log_success "BSP download skipped"
        return 0
    fi

    cd "${BUILD_DIR}" || error_exit "Failed to change to build directory" ${EXIT_BUILD_ERROR}

    log_info "Downloading NVIDIA Jetson Linux ${L4T_VERSION} BSP..."
    log_debug "URL: ${JETSON_LINUX_URL}"

    if ! wget -q --show-progress -O- "${JETSON_LINUX_URL}" | tar xj; then
        error_exit "Failed to download/extract BSP" ${EXIT_DOWNLOAD_ERROR}
    fi

    if [[ ! -d "${bsp_dir}" ]]; then
        error_exit "BSP extraction failed: Linux_for_Tegra not found" ${EXIT_BUILD_ERROR}
    fi

    log_success "BSP downloaded and extracted"
}

download_linux_kernel() {
    log_step "Downloading Linux kernel sources"

    local source_dir="${BUILD_DIR}/Linux_for_Tegra/source"

    # Check if kernel sources already synced
    if [[ -d "${source_dir}/kernel/kernel-jammy-src/.git" ]]; then
        log_info "Kernel sources already synced"
        log_success "Kernel source download skipped"
        return 0
    fi

    cd "${BUILD_DIR}/Linux_for_Tegra" || error_exit "Failed to change to L4T directory" ${EXIT_BUILD_ERROR}

    log_info "Syncing kernel sources for release tag: ${RELEASE_TAG}"
    log_info "This may take several minutes..."

    # Enter source directory
    pushd source > /dev/null || error_exit "Failed to enter source directory" ${EXIT_BUILD_ERROR}

    # Make source_sync.sh executable if needed
    if [[ ! -x source_sync.sh ]]; then
        chmod +x source_sync.sh || error_exit "Failed to make source_sync.sh executable" ${EXIT_BUILD_ERROR}
    fi

    # Run source sync
    if ! ./source_sync.sh -t "${RELEASE_TAG}"; then
        popd > /dev/null
        error_exit "Kernel source sync failed" ${EXIT_DOWNLOAD_ERROR}
    fi

    popd > /dev/null

    log_success "Kernel sources synced for JetPack ${JETPACK_VERSION}"
}

apply_git_format_patches() {
    log_step "Applying ADI ToF patches"

    # Configure git for non-interactive operation
    export GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-ADI ToF Build System}"
    export GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-tof@analog.com}"
    export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-ADI ToF Build System}"
    export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-tof@analog.com}"

    local l4t_dir="${BUILD_DIR}/Linux_for_Tegra"
    cd "${l4t_dir}" || error_exit "Failed to change to L4T directory" ${EXIT_BUILD_ERROR}

    local patch_count=0

    for component in ${COMPONENTS}; do
        case "${component}" in
            "nv-public")
                log_info "Applying patches to nv-public component..."
                local nv_public_dir="${l4t_dir}/source/hardware/nvidia/t23x/nv-public"

                if [[ ! -d "${nv_public_dir}" ]]; then
                    error_exit "nv-public directory not found: ${nv_public_dir}" ${EXIT_BUILD_ERROR}
                fi

                pushd "${nv_public_dir}" > /dev/null || error_exit "Failed to enter nv-public directory" ${EXIT_BUILD_ERROR}

                log_debug "Resetting nv-public to origin/l4t/l4t-r36.4.4..."
                git reset --hard origin/l4t/l4t-r36.4.4 || {
                    log_warning "Failed to reset nv-public, attempting fetch..."
                    git fetch origin l4t/l4t-r36.4.4 || error_exit "Failed to fetch nv-public branch" ${EXIT_BUILD_ERROR}
                    git reset --hard origin/l4t/l4t-r36.4.4 || error_exit "Failed to reset nv-public after fetch" ${EXIT_BUILD_ERROR}
                }

                local patch_dir="${ROOTDIR}/patches/hardware/nvidia/t23x/nv-public"
                if [[ -d "${patch_dir}" ]]; then
                    local patches=("${patch_dir}"/*.patch)
                    if [[ -f "${patches[0]}" ]]; then
                        log_info "Found ${#patches[@]} patches to apply"

                        # Apply all patches at once (more efficient and avoids buffering issues)
                        log_info "Applying all nv-public patches..."
                        if ! git am "${patch_dir}"/*.patch; then
                            log_error "Failed to apply patches"
                            log_error "Git status:"
                            git status
                            git am --abort 2>/dev/null || true
                            error_exit "Failed to apply nv-public patches" ${EXIT_BUILD_ERROR}
                        fi

                        # Count applied patches
                        local applied=$(git log --oneline origin/l4t/l4t-r36.4.4..HEAD | wc -l)
                        patch_count=$((patch_count + applied))
                        log_success "Applied ${applied} patches to nv-public"
                    else
                        log_warning "No patches found in ${patch_dir}"
                    fi
                fi

                popd > /dev/null
                log_success "nv-public patches applied"
                ;;

            "kernel-jammy-src")
                log_info "Applying patches to kernel-jammy-src component..."
                local kernel_dir="${l4t_dir}/source/kernel/kernel-jammy-src"

                if [[ ! -d "${kernel_dir}" ]]; then
                    error_exit "kernel-jammy-src directory not found: ${kernel_dir}" ${EXIT_BUILD_ERROR}
                fi

                pushd "${kernel_dir}" > /dev/null || error_exit "Failed to enter kernel directory" ${EXIT_BUILD_ERROR}

                log_debug "Resetting kernel-jammy-src to ${RELEASE_TAG}..."
                git reset --hard "${RELEASE_TAG}" || error_exit "Failed to reset kernel" ${EXIT_BUILD_ERROR}

                local patch_dir="${ROOTDIR}/patches/kernel/kernel-jammy-src"
                if [[ -d "${patch_dir}" ]]; then
                    local patches=("${patch_dir}"/*.patch)
                    if [[ -f "${patches[0]}" ]]; then
                        log_info "Found ${#patches[@]} patches to apply"

                        # Apply all patches at once
                        log_info "Applying all kernel-jammy-src patches..."
                        if ! git am "${patch_dir}"/*.patch; then
                            log_error "Failed to apply patches"
                            log_error "Git status:"
                            git status
                            git am --abort 2>/dev/null || true
                            error_exit "Failed to apply kernel-jammy-src patches" ${EXIT_BUILD_ERROR}
                        fi

                        # Count applied patches
                        local applied=$(git log --oneline "${RELEASE_TAG}"..HEAD | wc -l)
                        patch_count=$((patch_count + applied))
                        log_success "Applied ${applied} patches to kernel-jammy-src"
                    else
                        log_warning "No patches found in ${patch_dir}"
                    fi
                fi

                popd > /dev/null
                log_success "kernel-jammy-src patches applied"
                ;;

            "nvidia-oot")
                log_info "Applying patches to nvidia-oot component..."
                local nvidia_oot_dir="${l4t_dir}/source/nvidia-oot/drivers"

                if [[ ! -d "${nvidia_oot_dir}" ]]; then
                    error_exit "nvidia-oot directory not found: ${nvidia_oot_dir}" ${EXIT_BUILD_ERROR}
                fi

                pushd "${nvidia_oot_dir}" > /dev/null || error_exit "Failed to enter nvidia-oot directory" ${EXIT_BUILD_ERROR}

                log_debug "Resetting nvidia-oot to ${RELEASE_TAG}..."
                git reset --hard "${RELEASE_TAG}" || error_exit "Failed to reset nvidia-oot" ${EXIT_BUILD_ERROR}

                local patch_dir="${ROOTDIR}/patches/nvidia-oot/drivers"
                if [[ -d "${patch_dir}" ]]; then
                    local patches=("${patch_dir}"/*.patch)
                    if [[ -f "${patches[0]}" ]]; then
                        log_info "Found ${#patches[@]} patches to apply"

                        # Apply all patches at once
                        log_info "Applying all nvidia-oot patches..."
                        if ! git am "${patch_dir}"/*.patch; then
                            log_error "Failed to apply patches"
                            log_error "Git status:"
                            git status
                            git am --abort 2>/dev/null || true
                            error_exit "Failed to apply nvidia-oot patches" ${EXIT_BUILD_ERROR}
                        fi

                        # Count applied patches
                        local applied=$(git log --oneline "${RELEASE_TAG}"..HEAD | wc -l)
                        patch_count=$((patch_count + applied))
                        log_success "Applied ${applied} patches to nvidia-oot"
                    else
                        log_warning "No patches found in ${patch_dir}"
                    fi
                fi

                popd > /dev/null
                log_success "nvidia-oot patches applied"
                ;;

            *)
                error_exit "Invalid component: ${component}" ${EXIT_BUILD_ERROR}
                ;;
        esac
    done

    log_success "Applied ${patch_count} patches across ${COMPONENTS// /, } components"
}

build_kernel_Image() {
    log_step "Building Linux kernel and modules"

    local source_dir="${BUILD_DIR}/Linux_for_Tegra/source"
    cd "${source_dir}" || error_exit "Failed to change to source directory" ${EXIT_BUILD_ERROR}

    # Set build environment variables
    export INSTALL_MOD_PATH="${source_dir}/modules"
    export KERNEL_HEADERS="${source_dir}/kernel/kernel-jammy-src"

    # Check if cross-compilation is needed
    if [[ ! -f "/etc/nv_tegra_release" ]]; then
        log_info "Cross-compilation mode detected"
        export CROSS_COMPILE="${BUILD_DIR}/aarch64--glibc--stable-final/bin/aarch64-linux-"
        log_debug "CROSS_COMPILE=${CROSS_COMPILE}"
    else
        log_info "Native compilation mode detected"
    fi

    # Clean previous builds
    log_info "Cleaning previous build artifacts..."
    rm -rf modules || true
    make clean || log_warning "make clean reported warnings"

    cd "${KERNEL_HEADERS}" || error_exit "Failed to change to kernel directory" ${EXIT_BUILD_ERROR}
    make distclean || log_warning "make distclean reported warnings"

    cd "${source_dir}" || error_exit "Failed to return to source directory" ${EXIT_BUILD_ERROR}

    # Create output directories
    log_info "Creating output directories..."
    mkdir -p "${source_dir}/modules/boot"
    mkdir -p "${source_dir}/modules/dtb"

    # Calculate build parallelism (leave 2 cores free)
    local num_cores=$(nproc)
    local parallel_jobs=$((num_cores > 2 ? num_cores - 2 : 1))
    log_info "Building with ${parallel_jobs} parallel jobs (${num_cores} cores available)"

    # Build kernel
    log_info "Building kernel image..."
    local kernel_start=$(date +%s)
    if ! make -C kernel -j "${parallel_jobs}"; then
        error_exit "Kernel build failed" ${EXIT_BUILD_ERROR}
    fi
    local kernel_duration=$(($(date +%s) - kernel_start))
    log_success "Kernel built in ${kernel_duration}s"

    # Install kernel
    log_info "Installing kernel..."
    if ! make install -C kernel; then
        error_exit "Kernel install failed" ${EXIT_BUILD_ERROR}
    fi

    # Build out-of-tree modules
    log_info "Building out-of-tree kernel modules..."
    local modules_start=$(date +%s)
    if ! make modules -j "${parallel_jobs}"; then
        error_exit "Module build failed" ${EXIT_BUILD_ERROR}
    fi
    local modules_duration=$(($(date +%s) - modules_start))
    log_success "Modules built in ${modules_duration}s"

    # Install modules
    log_info "Installing modules..."
    if ! make modules_install; then
        error_exit "Module install failed" ${EXIT_BUILD_ERROR}
    fi

    # Build device trees
    log_info "Building device tree blobs..."
    if ! make dtbs -j "${parallel_jobs}"; then
        error_exit "DTB build failed" ${EXIT_BUILD_ERROR}
    fi

    # Copy DTBs
    log_info "Copying device tree blobs..."
    cp -f "${source_dir}/kernel-devicetree/generic-dts/dtbs/"*.dtb "${source_dir}/modules/dtb/" || error_exit "Failed to copy DTBs" ${EXIT_BUILD_ERROR}
    cp -f "${source_dir}/kernel-devicetree/generic-dts/dtbs/"*.dtbo "${source_dir}/modules/dtb/" || error_exit "Failed to copy DTBOs" ${EXIT_BUILD_ERROR}

    log_success "Kernel, modules, and device trees built successfully"

    # Package artifacts
    log_step "Packaging build artifacts"

    # Copy kernel Image
    log_info "Copying kernel Image..."
    if [[ -f "${source_dir}/modules/boot/Image" ]]; then
        cp "${source_dir}/modules/boot/Image" "${PATCH_DIR}/" || error_exit "Failed to copy kernel Image" ${EXIT_BUILD_ERROR}
        local image_size=$(stat -c%s "${PATCH_DIR}/Image" 2>/dev/null || echo "0")
        log_info "Kernel Image size: $((image_size / 1024 / 1024)) MB"
    else
        error_exit "Kernel Image not found" ${EXIT_BUILD_ERROR}
    fi

    # Copy device tree overlays
    log_info "Copying device tree overlays..."
    local dtbo_files=(
        "tegra234-p3767-camera-p3768-adsd3500.dtbo"
        "tegra234-p3767-camera-p3768-dual-adsd3500-adsd3100.dtbo"
        "tegra234-p3767-camera-p3768-dual-adsd3500-adsd3100-arducam-ar0234.dtbo"
    )

    local dtbo_count=0
    for dtbo in "${dtbo_files[@]}"; do
        local dtbo_path="${source_dir}/modules/dtb/${dtbo}"
        if [[ -f "${dtbo_path}" ]]; then
            cp "${dtbo_path}" "${PATCH_DIR}/" || error_exit "Failed to copy ${dtbo}" ${EXIT_BUILD_ERROR}
            log_info "Copied: ${dtbo}"
            dtbo_count=$((dtbo_count + 1))
        else
            log_warning "DTBO not found: ${dtbo}"
        fi
    done
    log_success "Copied ${dtbo_count}/3 device tree overlays"

    # Create kernel modules archive
    log_info "Creating kernel modules archive..."
    cd "${source_dir}/modules" || error_exit "Failed to change to modules directory" ${EXIT_BUILD_ERROR}

    if ! tar --owner root --group root -cjf "${source_dir}/kernel_supplements.tbz2" lib/modules; then
        error_exit "Failed to create modules archive" ${EXIT_BUILD_ERROR}
    fi

    mv "${source_dir}/kernel_supplements.tbz2" "${PATCH_DIR}/" || error_exit "Failed to move modules archive" ${EXIT_BUILD_ERROR}

    local modules_size=$(stat -c%s "${PATCH_DIR}/kernel_supplements.tbz2" 2>/dev/null || echo "0")
    log_info "Modules archive size: $((modules_size / 1024 / 1024)) MB"

    log_success "Build artifacts packaged"
}

copy_ubuntu_overlay() {
    log_step "Copying Ubuntu overlay"

    local overlay_src="${ROOTDIR}/patches/ubuntu_overlay"

    if [[ -d "${overlay_src}" ]]; then
        cp -rf "${overlay_src}" "${PATCH_DIR}/" || error_exit "Failed to copy ubuntu_overlay" ${EXIT_BUILD_ERROR}
        log_success "Ubuntu overlay copied"
    else
        log_warning "ubuntu_overlay directory not found - skipping"
    fi
}

sw_version_info() {
    log_step "Generating software version information"

    local version_file="${PATCH_DIR}/sw-versions"

    {
        echo "SDK    Version : ${SDK_VERSION}"
        echo "Branch Name    : ${BRANCH}"
        echo "Branch Commit  : ${BR_COMMIT}"
        echo "Build  Date    : $(date)"
        echo "Kernel Version : ${KERNEL_VERSION}"
        echo "JetPack Version: ${JETPACK_VERSION}"
        echo "L4T Version    : ${L4T_VERSION}"
        echo "Script Version : ${SCRIPT_VERSION}"
    } > "${version_file}" || error_exit "Failed to create version file" ${EXIT_BUILD_ERROR}

    log_info "Version information:"
    cat "${version_file}"

    log_success "Software version file created: ${version_file}"
}

create_package() {
    log_step "Creating distribution package"

    # Copy apply_patch.sh script
    local apply_script="${ROOTDIR}/scripts/system_upgrade/apply_patch.sh"
    if [[ -f "${apply_script}" ]]; then
        cp "${apply_script}" "${PATCH_DIR}/" || log_warning "Failed to copy apply_patch.sh"
        log_info "Copied: apply_patch.sh"
    else
        log_warning "apply_patch.sh not found at ${apply_script}"
    fi

    # Copy patch_validation.sh script
    local validation_script="${ROOTDIR}/scripts/system_upgrade/patch_validation.sh"
    if [[ -f "${validation_script}" ]]; then
        cp "${validation_script}" "${PATCH_DIR}/" || log_warning "Failed to copy patch_validation.sh"
        log_info "Copied: patch_validation.sh"
    else
        log_warning "patch_validation.sh not found at ${validation_script}"
    fi


    local archive_name="NVIDIA_ToF_ADSD3500_REL_PATCH_$(date +"%d%b%y").zip"
    local patch_dir_name=$(basename "${PATCH_DIR}")

    log_info "Creating archive: ${archive_name}"
    log_info "Archiving directory: ${patch_dir_name}"

    # Change to build directory
    cd "${BUILD_DIR}" || error_exit "Failed to change to build directory" ${EXIT_ARCHIVE_ERROR}

    # Create ZIP archive
    local zip_output
    zip_output=$(zip -r "${archive_name}" "${patch_dir_name}" 2>&1)
    local zip_status=$?

    # Log output
    echo "${zip_output}" >> "${LOG_FILE}"
    echo "${zip_output}" | head -20

    if [[ ${zip_status} -ne 0 ]]; then
        error_exit "Failed to create archive (zip exit code: ${zip_status})" ${EXIT_ARCHIVE_ERROR}
    fi

    # Verify archive
    if [[ ! -f "${archive_name}" ]]; then
        error_exit "Archive file not found after creation: ${archive_name}" ${EXIT_ARCHIVE_ERROR}
    fi

    local archive_size=$(stat -c%s "${archive_name}" 2>/dev/null || stat -f%z "${archive_name}" 2>/dev/null)
    log_success "Archive created: ${archive_name} ($(numfmt --to=iec-i --suffix=B ${archive_size} 2>/dev/null || echo "${archive_size} bytes"))"

    # Move archive to root
    mv "${archive_name}" "${ROOTDIR}/" || error_exit "Failed to move archive to root directory" ${EXIT_ARCHIVE_ERROR}
    log_info "Archive moved to: ${ROOTDIR}/${archive_name}"

    # Return to root
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
    log_step "Starting NVIDIA Jetson Orin Nano ToF ADSD3500 Build Process"
    log_info "Script version: ${SCRIPT_VERSION}"
    log_info "Target: JetPack ${JETPACK_VERSION} (L4T ${L4T_VERSION})"

    # Validate arguments first
    validate_arguments "$@"

    # Check dependencies
    check_dependencies

    # Initialize environment
    init_environment

    # Execute build steps
    configure_toolchain
    download_bsp_source
    download_linux_kernel
    apply_git_format_patches
    build_kernel_Image
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
    log_info "Total execution time: ${hours}h ${minutes}m ${seconds}s"
    log_success "Distribution package ready for deployment"

}

# Trap errors
trap 'error_exit "Script interrupted or failed at line $LINENO" ${EXIT_BUILD_ERROR}' ERR INT TERM

# Execute main function
main "$@"
