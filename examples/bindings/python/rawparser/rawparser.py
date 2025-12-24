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
from PIL import Image

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

# RGB Frame Constants (for direct binary extraction)
DEPTH_FRAME_SIZE_MP = 4194304   # Mode 0: 1024*1024*4 bytes (Depth+AB)
DEPTH_FRAME_SIZE_QMP = 2621440  # QMP modes: 512*512*10 bytes (Depth+AB+Conf+XYZ)
RGB_FRAME_SIZE = 3456000        # 1920x1200 NV12 format
RGB_WIDTH = 1920
RGB_HEIGHT = 1200

def safe_join(*args):
    return os.path.join(*args)

def nv12_to_rgb(nv12_data, width, height):
    """
    Convert NV12 format to RGB using BT.601 coefficients

    NV12 Layout:
    - Y plane: width * height bytes (luminance)
    - UV plane: width * height / 2 bytes (chrominance, interleaved)
    """
    y_size = width * height
    uv_size = y_size // 2

    # Extract Y and UV planes
    y_plane = np.frombuffer(nv12_data[:y_size], dtype=np.uint8).reshape((height, width))
    uv_plane = np.frombuffer(nv12_data[y_size:y_size + uv_size], dtype=np.uint8).reshape((height // 2, width // 2, 2))

    # Upsample UV to full resolution
    u = np.repeat(np.repeat(uv_plane[:, :, 0], 2, axis=0), 2, axis=1)
    v = np.repeat(np.repeat(uv_plane[:, :, 1], 2, axis=0), 2, axis=1)

    # Convert to float for calculations
    y = y_plane.astype(np.float32)
    u = u.astype(np.float32) - 128.0
    v = v.astype(np.float32) - 128.0

    # BT.601 conversion (standard for SD video)
    r = y + 1.402 * v
    g = y - 0.344136 * u - 0.714136 * v
    b = y + 1.772 * u

    # Clip and convert to uint8
    rgb = np.stack([
        np.clip(r, 0, 255).astype(np.uint8),
        np.clip(g, 0, 255).astype(np.uint8),
        np.clip(b, 0, 255).astype(np.uint8)
    ], axis=2)

    return rgb

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
    end_str = match.group(2)
    end = int(end_str) if end_str else sys.maxsize
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
    try:
        # XYZ is stored as uint16 array but represents int16 values (3 per pixel)
        xyz_data = xyz_frame.view(np.int16)
        total_pixels = height * width
        expected_size = total_pixels * 3

        if xyz_data.size < expected_size:
            print(f"Warning: XYZ data size mismatch. Expected {expected_size}, got {xyz_data.size}")
            return

        # Reshape to (N, 3) for point cloud
        xyz_data = xyz_data[:expected_size].reshape(total_pixels, 3)

        point_cloud = o3d.geometry.PointCloud()
        point_cloud.points = o3d.utility.Vector3dVector(xyz_data.astype(np.float64))
        point_cloud.transform([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
        o3d.io.write_point_cloud(safe_join(directory, f'pointcloud_{base_filename}_{index}{PLY_EXT}'), point_cloud)
        except Exception as e:
        print(f"Error generating point cloud: {e}")

def generate_rgb(rgb_data, directory, base_filename, index):
    """Generate RGB PNG from NV12 binary data"""
    try:
        rgb_image = nv12_to_rgb(rgb_data, RGB_WIDTH, RGB_HEIGHT)
        output_path = safe_join(directory, f'rgb_{base_filename}_{index}{PNG_EXT}')
        Image.fromarray(rgb_image).save(output_path)
    except Exception as e:
        print(f"\nWarning: Failed to generate RGB frame {index}: {e}")


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

    # Get first frame to determine dimensions
    frame = tof.Frame()
    status = camera1.requestFrame(frame, 0)
    if status != tof.Status.Ok:
        sys.exit("Error: Cannot read first frame to get dimensions")

    frameDataDetails = tof.FrameDataDetails()
    frame.getDataDetails("depth", frameDataDetails)
    width = frameDataDetails.width
    height = frameDataDetails.height

    print(f"Frame dimensions: {width}x{height}")

    # Open binary file for direct RGB extraction from concatenated buffers
    rgb_file_handle = None
    header_offset = 0
    try:
        rgb_file_handle = open(args.filename, 'rb')
        # Skip header
        marker = struct.unpack('I', rgb_file_handle.read(4))[0]
        if marker == 0xFFFFFFFF:
            header_size = struct.unpack('I', rgb_file_handle.read(4))[0]
            rgb_file_handle.read(header_size)
            header_offset = 8 + header_size
            print(f"RGB extraction enabled (skipped {header_size} byte header)")
        else:
            print("Warning: Could not find frame marker, RGB extraction may fail")
            rgb_file_handle = None
    except Exception as e:
        print(f"Warning: Could not open file for RGB extraction: {e}")
        rgb_file_handle = None

    # Calculate RGB offset within frame buffer
    # File format: [Depth|AB|RGB] (no XYZ, no metadata in file)
    depth_size = width * height * 2  # uint16_t
    ab_size = width * height * 2      # uint16_t
    rgb_offset_in_frame = depth_size + ab_size

    frame_idx = start_frame
    while (status == tof.Status.Ok):
        print(f"\rProcessing Frame: {frame_idx}", end='', flush=True)
        frame = tof.Frame()
        status = camera1.requestFrame(frame, frame_idx)
        if (status != tof.Status.Ok):
            print("No more frames to read from file.")
            break

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
        print(f"\nDebug: Processing frame {frame_idx}")
        # Process Depth
        try:
            depth_details = tof.FrameDataDetails()
            status_depth = frame.getDataDetails("depth", depth_details)
            if status_depth == tof.Status.Ok:
                print(f"  - Extracting depth ({depth_details.width}x{depth_details.height})")
                depth_data = frame.getData("depth")
                depth_arr = np.array(depth_data, copy=False)
                generate_depth(depth_arr, frame_dir, base_filename, str_frame_idx)
                print(f"    Saved depth PNG")
        except Exception as e:
            print(f"  Error processing depth: {e}")

        # Process AB
        try:
            ab_details = tof.FrameDataDetails()
            status_ab = frame.getDataDetails("ab", ab_details)
            if status_ab == tof.Status.Ok:
                print(f"  - Extracting AB ({ab_details.width}x{ab_details.height})")
                ab_data = frame.getData("ab")
                ab_arr = np.array(ab_data, copy=False)
                generate_ab(ab_arr, frame_dir, base_filename, str_frame_idx)
                print(f"    Saved AB PNG")
        except Exception as e:
            print(f"  Error processing AB: {e}")

        # Process XYZ (commented out due to segfault)
        # try:
        #     xyz_details = tof.FrameDataDetails()
        #     status_xyz = frame.getDataDetails("xyz", xyz_details)
        #     if status_xyz == tof.Status.Ok:
        #         print(f"  - Extracting XYZ point cloud ({xyz_details.width}x{xyz_details.height})")
        #         xyz_data = frame.getData("xyz")
        #         xyz_arr = np.array(xyz_data, copy=False)
        #         generate_pcloud(xyz_arr, frame_dir, base_filename, str_frame_idx, xyz_details.height, xyz_details.width)
        #         print(f"    Saved point cloud PLY")
        # except Exception as e:
        #     print(f"  Error processing XYZ: {e}")

        # Extract RGB from concatenated frame buffer
        # File format: [Depth|AB|RGB] - RGB starts at depth_size + ab_size
        if rgb_file_handle is not None:
            try:
                # Calculate position of current frame in file
                frame_position = header_offset
                for i in range(frame_idx):
                    rgb_file_handle.seek(frame_position)
                    frame_marker = struct.unpack('I', rgb_file_handle.read(4))[0]
                    frame_size = struct.unpack('I', rgb_file_handle.read(4))[0]
                    frame_position += 8 + frame_size

                # Now at current frame
                rgb_file_handle.seek(frame_position)
                frame_marker = struct.unpack('I', rgb_file_handle.read(4))[0]
                frame_size = struct.unpack('I', rgb_file_handle.read(4))[0]

                # Check if RGB is in this frame (frame > depth+AB only)
                if frame_size > (depth_size + ab_size):
                    # Seek to RGB data within frame buffer
                    rgb_file_handle.seek(frame_position + 8 + rgb_offset_in_frame)
                    rgb_data = rgb_file_handle.read(RGB_FRAME_SIZE)

                    if len(rgb_data) == RGB_FRAME_SIZE:
                        print(f"  - Extracting RGB (1920x1200, NV12 format)")
                        generate_rgb(rgb_data, frame_dir, base_filename, str_frame_idx)
                        print(f"    Saved RGB PNG")
                    else:
                        print(f"  RGB data incomplete: {len(rgb_data)} bytes (expected {RGB_FRAME_SIZE})")
                else:
                    print(f"  - No RGB in frame (size: {frame_size} bytes, needs > {depth_size + ab_size})")
            except Exception as e:
                print(f"  Error extracting RGB: {e}")

        frame_idx += 1
        if frame_idx > end_frame:
            break

    print(f"Processed {frame_idx - start_frame} frames."

    if rgb_file_handle is not None:
    rgb_file_handle.close()

    camera1.stop()

if __name__ == "__main__":
    main()
