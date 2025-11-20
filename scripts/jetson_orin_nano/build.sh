#!/bin/bash

# Function to display help
show_help() {
    cat << EOF
Usage: $0 [OPTIONS] [ADCAM_BRANCH] [LIBADITOF_BRANCH]

Build a Docker container to test ADCAM repository build in a clean environment.

Arguments:
    ADCAM_BRANCH        Branch/tag for ADCAM repository (default: main)
    LIBADITOF_BRANCH    Branch/tag for libaditof submodule (default: main)
                        (ignored when --local is used)

Options:
    -h, --help          Show this help message
    -j, --jobs N        Number of parallel build jobs (default: 6)
    -t, --tag NAME      Docker image tag name (default: adcam-build-test)
    -l, --libs PATH     Path to libs folder to copy into container (required)
    -v, --verbose       Show verbose build output
    --no-cache          Build without using Docker cache
    --local             Use local code from current workspace instead of cloning

Examples:
    $0 -l /path/to/libs                     # Build with main branches
    $0 -l /path/to/libs main main           # Explicitly specify main branches
    $0 -l /path/to/libs feature-branch main # Test a feature branch
    $0 -j 4 -l /path/to/libs main main      # Build with 4 parallel jobs
    $0 --no-cache -l /path/to/libs main main # Force clean build
    $0 --local -l /path/to/libs             # Build using local code

The build output is saved to build_output.log
EOF
    exit 0
}

# Default values
JOBS=6
IMAGE_TAG="adcam-build-test"
DOCKER_OPTS="--progress=plain"
LIBS_PATH=""
USE_LOCAL=false

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
        -l|--libs)
            LIBS_PATH="$2"
            shift 2
            ;;
        -v|--verbose)
            DOCKER_OPTS="$DOCKER_OPTS --no-cache"
            shift
            ;;
        --no-cache)
            DOCKER_OPTS="$DOCKER_OPTS --no-cache"
            shift
            ;;
        --local)
            USE_LOCAL=true
            shift
            ;;
        -*)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

# Check if libs path is provided
if [ -z "$LIBS_PATH" ]; then
    echo "Error: libs path is required. Use -l or --libs to specify the path."
    echo "Use -h or --help for usage information"
    exit 1
fi

# Verify libs path exists
if [ ! -d "$LIBS_PATH" ]; then
    echo "Error: libs path does not exist: $LIBS_PATH"
    exit 1
fi

# Get absolute path
LIBS_PATH=$(realpath "$LIBS_PATH")

# Copy libs to local directory for Docker context
echo "Copying libs from $LIBS_PATH to ./libs..."
rm -rf ./libs
cp -r "$LIBS_PATH" ./libs

# Handle local mode
if [ "$USE_LOCAL" = true ]; then
    echo "Using local code from workspace..."
    
    # Get the workspace root (two levels up from this script)
    WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    
    # Copy local code, excluding build directories and scripts
    echo "Copying local workspace to ./local_code..."
    rm -rf ./local_code
    mkdir -p ./local_code
    
    # Use rsync for efficient copying with exclusions
    rsync -a --exclude='build' \
             --exclude='libaditof/build' \
             --exclude='scripts' \
             --exclude='.git' \
             "$WORKSPACE_ROOT/" ./local_code/
    
    echo "  Source: $WORKSPACE_ROOT"
    echo "  Excluded: build/, libaditof/build/, scripts/, .git/"
    
    DOCKERFILE="Dockerfile.local"
else
    # Get branch arguments (remaining positional parameters)
    ADCAM_BRANCH=${1:-main}
    LIBADITOF_BRANCH=${2:-main}
    
    DOCKERFILE="Dockerfile"
fi

# Build the Docker image with output visible
echo "Building Docker image for ADCAM..."
if [ "$USE_LOCAL" = true ]; then
    echo "  Mode: Local workspace"
else
    echo "  ADCAM branch: $ADCAM_BRANCH"
    echo "  libaditof branch: $LIBADITOF_BRANCH"
fi
echo "  Build jobs: $JOBS"
echo "  Image tag: $IMAGE_TAG"
echo "  Libs source: $LIBS_PATH"
echo "  Dockerfile: $DOCKERFILE"
echo ""

if [ "$USE_LOCAL" = true ]; then
    sudo docker build \
        $DOCKER_OPTS \
        --build-arg BUILD_JOBS=$JOBS \
        -f $DOCKERFILE \
        -t $IMAGE_TAG . 2>&1 | tee build_output.log
else
    sudo docker build \
        $DOCKER_OPTS \
        --build-arg ADCAM_BRANCH=$ADCAM_BRANCH \
        --build-arg LIBADITOF_BRANCH=$LIBADITOF_BRANCH \
        --build-arg BUILD_JOBS=$JOBS \
        -f $DOCKERFILE \
        -t $IMAGE_TAG . 2>&1 | tee build_output.log
fi

# Check if build succeeded
if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Docker image built successfully!"
    echo "Full build log saved to: build_output.log"
    echo ""
    echo "To run the container:"
    echo "  sudo docker run --rm $IMAGE_TAG"
else
    echo ""
    echo "✗ Docker build failed"
    echo "Check build_output.log for details"
    exit 1
fi
