#!/bin/bash

set -e

# Function to display help
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Build Docker container for ADCAM testing in a clean environment.

Options:
    -h, --help          Show this help message
    -j, --jobs N        Number of parallel build jobs (default: 6)
    -t, --tag NAME      Docker image tag name (default: adcam-test)
    -b, --branch NAME   Git branch to checkout and build (default: current branch)
    --no-cache          Build without using Docker cache
    --nvidia            Build for NVIDIA Jetson target

Examples:
    $0                          # Build with defaults
    $0 -j 4 --no-cache          # Build with 4 jobs, no cache
    $0 -b feature-branch        # Build specific branch
    $0 --nvidia                 # Build for Jetson target
EOF
    exit 0
}

# Default values
JOBS=6
IMAGE_TAG="adcam-test"
DOCKER_OPTS="--progress=plain"
NVIDIA_BUILD=false
GIT_BRANCH=""

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -j|--jobs)
            JOBS="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -b|--branch)
            GIT_BRANCH="$2"
            shift 2
            ;;
        --no-cache)
            DOCKER_OPTS="$DOCKER_OPTS --no-cache"
            shift
            ;;
        --nvidia)
            NVIDIA_BUILD=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Dockerfile exists
DOCKERFILE="Dockerfile.test"
if [ ! -f "$DOCKERFILE" ]; then
    echo "Error: $DOCKERFILE not found"
    exit 1
fi

# Get workspace root (2 levels up from docker/)
WORKSPACE_ROOT="$(cd ../.. && pwd)"

# Check for ToFi libraries in multiple locations
LIBS_DIR=""
if [ -d "$WORKSPACE_ROOT/libs" ]; then
    LIBS_DIR="$WORKSPACE_ROOT/libs"
    echo "Found ToFi libraries at $LIBS_DIR (inside repo)"
elif [ -d "$WORKSPACE_ROOT/../libs" ]; then
    LIBS_DIR="$WORKSPACE_ROOT/../libs"
    echo "Found ToFi libraries at $LIBS_DIR (parent directory)"
else
    echo "Warning: ToFi libraries not found!"
    echo "Searched locations:"
    echo "  1. $WORKSPACE_ROOT/libs (inside repo)"
    echo "  2. $WORKSPACE_ROOT/../libs (parent directory)"
    echo ""
    echo "Expected files:"
    echo "  - libtofi_compute.so"
    echo "  - libtofi_config.so"
    echo ""
    echo "Tests will build but may not run correctly without these libraries."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Always create libs directory for Docker context
rm -rf libs
mkdir -p libs

# Copy libs to docker context if found
if [ -n "$LIBS_DIR" ]; then
    cp "$LIBS_DIR"/*.so libs/ 2>/dev/null || true
    
    # Verify critical libraries are present
    if [ -f "libs/libtofi_compute.so" ] && [ -f "libs/libtofi_config.so" ]; then
        echo "✓ Copied libtofi_compute.so and libtofi_config.so"
    else
        echo "Warning: Some ToFi libraries may be missing"
        ls -la libs/ 2>/dev/null || echo "  (empty directory)"
    fi
else
    echo "Creating empty libs directory for Docker context"
    touch libs/.gitkeep
fi

echo "========================================"
echo "Building ADCAM Test Docker Image"
echo "========================================"
echo "Image: $IMAGE_TAG"
echo "Jobs: $JOBS"
echo "Workspace: $WORKSPACE_ROOT"
echo "Git Branch: ${GIT_BRANCH:-'(current)'}"
echo "NVIDIA Build: $NVIDIA_BUILD"
echo ""

# Prepare local code (exclude build artifacts)
echo "Preparing local code..."
rm -rf ./local_code
mkdir -p ./local_code

# Use rsync to copy, excluding unnecessary directories
# NOTE: .git is included to support git submodules and branch operations
rsync -a --exclude='build' \
         --exclude='build-*' \
         --exclude='tests/docker/local_code' \
         --exclude='tests/docker/libs' \
         --exclude='**/test-results' \
         --exclude='**/test-logs' \
         --exclude='*.pyc' \
         --exclude='__pycache__' \
         "$WORKSPACE_ROOT/" ./local_code/

echo ""
echo "========================================"
echo "Cleaning up old containers..."
echo "========================================"
# Stop and remove any containers using this image
CONTAINERS=$(docker ps -a --filter "ancestor=$IMAGE_TAG:latest" -q 2>/dev/null)
if [ -n "$CONTAINERS" ]; then
    echo "Found existing containers, removing..."
    docker stop $CONTAINERS 2>/dev/null || true
    docker rm $CONTAINERS 2>/dev/null || true
    echo "✓ Cleaned up old containers"
else
    echo "No existing containers found"
fi

echo ""
echo "Building Docker image..."

# Set NVIDIA build arg based on flag
if $NVIDIA_BUILD; then
    NVIDIA_ARG="ON"
else
    NVIDIA_ARG="OFF"
fi

docker build \
    $DOCKER_OPTS \
    --build-arg BUILD_JOBS=$JOBS \
    --build-arg GIT_BRANCH="$GIT_BRANCH" \
    --build-arg NVIDIA_BUILD=$NVIDIA_ARG \
    -f $DOCKERFILE \
    -t $IMAGE_TAG:latest \
    . 2>&1 | tee build_output.log

BUILD_EXIT_CODE=${PIPESTATUS[0]}

if [ $BUILD_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "✗ Docker build failed"
    echo "Check build_output.log for details"
    exit $BUILD_EXIT_CODE
fi

# Cleanup temporary files
echo ""
echo "Cleaning up temporary files..."
rm -rf ./local_code

echo ""
echo "✓ Docker image built successfully!"
echo ""
echo "Image: $IMAGE_TAG:latest"
echo ""
echo "To run tests:"
echo "  cd tests/docker"
echo "  bash ./run_tests.sh -f ../test_csvs/system_test_list.csv -o ./test-results"
echo ""
echo "Or use the main test wrapper:"
echo "  cd tests"
echo "  bash ./start_tests.sh -f test_csvs/system_test_list.csv -o ./test-results"
