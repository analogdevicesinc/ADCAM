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
import argparse
import cv2 as cv
import open3d as o3d
import struct
import re

# ---- CONSTANTS ----
MEGA_PIXEL = 1024
QMEGA_PIXEL = [512, 640, 256, 320]
PNG_EXT = '.png'
PLY_EXT = '.ply'
METADATA_LENGTH = 128
RAW_PARSER_VERSION = "2.0.0"
DEFAULT_CONF_BYTES = 4
DEFAULT_AB_BYTES = 2
DEFAULT_XYZ_BYTES = 6
DEFAULT_DEPTH_BYTES = 2

def safe_join(*args):
    return os.path.join(*args)

def parse_frame_range(range_str):
    """
    Accepts range_str (e.g. '30', '30-', '30-40') and total_frames.
    Returns (start, end) inclusive.
    """

    match = re.fullmatch(r'(\d+)(?:-(\d*)?)?', range_str)
    if not match:
        raise ValueError(f"Invalid frame range: {range_str}")
    start = int(match.group(1))
    end = match.group(2)
    return start, end

def generate_metadata(metadata, directory, base_filename, index):
    meta_path = safe_join(directory, f'metadata_{base_filename}_{index}.txt')
    with open(meta_path, 'w') as outfile:
        outfile.writelines(f'Metadata for frame {index}:\n')
        outfile.writelines(f'frameWidth: {metadata.width}\n')
        outfile.writelines(f'frameHeight: {metadata.height}\n')
        outfile.writelines(f'outputconfig: {metadata.outputConfiguration}\n')
        outfile.writelines(f'depthPhaseBits: {metadata.bitsInDepth}\n')
        outfile.writelines(f'ABBits: {metadata.bitsInAb}\n')
        outfile.writelines(f'confidenceBits: {metadata.bitsInConfidence}\n')
        outfile.writelines(f'invalidPhaseValue: {metadata.invalidPhaseValue}\n')
        outfile.writelines(f'frequencyIndex: {metadata.frequencyIndex}\n')
        outfile.writelines(f'frameNumber: {metadata.frameNumber}\n')
        outfile.writelines(f'imagerMode: {metadata.imagerMode}\n')
        outfile.writelines(f'numberOfPhases: {metadata.numberOfPhases}\n')
        outfile.writelines(f'numberOfFrequencies: {metadata.numberOfFrequencies}\n')
        outfile.writelines(f'ElapsedTimeinFrac: {metadata.elapsedTimeFractionalValue}\n')
        outfile.writelines(f'ElapsedTimeinSec: {metadata.elapsedTimeSecondsValue}\n')
        outfile.writelines(f'sensorTemp: {metadata.sensorTemperature}\n')
        outfile.writelines(f'laserTemp: {metadata.laserTemperature}\n')

def generate_depth(depth_data, directory, base_filename, index):
    depth_frame = np.reshape(depth_data, (depth_data.shape[0], depth_data.shape[1]))
    norm_depth = cv.normalize(depth_frame, None, 0, 255, cv.NORM_MINMAX, dtype=cv.CV_8U)
    color_depth = cv.applyColorMap(norm_depth, cv.COLORMAP_TURBO)
    img = o3d.geometry.Image(color_depth)
    o3d.io.write_image(safe_join(directory, f'depth_{base_filename}_{index}{PNG_EXT}'), img)

def generate_ab(ab_frame, directory, base_filename, index, log_image = False):
    norm_ab = cv.normalize(ab_frame, None, 0, 255, cv.NORM_MINMAX, dtype=cv.CV_8U)
    if log_image:
        c = 255 / np.log(1 + np.max(norm_ab))
        norm_ab = c * (np.log(norm_ab + 1))
        norm_ab = np.array(norm_ab, dtype=np.uint8)
    else:
        norm_ab = np.uint8(norm_ab)
    norm_ab = cv.cvtColor(norm_ab, cv.COLOR_GRAY2RGB)
    img = o3d.geometry.Image(norm_ab)
    o3d.io.write_image(safe_join(directory, f'ab_{base_filename}_{index}{PNG_EXT}'), img)

def generate_confidence(conf_frame, directory, base_filename, index):
    norm_conf = cv.normalize(conf_frame, None, 0, 255, cv.NORM_MINMAX, dtype=cv.CV_8U)
    norm_conf = 255 - np.uint8(norm_conf)
    img = o3d.geometry.Image(norm_conf)
    o3d.io.write_image(safe_join(directory, f'conf_{base_filename}_{index}{PNG_EXT}'), img)

