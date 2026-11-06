#
# MIT License
#
# Copyright (c) 2025 Analog Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import aditofpython as tof
import numpy as np
import sys
import os
import cv2

# cv2 points Qt at its own (empty) font dir on import; use the system fonts instead.
if os.path.isdir("/usr/share/fonts/truetype/dejavu"):
    os.environ["QT_QPA_FONTDIR"] = "/usr/share/fonts/truetype/dejavu"

import struct
import argparse

parser = argparse.ArgumentParser(
    description="ADCAM First Frame Example - Capture and save/display ToF frames",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  # Target with mode 2, show visualization
  python %(prog)s -m 2 -o show

  # Network with mode 3, save snapshot
  python %(prog)s -m 3 -i 192.168.56.1 -o snap

  # Target with mode 5, dump binary files
  python %(prog)s -m 5 -o bin

  # ADTF3066: fuse short-range mode 0 with long-range mode 7
  python %(prog)s --fuse 0,7 -o show
"""
)
parser.add_argument('-m', '--mode', type=int, default=None,
                    help='Frame mode number ; required unless --fuse is given')
parser.add_argument('-f', '--fuse', type=str, default='',
                    help='ADTF3066 only: fuse an SR mode (0, 1, 3, 6) with an LR mode (7, 8), '
                         'given as FIRST,SECOND e.g. --fuse 0,7 (the first mode leads). '
                         'Overrides -m. Not supported with --ip')
parser.add_argument('-i', '--ip', type=str, default='',
                    help='IP address for network connection (omit for target)')
parser.add_argument('-o', '--output', type=str, choices=['bin', 'snap', 'show'], default='show',
                    help='Output type: bin=binary dumps, snap=snapshot files, show=visualization (default: show)')

args = parser.parse_args()

mode = args.mode
ip = args.ip
output_type = args.output


fuse_pair = None
if args.fuse:
    try:
        fuse_pair = tuple(int(v) for v in args.fuse.split(','))
    except ValueError:
        fuse_pair = ()
    if len(fuse_pair) != 2:
        print(f"Error: invalid --fuse '{args.fuse}': expected FIRST,SECOND e.g. --fuse 0,7")
        exit(-1)
    if ip:
        print("Error: mode fusion is not supported with --ip")
        exit(-1)
elif mode is None:
    parser.error("-m/--mode is required unless --fuse is given")

system = tof.System()

print("SDK version: ", tof.getApiVersion(), " | branch: ", tof.getBranchVersion(), " | commit: ", tof.getCommitVersion())

cameras = []
if ip:
    print(f"Looking for camera on network @ {ip}.")
    ip = "ip:" + ip
    status = system.getCameraList(cameras, ip)
else:
    print("Looking for camera on Target.")
    status = system.getCameraList(cameras)
print("system.getCameraList()", status)

camera1 = cameras[0]

#create callback and register it to the interrupt routine
def callbackFunction(callbackStatus):
    print("Running the python callback for which the status of ADSD3500 has been forwarded. ADSD3500 status = ", callbackStatus)

sensor = camera1.getSensor()
status = sensor.adsd3500_register_interrupt_callback(callbackFunction)

status = camera1.initialize()
print("camera1.initialize()", status)

modes = []
status = camera1.getAvailableModes(modes)
print("camera1.getAvailableModes()", status)
print(modes)

if fuse_pair is None and int(mode) not in modes:
    print(f"Error: Unknown mode - {mode}")
    exit(-3)

camDetails = tof.CameraDetails()
status = camera1.getDetails(camDetails)
print("camera1.getDetails()", status)
print("camera1 details:", "id:", camDetails.cameraId, "connection:", camDetails.connection)

if fuse_pair is not None:
    first_mode, second_mode = fuse_pair
    status = camera1.setModeFusion(first_mode, second_mode)
    print("camera1.setModeFusion(", first_mode, ",", second_mode, ")", status)
    if status != tof.Status.Ok:
        exit(-3)
    mode = f"{first_mode}_{second_mode}"
else:
    status = camera1.setMode(int(mode))
    print("camera1.setMode(",mode,")", status)

# Example of getting/modifying/setting the current ADSD3500 parameters
# status, currentFrameProcessParams = camera1.getFrameProcessParams()
# currentFrameProcessParams["ab_thresh_min"] = "4"
# camera1.setFrameProcessParams(currentFrameProcessParams)

status = camera1.start()
print("camera1.start()", status)

frame = tof.Frame()

status = camera1.requestFrame(frame)
print("camera1.requestFrame()", status)

frameDataDetails = tof.FrameDataDetails()
status = frame.getDataDetails("depth", frameDataDetails)
print("frame.getDataDetails()", status)
print("depth frame details:", "width:", frameDataDetails.width, "height:", frameDataDetails.height, "type:", frameDataDetails.type)

status = camera1.stop()
print("camera1.stop()", status)

# Get frame details to check which data types are available
frameDetails = tof.FrameDetails()
status = frame.getDetails(frameDetails)

# Build a list of available frame types
available_types = [detail.type for detail in frameDetails.dataDetails]
print(f"Available frame types: {available_types}")

# Get frame data - only retrieve what's available
image_depth = None
image_ab = None
image_conf = None
image_xyz = None

# Get the depth frame
if "depth" in available_types:
    image_depth = np.asarray(frame.getData("depth"))
    print("Depth frame retrieved")
else:
    print("Warning: Depth frame not available")

# Get the AB frame
if "ab" in available_types:
    image_ab = np.asarray(frame.getData("ab"))
    print("AB frame retrieved")
else:
    print("Warning: AB frame not available (bitsInAB=0)")

# Get the confidence frame
if "conf" in available_types:
    image_conf = np.asarray(frame.getData("conf"))
    image_conf2 = image_conf.flatten()
    count = 0
    
    final_conf = np.zeros(frameDataDetails.width*frameDataDetails.height*4)
    for i in range(frameDataDetails.width*(frameDataDetails.height // 2)):
        packed_float = struct.pack('f', image_conf2[i])

    # Unpack the bytes into four uint8 values
        uint8_values = struct.unpack('2H', packed_float)
        array_data = np.array(uint8_values)
        for j in range(2):
            final_conf[count+j] = array_data[j]
            #print(j)
        count = count + 2
    image_conf = np.reshape(final_conf[frameDataDetails.width*frameDataDetails.height*0:frameDataDetails.width*frameDataDetails.height*1], \
                            [frameDataDetails.height,frameDataDetails.width])
    print("Confidence frame retrieved")
else:
    print("Warning: Confidence frame not available (bitsInConf=0)")

# Get the XYZ frame
if "xyz" in available_types:
    image_xyz = np.asarray(frame.getData("xyz"))
    print("XYZ frame retrieved")
else:
    print("Warning: XYZ frame not available (xyzEnable=0)")

metadata = tof.Metadata
status, metadata = frame.getMetadataStruct()

#Unregister callback
status = sensor.adsd3500_unregister_interrupt_callback(callbackFunction)

# Metadata values
sensor_temp = metadata.sensorTemperature
laser_temp = metadata.laserTemperature
frame_num = metadata.frameNumber
imager_mode = metadata.imagerMode

print("Sensor temperature from metadata: ", sensor_temp)
print("Laser temperature from metadata: ", laser_temp)
print("Frame number from metadata: ", frame_num)
print("Mode from metadata: ", imager_mode)

EQ_TRIM = 0.005  # ignore this fraction of valid pixels at each end (stray / flying pixels)
EQ_BLEND = 0.75  # 1 = fully equalised (most detail), 0 = linear (colour tracks distance)
MM_RANGE = np.arange(65536, dtype=np.float32)

def equalize_cdf(depth):
    """Auto colour scale: clip-limited histogram equalisation of valid depth.

    Returns a 65536-entry table mapping depth (mm) to its colour position in
    [0, 1], or None if no pixel is valid. Colours go where the pixels are, but no
    single mm value may take more than 1/256 of them, so a large flat surface
    (e.g. a wall) can't swallow the colormap. The outer EQ_TRIM of pixels at each
    end are clamped, and the result is blended with a linear scale (EQ_BLEND).
    """
    hist = np.bincount(depth[::2, ::2].astype(np.uint16, copy=False).ravel(),
                       minlength=65536).astype(np.float32)
    hist[0] = 0  # invalid depth
    total = hist.sum()
    if total == 0:
        return None
    cum = np.cumsum(hist)
    lo = int(np.searchsorted(cum, EQ_TRIM * total))
    hi = int(np.searchsorted(cum, (1 - EQ_TRIM) * total))
    hist[:lo] = 0
    hist[hi + 1:] = 0
    np.minimum(hist, max(1.0, hist.sum() / 256), out=hist)
    eq = np.cumsum(hist)
    eq /= eq[-1]
    lin = np.clip((MM_RANGE - lo) / max(hi - lo, 1), 0.0, 1.0)
    cdf = EQ_BLEND * eq + (1 - EQ_BLEND) * lin
    cdf[0] = 0.0
    return cdf

def cdf_ticks(cdf):
    """(colour position, mm) colorbar labels for an equalised scale."""
    return [(f, float(np.searchsorted(cdf, max(f, 1e-6)))) for f in (1.0, 0.75, 0.5, 0.25, 0.0)]

# Jet sampled at full 8-bit precision: 1020 distinct colours (cv2.COLORMAP_JET has 256).
_JET_T = np.linspace(0.0, 1.0, 4096)[:, None]
JET_LUT_BGR = (np.clip(1.5 - 4.0 * np.abs(_JET_T - [0.25, 0.5, 0.75]), 0.0, 1.0) * 255 + 0.5).astype(np.uint8)

def jet_bgr(norm):
    """Map values in [0, 1] to BGR uint8 using the 1020-colour jet."""
    return JET_LUT_BGR.take((np.clip(norm, 0.0, 1.0) * 4095 + 0.5).astype(np.uint16), axis=0)

def make_panel(image, title, jet=False, size=400, cdf=None, unit=""):
    """Render an image as a BGR panel with a title and a colorbar.

    cdf (from equalize_cdf) colours depth by histogram equalisation; otherwise
    the image min/max is used.
    """
    if cdf is not None:
        norm = cdf.take(np.asarray(image, dtype=np.uint16)).astype(np.float32)
        ticks = cdf_ticks(cdf)
    else:
        img = np.nan_to_num(np.asarray(image, dtype=np.float32))
        vmin, vmax = float(img.min()), float(img.max())
        norm = np.clip((img - vmin) / max(vmax - vmin, 1e-6), 0.0, 1.0)
        ticks = [(1.0, vmax), (0.0, vmin)]
    width = max(1, round(norm.shape[1] * size / norm.shape[0]))
    norm = cv2.resize(norm, (width, size), interpolation=cv2.INTER_NEAREST)
    ramp = np.repeat(np.linspace(1.0, 0.0, size, dtype=np.float32)[:, None], 20, axis=1)
    if jet:
        body, bar = jet_bgr(norm), jet_bgr(ramp)
        if cdf is not None:
            invalid = cv2.resize((np.asarray(image) == 0).astype(np.uint8), (width, size),
                                 interpolation=cv2.INTER_NEAREST) > 0
            body[invalid] = 0  # black, not the nearest-depth colour
    else:
        body = cv2.cvtColor((norm * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        bar = cv2.cvtColor((ramp * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    panel = np.full((size + 40, width + 100, 3), 255, dtype=np.uint8)
    panel[30:30 + size, :width] = body
    panel[30:30 + size, width + 10:width + 30] = bar
    text = dict(fontFace=cv2.FONT_HERSHEY_SIMPLEX, color=(0, 0, 0), lineType=cv2.LINE_AA)
    cv2.putText(panel, title, (5, 20), fontScale=0.6, thickness=1, **text)
    if unit:
        cv2.putText(panel, unit, (width + 34, 20), fontScale=0.45, thickness=1, **text)
    for frac, val in ticks:
        y = 30 + round((1.0 - frac) * (size - 1))
        cv2.putText(panel, f"{val:.0f}", (width + 34, y + 5), fontScale=0.45, thickness=1, **text)
    return panel

if output_type == 'show':
    panels = []
    if image_depth is not None:
        depth_cdf = equalize_cdf(image_depth)
        if depth_cdf is not None:
            print("Depth colours (auto, equalised): mm at colorbar ticks:",
                  [round(v) for _, v in cdf_ticks(depth_cdf)])
        panels.append(make_panel(image_depth, "Depth Image (auto)", jet=True,
                                 cdf=depth_cdf, unit="mm"))
    if image_ab is not None:
        panels.append(make_panel(image_ab, "AB Image"))
    if image_conf is not None:
        panels.append(make_panel(image_conf, "Confidence Image"))

    # Metadata as text
    info = np.full_like(panels[0], 255) if panels else np.full((440, 500, 3), 255, dtype=np.uint8)
    metadata_lines = [
        f"Sensor Temp: {sensor_temp} C",
        f"Laser Temp: {laser_temp} C",
        f"Frame #: {frame_num}",
        f"Mode: {imager_mode}",
    ]
    for i, line in enumerate(metadata_lines):
        cv2.putText(info, line, (20, 180 + i * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 0), 1, cv2.LINE_AA)
    panels.append(info)

    # 2-column grid
    if len(panels) % 2:
        panels.append(np.full_like(panels[0], 255))
    grid = np.vstack([np.hstack(panels[i:i + 2]) for i in range(0, len(panels), 2)])
    cv2.imshow("ADCAM First Frame", grid)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
elif output_type == 'snap':
    handler = tof.FrameHandler()
    base_name = "snapshot_mode_" + str(mode)
    status = handler.SnapShotFrames(base_name, frame)
    print("FrameHandler.SnapShotFrames()", status)
elif output_type == 'bin':
    # dump the files - only save frames that are available
    if image_depth is not None:
        image_depth.tofile("depth_mode_" + str(mode) + ".bin")
        print(f"Saved: depth_mode_{mode}.bin")
    if image_ab is not None:
        image_ab.tofile("ab_mode_" + str(mode) + ".bin")
        print(f"Saved: ab_mode_{mode}.bin")
    if image_conf is not None:
        image_conf.tofile("conf_mode_" + str(mode) + ".bin")
        print(f"Saved: conf_mode_{mode}.bin")
    if image_xyz is not None:
        image_xyz.tofile("xyz_mode_" + str(mode) + ".bin")
        print(f"Saved: xyz_mode_{mode}.bin")


