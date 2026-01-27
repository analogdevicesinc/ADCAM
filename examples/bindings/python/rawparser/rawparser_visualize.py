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

"""
PNG and PLY File Visualizer

This script visualizes PNG images and PLY point cloud files.
It can display single files or multiple files from a directory.

Usage:
    python visualize_data.py --file <path_to_file>
    python visualize_data.py --directory <path_to_directory>
    python visualize_data.py --directory <path> --filter depth
"""

import argparse
import os
import sys
import glob
import cv2 as cv
import open3d as o3d
import numpy as np
import time


def visualize_ply(file_path):
    """
    Visualize a PLY point cloud using Open3D.
    
    Args:
        file_path: Path to the PLY file
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return False
    
    print(f"Loading PLY: {file_path}")
    
    try:
        point_cloud = o3d.io.read_point_cloud(file_path)
        
        if not point_cloud.has_points():
            print(f"Error: No points found in {file_path}")
            return False
        
        num_points = np.asarray(point_cloud.points).shape[0]
        has_colors = point_cloud.has_colors()
        has_normals = point_cloud.has_normals()
        
        print(f"  Number of points: {num_points}")
        print(f"  Has colors: {has_colors}")
        print(f"  Has normals: {has_normals}")
        
        # Get bounding box info
        if num_points > 0:
            points = np.asarray(point_cloud.points)
            min_bound = np.min(points, axis=0)
            max_bound = np.max(points, axis=0)
            print(f"  Bounding box min: [{min_bound[0]:.2f}, {min_bound[1]:.2f}, {min_bound[2]:.2f}]")
            print(f"  Bounding box max: [{max_bound[0]:.2f}, {max_bound[1]:.2f}, {max_bound[2]:.2f}]")
        
        # Visualize
        print(f"Visualizing point cloud.")
        print("Close the window or press 'Q' to continue...")
        
        # Create visualizer with custom settings
        vis = o3d.visualization.Visualizer()
        vis.create_window(window_name=os.path.basename(file_path), width=1200, height=900)
        vis.add_geometry(point_cloud)
        
        # Set point size to 1
        render_option = vis.get_render_option()
        render_option.point_size = 1.0
        
        vis.run()
        vis.destroy_window()
        
        return True
        
    except Exception as e:
        print(f"Error loading PLY file: {e}")
        return False


def read_metadata(file_path):
    """
    Read and display metadata from a text file.
    
    Args:
        file_path: Path to the metadata text file
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return False
    
    print(f"Reading metadata: {file_path}")
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            print("-" * 60)
            print(content)
            print("-" * 60)
        return True
    except Exception as e:
        print(f"Error reading metadata file: {e}")
        return False


