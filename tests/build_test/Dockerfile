# Use Ubuntu 22.04 as base (matches JetPack 6.2.1 environment)
# This will use the ARM64 version when built on Jetson
FROM ubuntu:22.04

# Build arguments for branch selection
ARG ADCAM_BRANCH=main
ARG LIBADITOF_BRANCH=main
ARG BUILD_JOBS=6

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    cmake \
    g++ \
    git \
    python3.10 \
    python3.10-dev \
    libopencv-contrib-dev \
    libopencv-dev \
    libgl1-mesa-dev \
    libglfw3-dev \
    libxinerama-dev \
    libxcursor-dev \
    libxi-dev \
    libxrandr-dev \
    doxygen \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Copy the local libs folder to the workspace
COPY libs /workspace/libs

# Clone the repository
RUN git clone https://github.com/analogdevicesinc/ADCAM.git

# Set working directory to the cloned repo
WORKDIR /workspace/ADCAM

# Checkout specified branch for ADCAM
RUN echo "Checking out ADCAM branch: $ADCAM_BRANCH" && \
    git checkout $ADCAM_BRANCH

# Initialize submodules
RUN git submodule update --init

# Checkout specified branch for libaditof submodule
RUN echo "Checking out libaditof branch: $LIBADITOF_BRANCH" && \
    cd libaditof && \
    git checkout $LIBADITOF_BRANCH && \
    cd ..

# Create build directory
RUN mkdir build

# Set working directory to build
WORKDIR /workspace/ADCAM/build

# Configure with CMake - output will be visible during docker build
RUN cmake -DCMAKE_BUILD_TYPE=Release ..

# Build the project with verbose output
RUN cmake --build . -j ${BUILD_JOBS} --verbose

# Default command to show build succeeded
CMD ["echo", "Build completed successfully!"]
