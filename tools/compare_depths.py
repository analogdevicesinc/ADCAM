#!/usr/bin/env python3
"""
Simple tool to compare two raw uint16 depth images and detect shifts

Usage:
  python3 compare_depths.py <width> <height> <all_frames_depth.bin> <depth_only_depth.bin> [max_shift]

The script prints basic diff statistics and performs a small brute-force search
for integer (dx,dy) shifts that minimize mean absolute difference.
"""
import sys
import numpy as np


def load_raw_uint16(path, width, height):
    data = np.fromfile(path, dtype=np.uint16)
    expected = width * height
    if data.size != expected:
        raise ValueError(f"Unexpected file size for {path}: {data.size} != {expected}")
    return data.reshape((height, width))


def diff_stats(a, b):
    d = a.astype(np.int32) - b.astype(np.int32)
    return np.min(d), np.max(d), np.mean(d), np.std(d)


def find_best_shift(a, b, max_shift=10):
    h, w = a.shape
    best = None
    for dy in range(-max_shift, max_shift + 1):
        for dx in range(-max_shift, max_shift + 1):
            ys_a = max(0, dy)
            ys_b = max(0, -dy)
            ye_a = min(h, h + dy)
            ye_b = min(h, h - dy)
            xs_a = max(0, dx)
            xs_b = max(0, -dx)
            xe_a = min(w, w + dx)
            xe_b = min(w, w - dx)
            if ye_a - ys_a <= 0 or xe_a - xs_a <= 0:
                continue
            ra = a[ys_a:ye_a, xs_a:xe_a]
            rb = b[ys_b:ye_b, xs_b:xe_b]
            score = np.mean(np.abs(ra.astype(np.int32) - rb.astype(np.int32)))
            if best is None or score < best[0]:
                best = (score, dx, dy, ra.shape)
    return best


def main():
    if len(sys.argv) < 5:
        print("Usage: compare_depths.py width height all_frames_depth.bin depth_only_depth.bin [max_shift]")
        sys.exit(2)
    width = int(sys.argv[1])
    height = int(sys.argv[2])
    file_all = sys.argv[3]
    file_depth = sys.argv[4]
    max_shift = int(sys.argv[5]) if len(sys.argv) > 5 else 20

    a = load_raw_uint16(file_all, width, height)
    b = load_raw_uint16(file_depth, width, height)

    mn, mx, mean, std = diff_stats(a, b)
    print(f"Diff stats (a - b): min={mn}, max={mx}, mean={mean:.2f}, std={std:.2f}")

    best = find_best_shift(a, b, max_shift)
    if best:
        score, dx, dy, shape = best
        print(f"Best shift: dx={dx}, dy={dy}, score={score:.3f}, overlap_shape={shape}")
    else:
        print("No valid overlap for shifts searched")


if __name__ == '__main__':
    main()
