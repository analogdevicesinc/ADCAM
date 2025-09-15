#!/bin/bash

if [[ $EUID > 0 ]]; then
	echo "This script must be run as root user"
	echo "Usage: sudo ./adi-adsd3500-enable-external-fsync.sh"
	exit
fi

# export NET HOST_IO_SEL Pin
if [ ! -d /sys/class/gpio/gpio305 ]
then
	echo 305 > /sys/class/gpio/export
	echo out > /sys/class/gpio/gpio305/direction
fi

# export HOST_IO_DIR Pin
if [ ! -d /sys/class/gpio/gpio308 ]
then
	echo 308 > /sys/class/gpio/export
	echo out > /sys/class/gpio/gpio308/direction
fi

# Set 0: EXT_FSYNC / 1: ISP_INT
echo 0 > /sys/class/gpio/gpio305/value

# Set 0: EXT_FSYNC / 1: ISP_INT
echo 0 > /sys/class/gpio/gpio308/value

# Enable external fsync
v4l2-ctl --set-ctrl=fsync_trigger=0 -d /dev/v4l-subdev1
