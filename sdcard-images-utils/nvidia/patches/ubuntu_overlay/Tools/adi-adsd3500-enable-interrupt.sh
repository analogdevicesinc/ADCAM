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

# Resolve GPIOs dynamically from labels in debugfs
declare -A GPIO
GPIO_LABELS=("NET_HOST_IO_SEL" "HOST_IO_DIR")
HIGH_LEVEL="1"
MODE_INTERRUPT="1"

for label in "${GPIO_LABELS[@]}"; do
    result=$(cat /sys/kernel/debug/gpio 2>/dev/null | grep -i "\\b${label}\\b" | head -n1)
    if [[ -z "$result" ]]; then
        echo "Label not found in /sys/kernel/debug/gpio: $label"
        exit 1
    fi

    gpio_num=$(echo "$result" | sed -E 's/.*gpio-([0-9]+).*/\1/')
    if [[ -z "$gpio_num" ]]; then
        echo "Failed to extract GPIO number for label: $label"
        exit 1
    fi

    GPIO["$label"]="$gpio_num"
done

# Set 0: EXT_FSYNC / 1: ISP_INT
echo "$HIGH_LEVEL" > "/sys/class/gpio/gpio${GPIO[NET_HOST_IO_SEL]}/value"

# Set 0: EXT_FSYNC / 1: ISP_INT
echo "$HIGH_LEVEL" > "/sys/class/gpio/gpio${GPIO[HOST_IO_DIR]}/value"

# Enable external fsync
v4l2-ctl --set-ctrl="fsync_trigger=${MODE_INTERRUPT}" -d "$SUBDEV_PATH"
