## Overview

ADSD3500 debugging apps

## Directory Structure
| Directory | Description |
| --------- | ----------- |
| ctrl_app | Application to interract through V4L2 with ADSD3500 host protocol |

## Prerequisites

- CMake version 3.0 or later
- GNU Make
- A supported Linux environment
- Required development libraries and headers for your target platform

## Build Instructions (NVIDIA Platform)

Follow the steps below to build the project for the NVIDIA Jetson Orin nano platform.

```bash
mkdir build
cd build
cmake -DNVIDIA=ON ..
make
```

## Build Instructions (RPI Platform)

Follow the steps below to build the project for the Raspberry Pi 5 platform.

```bash
mkdir build
cd build
cmake -DRPI=ON ..
make
```

## Clean Build (Recommended)

Before switching platforms or rebuilding from scratch, perform a clean build:

```bash
rm -rf build
```
