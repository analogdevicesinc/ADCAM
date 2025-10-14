#!/bin/bash

set -x

ROOTDIR=`pwd`

function apply_ubuntu_overlay()
{

	#Set the MTU size to 15000 by default
        echo "Configuring the MTU size to 15000 by default"
        sudo cp $ROOTDIR/ubuntu_overlay/etc/NetworkManager/conf.d/10-ignore-interface.conf 	/etc/NetworkManager/conf.d/
        sudo cp $ROOTDIR/ubuntu_overlay/etc/systemd/network/10-rndis0.network      		/etc/systemd/network/

        echo "Updating the usb device mode configuration"
	sed -i 's/^net_dhcp_lease_time=15$/net_dhcp_lease_time=1500/' /opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-config.sh
	grep -Fxq 'sudo ip link set l4tbr0 mtu 15000' /opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-start.sh || sed -i '255i sudo ip link set l4tbr0 mtu 15000' /opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-start.sh

	echo "Copy all the service files"
	sudo cp $ROOTDIR/ubuntu_overlay/etc/systemd/system/*.service 		/etc/systemd/system/

	echo "Copy all the shell scripts"
	sudo cp $ROOTDIR/ubuntu_overlay/usr/share/systemd/*.sh		/usr/share/systemd/

}

function install_packages()
{
	sudo -s <<EOF
        echo "Enter into the root shell"

	echo "Install v4l-utils package"
	apt-get install v4l-utils

	echo "Install cmake package"
	apt install cmake -y

	echo "Install build-essential for C++ compilation tools"
	apt install build-essential -y

	echo "Install ZMQ libraries"
	apt install libzmq3-dev

	echo "Install OpenGL libraries"
	apt install libglfw3-dev
		
        exit
EOF
    echo "Exited from the root shell"


}

function update_kernel()
{
	pushd .
	sudo cp sw-versions /boot/
	if [ ! -f /boot/Image.backup ]; then
		echo "The regular file /boot/Image.backup does not exist."
		echo " Make a backup of the original kernel"
		sudo cp /boot/Image /boot/Image.backup
	fi
	mkdir test && tar -xjf kernel_supplements.tbz2 -C test > /dev/null 2>&1
	sudo rm -rf /boot/adi
	sudo mkdir -p /boot/adi/
	sudo cp Image /boot/adi/Image
	sudo cp -rf tegra234-p3767-camera-p3768-*.dtbo /boot/adi/
	cd test/lib/modules/
	sudo cp -rf 5.15.148-adi-tegra /lib/modules/
	popd
	sudo rm -rf test/
}

function start_services()
{
	sudo systemctl reload NetworkManager
	sudo systemctl enable systemd-networkd
	sudo systemctl start  systemd-networkd
	sudo systemctl enable adi-tof
	sudo systemctl start adi-tof

}

extlinux_conf_file="/boot/extlinux/extlinux.conf"

function truncate_file() {
  if [[ ! -f "$extlinux_conf_file" ]]; then
    echo "File not found!"
    return 1
  fi

  sed -i '30,$d' "$extlinux_conf_file"

  echo "Set the default label name to primary"
  sed -i "s/^DEFAULT .*/DEFAULT primary/" "$extlinux_conf_file"
}

function get_root_count()
{
	count_value="$(grep -c "root=/dev/mmcblk0p1" ${extlinux_conf_file})"
	echo "get_root_count = ${count_value}"
}

function add_boot_label()
{
	sudo -s <<EOF
	echo "Add the backup kernel label"
	echo " " >> ${extlinux_conf_file}
	echo "LABEL backup" >> ${extlinux_conf_file}
	echo "      MENU LABEL backup kernel" >> ${extlinux_conf_file}
	echo "      LINUX /boot/Image.backup" >> ${extlinux_conf_file}
	echo "      FDT /boot/dtb/kernel_tegra234-p3768-0000+p3767-0005-nv-super.dtb" >> ${extlinux_conf_file}
	echo "      INITRD /boot/initrd" >> ${extlinux_conf_file}
	echo "       APPEND ${cbootargs} root=/dev/mmcblk0p1 rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0" >> ${extlinux_conf_file}
	echo " " >> ${extlinux_conf_file}

	echo "Add the ADSD3500+ADSD3100 label"
	echo "LABEL ADSD3500+ADSD3100" >> ${extlinux_conf_file}
	echo "      MENU LABEL ADSD3500: <CSI ToF Camera ADSD3100>" >> ${extlinux_conf_file}
	echo "      LINUX /boot/adi/Image" >> ${extlinux_conf_file}
	echo "      FDT /boot/dtb/kernel_tegra234-p3768-0000+p3767-0005-nv-super.dtb" >> ${extlinux_conf_file}
	echo "      OVERLAYS /boot/adi/tegra234-p3767-camera-p3768-adsd3500.dtbo" >> ${extlinux_conf_file}
	echo "      INITRD /boot/initrd" >> ${extlinux_conf_file}
	echo "      APPEND ${cbootargs} root=/dev/mmcblk0p1 rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0" >> ${extlinux_conf_file}
	echo " " >> ${extlinux_conf_file}

	echo "Add the ADSD3500-DUAL+ADSD3100 label"
        echo "LABEL ADSD3500-DUAL+ADSD3100" >> ${extlinux_conf_file}
        echo "      MENU LABEL ADSD3500-DUAL: <CSI ToF Camera ADSD3100>" >> ${extlinux_conf_file}
        echo "      LINUX /boot/adi/Image" >> ${extlinux_conf_file}
        echo "      FDT /boot/dtb/kernel_tegra234-p3768-0000+p3767-0005-nv-super.dtb" >> ${extlinux_conf_file}
        echo "      OVERLAYS /boot/adi/tegra234-p3767-camera-p3768-dual-adsd3500-adsd3100.dtbo" >> ${extlinux_conf_file}
        echo "      INITRD /boot/initrd" >> ${extlinux_conf_file}
        echo "      APPEND ${cbootargs} root=/dev/mmcblk0p1 rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0" >> ${extlinux_conf_file}
        echo " " >> ${extlinux_conf_file}

	exit
EOF
}

function set_default_boot_label()
{
        echo "Setting the default label name to ADSD3500-DUAL+ADSD3100"
        sudo sed -i "s/^DEFAULT .*/DEFAULT ADSD3500-DUAL+ADSD3100/" ${extlinux_conf_file}
}

function main()
{
	echo "******* Install Software Packages *******"
	install_packages
	
	echo "******* Update the Extlinux Conf file *******"
	truncate_file
	get_root_count
	if [[ "${count_value}" == 1 ]]; then
		add_boot_label
	fi
	set_default_boot_label

	echo "******* Apply Ubuntu Overlay *******"
	apply_ubuntu_overlay
	
	echo "******* Update Kernel *******"
	update_kernel
	
	echo "******* Start background services *******"
	start_services
	
	echo "******* Reboot the system *******"
	sudo reboot

}

main
