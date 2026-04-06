# Linux Example Program

This is a Linux example program that shows the usage of ADSD3500, device driver and Depth-Compute Library on the NVIDIA Jetson Orin Nano platform.

## Functionality

The example program performs the following:

1. Resets the ADSD3500 device
2. Configures the ADSD3500 and depth compute library with the ini file
3. Configures depth compute library with CCB parameters from the ADSD3500
4. Sets up the interrupt support
5. Sets the imaging mode
6. Starts streaming
7. Receives frames
8. Passes the received frames to the depth compute library
9. Saves the AB, Depth, Confidence and metadata to the file system
10. Stops streaming
11. Closes the camera
12. Exits

## Prerequisites

- NVIDIA Jetson Orin Nano Developer Kit
- Kernel driver `nv_adsd3500` loaded
- Depth Compute Library files (`libtofi_compute.so`, `libtofi_config.so`)

## Install Depth Compute Library Files

The Depth Compute Library files must be installed in a location where the system can find them.

### Option 1: System Library Path

Navigate to the library directory and copy the files to `/usr/lib/`:

```bash
cd <path-to-tofi-libs>/
sudo cp libtofi_compute.so libtofi_config.so /usr/lib/
```

### Option 2: Custom Path (../lib relative to ADCAM)

Place the library files one level above the ADCAM repository:

```bash
mkdir -p ../lib
cp libtofi_compute.so libtofi_config.so ../lib/
```

The CMake build system will automatically find them in `../lib/`.

## Build

This example is built as part of the ADCAM project.

Navigate to the ADCAM repository root and build:

```bash
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DNVIDIA=ON -DWITH_EXAMPLES=ON ..
cmake --build . -j$(nproc)
```

The executable will be located at:
```
build/examples/adsd3500_sample_program/adsd3500_sample_program
```

## Usage

Navigate to the build directory:

```bash
cd build/examples/adsd3500_sample_program
```

Run the application with the following command:

```bash
sudo ./adsd3500_sample_program -m <mode_number> -n <number_of_frames>
```

### Examples

```bash
# Capture 1 frame in mode 2 (QMP short-range native)
sudo ./adsd3500_sample_program -m 2 -n 1

# Capture 10 frames in mode 0 (MP PCM native)
sudo ./adsd3500_sample_program -m 0 -n 10
```

## Output Files

The program generates the following files in the current directory:

- `out_depth.bin` - Depth data (uint16, millimeters)
- `out_ab.bin` - Active Brightness data (uint16, IR intensity)
- `out_conf.bin` - Confidence map (uint8, 0-255)
- `metadata.txt` - Frame metadata (imager type, mode, dimensions)

## Visualizing Frames

Use the included Python script to visualize captured frames:

```bash
# Save frames as PNG images
python3 ../../examples/adsd3500_sample_program/visualize.py --save

# Display help
python3 ../../examples/adsd3500_sample_program/visualize.py --help
```

Generated PNG files:
- `frame_000_depth.png` - Depth map (jet colormap)
- `frame_000_ab.png` - Active Brightness (grayscale)
- `frame_000_conf.png` - Confidence map (grayscale)

## References

- [ADCAM SDK Documentation](../../README.md)
- [ADSD3500 Datasheet](https://www.analog.com/ADSD3500)
- [ADTF3175D Datasheet](https://www.analog.com/ADTF3175D)

