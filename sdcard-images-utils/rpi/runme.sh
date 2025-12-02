#!/bin/bash
set -ex

if [ "$#" -ne 2 ]; then
        echo 'usage: ./runme.sh <sdk_version> <tof_branch_name>'
        exit 1
fi


### Command Line args

SDK_VERSION=$1
BRANCH=$2

echo ${SDK_VERSION}
echo ${BRANCH}

if [ -z ${SDK_VERSION} ]; then
        echo 'usage: ./runme.sh <sdk_version> <tof_branch_name>'
        exit 1
fi

if [ -z ${BRANCH} ]; then
        echo 'usage: ./runme.sh <sdk_version> <tof_branch_name>'
        exit 1
fi

ROOTDIR=`pwd`
BR_COMMIT=`git log -1 --pretty=format:%h`
PATCH_DIR=$ROOTDIR/RPI_ToF_ADSD3500_REL_PATCH_$(date +"%d%b%y")
mkdir -p $PATCH_DIR

REPO_URL="https://github.com/raspberrypi/linux.git"
REPO_DIR="linux"
STABLE_TAG="stable_20250916"

function download_linux_kernel()
{
	mkdir -p build
	cd "$ROOTDIR/build" || { echo "Failed to enter build directory"; exit 1; }

	echo "=== Cloning Raspberry Pi Linux repository ==="
	if [ -d "$REPO_DIR" ]; then
		echo "Directory '$REPO_DIR' already exists. Skipping clone."
	else
		git clone "$REPO_URL"
	fi

	cd "$REPO_DIR" || { echo "Failed to enter directory '$REPO_DIR'"; exit 1; }

	echo "=== Fetching all tags ==="
	git fetch --all --tags

	echo "=== Checking out stable tag: $STABLE_TAG ==="
	git checkout "tags/$STABLE_TAG" -b "$STABLE_TAG" || { echo "Failed to checkout tag $STABLE_TAG"; exit 1; }

	echo "=== Repository is now at tag $STABLE_TAG ==="

}

function apply_git_format_patches()
{

	cd "$ROOTDIR/build/$REPO_DIR"
	git reset --hard "tags/$STABLE_TAG"
	git am $ROOTDIR/patches/linux/*.patch

}

function build_kernel()
{

	BUILD_DIR=$ROOTDIR/build/linux
	cd $BUILD_DIR

	echo "Building Raspberry Pi 5 kernel (bcm2712)..."
	export ARCH=arm64
	export CROSS_COMPILE=aarch64-linux-gnu-
	export KERNEL=kernel_2712

	# Clean previous builds
	make distclean

	# Configure for Raspberry Pi 5
	make bcm2712_defconfig

	# Build kernel image, modules, and device trees
	make -j"$(nproc)" Image.gz modules dtbs KERNEL=$KERNEL

	# Prepare modules
	rm -rf modules
	mkdir -p modules
	make modules_install INSTALL_MOD_PATH=./modules KERNEL=$KERNEL

	# Package modules
	tar czvf modules.tar.gz -C modules .

	# Patch: package with kernel Image, kernel modules and DTB 
	mv -v modules.tar.gz $PATCH_DIR
	cp -v arch/arm64/boot/Image.gz $PATCH_DIR/
	cp -v arch/arm64/boot/dts/broadcom/bcm2712-rpi-5-b.dtb $PATCH_DIR
	cp -v arch/arm/boot/dts/overlays/adsd3500.dtbo $PATCH_DIR

	echo "Build kernel completed!!!!"
}

function sw_version_info()
{
	touch sw-versions
	SW_VERSION_FILE=sw-versions
	echo -n "SDK    Version : " >> $SW_VERSION_FILE ; echo "$SDK_VERSION" >> $SW_VERSION_FILE
	echo -n "Branch Name    : " >> $SW_VERSION_FILE ; echo "$BRANCH" >> $SW_VERSION_FILE
	echo -n "Branch Commit  : " >> $SW_VERSION_FILE ; echo "$BR_COMMIT" >> $SW_VERSION_FILE
	echo -n "Build  Date    : " >> $SW_VERSION_FILE ; date >> $SW_VERSION_FILE
	echo    "Kernel Version : 6.12.47" >> $SW_VERSION_FILE
	mv $SW_VERSION_FILE $PATCH_DIR
}

function copy_ubuntu_overlay()
{
	cp -rf $ROOTDIR/patches/ubuntu_overlay $PATCH_DIR

}


function create_package()
{

	
	cd $ROOTDIR
	cp $ROOTDIR/scripts/system_upgrade/apply_patch.sh $PATCH_DIR
	ARCHIVE_FILENAME="RPI_ToF_ADSD3500_REL_PATCH_$(date +"%d%b%y").zip"
	zip -r "RPI_ToF_ADSD3500_REL_PATCH_$(date +"%d%b%y").zip" RPI_ToF_ADSD3500_REL_PATCH_*
	rm -rf $PATCH_DIR
	echo "System image patch $ARCHIVE_FILENAME file created successfully."
}

function main()
{
	
	#download_linux_kernel

	apply_git_format_patches

	build_kernel

	copy_ubuntu_overlay

	sw_version_info

	create_package
}

main

