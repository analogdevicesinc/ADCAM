#!/bin/bash

sudo apt-get update
sudo apt-get install -y wget
wget https://github.com/Kitware/CMake/releases/download/v3.22.0/cmake-3.22.0-linux-x86_64.sh
sudo sh cmake-3.22.0-linux-x86_64.sh --skip-license --prefix=/usr/local

git config --global --add safe.directory /ToF/libaditof
git config --global --add safe.directory /ToF/libaditof/glog
git config --global --add safe.directory /ToF/libaditof/protobuf
git config --global --add safe.directory /ToF/libaditof/libzmq
git config --global --add safe.directory /ToF/libaditof/cppzmq

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
cmake .. ${ARGS} -DCMAKE_PREFIX_PATH="${GLOG_INSTALL_DIR};${PROTOBUF_INSTALL_DIR};${LIBZMQ_INSTALL_DIR};${OPENCV_INSTALL_DIR}" -DWITH_OPENCV=0
make -j${NUM_JOBS}
popd #build

popd # ${project_dir}
