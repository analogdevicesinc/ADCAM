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
    frame_000_depth.png  - Depth with jet colormap, auto (equalised)
    frame_000_ab.png     - Active Brightness (grayscale)
    frame_000_conf.png   - Confidence (grayscale)

Colormaps:
    Depth:       Jet colormap (blue→cyan→green→yellow→red), histogram-equalised so
                 depths shared by many pixels (e.g. a face) get more colours
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

    # cv2 points Qt at its own (empty) font dir on import; use the system fonts instead.
    if os.path.isdir("/usr/share/fonts/truetype/dejavu"):
        os.environ["QT_QPA_FONTDIR"] = "/usr/share/fonts/truetype/dejavu"
    
    if frame_idx >= len(depth_array):
        print(f"Error: frame_idx {frame_idx} out of range (max: {len(depth_array)-1})")
        return
    
    depth = depth_array[frame_idx]
    ab = ab_array[frame_idx]
    conf = conf_array[frame_idx]

    def make_panel(image, title, label, jet=False, size=480, cdf=None):
        """BGR panel: scaled image, title and a colorbar.

        cdf (from equalize_cdf) colours depth by histogram equalisation; otherwise
        the image min/max is used.
        """
        if cdf is not None:
            norm = cdf.take(image.astype(np.uint16, copy=False)).astype(np.float32)
            ticks = cdf_ticks(cdf)
        else:
            img = image.astype(np.float32)
            vmin, vmax = float(img.min()), float(img.max())
            norm = np.clip((img - vmin) / max(vmax - vmin, 1e-6), 0.0, 1.0)
            ticks = [(1.0, vmax), (0.0, vmin)]
        width = max(1, round(norm.shape[1] * size / norm.shape[0]))
        norm = cv2.resize(norm, (width, size), interpolation=cv2.INTER_NEAREST)
        ramp = np.repeat(np.linspace(1.0, 0.0, size, dtype=np.float32)[:, None], 20, axis=1)
        if jet:
            body = apply_jet_colormap(norm)[..., ::-1]  # RGB -> BGR
            bar = apply_jet_colormap(ramp)[..., ::-1]
            if cdf is not None:
                invalid = cv2.resize((image == 0).astype(np.uint8), (width, size),
                                     interpolation=cv2.INTER_NEAREST) > 0
                body[invalid] = 0  # black, not the nearest-depth colour
        else:
            body = cv2.cvtColor((norm * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
            bar = cv2.cvtColor((ramp * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        panel = np.full((size + 70, width + 110, 3), 255, dtype=np.uint8)
        panel[50:50 + size, :width] = body
        panel[50:50 + size, width + 10:width + 30] = bar
        font, black = cv2.FONT_HERSHEY_SIMPLEX, (0, 0, 0)
        cv2.putText(panel, f"{title} (Frame {frame_idx})", (5, 20), font, 0.55, black, 1, cv2.LINE_AA)
        if cdf is not None:
            cv2.putText(panel, "Colours: auto (equalised)", (5, 42), font, 0.5, black, 1, cv2.LINE_AA)
        else:
            cv2.putText(panel, f"Range: {image.min()}-{image.max()}", (5, 42), font, 0.5, black, 1, cv2.LINE_AA)
        for frac, val in ticks:
            y = 50 + round((1.0 - frac) * (size - 1))
            cv2.putText(panel, f"{val:.0f}", (width + 34, y + 5), font, 0.45, black, 1, cv2.LINE_AA)
        cv2.putText(panel, label, (width + 10, size + 65), font, 0.4, black, 1, cv2.LINE_AA)
        return panel

    combined = np.hstack([
        make_panel(depth, "Depth", "Depth (mm)", jet=True, cdf=equalize_cdf(depth)),
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
    """Apply jet colormap (blue->cyan->yellow->red) to normalized data [0-1].

    Computed at full 8-bit precision: 1020 distinct colours (cv2.COLORMAP_JET has 256).
    """
    # Classic jet colormap: blue -> cyan -> green -> yellow -> red
    r = np.clip(1.5 - 4 * np.abs(data_norm - 0.75), 0, 1)
    g = np.clip(1.5 - 4 * np.abs(data_norm - 0.5), 0, 1)
    b = np.clip(1.5 - 4 * np.abs(data_norm - 0.25), 0, 1)
    
    rgb = np.stack([r, g, b], axis=-1)
    return (rgb * 255).astype(np.uint8)

def save_frames_as_images(depth_array, ab_array, conf_array, output_prefix="frame"):
    """Save frames as PNG images with enhanced colormaps."""
    for i in range(len(depth_array)):
        # Depth: equalised jet colours (invalid 0 pixels black)
        cdf = equalize_cdf(depth_array[i])
        depth_norm = (np.zeros(depth_array[i].shape, np.float32) if cdf is None
                      else cdf.take(depth_array[i]).astype(np.float32))
        depth_rgb = apply_jet_colormap(depth_norm)
        depth_rgb[depth_array[i] == 0] = 0  # invalid -> black
        write_png(f"{output_prefix}_{i:03d}_depth.png", depth_rgb)
        if cdf is not None:
            print(f"  frame {i}: depth colours (auto, equalised), mm at colorbar ticks:",
                  [round(v) for _, v in cdf_ticks(cdf)])

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
