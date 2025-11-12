#!/bin/bash

set -ex

function update_kernel(){
	
	chmod 755 bcm2712-rpi-5-b.dtb	
	sudo cp bcm2712-rpi-5-b.dtb /boot/firmware/
	sudo cp Image.gz /boot/firmware/kernel_adi.img
	mkdir -p test
	tar -xvf modules.tar.gz -C test
	sudo cp -rf test/lib/modules/6.12.47* /lib/modules/
	sudo rm -rf test



}

function main() {

	echo "******* Update Kernel *******"
	update_kernel

	echo "******* Reboot the system *******"
	sudo reboot
}
main
