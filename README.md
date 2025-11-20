# ADCAM Camera Kit

## Latest Release

* [ADCAM Release 0.1.0-a.1](https://github.com/analogdevicesinc/ADCAM/releases/tag/v0.1.0-a.1)

## Overview

This repository contains the source code for the ADI **ADCAM Camera Kit**, which is built around the **ADTF3175D Time-of-Flight (ToF) Mega-Pixel imager** and the **ADSD3500 Depth ISP**.  

The ADCAM hardware interfaces with the **NVIDIA Jetson Orin Nano Developer Kit** over **MIPI CSI-2** for image data, and uses **USB-C** solely for power. Unlike the earlier **ADTF3175D Evaluation Kit**, the ADCAM introduces two key improvements:

* **Dual ADSD3500 Depth ISPs**  
  Depth computation is fully handled by hardware, eliminating the need for proprietary SoC-based depth processing libraries. The only exception is the radial-to-XYZ (point cloud generation) step, which is implemented in the open-source [`libaditof`](https://github.com/analogdevicesinc/libaditof/tree/main) library.
* **Optimized for Jetson Orin Nano**  
  Designed specifically to operate on the NVIDIA Jetson Orin Nano Developer Kit platform.

This repository depends on the following components:

* [**ToF-drivers**](https://github.com/analogdevicesinc/ToF-drivers/tree/main)  
  Provides the V4L2 camera sensor driver for the ADSD3500 Depth ISP, along with device tree sources and kernel patches as required.
* [**libaditof**](https://github.com/analogdevicesinc/libaditof/tree/main)  
  Provides the SDK supporting the ADCAM system, integrating ADSD3500 Depth ISP processing with the ADI ToF imager.

---

## License and Documentation

* License: [![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)  
* Hardware Documentation: [![Hardware](https://img.shields.io/badge/hardware-wiki-green.svg)]()

---

## Supported Platforms

* [NVIDIA Jetson Orin Nano Developer Kit](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/)

### Requirements

* **JetPack 6.2.1** installed on a microSD card  
  (Support for SSD installation is planned and will be available in a future release.)


## Examples
| Example | Language | Description |
| --------- | ------------- | ----------- |
| tof-viewer | <a href="examples/tof-viewer"> C++ </a> | Graphical User interface for visualising stream from depth camera |
| data-collect | <a href="examples/data_collect"> C++ </a> | A command line application that takes in command line input arguments (like number of frames, mode to be set, folder location to save frame data) and captures the frames and stores in path provided |
| first-frame | <a href="examples/first-frame"> C++ </a> <br> <a href="bindings/python/examples/first_frame"> Python </a> | An example code that shows the steps required to get to the point where camera frames can be captured. |

## Other Examples
| Example | Language | Description |
| --------- | ------------- | ----------- |
| ROS2 Application | <a href="https://github.com/analogdevicesinc/adi_3dtof_adtf31xx"> C++ </a> | A more extensive ROS2 example based on the ADI ToF SDK. |
| Stitching Algorithm | <a href="https://github.com/analogdevicesinc/adi_3dtof_image_stitching"> C++ </a> | A stiching algorithm using ADI ToF data. |

## Directory Structure
| Directory | Description |
| --------- | ----------- |
| apps | Applications specific to various targets and hosts |
| bindings | SDK bindings to other languages |
| ci | Useful scripts for continuous integration |
| cmake | Helper files for cmake |
| dependencies | Contains third-party and owned libraries |
| doc | Documentation |
| drivers | Holds drivers for nxp and nvidia |
| examples | Example code for the supported programming languages |
| scripts | Useful development scripts |
| tools | Standalone applications |
| ToF-drivers *(submodule)*| ADSD3500 V4L2 Camera Sensor device driver |
| libaditof *(submodule)*| Submodule with SDK source code |

## Building the Eval Kit

Note, prior to committing to the repo it is important to format the source code, see the [code formatting](doc/code-formatting.md) document.

### Standard Build

### Pre-requisites
* CMake
* g++
* Python 3 - note, we are assuming Python 3.8 in this document, change as needed for your setup
* OpenCV - for the examples
* OpenGL - for the examples
* Doxygen - for documentation generation
* Graphviz - for documentation generation

#### Installing the pre-requisites
```console
sudo apt update
sudo apt install cmake g++ \
     libopencv-dev \
     libgl1-mesa-dev libglfw3-dev \
     doxygen graphviz \
     libxinerama-dev \
     libxcursor-dev \
     libxi-dev \
     libxrandr-dev
```

For Linux builds install the necessary version of Python dev libraries. For example for Ubuntu 22.04 with Python 3.10 as the default Python:
```console
sudo apt install python3.10-dev
```
### Building the SDK
```
git clone https://github.com/analogdevicesinc/ADCAM.git
cd ADCAM
git submodule update --init
git checkout <branch or tag>
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
cmake --build . -j 6
```

---
