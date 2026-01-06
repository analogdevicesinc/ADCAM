#!/bin/bash

#############################################################################
# ADCAM Build Script
# Builds the ADCAM SDK with RGB camera support
#############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
BUILD_TYPE="Release"
WITH_RGB_CAMERA="ON"
BUILD_DIR="build"
CLEAN_BUILD=0
NUM_JOBS=$(nproc)
VERBOSE=0

#############################################################################
# Functions
#############################################################################

print_header() {
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ADCAM SDK Build Script                                ${BLUE}║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_usage() {
    cat << USAGE
Usage: $0 [OPTIONS]

Build the ADCAM SDK with configurable options.

OPTIONS:
    -h, --help              Show this help message
    -c, --clean             Clean build (remove build directory first)
    -d, --debug             Build in Debug mode (default: Release)
    -r, --release           Build in Release mode (default)
    --no-rgb                Build without RGB camera support
    --rgb                   Build with RGB camera support (default)
    -j, --jobs N            Number of parallel jobs (default: $(nproc))
    -b, --build-dir DIR     Build directory (default: build)
    -v, --verbose           Verbose output
    --test                  Run tests after build

EXAMPLES:
    # Standard build with RGB camera
    $0

    # Clean build in debug mode
    $0 --clean --debug

    # Build without RGB camera, 4 jobs
    $0 --no-rgb -j 4

    # Verbose clean build
    $0 -c -v

USAGE
}

check_dependencies() {
    print_info "Checking dependencies..."
    
    local missing_deps=0
    
    # Check for required tools
    for cmd in cmake make gcc g++ pkg-config; do
        if ! command -v $cmd &> /dev/null; then
            print_error "Required tool '$cmd' not found"
            missing_deps=1
        fi
    done
    
    # Check for GStreamer if RGB camera is enabled
    if [ "$WITH_RGB_CAMERA" = "ON" ]; then
        if ! pkg-config --exists gstreamer-1.0; then
            print_error "GStreamer not found (required for RGB camera)"
            print_info "Install with: sudo apt-get install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev"
            missing_deps=1
        fi
    fi
    
    if [ $missing_deps -eq 1 ]; then
        print_error "Missing dependencies. Please install them first."
        exit 1
    fi
    
    print_info "All dependencies found ✓"
}

configure_cmake() {
    print_info "Configuring CMake..."
    
    local cmake_args=(
        "-DCMAKE_BUILD_TYPE=$BUILD_TYPE"
        "-DWITH_RGB_CAMERA=$WITH_RGB_CAMERA"
        "-DUSE_DEPTH_COMPUTE_OPENSOURCE=ON"
    )
    
    if [ $VERBOSE -eq 1 ]; then
        cmake_args+=("-DCMAKE_VERBOSE_MAKEFILE=ON")
    fi
    
    print_info "Configuration:"
    print_info "  Build type:    $BUILD_TYPE"
    print_info "  RGB camera:    $WITH_RGB_CAMERA"
    print_info "  Build dir:     $BUILD_DIR"
    print_info "  Jobs:          $NUM_JOBS"
    echo ""
    
    cmake "${cmake_args[@]}" .. || {
        print_error "CMake configuration failed"
        exit 1
    }
    
    print_info "CMake configuration completed ✓"
}

build_project() {
    print_info "Building project with $NUM_JOBS parallel jobs..."
    
    local make_args="-j$NUM_JOBS"
    if [ $VERBOSE -eq 1 ]; then
        make_args="$make_args VERBOSE=1"
    fi
    
    make $make_args || {
        print_error "Build failed"
        exit 1
    }
    
    print_info "Build completed ✓"
}

print_summary() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  Build Summary                                            ${GREEN}║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Build type:       ${GREEN}$BUILD_TYPE${NC}"
    echo -e "  RGB camera:       ${GREEN}$WITH_RGB_CAMERA${NC}"
    echo -e "  Build directory:  ${GREEN}$BUILD_DIR${NC}"
    echo ""
    echo -e "${GREEN}Built artifacts:${NC}"
    
    # List key outputs (using paths relative to current dir since we're in build/)
    if [ -f "libaditof/sdk/libaditof.so" ]; then
        local lib_size=$(du -h libaditof/sdk/libaditof.so | cut -f1)
        echo -e "  ✓ libaditof.so ($lib_size)"
    fi
    
    if [ -f "examples/first-frame/first-frame" ]; then
        echo -e "  ✓ first-frame example"
    fi
    
    if [ -f "examples/data_collect/data_collect" ]; then
        echo -e "  ✓ data_collect example"
    fi
    
    if [ -f "examples/tof-viewer/ADIToFGUI" ]; then
        echo -e "  ✓ tof-viewer (ADIToFGUI)"
    fi
    
    echo ""
    echo -e "${GREEN}Quick test commands:${NC}"
    echo -e "  cd $BUILD_DIR/examples/data_collect && ./data_collect --m 0 --n 10"
    echo -e "  cd $BUILD_DIR/examples/first-frame && ./first-frame"
    echo ""
}

#############################################################################
# Main Script
#############################################################################

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            print_usage
            exit 0
            ;;
        -c|--clean)
            CLEAN_BUILD=1
            shift
            ;;
        -d|--debug)
            BUILD_TYPE="Debug"
            shift
            ;;
        -r|--release)
            BUILD_TYPE="Release"
            shift
            ;;
        --no-rgb)
            WITH_RGB_CAMERA="OFF"
            shift
            ;;
        --rgb)
            WITH_RGB_CAMERA="ON"
            shift
            ;;
        -j|--jobs)
            NUM_JOBS="$2"
            shift 2
            ;;
        -b|--build-dir)
            BUILD_DIR="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        --test)
            RUN_TESTS=1
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Print header
print_header

# Get to project root
cd "$(dirname "$0")"

# Check dependencies
check_dependencies

# Clean build if requested
if [ $CLEAN_BUILD -eq 1 ]; then
    print_warn "Cleaning build directory: $BUILD_DIR"
    rm -rf "$BUILD_DIR"
fi

# Create build directory
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Configure
configure_cmake

# Build
build_project

# Print summary
print_summary

# Success
echo -e "${GREEN}✓ Build completed successfully!${NC}"
echo ""

exit 0
