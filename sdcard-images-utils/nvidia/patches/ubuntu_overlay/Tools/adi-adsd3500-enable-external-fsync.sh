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

# Declare GPIO mapping directly
declare -A GPIO=(
    [EN_1P8]=300
    [EN_0P8]=301
    [P2]=302
    [I2CM_SEL]=303
    [ISP_BS3]=304
    [NET_HOST_IO_SEL]=305
    [ISP_BS0]=306
    [ISP_BS1]=307
    [HOST_IO_DIR]=308
    [ISP_BS4]=309
    [ISP_BS5]=310
    [FSYNC_DIR]=311
    [EN_VAUX]=312
    [EN_VAUX_LS]=313
    [EN_SYS]=314
)

# Set 0: EXT_FSYNC / 1: ISP_INT
echo 0 > /sys/class/gpio/gpio${GPIO[NET_HOST_IO_SEL]}/value

# Set 0: EXT_FSYNC / 1: ISP_INT
echo 0 > /sys/class/gpio/gpio${GPIO[HOST_IO_DIR]}/value

# Enable external fsync
v4l2-ctl --set-ctrl=fsync_trigger=0 -d $SUBDEV_PATH
