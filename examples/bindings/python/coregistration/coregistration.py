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
ADCAM RGB-Depth Coregistration Example
=======================================

Maps a ToF depth frame into the RGB camera image plane and produces:
  - A registered depth image at the RGB camera resolution
  - A side-by-side RGB | colourised-depth visualisation (matching the images
    attached to the feature request)

Algorithm
---------
For each valid ToF pixel (u_tof, v_tof) with depth d (mm):

  1. Normalise:
       x = (u_tof - cx_tof) / fx_tof
       y = (v_tof - cy_tof) / fy_tof

  2. Undistort using the rational Brown-Conrady model (k1-k6, p1, p2).

  3. Back-project to 3-D in the ToF camera frame:
       P_tof = [x_u * d,  y_u * d,  d]

  4. Rigid-body transform to the RGB camera frame:
       P_rgb = R @ P_tof + t          (R: 3x3 rotation, t: 3-vector, mm)

  5. Project onto the RGB image (with optional RGB distortion):
       u_rgb = fx_rgb * (X_rgb / Z_rgb) + cx_rgb
       v_rgb = fy_rgb * (Y_rgb / Z_rgb) + cy_rgb

  6. Write the depth into registered_depth[v_rgb, u_rgb]; keep nearer surface
     when two ToF pixels map to the same RGB pixel (z-buffer).

Calibration JSON schema
-----------------------
{
  "tof": {
    "width": 512, "height": 512,
    "fx": ..., "fy": ..., "cx": ..., "cy": ...,
    "k1": 0, "k2": 0, "k3": 0, "k4": 0, "k5": 0, "k6": 0,
    "p1": 0, "p2": 0
  },
  "rgb": {
    "width": 1920, "height": 1200,
    "fx": ..., "fy": ..., "cx": ..., "cy": ...,
    "k1": 0, "k2": 0, "k3": 0, "k4": 0, "k5": 0, "k6": 0,
    "p1": 0, "p2": 0
  },
  "extrinsics": {
    "rotation":    [r00, r01, r02, r10, r11, r12, r20, r21, r22],
    "translation": [tx, ty, tz]
  }
}

Usage
-----
  # From saved rawparser frames:
  python coregistration.py \\
      --depth  /path/to/frames/frame_000001/depth_capture_000001.png \\
      --rgb    /path/to/frames/frame_000001/rgb_capture_000001.jpg   \\
      --calib  sample_calib.json                                     \\
      --output /path/to/out/

  # From a live camera (mode 2, QMP):
  python coregistration.py --live --mode 2 --calib sample_calib.json

