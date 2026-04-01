#!/bin/bash

# Install CMake 3.22+ (required by imgui dependency)
CMAKE_VERSION="3.22.6"
CMAKE_DIR="/tmp/cmake-${CMAKE_VERSION}"
if [ ! -d "${CMAKE_DIR}" ]; then
    echo "Installing CMake ${CMAKE_VERSION}..."
    apt-get update -qq && apt-get install -y -qq wget > /dev/null
    wget -q https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}/cmake-${CMAKE_VERSION}-linux-aarch64.tar.gz -O /tmp/cmake.tar.gz
    mkdir -p ${CMAKE_DIR}
    tar -xzf /tmp/cmake.tar.gz -C ${CMAKE_DIR} --strip-components=1
    rm /tmp/cmake.tar.gz
fi
export PATH="${CMAKE_DIR}/bin:${PATH}"
echo "Using CMake version: $(cmake --version | head -n1)"

git config --global --add safe.directory /ToF/libaditof
#git config --global --add safe.directory /ToF/libaditof/dependencies/third-party/protobuf
#git config --global --add safe.directory /ToF/libaditof/dependencies/third-party/libzmq
#git config --global --add safe.directory /ToF/libaditof/dependencies/third-party/cppzmq
#git config --global --add safe.directory /libaditof/dependencies/third-party/gtest

project_dir=$1
pushd ${project_dir}

GLOG_INSTALL_DIR="/aditof-deps/installed/glog"
PROTOBUF_INSTALL_DIR="/aditof-deps/installed/protobuf"
OPENCV_INSTALL_DIR="/aditof-deps/installed/opencv"
LIBZMQ_INSTALL_DIR="/aditof-deps/installed/libzmq"
NUM_JOBS=4
ARGS="$2"

mkdir -p build
mkdir ../libs

pushd build
#cmake .. ${ARGS} -DCMAKE_PREFIX_PATH="${GLOG_INSTALL_DIR};${PROTOBUF_INSTALL_DIR};${LIBZMQ_INSTALL_DIR};${OPENCV_INSTALL_DIR}" -DWITH_OPENCV=0
cmake .. ${ARGS} 
make -j${NUM_JOBS}
popd #build

popd # ${project_dir}
