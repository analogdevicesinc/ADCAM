#!/bin/bash

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
echo 1 > /sys/class/gpio/gpio305/value

# Set 0: EXT_FSYNC / 1: ISP_INT
echo 1 > /sys/class/gpio/gpio308/value

# Enable interrupt support
v4l2-ctl --set-ctrl=fsync_trigger=1 -d /dev/v4l-subdev1
