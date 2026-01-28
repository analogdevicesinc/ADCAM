# ADCAM Docker Build Test Environment

This Docker container provides a clean environment to test building the [ADCAM repository](https://github.com/analogdevicesinc/ADCAM) before making a PR, ensuring no dependencies are missing.

## Quick Start

Build with default settings (main branches):
```bash
./build.sh -l /path/to/libs
```

Build with specific branches:
```bash
./build.sh -l /path/to/libs <adcam-branch> <libaditof-branch>
```

Build using local workspace code:
```bash
./build.sh --local -l /path/to/libs
```

## Usage

```bash
./build.sh [OPTIONS] [ADCAM_BRANCH] [LIBADITOF_BRANCH]
```

### Options

- `-h, --help` - Show help message
- `-l, --libs PATH` - Path to libs folder to copy into container **(required)**
- `-j, --jobs N` - Number of parallel build jobs (default: 6)
- `-t, --tag NAME` - Docker image tag name (default: adcam-build-test)
- `--no-cache` - Build without using Docker cache
- `--local` - Use local workspace code instead of cloning from GitHub

### Examples

```bash
# Use main for both repos (default)
./build.sh -l /path/to/libs

# Use specific branches
./build.sh -l /path/to/libs feature-branch main

# Build with 4 parallel jobs
./build.sh -j 4 -l /path/to/libs main main

# Force clean build without cache
./build.sh --no-cache -l /path/to/libs main main

# Custom image tag
./build.sh -t my-test-build -l /path/to/libs main main

# Use local workspace code (test uncommitted changes)
./build.sh --local -l /path/to/libs

# Use local code with clean build
./build.sh --local --no-cache -l /path/to/libs
```

### Manual Docker Build

**Standard Mode:**
```bash
# First copy libs to the Docker context
cp -r /path/to/libs ./libs

# Then build
sudo docker build \
  --progress=plain \
  --build-arg ADCAM_BRANCH=main \
  --build-arg LIBADITOF_BRANCH=main \
  --build-arg BUILD_JOBS=6 \
  -t adcam-build-test .
```

**Local Mode:**
```bash
# First copy libs and local code to the Docker context
cp -r /path/to/libs ./libs
rsync -a --exclude='build' --exclude='libaditof/build' --exclude='scripts' --exclude='.git' ../../ ./local_code/

# Then build using Dockerfile.local
sudo docker build \
  --progress=plain \
  --build-arg BUILD_JOBS=6 \
  -f Dockerfile.local \
  -t adcam-build-test .
```

## What's Included

- Ubuntu 22.04 base image
- All required build dependencies:
  - CMake
  - g++
  - Python 3.10 with dev libraries
  - OpenCV (with contrib modules)
  - OpenGL and GLFW3
  - X11 libraries (Xinerama, Xcursor, Xi, Xrandr)
  - Doxygen and Graphviz (for documentation)
- ADCAM code (cloned from GitHub or copied from local workspace)
- Pre-built project (Release configuration)

## Viewing Build Output

The build script saves full output to `build_output.log`. Use the view-log helper script:

```bash
./view-log.sh              # Follow last 50 lines in real-time
./view-log.sh errors       # Show all errors and warnings
./view-log.sh grep cmake   # Search for specific text
./view-log.sh all          # Browse entire log with less
```

Or view directly:
```bash
tail -f build_output.log                  # Follow in real-time
grep -i error build_output.log            # Search for errors
less build_output.log                     # Browse the full log
```

## Build Process

The Dockerfile performs the following steps:

### Standard Mode (default)
1. Copies local `libs` folder into the container (if present)
2. Installs all dependencies from the ADCAM README
3. Clones the ADCAM repository
4. Checks out specified branches for ADCAM and libaditof
5. Initializes git submodules (ToF-drivers and libaditof)
6. Runs CMake configuration (Release mode)
7. Builds the project with configurable parallel jobs and verbose output

### Local Mode (--local flag)
1. Copies local `libs` folder into the container
2. Installs all dependencies from the ADCAM README
3. Copies local workspace code (excluding `build/`, `libaditof/build/`, `scripts/`, and `.git/`)
4. Runs CMake configuration (Release mode)
5. Builds the project with configurable parallel jobs and verbose output

All build output is visible during the Docker build process, allowing you to catch any issues early.

## Customization

**Testing specific branches:**
Use the branch arguments when running `build.sh`:
```bash
./build.sh -l /path/to/libs <adcam-branch> <libaditof-branch>
```

**Testing local uncommitted changes:**
Use the `--local` flag:
```bash
./build.sh --local -l /path/to/libs
```

**Inspecting the built container:**
```bash
docker run --rm -it adcam-build-test bash
```

## Cleanup

Since this is a build testing environment, you should clean up Docker artifacts after testing:

```bash
./cleanup.sh
```

This will:
- Remove the adcam-build-test image
- Remove any custom tagged images
- Clean up dangling images and build cache
- Remove temporary folders (`libs/`, `local_code/`)
- Remove build log file (`build_output.log`)
- Reclaim disk space

Manual cleanup:
```bash
sudo docker image rm adcam-build-test
sudo docker system prune -f
```

## Notes

- The build uses `-j 6` for parallel compilation (6 jobs)
- Build type is set to `Release`
- The container is based on Ubuntu 22.04, matching the JetPack 6.2.1 environment