Dependencies: numpy, opencv-python, (optional) aditofpython for live mode
"""

import argparse
import json
import os
import sys

import cv2 as cv
import numpy as np


# ===========================================================================
# Calibration data classes
# ===========================================================================

class CameraIntrinsics:
    """Pinhole camera with rational Brown-Conrady distortion (k1-k6, p1, p2)."""

    def __init__(self, fx, fy, cx, cy,
                 k1=0., k2=0., k3=0., k4=0., k5=0., k6=0.,
                 p1=0., p2=0., width=0, height=0):
        self.fx = float(fx)
        self.fy = float(fy)
        self.cx = float(cx)
        self.cy = float(cy)
        self.k1, self.k2, self.k3 = float(k1), float(k2), float(k3)
        self.k4, self.k5, self.k6 = float(k4), float(k5), float(k6)
        self.p1, self.p2 = float(p1), float(p2)
        self.width  = int(width)
        self.height = int(height)

    @property
    def K(self):
        """3×3 camera matrix."""
        return np.array([[self.fx, 0, self.cx],
                         [0, self.fy, self.cy],
                         [0,      0,      1]], dtype=np.float64)

    @property
    def dist_coeffs(self):
        """OpenCV-style distortion vector [k1,k2,p1,p2,k3,k4,k5,k6]."""
        return np.array([self.k1, self.k2, self.p1, self.p2,
                         self.k3, self.k4, self.k5, self.k6], dtype=np.float64)


class RGBDCalibration:
    """Container for ToF intrinsics, RGB intrinsics, and stereo extrinsics."""

    def __init__(self, tof: CameraIntrinsics, rgb: CameraIntrinsics,
                 R: np.ndarray, t: np.ndarray):
        self.tof = tof
        self.rgb = rgb
        self.R   = R   # (3, 3) float64
        self.t   = t   # (3,)   float64, mm

    @classmethod
    def from_json(cls, json_path: str) -> "RGBDCalibration":
        with open(json_path) as f:
            data = json.load(f)

        def _parse_intrinsics(d):
            return CameraIntrinsics(
                fx=d["fx"], fy=d["fy"], cx=d["cx"], cy=d["cy"],
                k1=d.get("k1", 0), k2=d.get("k2", 0), k3=d.get("k3", 0),
                k4=d.get("k4", 0), k5=d.get("k5", 0), k6=d.get("k6", 0),
                p1=d.get("p1", 0), p2=d.get("p2", 0),
                width=d.get("width", 0), height=d.get("height", 0),
            )

        tof = _parse_intrinsics(data["tof"])
        rgb = _parse_intrinsics(data["rgb"])
        ext = data["extrinsics"]
        R = np.array(ext["rotation"],    dtype=np.float64).reshape(3, 3)
        t = np.array(ext["translation"], dtype=np.float64)  # mm

        return cls(tof, rgb, R, t)


# ===========================================================================
# Core coregistration logic (pure NumPy, no OpenCV dependency in hot path)
# ===========================================================================

def _undistort_points(x_norm: np.ndarray, y_norm: np.ndarray,
                      K: CameraIntrinsics):
    """
    Undistort normalised ToF image coordinates using the rational Brown-Conrady
    model:
        radial = (1 + k1*r² + k2*r⁴ + k3*r⁶) / (1 + k4*r² + k5*r⁴ + k6*r⁶)
    """
    r2 = x_norm ** 2 + y_norm ** 2
    r4 = r2 ** 2
    r6 = r4 * r2
    numer  = 1 + K.k1 * r2 + K.k2 * r4 + K.k3 * r6
    denom  = 1 + K.k4 * r2 + K.k5 * r4 + K.k6 * r6
    denom  = np.where(np.abs(denom) > 1e-6, denom, 1.0)
    radial = numer / denom

    x_u = (radial * x_norm
           + 2 * K.p1 * x_norm * y_norm
           + K.p2 * (r2 + 2 * x_norm ** 2))
    y_u = (radial * y_norm
           + K.p1 * (r2 + 2 * y_norm ** 2)
           + 2 * K.p2 * x_norm * y_norm)
    return x_u, y_u


def _project_points(x_norm: np.ndarray, y_norm: np.ndarray,
                    K: CameraIntrinsics):
    """
    Project normalised directions through the RGB lens model (with distortion)
    and return pixel coordinates.
    """
    r2 = x_norm ** 2 + y_norm ** 2
    r4 = r2 ** 2
    r6 = r4 * r2
    numer  = 1 + K.k1 * r2 + K.k2 * r4 + K.k3 * r6
    denom  = 1 + K.k4 * r2 + K.k5 * r4 + K.k6 * r6
    denom  = np.where(np.abs(denom) > 1e-6, denom, 1.0)
    radial = numer / denom

    x_d = (radial * x_norm
            + 2 * K.p1 * x_norm * y_norm
            + K.p2 * (r2 + 2 * x_norm ** 2))
    y_d = (radial * y_norm
            + K.p1 * (r2 + 2 * y_norm ** 2)
            + 2 * K.p2 * x_norm * y_norm)

    u = K.fx * x_d + K.cx
    v = K.fy * y_d + K.cy
    return u, v


def register_depth_to_rgb(depth_mm: np.ndarray, calib: RGBDCalibration,
                          rgb_width: int, rgb_height: int) -> np.ndarray:
    """
    Map a ToF depth frame into the RGB camera image plane.

    Parameters
    ----------
    depth_mm   : (H_tof, W_tof) uint16 array; depth in mm, 0 = invalid.
    calib      : RGBDCalibration with tof/rgb intrinsics and extrinsics.
    rgb_width  : Target RGB image width  (pixels).
    rgb_height : Target RGB image height (pixels).

    Returns
    -------
    registered : (rgb_height, rgb_width) uint16 array; registered depth in mm,
                 0 where no ToF data maps to that RGB pixel.
    """
    tof_h, tof_w = depth_mm.shape

    # Valid pixel mask
    valid = depth_mm > 0
    rows, cols = np.where(valid)
    depths = depth_mm[valid].astype(np.float64)  # mm

    # 1. Normalise pixel coordinates using ToF intrinsics
    x_norm = (cols.astype(np.float64) - calib.tof.cx) / calib.tof.fx
    y_norm = (rows.astype(np.float64) - calib.tof.cy) / calib.tof.fy

    # 2. Undistort ToF image points
    x_u, y_u = _undistort_points(x_norm, y_norm, calib.tof)

    # 3. Back-project to 3-D in the ToF camera frame (depth in mm)
    pts_tof = np.stack([x_u * depths, y_u * depths, depths], axis=0)  # (3, N)

    # 4. Rigid transform to RGB camera frame:  P_rgb = R @ P_tof + t
    pts_rgb = calib.R @ pts_tof + calib.t[:, np.newaxis]              # (3, N)
    Z_rgb = pts_rgb[2]

    # Discard points behind the RGB camera
    front = Z_rgb > 0
    pts_rgb = pts_rgb[:, front]
    depths_in_rgb = pts_rgb[2]                                         # mm

    # 5. Project onto the RGB image (with distortion)
    x_rgb_norm = pts_rgb[0] / pts_rgb[2]
    y_rgb_norm = pts_rgb[1] / pts_rgb[2]
    u_f, v_f = _project_points(x_rgb_norm, y_rgb_norm, calib.rgb)

    u_i = np.round(u_f).astype(np.int32)
    v_i = np.round(v_f).astype(np.int32)

    # 6. Bounds check
    in_bounds = (u_i >= 0) & (u_i < rgb_width) & (v_i >= 0) & (v_i < rgb_height)
    u_i = u_i[in_bounds]
    v_i = v_i[in_bounds]
    depths_in_rgb = depths_in_rgb[in_bounds]

    # 7. z-buffer: keep nearer surface when multiple ToF pixels map to the same
    #    RGB pixel.  Sort by depth descending so closer points overwrite farther.
    order = np.argsort(depths_in_rgb)[::-1]
    u_i          = u_i[order]
    v_i          = v_i[order]
    depths_in_rgb = depths_in_rgb[order]

    registered = np.zeros((rgb_height, rgb_width), dtype=np.uint16)
    registered[v_i, u_i] = np.clip(depths_in_rgb, 0, 65535).astype(np.uint16)

    return registered


# ===========================================================================
# Visualisation helpers
# ===========================================================================

def colorise_depth(depth_mm: np.ndarray,
                   min_mm: int = 300,
                   max_mm: int = 4000,
                   colormap: int = cv.COLORMAP_TURBO) -> np.ndarray:
    """
    Convert a uint16 depth image (mm) to a colourised BGR image.
    Pixels with depth == 0 are shown in black (no data).
    """
    valid = depth_mm > 0
    depth_clipped = np.clip(depth_mm, min_mm, max_mm)
    # Normalise the valid range to [0, 255]
    depth_norm = np.zeros_like(depth_mm, dtype=np.uint8)
    if valid.any():
        depth_norm[valid] = (
            255.0 * (depth_clipped[valid] - min_mm) / (max_mm - min_mm)
        ).astype(np.uint8)
    colour = cv.applyColorMap(depth_norm, colormap)
    colour[~valid] = 0          # Black for invalid pixels
    return colour


def make_side_by_side(rgb_bgr: np.ndarray,
                      registered_depth_mm: np.ndarray) -> np.ndarray:
    """
    Produce a side-by-side image: RGB (left) | colourised registered depth (right).
    Both halves are at the RGB camera resolution, matching the reference images
    supplied in the feature request.
    """
    h, w = rgb_bgr.shape[:2]
    depth_colour = colorise_depth(registered_depth_mm)
    depth_colour = cv.resize(depth_colour, (w, h))
    return cv.hconcat([rgb_bgr, depth_colour])


# ===========================================================================
# Live-camera helper (requires aditofpython)
# ===========================================================================

def _grab_live_frame(mode: int):
    """
    Capture one depth frame + one RGB frame from the live ADCAM camera.

    Returns
    -------
    depth_mm : (H, W) uint16 numpy array in mm
    rgb_bgr  : (H_rgb, W_rgb, 3) uint8 BGR numpy array  (or None)
    """
    try:
        import aditofpython as tof
    except ImportError:
        sys.exit("aditofpython not found – install the ADCAM Python bindings "
                 "or use --depth / --rgb to supply pre-captured images.")

    system  = tof.System()
    cameras = []
    system.getCameraList(cameras)
    if not cameras:
        sys.exit("No ADCAM camera found.")

    cam = cameras[0]
    cam.initialize()
    cam.setMode(mode)
    cam.start()

    # Drop first frame (sensor warm-up)
    _ = tof.Frame()
    cam.requestFrame(_)

    frame = tof.Frame()
    status = cam.requestFrame(frame)
    cam.stop()

    if status != tof.Status.Ok:
        sys.exit(f"requestFrame() failed: {status}")

    depth_arr = np.asarray(frame.getData("depth"), dtype=np.uint16)

    rgb_arr = None
    try:
        rgb_details = tof.FrameDataDetails()
        if frame.getDataDetails("rgb", rgb_details) == tof.Status.Ok:
            rgb_raw = np.array(frame.getData("rgb"), copy=False, dtype=np.uint8)
            rgb_arr = rgb_raw.reshape(rgb_details.height, rgb_details.width, 3)
    except Exception:
        pass

    return depth_arr, rgb_arr


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    ap = argparse.ArgumentParser(
        description="ADCAM RGB-Depth coregistration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Input sources (mutually exclusive: file-based vs live)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--live", action="store_true",
                     help="Capture one frame from the live ADCAM camera.")
    src.add_argument("--depth", metavar="DEPTH_PNG",
                     help="Path to a 16-bit PNG depth image (mm).")

    ap.add_argument("--rgb", metavar="RGB_IMG",
                    help="Path to the RGB image (required when --depth is used).")
    ap.add_argument("--calib", required=True, metavar="JSON",
                    help="Path to the calibration JSON file.")
    ap.add_argument("--mode", type=int, default=2,
                    help="Camera mode for live capture (default: 2).")
    ap.add_argument("--output", "-o", metavar="DIR", default=".",
                    help="Output directory for saved images (default: cwd).")
    ap.add_argument("--show", action="store_true",
                    help="Display the result in an OpenCV window.")
    ap.add_argument("--min-depth", type=int, default=300,
                    help="Min depth (mm) for colourisation (default: 300).")
    ap.add_argument("--max-depth", type=int, default=4000,
                    help="Max depth (mm) for colourisation (default: 4000).")
    args = ap.parse_args()

    # ------------------------------------------------------------------ inputs
    if args.live:
        print(f"Capturing live frame (mode {args.mode}) …")
        depth_mm, rgb_bgr = _grab_live_frame(args.mode)
        if rgb_bgr is None:
            print("Warning: RGB frame not available from live camera. "
                  "Provide --rgb to supply one.")
    else:
        if not args.rgb:
            ap.error("--rgb is required when using --depth.")
        depth_mm = cv.imread(args.depth, cv.IMREAD_ANYDEPTH)
        if depth_mm is None:
            sys.exit(f"Cannot load depth image: {args.depth}")
        depth_mm = depth_mm.astype(np.uint16)

        rgb_bgr = cv.imread(args.rgb, cv.IMREAD_COLOR)
        if rgb_bgr is None:
            sys.exit(f"Cannot load RGB image: {args.rgb}")

    print(f"  ToF depth frame : {depth_mm.shape[1]}×{depth_mm.shape[0]}")
    if rgb_bgr is not None:
        print(f"  RGB frame       : {rgb_bgr.shape[1]}×{rgb_bgr.shape[0]}")

    # --------------------------------------------------------- load calibration
    if not os.path.isfile(args.calib):
        sys.exit(f"Calibration file not found: {args.calib}")
    calib = RGBDCalibration.from_json(args.calib)
    print(f"  Calibration     : {args.calib}")
    print(f"    ToF  intrinsics  fx={calib.tof.fx:.1f}  fy={calib.tof.fy:.1f}  "
          f"cx={calib.tof.cx:.1f}  cy={calib.tof.cy:.1f}")
    print(f"    RGB  intrinsics  fx={calib.rgb.fx:.1f}  fy={calib.rgb.fy:.1f}  "
          f"cx={calib.rgb.cx:.1f}  cy={calib.rgb.cy:.1f}")
    print(f"    Translation (mm) {calib.t}")

    # Determine RGB output resolution from calibration file or actual image
    if rgb_bgr is not None:
        rgb_h, rgb_w = rgb_bgr.shape[:2]
    elif calib.rgb.width > 0 and calib.rgb.height > 0:
        rgb_w, rgb_h = calib.rgb.width, calib.rgb.height
    else:
        sys.exit("RGB image not provided and calibration has no rgb.width/height.")

    # ------------------------------------------------------- coregistration
    print("Running coregistration …")
    registered = register_depth_to_rgb(depth_mm, calib, rgb_w, rgb_h)
    print(f"  Registered depth : {rgb_w}×{rgb_h}, "
          f"valid pixels: {(registered > 0).sum()}")

    # ----------------------------------------------------------- save outputs
    os.makedirs(args.output, exist_ok=True)

    reg_path = os.path.join(args.output, "registered_depth.png")
    cv.imwrite(reg_path, registered)
    print(f"  Saved: {reg_path}")

    if rgb_bgr is not None:
        sbs = make_side_by_side(rgb_bgr, registered)
        sbs_path = os.path.join(args.output, "rgbd_coregistered.png")
        cv.imwrite(sbs_path, sbs)
        print(f"  Saved: {sbs_path}")

        depth_colour = colorise_depth(registered, args.min_depth, args.max_depth)
        overlay = rgb_bgr.copy().astype(np.float32)
        mask = registered > 0
        if mask.any():
            alpha = 0.5
            overlay[mask] = (
                (1 - alpha) * overlay[mask] +
                alpha * depth_colour[mask].astype(np.float32)
            )
        overlay_path = os.path.join(args.output, "rgbd_overlay.png")
        cv.imwrite(overlay_path, overlay.astype(np.uint8))
        print(f"  Saved: {overlay_path}")

        if args.show:
            cv.imshow("RGB | Registered Depth", sbs)
            cv.imshow("RGBD Overlay", overlay.astype(np.uint8))
            print("  Press any key in the OpenCV window to exit.")
            cv.waitKey(0)
            cv.destroyAllWindows()
    else:
        depth_colour = colorise_depth(registered, args.min_depth, args.max_depth)
        col_path = os.path.join(args.output, "registered_depth_colourised.png")
        cv.imwrite(col_path, depth_colour)
        print(f"  Saved: {col_path}")

        if args.show:
            cv.imshow("Registered Depth (colourised)", depth_colour)
            cv.waitKey(0)
            cv.destroyAllWindows()

    print("Done.")


if __name__ == "__main__":
    main()
