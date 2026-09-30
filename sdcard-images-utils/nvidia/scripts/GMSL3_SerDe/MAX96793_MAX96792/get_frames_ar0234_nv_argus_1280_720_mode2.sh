#!/bin/bash

MODE=${1:-1}
NUM_FRAMES=${2:-1}
FRAMERATE=${3:-30}

SENSOR_ID=0

WIDTH=1280
HEIGHT=720

usage()
{
    echo "Usage:"
    echo "  $0 <mode> [num_frames] [framerate]"
    echo ""
    echo "Modes:"
    echo "  1 = Stream"
    echo "  2 = Capture JPG"
    echo "  3 = Capture BIN"
    echo ""
    echo "Examples:"
    echo "  $0 1"
    echo "  $0 2 1 15"
    echo "  $0 3 100 30"
    exit 1
}

case "$MODE" in

1)
    echo "Streaming..."
    gst-launch-1.0 \
        nvarguscamerasrc sensor-id=${SENSOR_ID} ! \
        "video/x-raw(memory:NVMM),width=${WIDTH},height=${HEIGHT},framerate=${FRAMERATE}/1,format=NV12" ! \
        nvvidconv flip-method=0 ! \
        "video/x-raw,width=960,height=720" ! \
        nvvidconv ! \
        fpsdisplaysink
    ;;

2)
    echo "Capturing JPG..."
    gst-launch-1.0 -e \
        nvarguscamerasrc num-buffers=1 sensor-id=${SENSOR_ID} ! \
        "video/x-raw(memory:NVMM),width=${WIDTH},height=${HEIGHT},framerate=${FRAMERATE}/1" ! \
        nvjpegenc ! \
        multifilesink location="AR0234_${WIDTH}x${HEIGHT}.jpg"
    ;;

3)
    echo "Capturing BIN..."
    gst-launch-1.0 -e \
        nvarguscamerasrc num-buffers=${NUM_FRAMES} sensor-id=${SENSOR_ID} ! \
        "video/x-raw(memory:NVMM),width=${WIDTH},height=${HEIGHT},framerate=${FRAMERATE}/1" ! \
        nvvidconv ! \
        "video/x-raw,format=NV12" ! \
        multifilesink location="AR0234_%05d_${WIDTH}x${HEIGHT}_nv12.bin" next-file=buffer
    ;;

*)
    echo "Invalid mode: $MODE"
    usage
    ;;
esac
