# ADCAM Camera Kit 

## Overview

This repository holds the code for the ADI ADCAM Camera Kit. The ADCAM Camera Kit is based on the ADI AD3175D Time-of-Flight Mega-Pixel imager and the ADSD3500 Depth ISP. The ADCAM hardware connects to the Jetson Orin Nano Dev Kit via MIPI. The only other connector is USB C for power. The ADCAM is designed to run on the NVIDIA Jetson Orin Nano Dev Kit. The ADCAM differs from the previous ADTF3175D Eval Kit in two key ways:

* ADCAM utliizes two ADSD3500 Depth ISP. This removes the need for closed source depth processing libraries on the SoC. All depth computation, with the exception of radial to XYZ (point cloud generation) is done by the dual ADSD3500 hardware. Note, the radial to XYZ library is open source and available in the libaditof repo (see below).
* Designed to run on the NVIDIA Jetson Orin Nano Dev Kit.

This repostiory is dependent on the [ToF-drivers](https://github.com/analogdevicesinc/ToF-drivers/tree/main) and [libaditof](https://github.com/analogdevicesinc/libaditof/tree/main) repositories.

* ToF-drivers: Contains the V4L2 Camera Sensor Driver for the ADSD3500 Depth ISP, device tree sources, and kernel patches - where needed.
* libaditof: Contains the software development kit (SDK) for the ADCAM combination of ADSD3500 Depth ISP and ADI Time-of-Flight Imager.

License : [![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Platform details : [![Hardware](https://img.shields.io/badge/hardware-wiki-green.svg)]()

## Supported Platforms

* [Jetson Orin Nano Dev Kit](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/)

### Requirements

* JetPack 6.2.1 installed to the Micro SD card (note, support for installation to the SSD is coming soon). 

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
| sdcard-images-utils | Things required to build a SD card image for targets |
| libaditof | Submodule with SDK source code |
| tools | Standalone applications |

## Building the Eval Kit



---
