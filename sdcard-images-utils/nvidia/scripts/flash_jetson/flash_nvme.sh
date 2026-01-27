#!/bin/bash


if [[ $EUID > 0 ]]; then
        echo "This script must be run as root user"
        echo "Usage: sudo ./flash_nvme.sh"
        exit
fi

ROOTDIR=`pwd`

cd $ROOTDIR/build/Linux_for_Tegra

sudo ./tools/l4t_create_default_user.sh -u analog -p analog -n ubuntu

sudo ./tools/kernel_flash/l4t_initrd_flash.sh --external-device nvme0n1p1 -c tools/kernel_flash/flash_l4t_t234_nvme.xml -p '-c bootloader/generic/cfg/flash_t234_qspi.xml' --showlogs --network usb0 jetson-orin-nano-devkit-super internal
