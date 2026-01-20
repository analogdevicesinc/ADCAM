#!/bin/bash

MEDIA_DEVICE="/dev/media0"
DOT_OUTPUT=$(media-ctl -d "$MEDIA_DEVICE" --print-dot)
DOT_OUTPUT=$(echo "$DOT_OUTPUT" | sed 's/\\n/\n/g')
SUBDEV_PATH=$(echo "$DOT_OUTPUT" | awk '/adsd3500/ {getline; if ($0 ~ /\/dev\/v4l-subdev/) print $1}' | tr -d '",')
VIDEO_PATH=$(echo "$DOT_OUTPUT" | awk '/vi-output, adsd3500/ {getline; if ($0 ~ /\/dev\/video/) print $1}' | tr -d '",')

if [[ -n "$SUBDEV_PATH" && -n "$VIDEO_PATH" ]]; then
    echo "adsd3500 subdev: $SUBDEV_PATH" > /dev/null
    echo "adsd3500 video : $VIDEO_PATH"  > /dev/null
else
    echo "adsd3500 device not found in $MEDIA_DEVICE"
    exit 1
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
v4l2-ctl --set-ctrl=fsync_trigger=0 -d $SUBDEV_PATH
