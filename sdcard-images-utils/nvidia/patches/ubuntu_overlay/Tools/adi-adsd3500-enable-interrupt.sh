#!/bin/bash

# Discover adsd3500 V4L2 sub-device and video nodes by parsing the media controller graph
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

# Fixed GPIO mapping from gpiochip2 (max7327)
NET_HOST_IO_SEL_GPIO="713"
HOST_IO_DIR_GPIO="716"
HIGH_LEVEL="1"
MODE_INTERRUPT="1"

# Set 0: EXT_FSYNC / 1: ISP_INT
echo "$HIGH_LEVEL" > "/sys/class/gpio/gpio${NET_HOST_IO_SEL_GPIO}/value"

# Set 0: EXT_FSYNC / 1: ISP_INT
echo "$HIGH_LEVEL" > "/sys/class/gpio/gpio${HOST_IO_DIR_GPIO}/value"

# Enable external fsync
v4l2-ctl --set-ctrl="fsync_trigger=${MODE_INTERRUPT}" -d "$SUBDEV_PATH"