def generate_pcloud(xyz_frame, directory, base_filename, index, height, width):
    xyz_frame = xyz_frame.view(np.int16)
    xyz_frame = xyz_frame.reshape(-1, 3)
    point_cloud = o3d.geometry.PointCloud()
    point_cloud.points = o3d.utility.Vector3dVector(xyz_frame)
    point_cloud.transform([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
    o3d.io.write_point_cloud(safe_join(directory, f'pointcloud_{base_filename}_{index}{PLY_EXT}'), point_cloud)

def generate_vid(main_dir, base_filename, processed_frames, width, height):
    vid_dir = safe_join(main_dir, f'vid_{base_filename}')
    make_dir(vid_dir)
    video_path = safe_join(vid_dir, f'vid_{base_filename}.mp4')
    video = cv.VideoWriter(video_path, cv.VideoWriter_fourcc(*"mp4v"), 10, (width * 2, height))
    for i in processed_frames:
        frame_dir = safe_join(main_dir, f"{base_filename}_{i}")
        depth_img = cv.imread(safe_join(frame_dir, f'depth_{base_filename}_{i}{PNG_EXT}'))
        ab_img = cv.imread(safe_join(frame_dir, f'ab_{base_filename}_{i}{PNG_EXT}'))
        if depth_img is None or ab_img is None:
            continue
        new_img = cv.hconcat([depth_img, ab_img])
        new_img = cv.resize(new_img, (width * 2, height))
        video.write(new_img)
    video.release()

def main():
    parser = argparse.ArgumentParser(
        description='Script to parse a raw file and extract different frame data')
    parser.add_argument("filename", type=str, help="bin filename to parse")
    parser.add_argument("-o", "--outdir", type=str, default=None, help="Output directory (optional)")
    parser.add_argument("-f", "--frames", type=str, default=None,
                        help="Frame range: N (just N), N- (from N to end), N-M (N to M inclusive)")
    args = parser.parse_args()

    if not os.path.exists(args.filename):
        sys.exit(f"Error: {args.filename} does not exist")

    base_filename, _ = os.path.splitext(os.path.basename(args.filename))
    if args.outdir:
        dir_path = os.path.abspath(args.outdir)
    else:
        base_dir, _ = os.path.splitext(args.filename)
        dir_path = base_dir

    print(f"rawparser {RAW_PARSER_VERSION}\nfilename: {args.filename}")

    system = tof.System()

    print("SDK version: ", tof.getApiVersion(), " | branch: ", tof.getBranchVersion(), " | commit: ", tof.getCommitVersion())

    # --- Parse frame range argument ---
    start_frame, end_frame = 0, sys.maxsize
    if args.frames:
        try:
            start_frame, end_frame = parse_frame_range(args.frames)
        except Exception as e:
            sys.exit(f"Invalid --frames argument: {e}")

    cameras = []
    status = system.getCameraList(cameras, "offline:")
    print("system.getCameraList()", status)

    camera1 = cameras[0]

    sensor = camera1.getSensor()
    
    status = camera1.initialize()
    if (status != tof.Status.Ok):
        sys.exit(f"Error: camera1.initialize() failed with status {status}")

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    status = camera1.setPlaybackFile(args.filename)
    status = camera1.setMode(0)
    status = camera1.start()

    status = tof.Status.Ok
    
    frame_idx = start_frame
    while (status == tof.Status.Ok):
        print(f"\rProcessing Frame: {frame_idx}", end='', flush=True)
        frame = tof.Frame()
        status = camera1.requestFrame(frame, frame_idx)
        if (status != tof.Status.Ok):
            print("No more frames to read from file.")
            break

        frameDataDetails = tof.FrameDataDetails()
        status = frame.getDataDetails("depth", frameDataDetails)

        height = frameDataDetails.height
        width = frameDataDetails.width

        # Process Metadata
        metadata = tof.Metadata
        status, metadata = frame.getMetadataStruct()
        if (status != tof.Status.Ok):
            print("Cannot read metadata from frame.")
            break


        frame_dir = safe_join(dir_path, f"{base_filename}_{frame_idx}")
        if not os.path.exists(frame_dir):
            os.makedirs(frame_dir)
    
        str_frame_idx = str(frame_idx).zfill(6)
        generate_metadata(metadata, frame_dir, base_filename, str_frame_idx)
        generate_depth(np.asarray(frame.getData("depth")), frame_dir, base_filename, str_frame_idx)
        generate_ab(np.asarray(frame.getData("ab")), frame_dir, base_filename, str_frame_idx, log_image = False)
        generate_confidence(np.asarray(frame.getData("conf")), frame_dir, base_filename, str_frame_idx)
        generate_pcloud(np.asarray(frame.getData("xyz")), frame_dir, base_filename, str_frame_idx, height, width)

        frame_idx += 1
        if frame_idx > end_frame:
            break

    print(f"Processed {frame_idx} frames.")

    camera1.stop()

if __name__ == "__main__":
    main()
