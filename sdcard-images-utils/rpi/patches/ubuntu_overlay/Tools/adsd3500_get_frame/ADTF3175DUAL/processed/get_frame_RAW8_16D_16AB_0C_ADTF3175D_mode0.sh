#!/bin/bash
 
nr_frames=${1:-1}
 
v4l2-ctl --set-ctrl=operating_mode=0 -d /dev/v4l-subdev2
v4l2-ctl --set-ctrl=phase_depth_bits=6 -d /dev/v4l-subdev2
v4l2-ctl --set-ctrl=ab_bits=6 -d /dev/v4l-subdev2
v4l2-ctl --set-ctrl=confidence_bits=0 -d /dev/v4l-subdev2
v4l2-ctl --set-ctrl=ab_averaging=0 -d /dev/v4l-subdev2
v4l2-ctl --set-ctrl=depth_enable=1 -d /dev/v4l-subdev2
v4l2-ctl --device /dev/video0 --set-fmt-video=width=1024,height=4096,pixelformat=RGGB 

./fix_rp1_cfe_format_mismatch.sh -f 8bit -r 1024x4096 > /dev/null 2>&1

v4l2-ctl --device /dev/video0 --stream-mmap --stream-to=mode0.bin --stream-count=$nr_frames
