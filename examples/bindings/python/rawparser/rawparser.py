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


def generate_ab(ab_frame, directory, base_filename, index, log_image=False):
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
    # Normalize confidence to 0-255 range
    norm_conf = cv.normalize(conf_frame, None, 0, 255, cv.NORM_MINMAX, dtype=cv.CV_8U)
    # Apply TURBO colormap for better visualization (high confidence = warm colors)
    color_conf = cv.applyColorMap(norm_conf, cv.COLORMAP_TURBO)
    output_path = safe_join(directory, f'conf_{base_filename}_{index}{PNG_EXT}')
    cv.imwrite(output_path, color_conf)


def generate_pcloud(xyz_frame, directory, base_filename, index, height, width):
    try:
        # Convert to numpy array with proper type
        xyz_arr = np.array(xyz_frame, dtype=np.uint16, copy=False)

        print(f"    XYZ array info: shape={xyz_arr.shape}, size={xyz_arr.size}, dtype={xyz_arr.dtype}")

        # Check if already in correct shape (height, width, 3)
        if len(xyz_arr.shape) == 3 and xyz_arr.shape[2] == 3:
            # Already shaped as (height, width, 3) - flatten to (N, 3)
            xyz_arr = xyz_arr.reshape(-1, 3)
        elif len(xyz_arr.shape) == 1:
            # Flat array - reshape to (N, 3)
            total_pixels = height * width
            expected_size = total_pixels * 3
            if xyz_arr.size != expected_size:
                print(f"    Warning: XYZ data size mismatch. Expected {expected_size}, got {xyz_arr.size}")
                if xyz_arr.size < expected_size:
                    print(f"    Insufficient XYZ data, skipping point cloud")
                    return
            xyz_arr = xyz_arr.reshape(total_pixels, 3)
        else:
            print(f"    Unexpected XYZ array shape: {xyz_arr.shape}")
            return

        # Convert uint16 to int16 (XYZ values are signed)
        xyz_signed = xyz_arr.view(np.int16).astype(np.float64)

        # Remove invalid points (all zeros or out of range)
        valid_mask = np.any(xyz_signed != 0, axis=1)
        xyz_valid = xyz_signed[valid_mask]

        if xyz_valid.shape[0] == 0:
            print(f"    No valid points in XYZ data, skipping point cloud")
            return

        print(f"    Valid points: {xyz_valid.shape[0]} / {xyz_signed.shape[0]}")

        # Apply transformation manually (flip Y and Z axes)
        xyz_transformed = xyz_valid.copy()
        xyz_transformed[:, 1] *= -1  # Flip Y
        xyz_transformed[:, 2] *= -1  # Flip Z

        # Write PLY file manually to avoid Open3D issues
        output_path = safe_join(directory, f'pointcloud_{base_filename}_{index}{PLY_EXT}')
        with open(output_path, 'w') as f:
            # PLY header
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write(f"element vertex {xyz_transformed.shape[0]}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("end_header\n")
            # Write vertices
            for point in xyz_transformed:
                f.write(f"{point[0]} {point[1]} {point[2]}\n")

        print(f"    Point cloud saved ({xyz_transformed.shape[0]} points)")

    except Exception as e:
        print(f"    Error generating point cloud: {e}")
        import traceback
        traceback.print_exc()


def generate_rgb(rgb_data, directory, base_filename, index, width, height):
    """Generate RGB JPG from BGR data (SDK already converted from NV12)"""
    try:
        # SDK returns BGR format (3 bytes per pixel)
        # rgb_data should already be reshaped to (height, width, 3)
        if isinstance(rgb_data, np.ndarray):
            if rgb_data.ndim == 3 and rgb_data.shape == (height, width, 3):
                # Already in correct BGR format
                bgr_image = rgb_data
            elif rgb_data.ndim == 2 and rgb_data.shape == (height, width):
                # Grayscale - replicate to 3 channels
                bgr_image = cv.cvtColor(rgb_data, cv.COLOR_GRAY2BGR)
            else:
                # Try to reshape
                bgr_image = rgb_data.reshape((height, width, 3))
        else:
            # Convert to numpy array and reshape
            bgr_image = np.array(rgb_data, dtype=np.uint8, copy=False)
            bgr_image = bgr_image.reshape((height, width, 3))

        # Save as JPG (OpenCV handles BGR natively)
        output_path = safe_join(directory, f'rgb_{base_filename}_{index}.jpg')
        cv.imwrite(output_path, bgr_image, [cv.IMWRITE_JPEG_QUALITY, 95])
    except Exception as e:
        print(f"\nWarning: Failed to generate RGB frame {index}: {e}")
        import traceback
        traceback.print_exc()


def find_latest_adcam_file():
    """
    Find the latest .adcam file in the data_collect media folder.
    Returns the absolute path to the latest file, or None if not found.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.abspath(os.path.join(script_dir, '../../../../build'))
    media_dir = os.path.join(build_dir, 'examples', 'data_collect', 'media')

    if not os.path.exists(media_dir):
        return None

    # Find all .adcam files
    adcam_files = [f for f in os.listdir(media_dir) if f.endswith('.adcam')]
    if not adcam_files:
        return None

    # Return the latest file (by modification time)
    latest_file = max([os.path.join(media_dir, f) for f in adcam_files],
                      key=os.path.getmtime)
    return latest_file


def generate_vid(main_dir, base_filename, processed_frames, width, height):
    vid_dir = safe_join(main_dir, f'vid_{base_filename}')
    if not os.path.exists(vid_dir):
        os.makedirs(vid_dir)
    video_path = safe_join(vid_dir, f'vid_{base_filename}.mp4')
    fourcc = cv.VideoWriter_fourcc(*"mp4v")
    video = cv.VideoWriter(video_path, fourcc, 10, (width * 2, height))
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
        description='Script to parse a raw file and extract different frame data'
    )
    parser.add_argument(
        "filename", nargs='?', type=str, default=None,
        help=".adcam filename to parse (optional, auto-finds latest from "
             "data_collect if not provided)"
    )
    parser.add_argument("-o", "--outdir", type=str, default=None,
                        help="Output directory (optional)")
    parser.add_argument(
        "-f", "--frames", type=str, default=None,
        help="Frame range: N (just N), N- (from N to end), "
             "N-M (N to M inclusive)"
    )
    args = parser.parse_args()

    # Auto-detect latest .adcam file if not provided
    if args.filename is None:
        args.filename = find_latest_adcam_file()
        if args.filename is None:
            sys.exit(
                "Error: No .adcam file provided and no latest file found in "
                "data_collect media folder"
            )
        print(f"Auto-detected latest file: {args.filename}")

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

    print("SDK version: ", tof.getApiVersion(),
          " | branch: ", tof.getBranchVersion(),
          " | commit: ", tof.getCommitVersion())

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
    if status != tof.Status.Ok:
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

    # Use SDK's getData("rgb") API (already converts NV12→BGR)
    print("RGB extraction enabled via SDK API")

    frame_idx = start_frame
    while status == tof.Status.Ok:
        print(f"\rProcessing Frame: {frame_idx}", end='', flush=True)
        frame = tof.Frame()
        status = camera1.requestFrame(frame, frame_idx)
        if status != tof.Status.Ok:
            print("No more frames to read from file.")
            break

        # Process Metadata
        metadata = tof.Metadata
        status, metadata = frame.getMetadataStruct()
        if status != tof.Status.Ok:
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

        # Process Confidence
        try:
            conf_details = tof.FrameDataDetails()
            status_conf = frame.getDataDetails("conf", conf_details)
            if status_conf == tof.Status.Ok:
                print(f"  - Extracting Confidence ({conf_details.width}x{conf_details.height})")
                conf_data = frame.getData("conf")
                conf_arr = np.array(conf_data, copy=False)
                generate_confidence(conf_arr, frame_dir, base_filename, str_frame_idx)
                print(f"    Saved confidence PNG")
        except Exception as e:
            print(f"  Error processing confidence: {e}")

        # Process RGB - extract from end of buffer (appended after depth+AB+conf)
        # NOTE: RGB is recorded as BGR (3 bytes/pixel) appended AFTER ToF data
        # The SDK's getData("rgb") doesn't work correctly for old recordings
        # due to metadata issues
        # So we'll extract it manually from the full frame buffer
        try:
            # First check if RGB metadata exists
            rgb_details = tof.FrameDataDetails()
            status_rgb = frame.getDataDetails("rgb", rgb_details)
            
            if (status_rgb == tof.Status.Ok and rgb_details.width > 0 and
                    rgb_details.height > 0):
                print(
                    f"  - Extracting RGB ({rgb_details.width}x{rgb_details.height}) "
                    f"- manual extraction"
                )
                
                
                # Try to use getData("rgb") first - if it returns correct size, use it
                try:
                    rgb_data = frame.getData("rgb")
                    rgb_arr = np.array(rgb_data, copy=False)
                    
                    # BGR format: 3 bytes per pixel
                    expected_rgb_size = (
                        rgb_details.width * rgb_details.height * 3
                    )
                    
                    
                    # If getData returns flat grayscale (wrong size),
                    # we need alternative approach
                    if rgb_arr.size < expected_rgb_size:
                        print(
                            f"    WARNING: SDK returned incomplete RGB data "
                            f"({rgb_arr.size} < {expected_rgb_size} bytes)"
                        )
                    else:
                        # SDK returned correct size - reshape and save
                        if len(rgb_arr.shape) == 1:
                            rgb_arr = rgb_arr.reshape(
                                (rgb_details.height, rgb_details.width, 3)
                            )
                        
                        # Data is in BGR format - save directly
                        generate_rgb(
                            rgb_arr, frame_dir, base_filename, str_frame_idx,
                            rgb_details.width, rgb_details.height
                        )
                        print(f"    Saved RGB JPG")
                        
                except Exception as inner_e:
                    print(f"    Could not extract RGB: {inner_e}")
            else:
                print(f"  - No RGB metadata in frame")
                
        except Exception as e:
            print(f"  Error processing RGB: {e}")
            import traceback
            traceback.print_exc()

        # Process XYZ
        try:
            xyz_details = tof.FrameDataDetails()
            status_xyz = frame.getDataDetails("xyz", xyz_details)
            if (status_xyz == tof.Status.Ok and xyz_details.width > 0 and
                    xyz_details.height > 0):
                print(
                    f"  - Extracting XYZ point cloud "
                    f"({xyz_details.width}x{xyz_details.height})"
                )
                xyz_data = frame.getData("xyz")
                xyz_arr = np.array(xyz_data, copy=False)
                generate_pcloud(xyz_arr, frame_dir, base_filename, str_frame_idx,
                                xyz_details.height, xyz_details.width)
                print(f"    Saved point cloud PLY")
            else:
                print(f"  - No XYZ data available in frame")
        except Exception as e:
            print(f"  Error processing XYZ: {e}")
            import traceback
            traceback.print_exc()

        frame_idx += 1
        if frame_idx > end_frame:
            break

    print(f"Processed {frame_idx - start_frame} frames.")

    camera1.stop()


if __name__ == "__main__":
    main()
