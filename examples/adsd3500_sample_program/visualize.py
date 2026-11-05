#!/usr/bin/env python3
"""
Visualize ADSD3500 captured frames (depth, AB, confidence).
Automatically detects frame dimensions and count from file sizes.

Supported resolutions:
    - MP (Megapixel):        1024×1024
    - QMP (Quarter MP):      512×512
    - VGA:                   640×480
    - QVGA:                  320×240
    - Custom square:         Auto-detected

Usage:
    ./visualize.py              # Display frames interactively (requires OpenCV with GUI support)
    ./visualize.py --save       # Save frames as PNG images 
    ./visualize.py 2            # Display frame index 2
    ./visualize.py 2 --save     # Save all frames including frame 2

Output files (from adsd3500_sample_program):
    out_depth.bin    - Depth data (uint16)
    out_ab.bin       - Active Brightness (uint16)
    out_conf.bin     - Confidence (uint8)

Generated PNG files (with --save):
    frame_000_depth.png  - Depth with jet colormap (classic rainbow)
    frame_000_ab.png     - Active Brightness (grayscale)
    frame_000_conf.png   - Confidence (grayscale)

Colormaps:
    Depth:       Jet colormap (blue→cyan→green→yellow→red)
    AB/Conf:     Grayscale
"""
import numpy as np
import struct
import sys
import os
import zlib

def write_png(path, image):
    """Write a uint8 HxW (grayscale) or HxWx3 (RGB) array as an 8-bit PNG."""
    image = np.ascontiguousarray(image, dtype=np.uint8)
    height, width = image.shape[:2]
    color_type = 2 if image.ndim == 3 else 0
    # Each scanline is prefixed with filter type 0 (None).
    raw = np.hstack([np.zeros((height, 1), dtype=np.uint8),
                     image.reshape(height, -1)]).tobytes()

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8,
                                           color_type, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 6)))
        f.write(chunk(b"IEND", b""))

def detect_frame_dimensions_and_count(depth_file):
    """Detect frame dimensions and count based on file size."""
    file_size = os.path.getsize(depth_file)
    
    # Common resolutions for ADSD3500
    # Format: (width, height, bytes_per_frame, description)
    known_resolutions = [
        (1024, 1024, 1024*1024*2, "MP (Megapixel)"),      # 2 MB per frame
        (512, 512, 512*512*2, "QMP (Quarter Megapixel)"), # 512 KB per frame
        (640, 480, 640*480*2, "VGA"),                     # 614.4 KB per frame
        (320, 240, 320*240*2, "QVGA"),                    # 153.6 KB per frame
    ]
    
    # Check which resolution divides evenly into the file size
    for width, height, bytes_per_frame, desc in known_resolutions:
        if file_size % bytes_per_frame == 0:
            num_frames = file_size // bytes_per_frame
            print(f"Detected {desc} resolution: {width}×{height}, {num_frames} frame(s)")
            return width, height, num_frames
    
    # Try to infer square resolution from single frame
    num_pixels_total = file_size // 2
    
    # Try common frame counts
    for num_frames in [1, 2, 3, 4, 5, 10]:
        if num_pixels_total % num_frames == 0:
            num_pixels_per_frame = num_pixels_total // num_frames
            side = int(np.sqrt(num_pixels_per_frame))
            if side * side == num_pixels_per_frame:
                print(f"Detected square resolution: {side}×{side}, {num_frames} frame(s)")
                return side, side, num_frames
    
    # Default fallback - assume single 512×512 frame
    print(f"Warning: Could not detect resolution from file size {file_size} bytes")
    print("Assuming single 512×512 frame")
    return 512, 512, 1

def load_frames(depth_path, ab_path, conf_path, width, height, num_frames=1):
    """Load depth, AB, and confidence frames from binary files."""
    
    # Calculate frame sizes
    depth_frame_size = height * width * 2  # uint16
    ab_frame_size = height * width * 2     # uint16
    conf_frame_size = height * width       # uint8
    
    # Allocate arrays
    depth_array = np.zeros((num_frames, height, width), dtype=np.uint16)
    ab_array = np.zeros((num_frames, height, width), dtype=np.uint16)
    conf_array = np.zeros((num_frames, height, width), dtype=np.uint8)
    
    # Load frames
    with open(depth_path, "rb") as depth_file, \
         open(ab_path, "rb") as ab_file, \
         open(conf_path, "rb") as conf_file:
        
        for i in range(num_frames):
            # Read depth frame
            depth_data = np.fromfile(depth_file, dtype=np.uint16, count=height*width)
            if depth_data.size != height * width:
                print(f"Warning: Only loaded {i} frames (expected {num_frames})")
                return depth_array[:i], ab_array[:i], conf_array[:i]
            depth_array[i] = depth_data.reshape((height, width))
            
            # Read AB frame
            ab_data = np.fromfile(ab_file, dtype=np.uint16, count=height*width)
            ab_array[i] = ab_data.reshape((height, width))
            
            # Read confidence frame
            conf_data = np.fromfile(conf_file, dtype=np.uint8, count=height*width)
            conf_array[i] = conf_data.reshape((height, width))
    
    print(f"Loaded {num_frames} frame(s)")
    return depth_array, ab_array, conf_array

