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

nr_frames=${1:-1}

v4l2-ctl --set-ctrl=operating_mode=2 -d $SUBDEV_PATH
v4l2-ctl --set-ctrl=phase_depth_bits=6 -d $SUBDEV_PATH
v4l2-ctl --set-ctrl=ab_bits=6 -d $SUBDEV_PATH
v4l2-ctl --set-ctrl=confidence_bits=2 -d $SUBDEV_PATH
v4l2-ctl --set-ctrl=ab_averaging=1 -d $SUBDEV_PATH
v4l2-ctl --set-ctrl=depth_enable=1 -d $SUBDEV_PATH
v4l2-ctl --device /dev/video0 --set-fmt-video=width=2560,height=512,pixelformat=RGGB --stream-mmap --stream-to=mode2.bin --stream-count=$nr_frames
