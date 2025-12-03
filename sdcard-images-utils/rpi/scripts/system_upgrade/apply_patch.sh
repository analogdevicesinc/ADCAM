#!/bin/bash

set -x

ROOTDIR=`pwd`

CONFIG_FILE="/boot/firmware/config.txt"
OVERLAY_ENTRY="dtoverlay=adsd3500,cam0"
KERNEL_ENTRY="kernel=kernel_adi.img"

function apply_ubuntu_overlay()
{

	echo "Copy all the service files"
	sudo cp $ROOTDIR/ubuntu_overlay/etc/systemd/system/*.service 	/etc/systemd/system/

	echo "Copy all the shell scripts"
	sudo cp $ROOTDIR/ubuntu_overlay/usr/share/systemd/*.sh		/usr/share/systemd/

}

function update_kernel(){
	
	chmod 755 bcm2712-rpi-5-b.dtb	
	sudo cp bcm2712-rpi-5-b.dtb /boot/firmware/
	sudo cp adsd3500.dtbo /boot/firmware/overlays/
	sudo cp Image.gz /boot/firmware/kernel_adi.img
	mkdir -p test
	tar -xvf modules.tar.gz -C test > /dev/null 2>&1
	sudo cp -rf test/lib/modules/6.12.47* /lib/modules/
	sudo rm -rf test



}

function start_services()
{
	sudo systemctl enable adi-tof
	sudo systemctl start adi-tof

}

function update_config_file() {

    echo "Cleaning config.txt after [all]..."

    # Remove everything after the [all] section
    sudo sed -i '/^\[all\]/q' "$CONFIG_FILE"

    echo "Appending overlay and kernel entries..."

    sudo sh -c "echo ${OVERLAY_ENTRY} >> ${CONFIG_FILE}"
    sudo sh -c "echo ${KERNEL_ENTRY} >> ${CONFIG_FILE}"

    echo "Update completed."
}

function main() {

	echo "******* Apply Ubuntu Overlay *******"
	apply_ubuntu_overlay

	echo "******* Update Kernel *******"
	update_kernel

	echo "******* Start background services *******"
	start_services

	echo "******* Add the module overlay name *****"
	update_config_file

	echo "******* Reboot the system *******"
	sudo reboot
}

main