def visualize_frames(depth_array, ab_array, conf_array, frame_idx=0):
    """Visualize frames using OpenCV."""
    try:
        import cv2
    except Exception as e:
        print(f"Error: OpenCV not available: {e}")
        print("\nTo install OpenCV, try:")
        print("  pip3 install opencv-python")
        print("\nOr use --save option to export images without GUI:")
        print("  ./visualize.py --save")
        return
    
    if frame_idx >= len(depth_array):
        print(f"Error: frame_idx {frame_idx} out of range (max: {len(depth_array)-1})")
        return
    
    depth = depth_array[frame_idx]
    ab = ab_array[frame_idx]
    conf = conf_array[frame_idx]

    def make_panel(image, title, label, colormap=None, size=480):
        """BGR panel: scaled image, title and a min/max colorbar."""
        img = image.astype(np.float32)
        vmin, vmax = float(img.min()), float(img.max())
        u8 = ((img - vmin) / max(vmax - vmin, 1e-6) * 255).astype(np.uint8)
        width = max(1, round(img.shape[1] * size / img.shape[0]))
        u8 = cv2.resize(u8, (width, size), interpolation=cv2.INTER_NEAREST)
        ramp = np.repeat(np.linspace(255, 0, size).astype(np.uint8)[:, None], 20, axis=1)
        if colormap is None:
            body = cv2.cvtColor(u8, cv2.COLOR_GRAY2BGR)
            bar = cv2.cvtColor(ramp, cv2.COLOR_GRAY2BGR)
        else:
            body = cv2.applyColorMap(u8, colormap)
            bar = cv2.applyColorMap(ramp, colormap)
        panel = np.full((size + 70, width + 110, 3), 255, dtype=np.uint8)
        panel[50:50 + size, :width] = body
        panel[50:50 + size, width + 10:width + 30] = bar
        font, black = cv2.FONT_HERSHEY_SIMPLEX, (0, 0, 0)
        cv2.putText(panel, f"{title} (Frame {frame_idx})", (5, 20), font, 0.55, black, 1, cv2.LINE_AA)
        cv2.putText(panel, f"Range: {image.min()}-{image.max()}", (5, 42), font, 0.5, black, 1, cv2.LINE_AA)
        cv2.putText(panel, f"{vmax:.0f}", (width + 34, 62), font, 0.45, black, 1, cv2.LINE_AA)
        cv2.putText(panel, f"{vmin:.0f}", (width + 34, size + 50), font, 0.45, black, 1, cv2.LINE_AA)
        cv2.putText(panel, label, (width + 10, size + 65), font, 0.4, black, 1, cv2.LINE_AA)
        return panel

    combined = np.hstack([
        make_panel(depth, "Depth", "Depth (mm)", cv2.COLORMAP_JET),
        make_panel(ab, "Active Brightness", "Intensity"),
        make_panel(conf, "Confidence", "Confidence"),
    ])
    
    # Print statistics
    print(f"\nFrame {frame_idx} Statistics:")
    print(f"  Depth:      min={depth.min()}, max={depth.max()}, mean={depth.mean():.1f}")
    print(f"  AB:         min={ab.min()}, max={ab.max()}, mean={ab.mean():.1f}")
    print(f"  Confidence: min={conf.min()}, max={conf.max()}, mean={conf.mean():.1f}")
    
    cv2.imshow("ADSD3500 Frames", combined)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def apply_jet_colormap(data_norm):
    """Apply jet colormap (blue->cyan->yellow->red) to normalized data [0-1]."""
    # Classic jet colormap: blue -> cyan -> green -> yellow -> red
    r = np.clip(1.5 - 4 * np.abs(data_norm - 0.75), 0, 1)
    g = np.clip(1.5 - 4 * np.abs(data_norm - 0.5), 0, 1)
    b = np.clip(1.5 - 4 * np.abs(data_norm - 0.25), 0, 1)
    
    rgb = np.stack([r, g, b], axis=-1)
    return (rgb * 255).astype(np.uint8)

def save_frames_as_images(depth_array, ab_array, conf_array, output_prefix="frame"):
    """Save frames as PNG images with enhanced colormaps."""
    for i in range(len(depth_array)):
        # Depth: Apply jet colormap (classic rainbow)
        depth_norm = depth_array[i].astype(np.float32) / max(depth_array[i].max(), 1)
        write_png(f"{output_prefix}_{i:03d}_depth.png", apply_jet_colormap(depth_norm))

        # AB: Grayscale
        ab_norm = (ab_array[i].astype(np.float32) / max(ab_array[i].max(), 1) * 255).astype(np.uint8)
        write_png(f"{output_prefix}_{i:03d}_ab.png", ab_norm)

        # Confidence: Grayscale
        write_png(f"{output_prefix}_{i:03d}_conf.png", conf_array[i])

    print(f"Saved {len(depth_array)} frame(s) (depth: jet colormap, AB/conf: grayscale)")

def main():
    """Main function."""
    # Show help
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        sys.exit(0)
    
    depth_file = 'out_depth.bin'
    ab_file = 'out_ab.bin'
    conf_file = 'out_conf.bin'
    
    # Check if files exist
    if not all(os.path.exists(f) for f in [depth_file, ab_file, conf_file]):
        print("Error: Output files not found!")
        print("Expected files: out_depth.bin, out_ab.bin, out_conf.bin")
        print("Run the adsd3500_sample_program first to generate these files.")
        sys.exit(1)
    
    # Detect frame dimensions and count
    width, height, num_frames = detect_frame_dimensions_and_count(depth_file)
    
    # Load frames
    depth_array, ab_array, conf_array = load_frames(depth_file, ab_file, conf_file, width, height, num_frames)
    
    # Check for save option
    if '--save' in sys.argv:
        save_frames_as_images(depth_array, ab_array, conf_array)
        return
    
    # Visualize frame (allow specifying frame index)
    frame_idx = 0
    for arg in sys.argv[1:]:
        if arg != '--save':
            try:
                frame_idx = int(arg)
                break
            except ValueError:
                print(f"Invalid frame index: {arg}")
                sys.exit(1)
    
    visualize_frames(depth_array, ab_array, conf_array, frame_idx)

if __name__ == "__main__":
    main()
