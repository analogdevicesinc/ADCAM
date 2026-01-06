#!/bin/bash

NET_HOST_IO_SEL=gpio628
HOST_IO_DIR=gpio631

# Set 0: EXT_FSYNC / 1: ISP_INT
echo 1 > /sys/class/gpio/$NET_HOST_IO_SEL/value

# Set 0: EXT_FSYNC / 1: ISP_INT
echo 1 > /sys/class/gpio/$HOST_IO_DIR/value

# Enable interrupt support
v4l2-ctl --set-ctrl=fsync_trigger=1 -d /dev/v4l-subdev2
