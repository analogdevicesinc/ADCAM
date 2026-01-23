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
	sudo sed -i 's/^net_dhcp_lease_time=15$/net_dhcp_lease_time=1500/' /opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-config.sh
	grep -Fxq 'sudo ip link set l4tbr0 mtu 15000' /opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-start.sh || sudo sed -i '255i sudo ip link set l4tbr0 mtu 15000' /opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-start.sh

	echo "Copy all the service files"
	sudo cp $ROOTDIR/ubuntu_overlay/etc/systemd/system/*.service 		/etc/systemd/system/

	echo "Copy all the shell scripts"
	sudo cp $ROOTDIR/ubuntu_overlay/usr/share/systemd/*.sh		/usr/share/systemd/

	echo "Copy the udev gpio rules"
	sudo cp $ROOTDIR/ubuntu_overlay/etc/udev/rules.d/99-gpio.rules /etc/udev/rules.d/
	sudo udevadm control --reload-rules
	sudo udevadm trigger

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
	sudo mkdir -p /lib/firmware/adi
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
	sudo systemctl enable jetson-performance
        sudo systemctl start jetson-performance

}

extlinux_conf_file="/boot/extlinux/extlinux.conf"

function get_boot_device_type()
{
	if [[ ! -f "$extlinux_conf_file" ]]; then
		echo "ERROR: File not found: ${extlinux_conf_file}"
		boot_device_type="unknown"
		return 1
	fi

	# Check for PARTUUID (SSD/NVMe boot)
	if grep -q "PARTUUID" "${extlinux_conf_file}"; then
		partuuid=$(grep -oP '(?<=PARTUUID=).{36}' "${extlinux_conf_file}" | head -n 1)
		boot_device_type="ssd"
		boot_device_info="${partuuid}"
		echo "Boot device: SSD (NVMe)"
		echo "PARTUUID: ${partuuid}"
		return 0
	# Check for microSD card boot
	elif grep -q "root=/dev/mmcblk0p1" "${extlinux_conf_file}"; then
		boot_device_type="sdcard"
		boot_device_info="/dev/mmcblk0p1"
		echo "Boot device: microSD card"
		echo "Root device: /dev/mmcblk0p1"
		return 0
	else
		boot_device_type="unknown"
		boot_device_info=""
		echo "WARNING: Unable to determine boot device type"
		return 2
	fi
}

function truncate_file() {
  if [[ ! -f "$extlinux_conf_file" ]]; then
    echo "File not found!"
    return 1
  fi

  sed -i '30,$d' "$extlinux_conf_file"

  echo "Set the default label name to primary"
  sed -i "s/^DEFAULT .*/DEFAULT primary/" "$extlinux_conf_file"
}

function add_boot_label()
{
	# Determine root device based on boot type
	local root_device
	if [[ "${boot_device_type}" == "ssd" ]]; then
		root_device="root=PARTUUID=${boot_device_info}"
		DTB_FILE="kernel_tegra234-p3768-0000+p3767-0003-nv-super.dtb"
	else
		root_device="root=/dev/mmcblk0p1"
		DTB_FILE="kernel_tegra234-p3768-0000+p3767-0005-nv-super.dtb"
	fi

	sudo -s <<EOF
	echo "Add the backup kernel label"
	echo " " >> ${extlinux_conf_file}
	echo "LABEL backup" >> ${extlinux_conf_file}
	echo "      MENU LABEL backup kernel" >> ${extlinux_conf_file}
	echo "      LINUX /boot/Image.backup" >> ${extlinux_conf_file}
	echo "      FDT /boot/dtb/${DTB_FILE}" >> ${extlinux_conf_file}
	echo "      INITRD /boot/initrd" >> ${extlinux_conf_file}
	echo "       APPEND \${cbootargs} ${root_device} rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0" >> ${extlinux_conf_file}
	echo " " >> ${extlinux_conf_file}

	echo "Add the ADSD3500+ADSD3100 label"
	echo "LABEL ADSD3500+ADSD3100" >> ${extlinux_conf_file}
	echo "      MENU LABEL ADSD3500: <CSI ToF Camera ADSD3100>" >> ${extlinux_conf_file}
	echo "      LINUX /boot/adi/Image" >> ${extlinux_conf_file}
	echo "      FDT /boot/dtb/${DTB_FILE}" >> ${extlinux_conf_file}
	echo "      OVERLAYS /boot/adi/tegra234-p3767-camera-p3768-adsd3500.dtbo" >> ${extlinux_conf_file}
	echo "      INITRD /boot/initrd" >> ${extlinux_conf_file}
	echo "      APPEND \${cbootargs} ${root_device} rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0" >> ${extlinux_conf_file}
	echo " " >> ${extlinux_conf_file}

	echo "Add the ADSD3500-DUAL+ADSD3100 label"
        echo "LABEL ADSD3500-DUAL+ADSD3100" >> ${extlinux_conf_file}
        echo "      MENU LABEL ADSD3500-DUAL: <CSI ToF Camera ADSD3100>" >> ${extlinux_conf_file}
        echo "      LINUX /boot/adi/Image" >> ${extlinux_conf_file}
	echo "      FDT /boot/dtb/${DTB_FILE}" >> ${extlinux_conf_file}
        echo "      OVERLAYS /boot/adi/tegra234-p3767-camera-p3768-dual-adsd3500-adsd3100.dtbo" >> ${extlinux_conf_file}
        echo "      INITRD /boot/initrd" >> ${extlinux_conf_file}
        echo "      APPEND \${cbootargs} ${root_device} rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0" >> ${extlinux_conf_file}
        echo " " >> ${extlinux_conf_file}

        echo "Add the ADSD3500-DUAL+ADSD3100+AR0234 label"
        echo "LABEL ADSD3500-DUAL+ADSD3100+AR0234" >> ${extlinux_conf_file}
        echo "      MENU LABEL ADSD3500-DUAL: <CSI ToF Camera ADSD3100>" >> ${extlinux_conf_file}
        echo "      LINUX /boot/adi/Image" >> ${extlinux_conf_file}
	echo "      FDT /boot/dtb/${DTB_FILE}" >> ${extlinux_conf_file}
        echo "      OVERLAYS /boot/adi/tegra234-p3767-camera-p3768-dual-adsd3500-adsd3100-arducam-ar0234.dtbo" >> ${extlinux_conf_file}
        echo "      INITRD /boot/initrd" >> ${extlinux_conf_file}
        echo "      APPEND \${cbootargs} ${root_device} rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 nospectre_bhb video=efifb:off console=tty0" >> ${extlinux_conf_file}
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
	echo "******* Update the Extlinux Conf file *******"
	truncate_file

	echo "******* Detect Boot Device Type *******"
	get_boot_device_type

	if [[ "${boot_device_type}" == "unknown" ]]; then
		echo "ERROR: Cannot proceed without valid boot device detection"
		exit 1
	fi

	# Check if boot labels need to be added
	if [[ "${boot_device_type}" == "sdcard" ]]; then
		# For SD card, check if root device is present
		if grep -q "root=/dev/mmcblk0p1" "${extlinux_conf_file}"; then
			add_boot_label
		fi
	elif [[ "${boot_device_type}" == "ssd" ]]; then
		# For SSD, check if PARTUUID is present
		if grep -q "PARTUUID" "${extlinux_conf_file}"; then
			add_boot_label
		fi
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