def visualize_directory(directory, view_mode='metadata'):
    """
    Visualize first file of each type in a directory.
    
    Args:
        directory: Path to directory containing files
        view_mode: What to display - 'metadata', 'png', or 'pointcloud' (default: 'metadata')
    """
    if not os.path.isdir(directory):
        print(f"Error: Directory not found: {directory}")
        return
    
    # New behavior: auto-detect and show first of each type
    print(f"\nScanning directory: {directory}")
    print("Looking for first file of each type...\n")
    
    files_to_show = []
    
    # Find first metadata file
    metadata_files = sorted(glob.glob(os.path.join(directory, "metadata*.txt")))
    if metadata_files:
        files_to_show.append(('metadata', metadata_files[0]))
        print(f"✓ Found metadata: {os.path.basename(metadata_files[0])}")
    else:
        print("✗ No metadata*.txt files found")
    
    # Find first AB file
    ab_files = sorted(glob.glob(os.path.join(directory, "ab*.png")))
    if ab_files:
        files_to_show.append(('ab', ab_files[0]))
        print(f"✓ Found AB image: {os.path.basename(ab_files[0])}")
    else:
        print("✗ No ab*.png files found")
    
    # Find first confidence file
    conf_files = sorted(glob.glob(os.path.join(directory, "conf*.png")))
    if conf_files:
        files_to_show.append(('conf', conf_files[0]))
        print(f"✓ Found confidence image: {os.path.basename(conf_files[0])}")
    else:
        print("✗ No conf*.png files found")
    
    # Find first depth file
    depth_files = sorted(glob.glob(os.path.join(directory, "depth*.png")))
    if depth_files:
        files_to_show.append(('depth', depth_files[0]))
        print(f"✓ Found depth image: {os.path.basename(depth_files[0])}")
    else:
        print("✗ No depth*.png files found")
    
    # Find first RGB file (saved as JPG by rawparser)
    rgb_files = sorted(glob.glob(os.path.join(directory, "rgb*.jpg")))
    if rgb_files:
        files_to_show.append(('rgb', rgb_files[0]))
        print(f"✓ Found RGB image: {os.path.basename(rgb_files[0])}")
    else:
        print("✗ No rgb*.jpg files found")
    
    # Find first pointcloud file
    pc_files = sorted(glob.glob(os.path.join(directory, "pointcloud*.ply")))
    if pc_files:
        files_to_show.append(('pointcloud', pc_files[0]))
        print(f"✓ Found point cloud: {os.path.basename(pc_files[0])}")
    else:
        print("✗ No pointcloud*.ply files found")
    
    if not files_to_show:
        print(f"\nNo data files found in {directory}")
        return
    
    print(f"\nDisplaying {len(files_to_show)} file(s)...\n")
    
    # Filter files based on view mode
    if view_mode == 'metadata':
        files_to_show = [(ft, fp) for ft, fp in files_to_show if ft == 'metadata']
        if not files_to_show:
            print("No metadata files to display")
            return
    elif view_mode == 'png':
        files_to_show = [(ft, fp) for ft, fp in files_to_show if ft in ['ab', 'depth', 'conf', 'rgb']]
        if not files_to_show:
            print("No PNG files to display")
            return
    elif view_mode == 'pointcloud':
        files_to_show = [(ft, fp) for ft, fp in files_to_show if ft == 'pointcloud']
        if not files_to_show:
            print("No point cloud files to display")
            return
    
    # Collect images for combined display
    images_dict = {}
    pointcloud_file = None
    metadata_file = None
    
    # Display each file
    for i, (file_type, file_path) in enumerate(files_to_show, 1):
        print(f"\n{'=' * 60}")
        print(f"File {i}/{len(files_to_show)}: {file_type.upper()}")
        print(f"{'=' * 60}")
        
        if file_type == 'metadata':
            metadata_file = file_path
            read_metadata(file_path)
        elif file_type == 'pointcloud':
            # Store for later display
            pointcloud_file = file_path
        elif file_type in ['ab', 'depth', 'conf', 'rgb']:
            # Load image for combined display
            if os.path.exists(file_path):
                img = cv.imread(file_path, cv.IMREAD_UNCHANGED)
                if img is not None:
                    images_dict[file_type] = img
                    height, width = img.shape[:2]
                    channels = 1 if len(img.shape) == 2 else img.shape[2]
                    print(f"  Loaded: {width}x{height}, {channels} channel(s)")
    
    # Create combined display if we have images
    if images_dict:
            print(f"\n{'=' * 60}")
            print(f"Creating combined display...")
            print(f"{'=' * 60}")
            
            # Prepare images in order: RGB, AB, Depth, Confidence
            display_order = [('rgb', 'RGB'), ('ab', 'AB'), ('depth', 'Depth'), ('conf', 'Confidence')]
            valid_images = [(file_type, label, images_dict[file_type]) 
                           for file_type, label in display_order 
                           if file_type in images_dict]
            
            if valid_images:
                # Find common height (use max height, resize others)
                max_height = max(img.shape[0] for _, _, img in valid_images)
                
                # Normalize and resize images
                processed_images = []
                for file_type, label, img in valid_images:
                    # Normalize to 8-bit for display
                    if img.dtype == np.uint16:
                        normalized = cv.normalize(img, None, 0, 255, cv.NORM_MINMAX, dtype=cv.CV_8U)
                    else:
                        normalized = img
                    
                    # Convert grayscale to BGR for consistent stacking (but keep RGB as-is)
                    if len(normalized.shape) == 2:
                        normalized = cv.cvtColor(normalized, cv.COLOR_GRAY2BGR)
                    elif file_type == 'rgb' and normalized.shape[2] == 3:
                        # RGB images are already in BGR format from cv.imread
                        # Resize RGB to 640x480 for display
                        normalized = cv.resize(normalized, (640, 480))
                    
                    # Resize to common height while maintaining aspect ratio
                    height, width = normalized.shape[:2]
                    if height != max_height:
                        aspect_ratio = width / height
                        new_width = int(max_height * aspect_ratio)
                        normalized = cv.resize(normalized, (new_width, max_height))
                    
                    # Add label at the top
                    label_height = 40
                    labeled_img = np.zeros((normalized.shape[0] + label_height, normalized.shape[1], 3), dtype=np.uint8)
                    labeled_img[label_height:, :] = normalized
                    
                    # Add text label
                    font = cv.FONT_HERSHEY_SIMPLEX
                    font_scale = 1.0
                    thickness = 2
                    text_size = cv.getTextSize(label, font, font_scale, thickness)[0]
                    text_x = (labeled_img.shape[1] - text_size[0]) // 2
                    text_y = (label_height + text_size[1]) // 2
                    cv.putText(labeled_img, label, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
                    
                    processed_images.append(labeled_img)
                
                # Stack images horizontally
                combined_image = np.hstack(processed_images)
                
                # Display combined image
                # Build window name dynamically based on available images
                view_labels = [label for _, label, _ in valid_images]
                window_name = "Combined View: " + " | ".join(view_labels)
                cv.imshow(window_name, combined_image)
                cv.waitKey(1)  # Force the window to render
                print(f"\nDisplaying combined image ({combined_image.shape[1]}x{combined_image.shape[0]})")
                print("Press any key in the window to continue (or Ctrl+C to exit)...")
                
                # Use polling loop to allow Ctrl+C
                try:
                    while True:
                        key = cv.waitKey(100)  # Check every 100ms
                        if key != -1:  # Key was pressed
                            break
                except KeyboardInterrupt:
                    print("\nInterrupted by user")
                    cv.destroyWindow(window_name)
                    cv.waitKey(1)
                    return
                
                cv.destroyWindow(window_name)
                cv.waitKey(1)  # Process the destroy event
    
    # Display point cloud after PNGs
    if pointcloud_file:
        print(f"\n{'=' * 60}")
        print(f"POINT CLOUD")
        print(f"{'=' * 60}")
        visualize_ply(pointcloud_file)
    
    print("\n" + "=" * 60)
    print("Visualization complete!")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Visualize PNG images and PLY point cloud files from rawparser output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect and show metadata only (default)
  python visualize_data.py ./recording_output
  
  # Show PNG images only
  python visualize_data.py ./recording_output --view png
  python visualize_data.py ./recording_output -v png
  
  # Show point cloud only
  python visualize_data.py ./recording_output --view pointcloud
  python visualize_data.py ./recording_output -v pointcloud
        """
    )
    
    parser.add_argument('directory', type=str,
                       help='Path to directory containing data files (metadata, PNG, PLY)')
    
    parser.add_argument('--view', '-v', type=str, default='metadata',
                        choices=['metadata', 'png', 'pointcloud'],
                        help='What to display: metadata (default), png (images only), or pointcloud (3D only)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("PNG and PLY File Visualizer")
    print("=" * 60)
    
    try:
        visualize_directory(args.directory, args.view)
    except KeyboardInterrupt:
        print("\n\nVisualization interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
