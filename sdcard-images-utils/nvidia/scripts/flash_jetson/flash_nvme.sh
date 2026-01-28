#!/bin/bash

set -ex

if [[ $EUID > 0 ]]; then
	echo "This script must be run as root user"
	echo "Usage: sudo ./flash_nvme.sh"
	exit
fi

ROOTDIR=`pwd`
BUILD_DIR="$ROOTDIR/build"
mkdir -p $BUILD_DIR

JETSON_LINUX_URL="https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v4.4/release/Jetson_Linux_r36.4.4_aarch64.tbz2"
SAMPLE_ROOTFS_URL="https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v4.4/release/Tegra_Linux_Sample-Root-Filesystem_r36.4.4_aarch64.tbz2"

function install_flash_prerequisties()
{
        echo "Install tge additional packages required for flashing"

        cd $BUILD_DIR/Linux_for_Tegra

        sudo ./apply_binaries.sh

        sudo ./tools/l4t_flash_prerequisites.sh

}

function download_bsp_source()
{
    # Check if the BSP source is already downloaded
    if [ ! -d "$BUILD_DIR/Linux_for_Tegra" ]; then
        echo "Download and Extract the NVIDIA Jetson Linux 36.4.4 BSP Driver package"
        cd $BUILD_DIR
        wget -q -O- "$JETSON_LINUX_URL" | tar xj
        echo "Cloned the NVIDIA L4T linux kernel sources"
        cd Linux_for_Tegra/
        pushd .
    else
        echo "BSP source already downloaded, skipping..."
    fi
}

function download_sample_rootfs()
{
    # Check if the rootfs directory exists and contains expected files
    if [ ! -d "$BUILD_DIR/Linux_for_Tegra/rootfs" ] || [ ! -d "$BUILD_DIR/Linux_for_Tegra/rootfs/etc" ] || [ ! -d "$BUILD_DIR/Linux_for_Tegra/rootfs/bin" ]; then
        echo "Download and extract the sample root file system"
        cd $BUILD_DIR/Linux_for_Tegra
        mkdir -p rootfs
        cd rootfs
        wget -q -O- $SAMPLE_ROOTFS_URL | tar xj
        cd ..
	install_flash_prerequisties
    else
        echo "Sample root filesystem already downloaded and extracted, skipping..."
    fi
}

function main()
{

	download_bsp_source

	download_sample_rootfs

	sudo ./tools/l4t_create_default_user.sh -u analog -p analog -n ubuntu

	sudo ./tools/kernel_flash/l4t_initrd_flash.sh --external-device nvme0n1p1 -c tools/kernel_flash/flash_l4t_t234_nvme.xml -p '-c bootloader/generic/cfg/flash_t234_qspi.xml' --showlogs --network usb0 jetson-orin-nano-devkit-super internal

	cd $ROOOTDIR
}

main
